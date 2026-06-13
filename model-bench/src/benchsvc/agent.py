from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from benchsvc.llm_client import LiteLLMGateway
from benchsvc.scoring import extract_json, score_agent_report
from benchsvc.settings import Settings
from benchsvc.tools import BenchmarkTools, WebSearchArgs, WriteReportArgs


class AgentState(BaseModel):
    run_id: str
    case_id: str
    model: str
    objective: str
    plan: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    final_report: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


class AgentMiniRunner:
    def __init__(self, settings: Settings, gateway: LiteLLMGateway, run_id: str):
        self.settings = settings
        self.gateway = gateway
        self.tools = BenchmarkTools(settings, run_id=run_id)

    def run(self, model: str) -> dict[str, Any]:
        state = AgentState(
            run_id=self.tools.run_id,
            case_id="agent_mini_vendor_readiness",
            model=model,
            objective="Evaluate DataEyes model-provider integration readiness using web search and local support tickets.",
        )

        plan_result = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only. You are a benchmark planning agent.",
                },
                {
                    "role": "user",
                    "content": 'Create a 3-6 step plan to evaluate a model-provider integration. Include one web_search step and one local ticket analysis step. Return {"steps":[{"name":...,"reason":...}]} only.',
                },
            ],
            response_format={"type": "json_object"},
        )
        ok, plan_payload, err = extract_json(plan_result.text)
        if ok and isinstance(plan_payload, dict):
            state.plan = plan_payload.get("steps", [])
        else:
            state.errors.append({"step": "plan", "error": err or plan_result.error_message})

        search_result = {}
        try:
            search_result = self.tools.web_search(
                WebSearchArgs(
                    query="DataEyes AI API models endpoint Langfuse LiteLLM integration", limit=5
                )
            )
            state.tool_results.append({"tool": "web_search", "result": search_result})
        except Exception as exc:
            state.errors.append({"step": "web_search", "error": str(exc)})

        tickets = self.tools.read_support_tickets()
        state.tool_results.append({"tool": "read_support_tickets", "result": tickets})

        synthesis_prompt = {
            "objective": state.objective,
            "plan": state.plan,
            "web_search": search_result.get("results", []),
            "support_tickets": tickets["rows"],
            "required_output": {
                "executive_summary": "string",
                "required_facts": ["string"],
                "risk_categories": ["string"],
                "benchmark_matrix": [
                    {"suite": "string", "purpose": "string", "metrics": ["string"]}
                ],
                "recommendation": "go|no-go|conditional-go",
                "next_actions": ["string"],
            },
        }
        synth_result = self.gateway.complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only. Do not invent prices. Prefer verifiable integration facts.",
                },
                {"role": "user", "content": json.dumps(synthesis_prompt, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        ok, report_payload, err = extract_json(synth_result.text)
        if ok and isinstance(report_payload, dict):
            state.final_report = report_payload
            try:
                self.tools.write_report(
                    WriteReportArgs(
                        title=f"Agent mini report {model}",
                        body_markdown="```json\n"
                        + json.dumps(report_payload, ensure_ascii=False, indent=2)
                        + "\n```",
                    )
                )
            except Exception as exc:
                state.errors.append({"step": "write_report", "error": str(exc)})
        else:
            state.errors.append({"step": "synthesis", "error": err or synth_result.error_message})
            report_payload = {}

        quality = score_agent_report(
            report_payload,
            latency_ms=synth_result.latency_ms_total,
            json_valid=ok,
            tool_results=state.tool_results,
        )
        return {
            "state": state.model_dump(mode="json"),
            "plan_call": plan_result.__dict__,
            "synthesis_call": synth_result.__dict__,
            "json_valid": ok,
            "schema_valid": ok,
            "score_details": quality,
            "score": quality["score"],
            "latency_ms_total": (plan_result.latency_ms_total or 0)
            + (synth_result.latency_ms_total or 0),
            "input_tokens": sum(
                x or 0 for x in [plan_result.input_tokens, synth_result.input_tokens]
            )
            or None,
            "output_tokens": sum(
                x or 0 for x in [plan_result.output_tokens, synth_result.output_tokens]
            )
            or None,
            "total_tokens": sum(
                x or 0 for x in [plan_result.total_tokens, synth_result.total_tokens]
            )
            or None,
            "tool_call_count": 3,
            "tool_error_count": len(state.errors),
            "error_type": None if ok else "invalid_json",
            "error_message": None if ok else str(err),
        }
