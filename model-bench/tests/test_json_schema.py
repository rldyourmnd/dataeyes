from pathlib import Path

from benchsvc.scoring import validate_schema


def test_benchmark_result_schema_accepts_valid_payload():
    payload = {
        "executive_summary": "This benchmark result is valid and includes enough detail.",
        "required_facts": ["model discovery", "base url", "langfuse"],
        "risk_categories": ["endpoint", "latency", "cost"],
        "benchmark_matrix": [
            {"suite": "smoke", "purpose": "availability", "metrics": ["latency", "success"]},
            {"suite": "agent_mini", "purpose": "quality", "metrics": ["score"]},
        ],
        "recommendation": "conditional-go",
        "next_actions": ["run smoke", "inspect Langfuse"],
        "estimated_cost_usd": None,
        "cost_status": "unknown",
    }
    ok, errors = validate_schema(payload, Path("schemas/benchmark_result.schema.json"))
    assert ok, errors
