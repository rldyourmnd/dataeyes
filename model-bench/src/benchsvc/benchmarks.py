from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
import traceback
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from benchsvc.agent import AgentMiniRunner
from benchsvc.fixtures.buggy_service import BUGGY_SERVICE_CODE
from benchsvc.fixtures.long_doc import LONG_DOC, LONG_DOC_QUESTIONS
from benchsvc.langfuse_tracing import LangfuseRecorder
from benchsvc.llm_client import DataEyesClient, LiteLLMGateway
from benchsvc.models import BenchmarkRun, ModelResult
from benchsvc.schemas import BenchmarkRunRequest, BenchmarkRunResponse, CaseResult
from benchsvc.scoring import (
    aggregate_results,
    estimate_cost_usd,
    extract_json,
    score_code_generation,
    score_fast_algorithms,
    score_fast_code,
    score_instruction_strict,
    score_long_context_qa,
    score_reasoning_multistep,
    score_smoke_json,
    score_ultra_algorithms,
    score_ultra_code_full,
    score_ultra_code_review,
    score_ultra_long_context,
    score_ultra_reasoning,
    score_ultra_system_design,
    validate_schema,
)
from benchsvc.settings import Settings
from benchsvc.storage import ArtifactStore

log = logging.getLogger(__name__)


