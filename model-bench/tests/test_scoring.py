import pytest

from benchsvc.scoring import aggregate_results, extract_json, score_agent_report, score_smoke_json


def test_extract_json_exact():
    ok, payload, err = extract_json('{"status":"ok"}')
    assert ok is True
    assert payload == {"status": "ok"}
    assert err is None


def test_extract_json_markdown_wrapped():
    # DataEyes models sometimes wrap JSON in markdown even with json_object mode
    text = '```json\n{"status":"ok","answer":42}\n```'
    ok, payload, err = extract_json(text)
    assert ok is True
    assert payload == {"status": "ok", "answer": 42}
    assert err is None


def test_score_smoke_json_exact():
    result = score_smoke_json(
        '{"status":"ok","provider_test":"dataeyes","answer":42}', latency_ms=100
    )
    assert result["score"] == 100
    assert result["json_valid"] is True


def test_score_smoke_json_markdown_wrapped():
    text = '```json\n{"status":"ok","provider_test":"dataeyes","answer":42}\n```'
    result = score_smoke_json(text, latency_ms=100)
    assert result["score"] == 100
    assert result["json_valid"] is True


def test_agent_score_hits_required_terms():
    payload = {
        "executive_summary": "Use model discovery and base url checks.",
        "required_facts": [
            "model discovery",
            "base url",
            "search api",
            "langfuse",
            "tool calling",
            "json fallback",
            "retry",
            "rate limit",
            "benchmark matrix",
        ],
        "risk_categories": [
            "endpoint",
            "model availability",
            "streaming",
            "tool",
            "latency",
            "cost",
            "observability",
        ],
        "benchmark_matrix": [{"suite": "smoke", "purpose": "availability", "metrics": ["latency"]}],
        "recommendation": "conditional-go",
    }
    result = score_agent_report(payload, latency_ms=1000)
    assert result["score"] >= 50
    assert result["fact_hits"] >= 5


def test_agent_score_with_tools_reaches_full_scale():
    """Full score should be possible with all 8 dimensions."""
    payload = {
        "executive_summary": "Use model discovery and base url checks with dynamic discovery.",
        "required_facts": [
            "model discovery",
            "base url",
            "search api",
            "langfuse",
            "tool calling",
            "json fallback",
            "retry",
            "rate limit",
            "benchmark matrix",
        ],
        "risk_categories": [
            "endpoint",
            "model availability",
            "streaming",
            "tool",
            "latency",
            "cost",
            "observability",
        ],
        "benchmark_matrix": [
            {"suite": "smoke", "purpose": "availability", "metrics": ["latency"]},
            {"suite": "agent_mini", "purpose": "quality", "metrics": ["score"]},
        ],
        "recommendation": "conditional-go",
        # ticket signals
        "analysis": "base url suffix and dynamic discovery noted from support tickets. tool call accuracy, latency variance, cost unknown, trace gateway routing, sequential approach, json validation tested.",
    }
    tool_results = [
        {"tool": "web_search", "result": {}},
        {"tool": "read_support_tickets", "result": {}},
    ]
    result = score_agent_report(
        payload, latency_ms=1000, json_valid=True, tool_results=tool_results
    )
    assert result["score"] >= 70
    assert result["tool_score"] == 15.0
    assert result["json_score"] == 15.0


def test_agent_score_max_100():
    """Verify score cannot exceed 100."""
    payload = {
        "executive_summary": "Use model discovery and base url checks.",
        "required_facts": [
            "model discovery",
            "base url",
            "search api",
            "langfuse",
            "tool calling",
            "json fallback",
            "retry",
            "rate limit",
            "benchmark matrix",
        ],
        "risk_categories": [
            "endpoint",
            "model availability",
            "streaming",
            "tool",
            "latency",
            "cost",
            "observability",
        ],
        "benchmark_matrix": [{"suite": "smoke", "purpose": "test", "metrics": ["latency"]}],
        "recommendation": "go",
    }
    result = score_agent_report(
        payload,
        latency_ms=100,
        json_valid=True,
        tool_results=[{"tool": "web_search"}, {"tool": "read_support_tickets"}],
    )
    assert result["score"] <= 100.0


def test_aggregate_results_empty():
    result = aggregate_results([])
    assert result["avg_score"] == 0.0
    assert result["error_rate"] == 1.0


def test_aggregate_results_mixed():
    results = [
        {"status": "passed", "score": 100.0, "latency_ms_total": 1000},
        {"status": "failed", "score": 40.0, "latency_ms_total": 2000},
        {"status": "error", "score": 0.0, "latency_ms_total": None},
    ]
    summary = aggregate_results(results)
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["errors"] == 1
    assert summary["avg_score"] == pytest.approx(46.67, abs=0.1)
