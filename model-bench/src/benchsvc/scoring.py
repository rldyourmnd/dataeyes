from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# ---------------------------------------------------------------------------
# Known vendor pricing: input / output per 1M tokens (USD, June 2026)
# ---------------------------------------------------------------------------
VENDOR_PRICING: dict[str, tuple[float, float]] = {
    # ---- Premium tier ----
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-fable-5": (10.00, 50.00),  # Anthropic Claude 5 flagship
    "gemini-3-pro-preview": (2.00, 12.00),  # Google Gemini 3 Pro (≤200k ctx)
    "gemini-2.5-pro-thinking": (1.25, 10.00),
    "gemini-2.5-pro-nothinking": (1.25, 10.00),
    "gpt-5.5": (5.00, 30.00),  # OpenAI GPT-5.5
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "kimi-k2-thinking": (0.60, 2.50),  # Moonshot Kimi K2
    "kimi-k2.6": (0.60, 2.50),
    "qwen3.7-max": (2.50, 7.50),  # Alibaba Qwen 3.7 Max (list)
    "doubao-seed-2-0-pro-260215": (0.44, 2.20),  # ByteDance Volcengine ¥3.2/¥16
    "MiniMax-M2.7": (0.28, 1.20),  # MiniMax official
    "mimo-v2.5-pro": (0.435, 0.87),  # Xiaomi MiMo v2.5 Pro
    # ---- Mid tier ----
    "deepseek-v4-pro": (0.435, 0.87),  # DeepSeek V4 Pro official
    "glm-5-turbo": (1.20, 4.00),  # Zhipu AI GLM-5 Turbo
    "gemini-3.5-flash": (0.15, 0.60),
    "gemini-2.5-flash-thinking": (0.15, 0.60),
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-3-flash-preview": (0.075, 0.30),
    "gpt-4.1-mini": (0.40, 1.60),
    "deepseek-v3-250324": (0.27, 1.10),
    # ---- Cheap tier (new defaults) ----
    "gpt-5.4-nano": (0.10, 0.40),  # cheapest GPT5
    "gpt-4.1-nano": (0.10, 0.40),  # cheapest GPT4.1
    "claude-haiku-4-5-20251001": (0.80, 4.00),  # cheapest working Claude
    "gemini-3.1-flash-lite": (0.10, 0.40),  # cheapest Gemini
    "gemini-3.1-flash-lite-preview": (0.10, 0.40),
    "deepseek-v4-flash": (0.14, 0.28),  # cheapest DeepSeek
    "doubao-seed-2-0-lite-260215": (0.075, 0.45),  # cheapest Doubao
    "doubao-seed-2-0-mini-260215": (0.05, 0.20),  # even cheaper Doubao
    "doubao-seed-1-6-flash-250828": (0.05, 0.15),
    "kimi-k2.5": (0.60, 2.50),  # non-thinking Kimi
    "MiniMax-M2.5": (0.20, 1.00),  # cheaper MiniMax
    "mimo-v2.5": (0.20, 0.80),  # non-pro Mimo
}