class BenchmarkRunner:
    def __init__(self, settings: Settings, db: Session):
        self.settings = settings
        self.db = db
        self.dataeyes = DataEyesClient(settings)
        self.gateway = LiteLLMGateway(settings)
        self.artifacts = ArtifactStore(settings)
        self.langfuse = LangfuseRecorder(settings)

    def run(self, request: BenchmarkRunRequest) -> BenchmarkRunResponse:
        db_run = BenchmarkRun(
            suite=request.suite,
            status="running",
            requested_models=request.model_dump(mode="json"),
            config_snapshot=self.settings.redacted_snapshot(),
        )
        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)
        run_id = str(db_run.id)

        lf_trace_id = self.langfuse.start_run_trace(
            run_id=run_id,
            suite=request.suite,
            metadata={
                "run_id": run_id,
                "suite": request.suite,
                "benchmark_version": self.settings.benchmark_version,
                "provider": "dataeyes",
                "gateway": "litellm_proxy",
            },
        )

        try:
            models = self._select_models(request)
            db_run.discovered_models_count = len(models)
            self.db.commit()
            self.artifacts.put_json(
                f"runs/{run_id}/config_snapshot.json", self.settings.redacted_snapshot()
            )

            results: list[CaseResult] = []
            cases = self._suite_cases(request.suite)
            db_lock = threading.Lock()

            def _run_model(model: str) -> list[CaseResult]:
                model_results = []
                for case_id in cases:
                    r = self._run_case(run_id=run_id, model=model, case_id=case_id)
                    model_results.append(r)
                return model_results

            max_workers = min(len(models), 5)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_run_model, m): m for m in models}
                for future in concurrent.futures.as_completed(futures):
                    failed_model = futures[future]
                    try:
                        model_results = future.result()
                    except Exception as exc:
                        log.error(
                            "Model %s failed with unhandled exception: %s\n%s",
                            failed_model,
                            exc,
                            traceback.format_exc(),
                        )
                        model_results = [
                            CaseResult(
                                model=failed_model,
                                suite=request.suite,
                                case_id=c,
                                status="error",
                                score=0.0,
                                error_type=type(exc).__name__,
                                error_message=str(exc)[:500],
                            )
                            for c in cases
                        ]
                    with db_lock:
                        for result in model_results:
                            results.append(result)
                            self._persist_result(db_run.id, result)
                            self.db.commit()
                            if lf_trace_id:
                                self.langfuse.record_case_score(
                                    trace_id=lf_trace_id,
                                    model=result.model,
                                    case_id=result.case_id,
                                    score=result.score,
                                    status=result.status,
                                )

            summary = aggregate_results([r.model_dump(mode="json") for r in results])
            db_run.status = (
                "completed" if summary["errors"] == 0 and summary["failed"] == 0 else "partial"
            )
            db_run.completed_at = datetime.now(UTC)
            db_run.summary = summary
            self.db.commit()
            self.artifacts.put_json(
                f"runs/{run_id}/exports/summary.json",
                {"summary": summary, "results": [r.model_dump(mode="json") for r in results]},
            )
            if lf_trace_id:
                self.langfuse.record_run_summary(lf_trace_id, summary)
            self.langfuse.flush()

            return BenchmarkRunResponse(
                run_id=run_id,
                status=db_run.status,  # type: ignore[arg-type]
                suite=request.suite,
                models_tested=len(models),
                summary=summary,
                results=results,
            )
        except Exception as exc:
            db_run.status = "failed"
            db_run.completed_at = datetime.now(UTC)
            db_run.summary = {"error_type": type(exc).__name__, "error_message": str(exc)}
            self.db.commit()
            self.langfuse.flush()
            return BenchmarkRunResponse(
                run_id=run_id,
                status="failed",
                suite=request.suite,
                models_tested=0,
                summary=db_run.summary,
                results=[],
            )

    def _select_models(self, request: BenchmarkRunRequest) -> list[str]:
        if isinstance(request.models, list):
            models = request.models
        else:
            discovered = self.dataeyes.list_models(include_raw=False)
            raw_models = [m.id for m in discovered]
            allowlist = self.settings.allowlist
            if allowlist:
                raw_models = [
                    m for m in raw_models if m in allowlist or f"dataeyes/{m}" in allowlist
                ]
            models = [m if m.startswith("dataeyes/") else f"dataeyes/{m}" for m in raw_models]
        if request.limit_models is not None:
            models = models[: request.limit_models]
        return models[: self.settings.max_models_per_run]

    def _suite_cases(self, suite: str) -> list[str]:
        if suite == "smoke":
            return ["smoke_json_exact"]
        if suite == "json_schema":
            return ["json_schema_vendor_readiness"]
        if suite == "tool_call":
            return ["tool_call_web_and_ticket_plan"]
        if suite == "agent_mini":
            return ["agent_mini_vendor_readiness"]
        if suite == "latency_repeated":
            return ["smoke_json_exact"] * 3
        if suite == "standard":
            return [
                "smoke_json_exact",
                "json_schema_vendor_readiness",
                "agent_mini_vendor_readiness",
            ]
        if suite == "deep_eval":
            return [
                "reasoning_multistep",
                "code_generation",
                "instruction_strict",
                "long_context_qa",
            ]
        if suite == "comprehensive":
            return [
                "smoke_json_exact",
                "json_schema_vendor_readiness",
                "reasoning_multistep",
                "code_generation",
                "instruction_strict",
                "long_context_qa",
            ]
        if suite == "ultra_deep":
            return [
                "ultra_reasoning",
                "ultra_code_full",
                "ultra_code_review",
                "ultra_algorithms",
                "ultra_long_context",
                "ultra_system_design",
            ]
        if suite == "fast":
            return [
                "fast_reasoning",
                "fast_code",
                "fast_algorithms",
                "fast_system_design",
            ]
        raise ValueError(f"Unsupported suite: {suite}")

    def _run_case(self, run_id: str, model: str, case_id: str) -> CaseResult:
        if case_id == "smoke_json_exact":
            return self._run_smoke(run_id, model)
        if case_id == "json_schema_vendor_readiness":
            return self._run_json_schema(run_id, model)
        if case_id == "agent_mini_vendor_readiness":
            return self._run_agent_mini(run_id, model)
        if case_id == "tool_call_web_and_ticket_plan":
            return self._run_agent_mini(run_id, model)
        if case_id == "reasoning_multistep":
            return self._run_reasoning_multistep(run_id, model)
        if case_id == "code_generation":
            return self._run_code_generation(run_id, model)
        if case_id == "instruction_strict":
            return self._run_instruction_strict(run_id, model)
        if case_id == "long_context_qa":
            return self._run_long_context_qa(run_id, model)
        if case_id == "ultra_reasoning":
            return self._run_ultra_reasoning(run_id, model)
        if case_id == "ultra_code_full":
            return self._run_ultra_code_full(run_id, model)
        if case_id == "ultra_code_review":
            return self._run_ultra_code_review(run_id, model)
        if case_id == "ultra_algorithms":
            return self._run_ultra_algorithms(run_id, model)
        if case_id == "ultra_long_context":
            return self._run_ultra_long_context(run_id, model)
        if case_id == "ultra_system_design":
            return self._run_ultra_system_design(run_id, model)
        if case_id == "fast_reasoning":
            return self._run_fast_reasoning(run_id, model)
        if case_id == "fast_code":
            return self._run_fast_code(run_id, model)
        if case_id == "fast_algorithms":
            return self._run_fast_algorithms(run_id, model)
        if case_id == "fast_system_design":
            return self._run_fast_system_design(run_id, model)
        raise ValueError(f"Unsupported case: {case_id}")

    def _run_smoke(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {"role": "system", "content": "Return JSON only. No markdown."},
                {
                    "role": "user",
                    "content": 'Return exactly {"status":"ok","provider_test":"dataeyes","answer":42}',
                },
            ],
            response_format={"type": "json_object"},
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__smoke.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_smoke_json(call.text, call.latency_ms_total)
        status = "passed" if call.error_type is None and scored["score"] >= 80 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="smoke",
            case_id="smoke_json_exact",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=scored["schema_valid"],
            error_type=call.error_type,
            error_message=call.error_message or scored.get("error"),
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _run_reasoning_multistep(self, run_id: str, model: str) -> CaseResult:
        prompt = """You are solving a business pricing problem. Think step by step, then return ONLY JSON.

A SaaS company offers 3 pricing tiers:
- Starter:    $25/month  | max 10 users | max 100 GB storage
- Business:   $99/month  | max 50 users | max 1 TB (1024 GB) storage
- Enterprise: $299/month | unlimited users | unlimited storage

Current customers and their tiers:
- ACME Corp:   8 users,   80 GB  → currently on Starter  ($25/month)
- Beta Ltd:   45 users,  800 GB  → currently on Business ($99/month)
- Gamma Inc: 120 users, 5120 GB  → currently on Enterprise ($299/month)

Questions to answer:
1. ACME Corp wants to add 3 more users and 30 GB of storage. What tier must they move to?
2. Beta Ltd wants to add 10 more users (to 55 total). Can they stay on Business tier?
3. What is the total monthly revenue from all 3 customers RIGHT NOW (before any changes)?
4. After ACME Corp upgrades (per Q1), what is the new total monthly revenue?
5. What is the minimum number of users that forces a move from Business to Enterprise?

Return ONLY this JSON (no explanation outside JSON):
{
  "acme_new_tier": "Starter" | "Business" | "Enterprise",
  "beta_can_stay_business": true | false,
  "current_total_revenue": <number>,
  "revenue_after_acme_upgrade": <number>,
  "min_users_for_enterprise": <number>,
  "reasoning": "<your step-by-step work>"
}"""
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise business analyst. Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__reasoning.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_reasoning_multistep(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 60 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="deep_eval",
            case_id="reasoning_multistep",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _run_code_generation(self, run_id: str, model: str) -> CaseResult:
        prompt = """Write a Python function and return it as JSON.

FUNCTION SPECIFICATION:
Name: benchmark_stats(results)
Input: list of dicts. Each dict may have keys: "model" (str), "score" (float 0-100), "latency_ms" (int), "tokens" (int). Some keys may be missing.
Returns: dict with exactly these keys:
  - "best_model": str — model name with highest score
  - "worst_model": str — model name with lowest score
  - "avg_score": float — mean score, rounded to 2 decimal places
  - "avg_latency_ms": int — mean latency_ms, rounded to nearest integer
  - "efficiency": dict — {model_name: round(score / (latency_ms / 1000), 2)} (score per second)
  - "passed": list[str] — model names where score >= 80.0
  - "total_tokens": int — sum of all tokens values

REQUIREMENTS:
1. If results is empty, return: {"best_model": null, "worst_model": null, "avg_score": 0, "avg_latency_ms": 0, "efficiency": {}, "passed": [], "total_tokens": 0}
2. Skip any item missing "model", "score", or "latency_ms" keys (use .get() or try/except)
3. The function must be complete and syntactically valid Python

Return ONLY this JSON:
{"code": "<complete Python function as a string>", "explanation": "<one sentence describing the function>"}"""
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only. The 'code' field must contain syntactically correct Python.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__code.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_code_generation(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 60 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="deep_eval",
            case_id="code_generation",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _run_instruction_strict(self, run_id: str, model: str) -> CaseResult:
        prompt = """Return ONLY valid JSON. No markdown. No explanation. No code blocks. No text before or after the JSON.

Create a competitive AI model analysis. The JSON must conform to this EXACT structure with ALL constraints satisfied:

{
  "analysis_date": "2026-06-10",
  "models": [
    {
      "rank": <integer 1-4, unique>,
      "provider": "<company name>",
      "model_name": "<model identifier>",
      "strengths": ["<item1>", "<item2>", "<item3>"],
      "weaknesses": ["<item1>", "<item2>"],
      "price_per_million_output_tokens": <number>,
      "latency_tier": "<fast | medium | slow>",
      "best_for": "<10 to 20 word description>"
    }
  ],
  "summary": "<Sentence one. Sentence two.>",
  "updated_by": "benchmark_runner_v2"
}

HARD CONSTRAINTS (will be automatically verified):
1. "analysis_date" must be exactly the string "2026-06-10"
2. "models" array must contain EXACTLY 4 entries
3. "rank" values must be 1, 2, 3, 4 with no duplicates
4. "strengths" must have 3, 4, or 5 items per model
5. "weaknesses" must have 2 or 3 items per model
6. "summary" must be exactly 2 sentences (each ending with a period)
7. "updated_by" must be exactly the string "benchmark_runner_v2"
8. Use real frontier models: Claude, Gemini, GPT-4, DeepSeek"""
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You follow instructions with extreme precision. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__instruction.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_instruction_strict(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 60 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="deep_eval",
            case_id="instruction_strict",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    _LONG_CONTEXT_DOCUMENT = """You are given benchmark evaluation data. Read it carefully — you will need to extract specific information and perform calculations.

<BENCHMARK_DATA>
{
  "run_id": "bench-2026-06-eval-001",
  "suite": "standard",
  "timestamp": "2026-06-10T09:00:00Z",
  "results": [
    {"model": "alpha-7b",       "case": "reasoning",    "score": 45.0, "latency_ms":  1200, "tokens":  450, "status": "failed"},
    {"model": "beta-13b",       "case": "reasoning",    "score": 78.0, "latency_ms":  3400, "tokens":  820, "status": "passed"},
    {"model": "gamma-70b",      "case": "reasoning",    "score": 92.0, "latency_ms":  8900, "tokens": 1340, "status": "passed"},
    {"model": "delta-frontier", "case": "reasoning",    "score": 98.0, "latency_ms": 12000, "tokens": 2100, "status": "passed"},
    {"model": "alpha-7b",       "case": "code_gen",     "score": 30.0, "latency_ms":   900, "tokens":  380, "status": "failed"},
    {"model": "beta-13b",       "case": "code_gen",     "score": 65.0, "latency_ms":  2800, "tokens":  710, "status": "failed"},
    {"model": "gamma-70b",      "case": "code_gen",     "score": 88.0, "latency_ms":  7200, "tokens": 1180, "status": "passed"},
    {"model": "delta-frontier", "case": "code_gen",     "score": 95.0, "latency_ms":  9800, "tokens": 1950, "status": "passed"},
    {"model": "alpha-7b",       "case": "instruction",  "score": 60.0, "latency_ms":   800, "tokens":  290, "status": "failed"},
    {"model": "beta-13b",       "case": "instruction",  "score": 82.0, "latency_ms":  1900, "tokens":  540, "status": "passed"},
    {"model": "gamma-70b",      "case": "instruction",  "score": 91.0, "latency_ms":  5100, "tokens":  920, "status": "passed"},
    {"model": "delta-frontier", "case": "instruction",  "score": 99.0, "latency_ms":  7400, "tokens": 1600, "status": "passed"}
  ]
}
</BENCHMARK_DATA>

Answer the following 5 questions using ONLY the data above. Show your calculations where needed.

Return ONLY this JSON (no text outside):
{
  "q1_highest_avg_score_model": "<model with highest average score across all 3 cases>",
  "q2_total_tokens_passed_cases": <sum of tokens for all results where status == passed>,
  "q3_fastest_model_reasoning": "<model with lowest latency_ms for the reasoning case>",
  "q4_models_all_cases_passed": ["<models that passed ALL 3 cases>"],
  "q5_avg_latency_gamma_70b_ms": <integer: average latency_ms across all 3 cases for gamma-70b>
}"""

    def _run_long_context_qa(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise data analyst. Extract information accurately from provided data. Return valid JSON only.",
                },
                {"role": "user", "content": self._LONG_CONTEXT_DOCUMENT},
            ],
            response_format={"type": "json_object"},
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__longctx.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_long_context_qa(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 60 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="deep_eval",
            case_id="long_context_qa",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _run_json_schema(self, run_id: str, model: str) -> CaseResult:
        schema_path = self.settings.repo_root / "schemas" / "benchmark_result.schema.json"
        prompt = {
            "task": "Return a vendor-readiness benchmark result object matching the provided schema. Do not invent prices.",
            "context": "We need to test DataEyes-hosted models with FastAPI, LiteLLM, Langfuse, PostgreSQL, and RustFS.",
            "schema_hint": json.loads(schema_path.read_text(encoding="utf-8")),
        }
        call = self.gateway.complete(
            model=model,
            messages=[
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__json_schema.json",
            call.raw or {"error": call.error_message},
        )
        ok, payload, json_err = extract_json(call.text)
        schema_valid = False
        schema_errors: list[str] = []
        if ok:
            schema_valid, schema_errors = validate_schema(payload, schema_path)
        score = 100.0 if ok and schema_valid else 40.0 if ok else 0.0
        status = "passed" if score >= 80 and not call.error_type else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="json_schema",
            case_id="json_schema_vendor_readiness",
            status=status,
            score=score,
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=ok,
            schema_valid=schema_valid,
            error_type=call.error_type,
            error_message=call.error_message or json_err or "; ".join(schema_errors[:3]) or None,
            raw_artifact_uri=raw_uri,
            extra={"schema_errors": schema_errors},
        )

    def _run_agent_mini(self, run_id: str, model: str) -> CaseResult:
        output = AgentMiniRunner(self.settings, self.gateway, run_id=run_id).run(model=model)
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__agent_mini.json", output
        )
        status = "passed" if output["score"] >= 70 and not output.get("error_type") else "failed"
        if output.get("error_type"):
            status = "error" if output["score"] == 0 else "failed"
        in_tok = output.get("input_tokens")
        out_tok = output.get("output_tokens")
        lat = output.get("latency_ms_total")
        tps = round(out_tok / (lat / 1000), 2) if out_tok and lat else None
        cost, cost_status = estimate_cost_usd(model, in_tok, out_tok)
        return CaseResult(
            model=model,
            suite="agent_mini",
            case_id="agent_mini_vendor_readiness",
            status=status,
            score=float(output["score"]),
            latency_ms_total=lat,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=output.get("total_tokens"),
            tokens_per_second=tps,
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=bool(output.get("json_valid")),
            schema_valid=bool(output.get("schema_valid")),
            tool_call_count=int(output.get("tool_call_count") or 0),
            tool_error_count=int(output.get("tool_error_count") or 0),
            error_type=output.get("error_type"),
            error_message=output.get("error_message"),
            raw_artifact_uri=raw_uri,
            extra=output.get("score_details") or {},
        )

    # ── ultra_deep tasks ──────────────────────────────────────────────────────

    _ULTRA_REASON_PROMPT = """You are solving 15 interconnected business / math / computer-science problems.

This is a DEEP REASONING benchmark. You MUST write out your full chain-of-thought.
MINIMUM EXPECTED LENGTH: 3000 words of reasoning before the final JSON.
For EVERY question: state all given values, enumerate all rules that apply,
show all arithmetic steps explicitly (no mental math shortcuts), state all
intermediate conclusions, then state the final answer with a one-sentence justification.
Do NOT abbreviate, summarize, or skip any step. More reasoning is better.
After your COMPLETE exhaustive chain-of-thought, output a JSON object at the very end.

══════════════════════════════════════════════════════════════════════════════
CONTEXT: The same SaaS company as before, but extended:

Pricing tiers:
  Starter:    $25/month  | max 10 users  | max 100 GB
  Business:   $99/month  | max 50 users  | max 1 TB (1024 GB)
  Enterprise: $299/month | unlimited

Customers (current state):
  ACME Corp   : 8 users,   80 GB  → Starter     ($25/month)
  Beta Ltd    : 45 users,  800 GB → Business    ($99/month)
  Gamma Inc   : 120 users, 5120 GB→ Enterprise  ($299/month)
  Delta LLC   : 3 users,   10 GB  → Starter     ($25/month)  ← new customer
  Echo GmbH   : 50 users,  1024 GB→ Business    ($99/month)  ← exactly at limit

Additional facts:
  • Annual plan discount: 15% off monthly price if paid yearly
  • Overage fee: $0.10 per GB above tier limit per month
  • Storage at Starter is hard-capped — no overage allowed, must upgrade
  • User limit has $5/user/month overage up to 20% above tier limit, then must upgrade

══════════════════════════════════════════════════════════════════════════════
QUESTIONS:

Q1. How many customers are currently on the Starter tier?
Q2. Can Echo GmbH add 1 more GB of storage and stay on Business? (true/false)
Q3. What is the total monthly revenue from ALL 5 customers right now?
Q4. ACME Corp adds 3 users (→11) and 30 GB (→110 GB). What is their new monthly bill?
    (They must upgrade. Consider storage hard-cap rule. New tier bill, no overage.)
Q5. What is the minimum number of users that forces a Business customer to pay overage
    instead of being able to stay on Business tier? (user count, not overage amount)
Q6. Can Beta Ltd (45 users, 800 GB) add 256 GB storage and still stay on Business?
    (true/false — consider 1024 GB limit)
Q7. Delta LLC wants to grow to 12 users and 150 GB. What tier must they move to?
    ("starter", "business", or "enterprise")
Q8. How many customers are currently AT or ABOVE 80% of their tier's user limit?
    (Count customers where current_users / tier_max_users >= 0.8. Enterprise = unlimited = 0%.)
Q9. If ALL 5 customers switch to annual plans today, what is the total annual revenue
    (after 15% discount)?
Q10. Gamma Inc is currently paying for Enterprise. If they dropped to 49 users and 900 GB,
     could they downgrade to Business and pay only $99/month? What would their bill be
     including storage overage? (900 GB > 1024 GB? No. 900 < 1024. No overage.)
Q11. What is the total current monthly revenue from Enterprise-tier customers only?
Q12. Echo GmbH is exactly at the Business storage limit (1024 GB). They add 1 GB.
     They CANNOT pay storage overage on Business (storage is hard-capped at Business tier too —
     same rule as Starter). Must they upgrade to Enterprise? (true/false)
Q13. If ALL 5 customers were on Business tier, what would the total monthly revenue be?
Q14. Is Delta LLC currently below 80% of their tier's user limit? (true/false)
Q15. How many distinct tier transitions (upgrades or downgrades) are implied by
     questions Q1–Q14 above? Count only transitions explicitly computed in answers
     Q4, Q7, Q10, Q12. (integer)

══════════════════════════════════════════════════════════════════════════════
After your COMPLETE chain-of-thought reasoning (think as long as you need),
output ONLY this JSON at the very end:

{
  "answers": {
    "q1": <integer>,
    "q2": <true|false>,
    "q3": <number>,
    "q4": <number>,
    "q5": <integer>,
    "q6": <true|false>,
    "q7": "<starter|business|enterprise>",
    "q8": <integer>,
    "q9": <number>,
    "q10": <number>,
    "q11": <number>,
    "q12": <true|false>,
    "q13": <number>,
    "q14": <true|false>,
    "q15": <integer>
  },
  "confidence": "<high|medium|low>"
}"""

    def _run_ultra_reasoning(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise analyst. Think step by step in FULL detail — "
                        "do not abbreviate or skip any reasoning steps. "
                        "After your complete chain-of-thought, output a final JSON block."
                    ),
                },
                {"role": "user", "content": self._ULTRA_REASON_PROMPT},
            ],
            max_tokens=32768,
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__ultra_reasoning.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_reasoning(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 50 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="ultra_deep",
            case_id="ultra_reasoning",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    _ULTRA_CODE_PROMPT = """This is a TEXT GENERATION task. Write all code as plain text strings
in your response — do not use tools, do not execute code, do not reference any workspace.

MINIMUM EXPECTED LENGTH: 5000+ lines of code across all modules.
Generate COMPLETE, PRODUCTION-GRADE Python source code for an async distributed task queue library.

REQUIREMENTS — write ALL of the following as text. Do NOT truncate or abbreviate any module.
Every function MUST have a complete, non-trivial body with proper error handling, logging,
type annotations, and docstrings. Write FULL implementations, not stubs or placeholders.
Include extensive inline comments explaining non-obvious logic.

══════════════════════════════════════════════════════════════════════════════
MODULE 1: queue_client.py
  - AsyncTaskQueueClient class with Redis backend
  - async def enqueue(task_name, payload, *, priority=0, delay_seconds=0, max_retries=3) -> str (task_id)
  - async def cancel(task_id) -> bool
  - async def get_result(task_id) -> TaskResult | None
  - async def get_status(task_id) -> TaskStatus
  - async def list_pending(limit=100) -> list[TaskInfo]
  - Proper connection pooling, timeout handling, reconnection logic

MODULE 2: queue_worker.py
  - AsyncWorker class
  - async def register(task_name)(decorator factory)
  - async def run(concurrency=4) — main event loop
  - async def _execute_task(task) — with retry logic (exponential backoff)
  - async def _handle_failure(task, exc) — dead-letter queue on max_retries exceeded
  - Graceful shutdown on SIGTERM/SIGINT

MODULE 3: models.py
  - Pydantic v2 models: Task, TaskResult, TaskStatus (enum), TaskInfo, WorkerConfig
  - All fields typed, with validation

MODULE 4: tests/test_queue.py
  - Full pytest async test suite using pytest-asyncio
  - Tests: enqueue_returns_id, cancel_pending_task, retry_on_failure,
           dead_letter_after_max_retries, concurrent_workers_no_duplicate_processing
  - Use unittest.mock to mock Redis, no live connections required

══════════════════════════════════════════════════════════════════════════════
Think through the design thoroughly before writing each module.
Show your reasoning about design decisions (e.g. why BLPOP vs ZADD for priority queues,
why exponential backoff intervals, how to ensure exactly-once delivery).

After your complete implementation and design notes, output this JSON at the very end:

{
  "client_code": "<complete queue_client.py contents>",
  "worker_code": "<complete queue_worker.py contents>",
  "models_code": "<complete models.py contents>",
  "test_code": "<complete tests/test_queue.py contents>",
  "design_notes": "<your reasoning about key design decisions, at least 500 words>"
}"""

    def _run_ultra_code_full(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior Python engineer completing a text-generation benchmark. "
                        "Your task is to WRITE code as plain text strings INLINE in this conversation. "
                        "Do NOT use tools, do NOT create files, do NOT execute code. "
                        "Simply generate all Python source code as text within your response. "
                        "Every function must be fully implemented — no stubs, no '# implement this'. "
                        "Show your design reasoning, then write every module in full."
                    ),
                },
                {"role": "user", "content": self._ULTRA_CODE_PROMPT},
            ],
            max_tokens=32768,
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__ultra_code_full.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_code_full(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 40 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="ultra_deep",
            case_id="ultra_code_full",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    @property
    def _ultra_code_review_prompt(self) -> str:
        return f"""This is a TEXT GENERATION task. Write your entire analysis inline as text
in this conversation — do not use tools, do not execute code.

Read the Python service below carefully and write an exhaustive security audit. Your task:

1. Find EVERY bug — security vulnerabilities, logic errors, performance issues,
   bad practices, race conditions, and anything else that would cause problems in production.
2. For each bug: state its location (function name + approximate line), classify it
   (e.g. SQL injection, logic error, race condition), assign CVSS severity
   (critical/high/medium/low), explain the exact exploit or failure scenario,
   and provide the fixed code snippet.
3. Think deeply — there are at least 15 distinct bugs. Do not stop at the obvious ones.
4. After your detailed analysis, provide a complete fixed version of the entire service.

Do NOT truncate your analysis. Go through the code function by function.
Think step by step — methodically examine each function, each variable, each query.

═══════════════════════════ BUGGY SERVICE CODE ═══════════════════════════════
{BUGGY_SERVICE_CODE}
═════════════════════════════════════════════════════════════════════════════

After your COMPLETE analysis (analyse every single function), output this JSON at the very end:

{{
  "bugs": [
    {{
      "id": 1,
      "function": "<function name>",
      "type": "<category e.g. sql_injection, hardcoded_secret, race_condition>",
      "severity": "<critical|high|medium|low>",
      "description": "<exact exploit or failure scenario>",
      "fix": "<corrected code snippet>"
    }}
  ],
  "fixed_code": "<complete fixed service as a single Python string>",
  "summary": "<executive summary: total bugs, critical count, top 3 recommendations>"
}}"""

    def _run_ultra_code_review(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior security engineer completing a text-generation benchmark. "
                        "Conduct an exhaustive code audit by writing your analysis INLINE as text. "
                        "Do NOT use tools, do NOT execute code, do NOT access files. "
                        "Find EVERY bug by reading the code provided. Think methodically through each function. "
                        "After your full written analysis, provide the complete fixed code as a text string."
                    ),
                },
                {"role": "user", "content": self._ultra_code_review_prompt},
            ],
            max_tokens=32768,
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__ultra_code_review.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_code_review(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 40 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="ultra_deep",
            case_id="ultra_code_review",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    _ULTRA_ALGO_PROMPT = """This is a TEXT GENERATION task. Write all code as plain text inline
in your response — do not use tools, do not execute code, do not reference any workspace.

Generate complete Python source code for 4 classic data structures from scratch
(no external libraries except the standard library).

For EACH data structure:
  (a) Explain the theory and invariants in detail (why it works, what guarantees it provides)
  (b) Write the COMPLETE Python implementation — every method fully implemented, no stubs
  (c) Analyse time and space complexity for every operation (Big-O notation, best/worst/average)
  (d) Write at least 3 meaningful unit tests that verify correctness including edge cases
  (e) Discuss real-world use cases and when you'd prefer this structure over alternatives

══════════════════════════════════════════════════════════════════════════════
DATA STRUCTURE 1: LRU Cache
  - get(key) → value | None   O(1) guaranteed
  - put(key, value, capacity)
  - Must use OrderedDict or doubly-linked list + hash map — explain your choice
  - Handle capacity=0, negative capacity, None values

DATA STRUCTURE 2: Trie (Prefix Tree)
  - insert(word)
  - search(word) → bool         (exact match)
  - starts_with(prefix) → bool
  - count_with_prefix(prefix) → int
  - delete(word) → bool
  - autocomplete(prefix, limit) → list[str]
  - Handle unicode, empty strings, None

DATA STRUCTURE 3: Bloom Filter
  - add(item)
  - might_contain(item) → bool  (false positives possible, false negatives impossible)
  - false_positive_rate() → float  (current estimate)
  - Constructor: __init__(expected_items, false_positive_rate)
  - Compute optimal bit_array_size and num_hash_functions from constructor params
  - Implement k independent hash functions using double hashing
  - Discuss why false negatives are impossible

DATA STRUCTURE 4: Consistent Hash Ring
  - add_node(node_id, virtual_nodes=150)
  - remove_node(node_id)
  - get_node(key) → str         (which node owns this key)
  - get_nodes(key, n) → list[str]  (top-n nodes for replication)
  - node_load_distribution() → dict[str, float]  (% of keyspace per node)
  - Discuss why virtual nodes matter for uniform distribution

DATA STRUCTURE 5: Red-Black Tree
  - insert(key, value)
  - delete(key)
  - search(key) → value | None
  - in_order() → list[tuple[key, value]]
  - height() → int
  - Full rotation logic (left-rotate, right-rotate) with fix-up after insert and delete
  - Prove the BST invariant and the 5 red-black properties are maintained
  - Explain why height is always O(log n) — walk through the proof

DATA STRUCTURE 6: Skip List
  - insert(key, value)
  - delete(key) → bool
  - search(key) → value | None
  - range_query(lo, hi) → list[tuple[key, value]]
  - level_distribution() → dict[int, int]  (how many nodes at each level)
  - Probabilistic level generation (p=0.5 coin flip per level)
  - Explain expected O(log n) search, insert, delete with full probability analysis
  - Compare to balanced BSTs: when would you choose a skip list?

══════════════════════════════════════════════════════════════════════════════
Think deeply about each design (expect to write 2000+ words of theory per structure).
After complete implementations, output this JSON:

{
  "lru_code": "<complete LRU Cache Python implementation>",
  "trie_code": "<complete Trie Python implementation>",
  "bloom_code": "<complete Bloom Filter Python implementation>",
  "consistent_hash_code": "<complete Consistent Hash Ring Python implementation>",
  "red_black_code": "<complete Red-Black Tree Python implementation>",
  "skip_list_code": "<complete Skip List Python implementation>",
  "complexity": {
    "lru":   {"get": "O(?)", "put": "O(?)"},
    "trie":  {"insert": "O(?)", "search": "O(?)", "prefix": "O(?)"},
    "bloom": {"add": "O(?)", "contains": "O(?)", "space": "O(?)"},
    "consistent_hash": {"add_node": "O(?)", "get_node": "O(?)", "remove": "O(?)"},
    "red_black": {"insert": "O(?)", "delete": "O(?)", "search": "O(?)"},
    "skip_list": {"insert": "O(?)", "search": "O(?)", "delete": "O(?)"}
  },
  "test_code": "<complete pytest test suite for all 6 structures>"
}"""

    def _run_ultra_algorithms(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a computer science expert completing a text-generation benchmark. "
                        "Write all data structure implementations as plain text INLINE in this conversation. "
                        "Do NOT use tools, do NOT execute code, do NOT create files. "
                        "Every method must be fully implemented in text — no stubs, no truncation. "
                        "Include full theory explanation before each implementation."
                    ),
                },
                {"role": "user", "content": self._ULTRA_ALGO_PROMPT},
            ],
            max_tokens=32768,
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__ultra_algorithms.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_algorithms(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 40 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="ultra_deep",
            case_id="ultra_algorithms",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    @property
    def _ultra_long_context_prompt(self) -> str:
        return f"{LONG_DOC}\n\n{LONG_DOC_QUESTIONS}"

    def _run_ultra_long_context(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise analyst. Read the provided report carefully. "
                        "Extract exact values — do not estimate or round unless instructed. "
                        "Think step by step. Output final JSON at the end of your response."
                    ),
                },
                {"role": "user", "content": self._ultra_long_context_prompt},
            ],
            max_tokens=16384,
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__ultra_long_context.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_long_context(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 50 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="ultra_deep",
            case_id="ultra_long_context",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    _ULTRA_SYSDESIGN_PROMPT = """This is a TEXT GENERATION task. Write your entire system design
inline as text in this conversation — do not use tools, do not create files.

MINIMUM EXPECTED LENGTH: 4000 words of detailed technical design.
Design a complete, production-ready URL shortener + analytics platform (like bit.ly + PostHog).

Think through every component deeply and write it all out IN FULL DETAIL.
For EVERY section: provide specific numbers, specific technology choices with justifications,
specific configuration values, specific schemas, specific algorithms with pseudocode.
Do NOT write vague overviews — write CONCRETE engineering decisions with their trade-offs.
Every section MUST be at least 300 words with specific technical depth.

══════════════════════════════════════════════════════════════════════════════
FUNCTIONAL REQUIREMENTS:
  • Shorten URLs: POST /shorten → returns short code (7-char alphanumeric)
  • Redirect: GET /{code} → 301 redirect with <10ms p99 latency globally
  • Analytics: track clicks, referrers, geo, device, UTM params in real-time
  • Custom slugs: allow user-chosen codes (collision-check required)
  • Link expiry: TTL-based expiry, cron cleanup
  • Rate limiting: 100 shorten/min per user, 1000 redirect/min per IP
  • Dashboard API: GET /analytics/{code}?from=&to= with aggregated metrics

SCALE REQUIREMENTS:
  • 100M active short links
  • 10B redirect requests/month (peak: 50K RPS)
  • 500M analytics events/month
  • Global: 6 regions, <50ms redirect latency p99 worldwide
  • 99.99% redirect availability (4 nines)

══════════════════════════════════════════════════════════════════════════════
DESIGN SECTIONS — cover each thoroughly:

1. CAPACITY ESTIMATION
   Show explicit math: storage bytes, bandwidth, QPS breakdown, DB size in 5 years.
   Example format: "50K RPS × 30 bytes/redirect = 1.5 MB/s bandwidth per region"

2. ARCHITECTURE OVERVIEW
   Describe all components (LB, app servers, cache, DB, analytics pipeline, CDN).
   Explain data flow for a redirect request end-to-end.

3. DATABASE SCHEMA
   Define all tables/collections with field names and types.
   Justify: SQL vs NoSQL choice for each entity. Include indexes.

4. API DESIGN
   Full REST API spec: endpoints, request/response schemas, HTTP status codes.
   Include auth headers, pagination, error formats.

5. CACHING STRATEGY
   Multi-layer caching (CDN → edge → Redis → DB).
   Cache-aside vs write-through. TTL strategy. Cache invalidation on link update.

6. ANALYTICS PIPELINE
   How do you handle 500M events/month without slowing down redirects?
   Describe: event ingestion (Kafka?), stream processing, storage (ClickHouse?), query.

7. RATE LIMITING IMPLEMENTATION
   Describe the algorithm (sliding window / token bucket). Redis Lua scripts or equivalent.
   How does it work across 6 regions without a single point of failure?

8. FAILURE MODES AND MITIGATIONS
   Identify 5 failure scenarios. For each: probability, impact, detection, mitigation.
   Include: Redis cache miss storm, DB primary failure, analytics queue backlog.

9. MONITORING AND ALERTING
   Key metrics, SLO definitions, alert thresholds.
   Specific Prometheus metrics with labels. Example Grafana dashboard panels.

10. DEPLOYMENT AND SCALING
    Kubernetes deployment config sketch. HPA settings. Multi-region active-active setup.
    Database replication strategy. Estimated infrastructure cost at stated scale.

══════════════════════════════════════════════════════════════════════════════
Think through each section in full depth. After your complete design narrative,
output this JSON at the very end:

{
  "architecture": "<1-paragraph architecture overview>",
  "db_schema": {
    "links":      {"id": "uuid", "code": "varchar(10)", "url": "text", "user_id": "uuid", "expires_at": "timestamptz", "created_at": "timestamptz"},
    "clicks":     {"id": "bigint", "code": "varchar(10)", "ts": "timestamptz", "ip": "inet", "referrer": "text", "country": "varchar(2)"},
    "users":      {"id": "uuid", "email": "text", "plan": "varchar(20)", "rate_limit_tier": "int"}
  },
  "api_endpoints": [
    {"method": "POST", "path": "/shorten",          "description": "..."},
    {"method": "GET",  "path": "/{code}",            "description": "..."},
    {"method": "GET",  "path": "/analytics/{code}",  "description": "..."},
    {"method": "DELETE","path": "/links/{code}",     "description": "..."}
  ],
  "capacity": {
    "peak_rps":          50000,
    "monthly_redirects": "10B",
    "storage_5yr_gb":    "<your calculation>",
    "redis_memory_gb":   "<your calculation>"
  },
  "caching_strategy": "<describe multi-layer cache strategy>",
  "monitoring": {
    "key_slos": ["redirect p99 < 10ms", "availability > 99.99%"],
    "critical_alerts": ["<alert 1>", "<alert 2>", "<alert 3>"]
  }
}"""

    def _run_ultra_system_design(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a principal engineer completing a text-generation benchmark. "
                        "Write your complete system design INLINE as text in this conversation. "
                        "Do NOT use tools, do NOT create files. "
                        "Every section must be concrete with real numbers — no placeholders. "
                        "Show all capacity math inline. Think through every failure mode in writing. "
                        "After your complete narrative, output the final JSON summary."
                    ),
                },
                {"role": "user", "content": self._ULTRA_SYSDESIGN_PROMPT},
            ],
            max_tokens=32768,
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__ultra_system_design.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_system_design(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 40 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="ultra_deep",
            case_id="ultra_system_design",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    # ── fast suite (max_tokens=2000, concise prompts, parallel-friendly) ─────

    _FAST_REASON_PROMPT = """You are solving 15 SaaS business / math problems. Think step by step, then output JSON.

CONTEXT:
Pricing tiers: Starter $25/mo (10 users, 100 GB) | Business $99/mo (50 users, 1 TB) | Enterprise $299/mo (unlimited)
Overage: users $5/user/mo up to 20% over limit then must upgrade. Starter storage: hard-capped (no overage, must upgrade). Business storage: $0.10/GB overage above 1 TB allowed.
Annual discount: 15% off.

Customers: ACME (8u,80GB,Starter) | Beta (45u,800GB,Business) | Gamma (120u,5120GB,Enterprise) | Delta (3u,10GB,Starter) | Echo (50u,1024GB,Business)

Q1 How many customers on Starter? Q2 Can Echo add 1 GB (→1025GB, Business overage $0.10/GB) and stay Business? Q3 Total monthly revenue all 5?
Q4 ACME adds 3u+30GB (→11u,110GB). New monthly bill? Q5 Minimum users to trigger Business user overage (not forced upgrade)?
Q6 Beta adds 256GB (→1056GB, Business overage allowed) — still Business? Q7 Delta grows to 12u,150GB — what tier?
Q8 How many customers at ≥80% of user limit? Q9 All 5 switch annual — total annual revenue?
Q10 Gamma drops to 49u,900GB — can downgrade to Business? What is bill?
Q11 Total monthly revenue from Enterprise customers? Q12 Assume Business storage is ALSO hard-capped (like Starter). Echo (50u,1024GB) adds 1GB — must upgrade? (true/false)
Q13 If all 5 were on Business, total monthly revenue? Q14 Is Delta below 80% of user limit? Q15 How many tier transitions in Q4,Q7,Q10,Q12?

Output JSON ONLY (no preamble):
{"answers":{"q1":<int>,"q2":<bool>,"q3":<num>,"q4":<num>,"q5":<int>,"q6":<bool>,"q7":"<tier>","q8":<int>,"q9":<num>,"q10":<num>,"q11":<num>,"q12":<bool>,"q13":<num>,"q14":<bool>,"q15":<int>},"confidence":"<high|medium|low>"}"""

    _FAST_CODE_PROMPT = """Implement a Python async task queue with these features:
- TaskQueue class: enqueue(fn, *args, **kwargs), start(workers=3), stop()
- Worker coroutines process tasks concurrently via asyncio
- Task status: pending/running/done/failed
- Retry on exception up to 3 times with exponential backoff
- result() method to await task completion

Output JSON:
{"queue_code": "<complete Python implementation with type hints>", "test_code": "<brief usage example>"}"""

    _FAST_ALGO_PROMPT = """Implement two Python data structures. Keep implementations concise but correct.

1. LRU Cache: O(1) get(key)/put(key, val) with capacity limit
2. Trie: insert(word), search(word), starts_with(prefix) → bool

Output JSON:
{"lru_code": "<Python class>", "trie_code": "<Python class>"}"""

    _FAST_SYSDESIGN_PROMPT = """Design a URL shortener service (like bit.ly). Be specific with numbers.

Requirements: 100M URLs stored, 10K writes/sec, 100K reads/sec, p99 redirect < 5ms.

Output JSON with exactly these keys:
{
  "architecture": "<tech stack, key components, e.g. PostgreSQL + Redis + Go>",
  "db_schema": {"urls": "<columns: id, code, original_url, created_at>", "clicks": "<columns: id, url_id, timestamp, ip>"},
  "api_endpoints": [
    {"method":"POST","path":"/shorten","description":"create short URL"},
    {"method":"GET","path":"/{code}","description":"redirect to original"},
    {"method":"GET","path":"/{code}/stats","description":"click analytics"}
  ],
  "capacity": "<numbers: storage, QPS, cache hit rate, e.g. 50GB, 100K read QPS, 95% cache hits>",
  "caching_strategy": "<e.g. Redis LRU, 10M most popular URLs, TTL 24h>",
  "monitoring": "<metrics: p99 latency, error rate, cache hit rate; tools: Prometheus + Grafana>"
}"""

    def _run_fast_reasoning(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise analyst. Output valid JSON only. No explanations inside JSON values — only numbers, booleans, and the confidence string.",
                },
                {"role": "user", "content": self._FAST_REASON_PROMPT},
            ],
            max_tokens=5000,
            response_format={"type": "json_object"},
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__fast_reasoning.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_reasoning(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 50 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="fast",
            case_id="fast_reasoning",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _run_fast_code(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only. Code must be syntactically correct Python.",
                },
                {"role": "user", "content": self._FAST_CODE_PROMPT},
            ],
            max_tokens=5000,  # thinking models (glm, deepseek) need headroom beyond reasoning tokens
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__fast_code.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_fast_code(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 40 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="fast",
            case_id="fast_code",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _run_fast_algorithms(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only. Python code must be syntactically correct.",
                },
                {"role": "user", "content": self._FAST_ALGO_PROMPT},
            ],
            max_tokens=5000,  # thinking models need headroom beyond reasoning tokens
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__fast_algorithms.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_fast_algorithms(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 40 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="fast",
            case_id="fast_algorithms",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _run_fast_system_design(self, run_id: str, model: str) -> CaseResult:
        call = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only. Be specific with numbers and technology choices.",
                },
                {"role": "user", "content": self._FAST_SYSDESIGN_PROMPT},
            ],
            max_tokens=5000,  # thinking models need headroom beyond reasoning tokens
        )
        raw_uri = self.artifacts.put_json(
            f"runs/{run_id}/raw/{safe_name(model)}__fast_system_design.json",
            call.raw or {"error": call.error_message},
        )
        scored = score_ultra_system_design(call.text)
        status = "passed" if not call.error_type and scored["score"] >= 30 else "failed"
        if call.error_type:
            status = "error"
        cost, cost_status = estimate_cost_usd(model, call.input_tokens, call.output_tokens)
        return CaseResult(
            model=model,
            suite="fast",
            case_id="fast_system_design",
            status=status,
            score=scored["score"],
            latency_ms_total=call.latency_ms_total,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            tokens_per_second=call.extra.get("tokens_per_second"),
            estimated_cost_usd=cost,
            cost_status=cost_status,
            json_valid=scored["json_valid"],
            schema_valid=None,
            error_type=call.error_type,
            error_message=call.error_message,
            raw_artifact_uri=raw_uri,
            extra={"scoring": scored},
        )

    def _persist_result(self, run_id, result: CaseResult) -> None:
        row = ModelResult(
            run_id=run_id,
            model=result.model,
            suite=result.suite,
            case_id=result.case_id,
            status=result.status,
            score=result.score,
            latency_ms_total=result.latency_ms_total,
            latency_ms_first_token=result.latency_ms_first_token,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            tokens_per_second=result.tokens_per_second,
            estimated_cost_usd=result.estimated_cost_usd,
            cost_status=result.cost_status,
            json_valid=result.json_valid,
            schema_valid=result.schema_valid,
            tool_call_count=result.tool_call_count,
            tool_error_count=result.tool_error_count,
            error_type=result.error_type,
            error_message=result.error_message,
            raw_artifact_uri=result.raw_artifact_uri,
            extra=result.extra,
        )
        self.db.add(row)


def safe_name(value: str) -> str:
    return value.replace("/", "__").replace(":", "_")[:120]