def estimate_cost_usd(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> tuple[float | None, str]:
    """Return (cost_usd, status). status = 'ok' | 'unknown_model' | 'no_tokens'."""
    if input_tokens is None or output_tokens is None:
        return None, "no_tokens"
    base = model.removeprefix("dataeyes/")
    pricing = VENDOR_PRICING.get(base)
    if pricing is None:
        return None, "unknown_model"
    in_price, out_price = pricing
    cost = (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price
    return round(cost, 8), "ok"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_AGENT_FACTS = [
    "model discovery",
    "base url",
    "search api",
    "langfuse",
    "tool calling",
    "json fallback",
    "retry",
    "rate limit",
    "benchmark matrix",
]
RISK_CATEGORIES = [
    "endpoint",
    "model availability",
    "streaming",
    "tool",
    "latency",
    "cost",
    "observability",
]
TICKET_SIGNALS = [
    "support ticket",
    "base url",
    "base_url",
    "dynamic discovery",
    "tool call",
    "tool_call",
    "latency variance",
    "cost unknown",
    "trace",
    "gateway routing",
    "sequential",
    "json validation",
]


def _try_ast_parse(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def extract_json(text: str | None) -> tuple[bool, Any, str | None]:
    """Parse JSON from model output, handling markdown fences and <think> tags."""
    if not text:
        return False, None, "empty_text"
    cleaned = text.strip()

    # Strip <think>...</think> blocks (DeepSeek-R1, Gemini thinking)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

    # Strip ```json ... ``` fences
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        return True, json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    # Fallback: extract first {...} or [...]
    for start_ch, end_ch in [("{", "}"), ("[", "]")]:
        start = cleaned.find(start_ch)
        end = cleaned.rfind(end_ch)
        if start >= 0 and end > start:
            try:
                return True, json.loads(cleaned[start : end + 1]), None
            except json.JSONDecodeError:
                pass

    return False, None, "json_decode_error: no valid JSON found"


def validate_schema(payload: Any, schema_path: str | Path) -> tuple[bool, list[str]]:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if not errors:
        return True, []
    return False, [f"{list(e.path)}: {e.message}" for e in errors]


# ---------------------------------------------------------------------------
# Case 1 – smoke
# ---------------------------------------------------------------------------


def score_smoke_json(
    text: str | None,
    latency_ms: int | None,
    latency_budget_ms: int = 15000,
) -> dict[str, Any]:
    ok, payload, err = extract_json(text)
    score = 0.0
    if ok:
        score += 40
        if (
            payload.get("status") == "ok"
            and payload.get("provider_test") == "dataeyes"
            and payload.get("answer") == 42
        ):
            score += 40
    if latency_ms is not None and latency_ms <= latency_budget_ms:
        score += 20
    return {"score": score, "json_valid": ok, "schema_valid": ok, "error": err, "payload": payload}


# ---------------------------------------------------------------------------
# Case 2 – agent (existing, unchanged)
# ---------------------------------------------------------------------------


def score_agent_report(
    payload: dict[str, Any],
    latency_ms: int | None = None,
    latency_budget_ms: int = 90000,
    json_valid: bool = True,
    tool_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False).lower()
    json_score = 15.0 if json_valid and bool(payload) else 0.0
    fact_hits = sum(1 for item in REQUIRED_AGENT_FACTS if item in text)
    fact_score = min(25.0, fact_hits / len(REQUIRED_AGENT_FACTS) * 25)
    tool_names = {r.get("tool") for r in (tool_results or [])}
    tool_score = (8.0 if "web_search" in tool_names else 0.0) + (
        7.0 if "read_support_tickets" in tool_names else 0.0
    )
    ticket_hits = sum(1 for term in TICKET_SIGNALS if term in text)
    local_score = min(15.0, ticket_hits / max(1, len(TICKET_SIGNALS) // 2) * 15)
    has_matrix = bool(payload.get("benchmark_matrix") or "benchmark matrix" in text)
    matrix_score = 10.0 if has_matrix else 0.0
    risk_hits = sum(1 for item in RISK_CATEGORIES if item in text)
    risk_score = min(10.0, risk_hits / len(RISK_CATEGORIES) * 10)
    has_recommendation = bool(payload.get("recommendation") or "go" in text or "no-go" in text)
    recommendation_score = 5.0 if has_recommendation else 0.0
    latency_score = 5.0 if (latency_ms is not None and latency_ms <= latency_budget_ms) else 0.0
    total = (
        json_score
        + fact_score
        + tool_score
        + local_score
        + matrix_score
        + risk_score
        + recommendation_score
        + latency_score
    )
    return {
        "score": round(total, 2),
        "fact_hits": fact_hits,
        "risk_hits": risk_hits,
        "has_matrix": has_matrix,
        "has_recommendation": has_recommendation,
        "json_score": json_score,
        "tool_score": tool_score,
        "local_score": round(local_score, 2),
        "ticket_hits": ticket_hits,
        "latency_score": latency_score,
    }


# ---------------------------------------------------------------------------
# Case 3 – reasoning_multistep  (SaaS tier calculation)
# ---------------------------------------------------------------------------
# Correct answers (deterministic):
#   acme_new_tier            = "Business"   (11 users > 10 limit; 110 GB > 100 GB limit)
#   beta_can_stay_business   = false        (55 users > 50 limit)
#   current_total_revenue    = 423          (25+99+299)
#   revenue_after_acme_upgrade = 497        (99+99+299)
#   min_users_for_enterprise = 51           (first over Business 50-user cap)


def score_reasoning_multistep(text: str | None) -> dict[str, Any]:
    """Score the SaaS-tier multi-step reasoning case. Max 100 pts, partial credit."""
    ok, payload, json_err = extract_json(text)
    details: dict[str, Any] = {}
    if not ok or not isinstance(payload, dict):
        return {"score": 0.0, "json_valid": False, "error": json_err, "details": details}

    score = 10.0  # JSON valid baseline
    details["json_valid"] = True

    # acme_new_tier = "Business" (20 pts)
    acme = str(payload.get("acme_new_tier", "")).strip().lower()
    if acme in ("business",):
        score += 20.0
        details["acme_tier"] = True

    # beta_can_stay_business = false (20 pts)
    beta = payload.get("beta_can_stay_business")
    if beta is False:
        score += 20.0
        details["beta_stay"] = True

    # current_total_revenue ≈ 423 (±2) (15 pts)
    rev = payload.get("current_total_revenue")
    if isinstance(rev, (int, float)) and abs(float(rev) - 423) <= 2:
        score += 15.0
        details["current_revenue"] = True

    # revenue_after_acme_upgrade ≈ 497 (±2) (20 pts)
    rev2 = payload.get("revenue_after_acme_upgrade")
    if isinstance(rev2, (int, float)) and abs(float(rev2) - 497) <= 2:
        score += 20.0
        details["post_upgrade_revenue"] = True

    # min_users_for_enterprise ≈ 51 (±1) (10 pts)
    mu = payload.get("min_users_for_enterprise")
    if isinstance(mu, (int, float)) and abs(float(mu) - 51) <= 1:
        score += 10.0
        details["min_users"] = True

    # reasoning present (5 pts)
    reason = payload.get("reasoning", "")
    if isinstance(reason, str) and len(reason) > 40:
        score += 5.0
        details["has_reasoning"] = True

    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ---------------------------------------------------------------------------
# Case 4 – code_generation
# ---------------------------------------------------------------------------

_REQUIRED_CODE_KEYS = [
    "best_model",
    "worst_model",
    "avg_score",
    "avg_latency_ms",
    "efficiency",
    "passed",
    "total_tokens",
]


def score_code_generation(text: str | None) -> dict[str, Any]:
    """Score Python code generation case. Max 100 pts."""
    ok, payload, json_err = extract_json(text)
    details: dict[str, Any] = {}
    if not ok or not isinstance(payload, dict):
        return {"score": 0.0, "json_valid": False, "error": json_err, "details": details}

    score = 10.0  # JSON valid
    details["json_valid"] = True

    code = payload.get("code", "")
    if not isinstance(code, str) or len(code.strip()) < 20:
        details["code_missing"] = True
        return {"score": score, "json_valid": True, "details": details}

    score += 10.0  # code field present
    details["code_present"] = True

    # AST parse (30 pts)
    try:
        ast.parse(code)
        score += 30.0
        details["ast_valid"] = True
    except SyntaxError as exc:
        details["ast_error"] = str(exc)
        return {"score": score, "json_valid": True, "details": details}

    # Function defined with correct name (5 pts)
    if "def benchmark_stats" in code:
        score += 5.0
        details["func_name"] = True

    # All 7 return keys present in code (20 pts, proportional)
    found_keys = sum(1 for k in _REQUIRED_CODE_KEYS if k in code)
    key_score = round(found_keys / len(_REQUIRED_CODE_KEYS) * 20.0, 2)
    score += key_score
    details["keys_found"] = found_keys

    # Efficiency calculation (score/latency) present (10 pts)
    if "efficiency" in code and ("latency" in code):
        score += 10.0
        details["efficiency_calc"] = True

    # Empty list / null handling (10 pts)
    if any(
        kw in code for kw in ("if not ", "if results", "len(results) == 0", "== []", "not results")
    ):
        score += 10.0
        details["empty_handling"] = True

    # Key error / missing key handling (5 pts)
    if any(kw in code for kw in (".get(", "try:", "KeyError", "get(model")):
        score += 5.0
        details["key_error_handling"] = True

    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ---------------------------------------------------------------------------
# Case 5 – instruction_strict  (multi-constraint format adherence, IFEval-style)
# ---------------------------------------------------------------------------


def score_instruction_strict(text: str | None) -> dict[str, Any]:
    """Score strict multi-constraint JSON instruction following. Max 100 pts, partial credit per constraint."""
    ok, payload, json_err = extract_json(text)
    details: dict[str, Any] = {}
    if not ok or not isinstance(payload, dict):
        return {"score": 0.0, "json_valid": False, "error": json_err, "details": details}

    score = 15.0  # JSON valid (most important)
    details["json_valid"] = True

    # analysis_date = "2026-06-10" (10 pts)
    if payload.get("analysis_date") == "2026-06-10":
        score += 10.0
        details["date_correct"] = True

    # updated_by = "benchmark_runner_v2" (10 pts)
    if payload.get("updated_by") == "benchmark_runner_v2":
        score += 10.0
        details["updated_by_correct"] = True

    models = payload.get("models", [])
    if not isinstance(models, list):
        return {"score": score, "json_valid": True, "details": details}

    # Exactly 4 models (15 pts)
    if len(models) == 4:
        score += 15.0
        details["models_count"] = True

        # Ranks 1–4, no duplicates (10 pts)
        ranks = [m.get("rank") for m in models if isinstance(m, dict)]
        if sorted(ranks) == [1, 2, 3, 4]:
            score += 10.0
            details["ranks_valid"] = True

        # All 8 required fields in every model entry (10 pts, proportional)
        required_fields = [
            "rank",
            "provider",
            "model_name",
            "strengths",
            "weaknesses",
            "price_per_million_output_tokens",
            "latency_tier",
            "best_for",
        ]
        fields_per_model = [
            sum(1 for f in required_fields if f in m) for m in models if isinstance(m, dict)
        ]
        avg_fields = sum(fields_per_model) / max(1, len(fields_per_model))
        score += round(avg_fields / len(required_fields) * 10.0, 2)
        details["avg_fields"] = round(avg_fields, 2)

        # strengths: 3–5 items each (10 pts)
        if all(
            isinstance(m.get("strengths"), list) and 3 <= len(m["strengths"]) <= 5
            for m in models
            if isinstance(m, dict)
        ):
            score += 10.0
            details["strengths_valid"] = True

        # weaknesses: 2–3 items each (10 pts)
        if all(
            isinstance(m.get("weaknesses"), list) and 2 <= len(m["weaknesses"]) <= 3
            for m in models
            if isinstance(m, dict)
        ):
            score += 10.0
            details["weaknesses_valid"] = True

    # summary = exactly 2 sentences (10 pts)
    summary = payload.get("summary", "")
    if isinstance(summary, str):
        sentences = [s.strip() for s in summary.rstrip(".").split(".") if s.strip()]
        if len(sentences) == 2:
            score += 10.0
            details["summary_2_sentences"] = True

    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ---------------------------------------------------------------------------
# Case 6 – long_context_qa  (needle-in-haystack with calculation)
# ---------------------------------------------------------------------------
# Correct answers (from embedded data):
#   q1_highest_avg_score_model    = "delta-frontier"   (avg 97.33)
#   q2_total_tokens_passed_cases  = 10450
#   q3_fastest_model_reasoning    = "alpha-7b"         (1200 ms)
#   q4_models_all_cases_passed    = ["gamma-70b","delta-frontier"] (any order)
#   q5_avg_latency_gamma_70b_ms   = 7067               ((8900+7200+5100)/3 ≈ 7066.67)


def score_long_context_qa(text: str | None) -> dict[str, Any]:
    """Score the long-context Q&A extraction case. Max 100 pts."""
    ok, payload, json_err = extract_json(text)
    details: dict[str, Any] = {}
    if not ok or not isinstance(payload, dict):
        return {"score": 0.0, "json_valid": False, "error": json_err, "details": details}

    score = 15.0  # JSON valid
    details["json_valid"] = True

    # q1: delta-frontier (20 pts)
    q1 = str(payload.get("q1_highest_avg_score_model", "")).lower()
    if "delta" in q1:
        score += 20.0
        details["q1"] = True

    # q2: 10450 ±10 (20 pts)
    q2 = payload.get("q2_total_tokens_passed_cases")
    if isinstance(q2, (int, float)) and abs(float(q2) - 10450) <= 10:
        score += 20.0
        details["q2"] = True

    # q3: alpha-7b (15 pts)
    q3 = str(payload.get("q3_fastest_model_reasoning", "")).lower()
    if "alpha" in q3:
        score += 15.0
        details["q3"] = True

    # q4: [gamma-70b, delta-frontier] any order, exactly 2 (20 pts)
    q4 = payload.get("q4_models_all_cases_passed", [])
    if isinstance(q4, list):
        q4_lower = [str(s).lower() for s in q4]
        if (
            any("gamma" in s for s in q4_lower)
            and any("delta" in s for s in q4_lower)
            and len(q4) == 2
        ):
            score += 20.0
            details["q4"] = True

    # q5: 7067 ±50 (10 pts)
    q5 = payload.get("q5_avg_latency_gamma_70b_ms")
    if isinstance(q5, (int, float)) and abs(float(q5) - 7067) <= 50:
        score += 10.0
        details["q5"] = True

    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ---------------------------------------------------------------------------
# ultra_deep suite scorers
# ---------------------------------------------------------------------------

# ── ultra_reasoning ──────────────────────────────────────────────────────────
# 15 hard interconnected questions; deterministic correct answers embedded in prompt.
# Answers key:  q1=3, q2=true, q3=423, q4=497, q5=51, q6=false, q7=business,
#               q8=7, q9=150, q10=900, q11=299, q12=false, q13=1497, q14=true, q15=4

_ULTRA_REASON_ANSWERS: dict[str, Any] = {
    # 5 customers: ACME(Starter), Beta(Business), Gamma(Enterprise), Delta(Starter), Echo(Business)
    "q1": 2,  # Starter customers: ACME + Delta = 2
    "q2": True,  # Echo +1GB → 1025GB; storage overage $0.10/GB allowed on Business (hard-cap only for Starter) → can stay
    "q3": 547,  # 25+99+299+25+99 = 547
    "q4": 99,  # ACME → 11 users, 110GB → must upgrade to Business → $99/month (no overage)
    "q5": 51,  # first user over Business 50-user cap triggers overage
    "q6": True,  # Beta +256GB → 1056GB > 1024GB; storage overage allowed on Business → can stay (pays overage)
    "q7": "business",  # Delta 12 users, 150GB → fits Business (max 50 users / 1024 GB)
    "q8": 3,  # ACME 80%, Beta 90%, Echo 100% → 3 customers
    "q9": 5579,  # 547×12×0.85 = 5579.40 ≈ 5579
    "q10": 99,  # Gamma → 49 users, 900GB → Business $99/month (no overage, 900<1024)
    "q11": 299,  # only Gamma on Enterprise = $299
    "q12": True,  # Echo +1GB; Q12 explicitly states Business storage hard-capped → must upgrade to Enterprise
    "q13": 495,  # all 5 on Business = 5×$99 = $495
    "q14": True,  # Delta 3/10 = 30% < 80% → is below 80%
    "q15": 4,  # transitions in Q4(ACME→Business), Q7(Delta→Business), Q10(Gamma→Business), Q12(Echo→Enterprise)
}


def score_ultra_reasoning(text: str | None) -> dict[str, Any]:
    ok, payload, json_err = extract_json(text)
    if not ok or not isinstance(payload, dict):
        return {"score": 0.0, "json_valid": False, "error": json_err, "details": {}}
    score = 5.0  # JSON valid baseline
    details: dict[str, Any] = {"json_valid": True}
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        # also accept list format
        if isinstance(answers, list):
            answers = {
                f"q{i + 1}": a.get("answer") if isinstance(a, dict) else a
                for i, a in enumerate(answers)
            }
        else:
            answers = {}
    _MISSING = object()
    for key, correct in _ULTRA_REASON_ANSWERS.items():
        val = answers.get(key, _MISSING)
        if val is _MISSING:
            val = payload.get(key, _MISSING)
        if val is _MISSING:
            continue
        pts = 6.0
        if isinstance(correct, bool):
            match = (
                str(val).lower() in ("true", "yes", "1")
                if correct
                else str(val).lower() in ("false", "no", "0")
            )
        elif isinstance(correct, str):
            match = str(val).lower() == correct.lower()
        else:
            try:
                match = abs(float(val) - float(correct)) <= (abs(float(correct)) * 0.02 + 1)
            except (TypeError, ValueError):
                match = False
        if match:
            score += pts
            details[key] = True
    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ── ultra_code_full ──────────────────────────────────────────────────────────
# Async distributed task queue: 4 Python modules expected in JSON fields.

_ULTRA_CODE_REQUIRED_FUNCS = [
    "enqueue",
    "dequeue",
    "worker",
    "retry",
    "schedule",
    "cancel",
    "result",
    "status",
    "async def",
    "asyncio",
]


def score_ultra_code_full(text: str | None) -> dict[str, Any]:
    ok, payload, json_err = extract_json(text)
    if not isinstance(payload, dict):
        ok = False
    full_text = text or ""
    base = 5.0 if not ok else 10.0
    score = base
    details: dict[str, Any] = {"json_valid": ok}
    # Required functions/patterns (25 pts) — run on full text regardless of JSON
    found = sum(1 for f in _ULTRA_CODE_REQUIRED_FUNCS if f in full_text)
    func_score = round(found / len(_ULTRA_CODE_REQUIRED_FUNCS) * 25.0, 2)
    score += func_score
    details["func_hits"] = found
    # Test code (15 pts)
    if any(kw in full_text for kw in ("def test_", "unittest", "pytest", "assert ")):
        score += 15.0
        details["has_tests"] = True
    # Error handling (10 pts)
    if any(kw in full_text for kw in ("except", "raise", "try:", "Exception", "Error")):
        score += 10.0
        details["has_error_handling"] = True
    # Output length (10 pts — proxy for completeness, min 5000 chars)
    if len(full_text) >= 5000:
        score += 10.0
        details["output_length"] = len(full_text)
    if not ok:
        details["json_error"] = json_err
        # AST validity via code fences (30 pts)
        ast_pts = 0
        for m in re.finditer(r"```python\s*(.*?)```", full_text, re.DOTALL):
            if len(m.group(1)) > 50:
                try:
                    ast.parse(m.group(1))
                    ast_pts += 7
                except SyntaxError:
                    pass
        if ast_pts:
            score += min(30.0, ast_pts)
            details["ast_valid_fence"] = True
        return {"score": min(100.0, score), "json_valid": False, "details": details}
    # Full JSON scoring
    all_code = " ".join(
        str(v)
        for k, v in payload.items()
        if isinstance(v, str) and ("code" in k or "impl" in k or "module" in k)
    )
    if not all_code.strip():
        all_code = " ".join(str(v) for v in payload.values() if isinstance(v, str) and len(v) > 100)
    # AST validity (30 pts)
    ast_pts = 0
    parsed_any = False
    for _k, v in payload.items():
        if isinstance(v, str) and len(v) > 50:
            try:
                ast.parse(v)
                ast_pts += 7
                parsed_any = True
            except SyntaxError:
                pass
    score += min(30.0, ast_pts)
    if parsed_any:
        details["ast_valid"] = True
    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ── ultra_code_review ────────────────────────────────────────────────────────
# 20 bugs planted; score proportional to number found + fixed code AST validity.

_KNOWN_BUG_TYPES = {
    "hardcoded_secret",
    "hardcoded",
    "secret",
    "memory_leak",
    "memory leak",
    "unbounded",
    "weak_prng",
    "predictable",
    "random.seed",
    "prng",
    "md5",
    "weak_hash",
    "password",
    "timing_attack",
    "timing",
    "constant.time",
    "constant-time",
    "backdoor",
    "admin_token",
    "sql_injection",
    "sql injection",
    "f-string",
    "injection",
    "logic_inversion",
    "logic",
    "overage",
    "type_confusion",
    "discount",
    "fraction",
    "race_condition",
    "race condition",
    "concurrency",
    "regex",
    "email",
    "validation",
    "timezone",
    "naive",
    "datetime",
    "path_traversal",
    "traversal",
    "directory",
    "sensitive_data",
    "password_hash",
    "data leak",
    "off_by_one",
    "off-by-one",
    "page=0",
    "inefficient",
    "bubble sort",
    "o(n",
    "open_redirect",
    "redirect",
    "unvalidated",
    "unsafe_deserialisation",
    "yaml.load",
    "deserialisation",
    "eviction",
    "unbounded cache",
}


def score_ultra_code_review(text: str | None) -> dict[str, Any]:
    ok, payload, json_err = extract_json(text)
    full_text = (text or "").lower()
    # Bug-category scoring runs on full text regardless of JSON validity.
    # The fixed_code JSON field often truncates at max_tokens; don't gate all scoring on JSON.
    bug_categories_found = set()
    for term in _KNOWN_BUG_TYPES:
        if term in full_text:
            if any(t in term for t in ("hardcoded", "secret")):
                bug_categories_found.add("hardcoded_secret")
            elif any(t in term for t in ("memory", "unbounded")):
                bug_categories_found.add("memory_leak")
            elif any(t in term for t in ("prng", "random.seed", "predictable")):
                bug_categories_found.add("weak_prng")
            elif any(t in term for t in ("md5", "weak_hash", "password")):
                bug_categories_found.add("weak_hash")
            elif any(t in term for t in ("timing",)):
                bug_categories_found.add("timing_attack")
            elif "backdoor" in term or "admin_token" in term:
                bug_categories_found.add("backdoor")
            elif any(t in term for t in ("injection", "f-string", "sql")):
                bug_categories_found.add("sql_injection")
            elif any(t in term for t in ("overage", "inversion")):
                bug_categories_found.add("logic_inversion")
            elif any(t in term for t in ("discount", "fraction", "type_confusion")):
                bug_categories_found.add("type_confusion")
            elif any(t in term for t in ("race", "concurrency")):
                bug_categories_found.add("race_condition")
            elif "regex" in term or "email" in term:
                bug_categories_found.add("regex_email")
            elif "timezone" in term or "naive" in term:
                bug_categories_found.add("timezone_naive")
            elif "traversal" in term or "directory" in term:
                bug_categories_found.add("path_traversal")
            elif any(t in term for t in ("sensitive", "hash", "data leak")):
                bug_categories_found.add("sensitive_data")
            elif "off" in term or "page=0" in term:
                bug_categories_found.add("off_by_one")
            elif "bubble" in term or "inefficient" in term:
                bug_categories_found.add("inefficient_algo")
            elif "redirect" in term:
                bug_categories_found.add("open_redirect")
            elif "yaml" in term or "deseriali" in term:
                bug_categories_found.add("unsafe_deserialise")
            elif "eviction" in term or "cache" in term:
                bug_categories_found.add("unbounded_cache")
    bugs_found = len(bug_categories_found)
    base = 5.0 if not ok else 10.0  # partial credit even without JSON
    bug_score = round(bugs_found / 20 * 60.0, 2)
    score = base + bug_score
    details: dict[str, Any] = {
        "json_valid": ok,
        "bugs_found": bugs_found,
        "bug_categories": sorted(bug_categories_found),
    }
    if not ok:
        details["json_error"] = json_err
        # Check for raw fixed code block in full response (code fence fallback)
        code_fence = re.search(r"```python\s*(.*?)```", text or "", re.DOTALL)
        if code_fence and len(code_fence.group(1)) > 100:
            try:
                ast.parse(code_fence.group(1))
                score += 15.0
                details["fixed_code_ast_valid_fence"] = True
            except SyntaxError:
                pass
        return {"score": min(100.0, score), "json_valid": False, "details": details}
    # Full JSON scoring
    if not isinstance(payload, dict):
        return {"score": min(100.0, score), "json_valid": False, "details": details}
    fixed = payload.get("fixed_code") or payload.get("fix") or ""
    if isinstance(fixed, str) and len(fixed) > 100:
        try:
            ast.parse(fixed)
            score += 20.0
            details["fixed_code_ast_valid"] = True
        except SyntaxError:
            pass
    has_summary = any(
        k in payload for k in ("summary", "analysis", "conclusion", "recommendations")
    )
    if has_summary:
        score += 10.0
        details["has_summary"] = True
    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ── ultra_algorithms ─────────────────────────────────────────────────────────
# 4 data structures: LRU cache, Trie, Bloom filter, consistent hashing.

_DS_REQUIRED = {
    "lru": ["lru", "get", "put", "capacity", "cache", "evict", "lru_cache"],
    "trie": ["trie", "insert", "search", "startswith", "prefix", "node"],
    "bloom": ["bloom", "hash", "false_positive", "bit_array", "false positive", "hashfunc"],
    "consistent_hash": ["consistent", "hash", "ring", "virtual", "node", "vnodes"],
    "red_black": [
        "red",
        "black",
        "rotate",
        "recolor",
        "rb_node",
        "red_black",
        "left_rotate",
        "right_rotate",
    ],
    "skip_list": ["skip", "skiplist", "skip_list", "level", "forward", "coin", "probabilistic"],
}


def score_ultra_algorithms(text: str | None) -> dict[str, Any]:
    ok, payload, json_err = extract_json(text)
    full_text = (text or "").lower()
    # DS keyword scoring always runs on full text — JSON fields add no extra signal here.
    base_ds = list(_DS_REQUIRED.keys())[:4]
    bonus_ds = list(_DS_REQUIRED.keys())[4:]
    base = 5.0 if not ok else 10.0
    score = base
    details: dict[str, Any] = {"json_valid": ok}
    if not ok:
        details["json_error"] = json_err
    for ds_name in base_ds:
        keywords = _DS_REQUIRED[ds_name]
        hits = sum(1 for kw in keywords if kw in full_text)
        if hits >= 3:
            score += 15.0
            details[f"{ds_name}_present"] = True
        elif hits >= 1:
            score += 5.0
            details[f"{ds_name}_partial"] = True
    for ds_name in bonus_ds:
        keywords = _DS_REQUIRED[ds_name]
        hits = sum(1 for kw in keywords if kw in full_text)
        if hits >= 3:
            score += 10.0
            details[f"{ds_name}_present"] = True
        elif hits >= 1:
            score += 3.0
            details[f"{ds_name}_partial"] = True
    # AST validity (20 pts): try JSON code fields first, then code fences
    code_values: list[str] = []
    if ok and isinstance(payload, dict):
        code_values = [v for v in payload.values() if isinstance(v, str) and len(v) > 50]
    if not code_values:
        code_values = [
            m.group(1) for m in re.finditer(r"```python\s*(.*?)```", text or "", re.DOTALL)
        ]
    valid_blocks = sum(1 for v in code_values if _try_ast_parse(v))
    if valid_blocks >= 2:
        score += 20.0
        details["ast_blocks_valid"] = valid_blocks
    elif valid_blocks == 1:
        score += 8.0
        details["ast_blocks_valid"] = valid_blocks
    # Complexity analysis
    has_complexity = any(
        kw in full_text for kw in ("o(1)", "o(n)", "o(log", "time complexity", "space complexity")
    )
    if has_complexity:
        details["complexity_analysis"] = True
    else:
        score = max(0.0, score - 10.0)
    return {"score": min(100.0, score), "json_valid": ok, "details": details}


# ── ultra_long_context ───────────────────────────────────────────────────────
# 12 questions about the embedded DataEyes eval report.
# Correct answers are constants defined in fixtures/long_doc.py

_LONG_DOC_ANSWERS: dict[str, Any] = {
    "q1_overall_sla_pct": 99.71,
    "q2_cheapest_model": "MiniMax-M2.7",
    "q3_highest_composite_score": 94.2,
    "q4_total_evaluation_cost_usd": 7841,
    "q5_ap_se1_incidents": 7,
    "q6_deepseek_v4_flash_avg_throughput": 312,
    "q7_minimax_vs_deepseek_monthly_savings_usd": 118,
    "q8_kimi_k2_ttft_p50_ms": 1240,
    "q9_models_tested_count": 14,
    "q10_glm5_context_window_tokens": 1048576,
    "q11_top_region_peak_rps": 4420,
    "q12_eu_west1_mttr_min": 22,
}


def score_ultra_long_context(text: str | None) -> dict[str, Any]:
    ok, payload, json_err = extract_json(text)
    if not ok or not isinstance(payload, dict):
        return {"score": 0.0, "json_valid": False, "error": json_err, "details": {}}
    score = 4.0
    details: dict[str, Any] = {"json_valid": True}
    for key, correct in _LONG_DOC_ANSWERS.items():
        val = payload.get(key)
        if val is None:
            continue
        pts = 8.0
        if isinstance(correct, str):
            match = str(val).lower().strip() == correct.lower().strip()
        elif isinstance(correct, float):
            try:
                match = abs(float(val) - correct) <= (correct * 0.01 + 0.1)
            except (TypeError, ValueError):
                match = False
        else:
            try:
                match = abs(int(float(val)) - int(correct)) <= max(1, int(correct) // 20)
            except (TypeError, ValueError):
                match = False
        if match:
            score += pts
            details[key] = True
        else:
            details[f"{key}_got"] = val
    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ── ultra_system_design ──────────────────────────────────────────────────────
# Complete system design: capacity math, DB schema, API, caching, monitoring.

_SYSDESIGN_REQUIRED_KEYS = [
    "architecture",
    "db_schema",
    "api_endpoints",
    "capacity",
    "caching_strategy",
    "monitoring",
]
_SYSDESIGN_KEYWORDS = [
    "load balancer",
    "cdn",
    "redis",
    "cache",
    "database",
    "index",
    "sharding",
    "replication",
    "rate limit",
    "circuit breaker",
    "horizontal scal",
    "availability",
    "latency",
    "throughput",
    "read replica",
    "write",
    "eventual consistency",
]


def score_ultra_system_design(text: str | None) -> dict[str, Any]:
    ok, payload, json_err = extract_json(text)
    full_lower = (text or "").lower()
    # Keyword richness and output length always run on raw text.
    kw_hits = sum(1 for kw in _SYSDESIGN_KEYWORDS if kw in full_lower)
    total_len = len(text or "")
    base = 5.0 if not ok else 10.0
    score = base
    details: dict[str, Any] = {"json_valid": ok}
    if not ok:
        details["json_error"] = json_err
    # Capacity estimation signals in full text (15 pts)
    has_numbers = sum(1 for ch in full_lower if ch.isdigit()) >= 20
    has_units = any(
        u in full_lower for u in ("qps", "rps", "req/s", "tb", "gb", "billion", "million", " 1000 ")
    )
    if has_numbers and has_units:
        score += 15.0
        details["capacity_math"] = True
    elif has_numbers or has_units:
        score += 6.0
    # Keyword richness (35 pts proportional — primary signal when JSON missing)
    score += round(kw_hits / len(_SYSDESIGN_KEYWORDS) * 35.0, 2)
    details["keyword_hits"] = kw_hits
    # Output length ≥ 3000 chars (10 pts)
    if total_len >= 3000:
        score += 10.0
        details["output_length"] = total_len
    if not ok or not isinstance(payload, dict):
        return {"score": min(100.0, score), "json_valid": False, "details": details}
    # Full JSON bonus scoring
    found_keys = sum(1 for k in _SYSDESIGN_REQUIRED_KEYS if k in payload)
    score += round(found_keys / len(_SYSDESIGN_REQUIRED_KEYS) * 15.0, 2)
    details["keys_found"] = found_keys
    endpoints = payload.get("api_endpoints", [])
    if isinstance(endpoints, list) and len(endpoints) >= 3:
        score += 5.0
        details["api_endpoints_ok"] = True
    db = payload.get("db_schema", {})
    if isinstance(db, dict) and len(db) >= 2:
        score += 5.0
        details["db_schema_ok"] = True
    return {"score": min(100.0, score), "json_valid": True, "details": details}


# ── fast_algorithms ───────────────────────────────────────────────────────────
# 2 data structures: LRU Cache + Trie. Concise implementations, max_tokens=2000.

_FAST_CODE_KW = [
    "taskqueue",
    "task_queue",
    "enqueue",
    "dequeue",
    "workers",
    "asyncio",
    "coroutine",
    "pending",
    "running",
    "failed",
    "retry",
    "backoff",
    "result",
    "asyncworker",
]


def score_fast_code(text: str | None) -> dict[str, Any]:
    """Score fast_code output: expects JSON with queue_code and test_code keys."""
    ok, payload, json_err = extract_json(text)
    if not isinstance(payload, dict):
        ok = False
    full_text = (text or "").lower()
    score = 5.0 if not ok else 10.0
    details: dict[str, Any] = {"json_valid": ok}
    # JSON structure (20 pts)
    if ok and isinstance(payload, dict):
        if "queue_code" in payload:
            score += 10.0
        if "test_code" in payload:
            score += 10.0
    # Keyword presence (40 pts)
    kw_hits = sum(1 for kw in _FAST_CODE_KW if kw in full_text)
    score += min(40.0, round(kw_hits / 5 * 40.0, 2))
    details["kw_hits"] = kw_hits
    # AST validity (30 pts)
    code_blocks: list[str] = []
    if ok and isinstance(payload, dict):
        code_blocks = [str(v) for v in payload.values() if isinstance(v, str) and len(v) > 50]
    if not code_blocks:
        code_blocks = [
            m.group(1)
            for m in re.finditer(r"```python\s*(.*?)```", text or "", re.DOTALL)
            if len(m.group(1)) > 50
        ]
    ast_pts = 0
    for block in code_blocks[:3]:
        try:
            ast.parse(block)
            ast_pts += 15
        except SyntaxError:
            pass
    score += min(30.0, ast_pts)
    if ast_pts:
        details["ast_valid"] = True
    return {"score": min(100.0, score), "json_valid": ok, "details": details}


_FAST_ALGO_LRU_KW = ["lru", "capacity", "get", "put", "cache", "evict", "doubly", "orderdict"]
_FAST_ALGO_TRIE_KW = ["trie", "insert", "search", "startswith", "prefix", "node", "children"]


def score_fast_algorithms(text: str | None) -> dict[str, Any]:
    ok, payload, json_err = extract_json(text)
    if not isinstance(payload, dict):
        ok = False
    full_text = (text or "").lower()
    score = 5.0 if not ok else 10.0
    details: dict[str, Any] = {"json_valid": ok}
    # LRU (35 pts)
    lru_hits = sum(1 for kw in _FAST_ALGO_LRU_KW if kw in full_text)
    score += min(35.0, round(lru_hits / 4 * 35.0, 2))
    details["lru_hits"] = lru_hits
    # Trie (35 pts)
    trie_hits = sum(1 for kw in _FAST_ALGO_TRIE_KW if kw in full_text)
    score += min(35.0, round(trie_hits / 4 * 35.0, 2))
    details["trie_hits"] = trie_hits
    # AST validity (20 pts)
    code_blocks: list[str] = []
    if ok and isinstance(payload, dict):
        code_blocks = [str(v) for v in payload.values() if isinstance(v, str) and len(v) > 50]
    if not code_blocks:
        code_blocks = [
            m.group(1)
            for m in re.finditer(r"```python\s*(.*?)```", text or "", re.DOTALL)
            if len(m.group(1)) > 50
        ]
    ast_pts = 0
    for block in code_blocks:
        try:
            ast.parse(block)
            ast_pts += 10
        except SyntaxError:
            pass
    score += min(20.0, ast_pts)
    if ast_pts:
        details["ast_valid"] = True
    return {"score": min(100.0, score), "json_valid": ok, "details": details}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "avg_score": 0.0,
            "error_rate": 1.0,
            "p50_latency_ms_total": None,
            "p95_latency_ms_total": None,
            "total_estimated_cost_usd": None,
            "cost_status": "unknown",
        }
    passed = sum(1 for r in results if r.get("status") == "passed")
    errors = sum(1 for r in results if r.get("status") == "error")
    failed = len(results) - passed - errors
    scores = [float(r.get("score") or 0) for r in results]
    latencies = sorted(int(r["latency_ms_total"]) for r in results if r.get("latency_ms_total"))
    p50 = latencies[len(latencies) // 2] if latencies else None
    p95 = latencies[int((len(latencies) - 1) * 0.95)] if latencies else None

    costs = [r.get("estimated_cost_usd") for r in results]
    valid_costs = [c for c in costs if c is not None]
    total_cost = round(sum(valid_costs), 8) if valid_costs else None
    cost_status = (
        "ok" if len(valid_costs) == len(results) else ("partial" if valid_costs else "unknown")
    )

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "error_rate": round((errors + failed) / len(results), 4),
        "avg_score": round(sum(scores) / len(scores), 2),
        "p50_latency_ms_total": p50,
        "p95_latency_ms_total": p95,
        "total_estimated_cost_usd": total_cost,
        "cost_status": cost_status,
    }
