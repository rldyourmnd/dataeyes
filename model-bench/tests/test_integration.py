"""Integration tests using mocked HTTP (respx) — no real API keys required."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
import respx

from benchsvc.llm_client import (
    DataEyesClient,
    LLMCallResult,
    classify_exception,
    normalize_search_payload,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_settings(**overrides):
    s = MagicMock()
    s.dataeyes_api_key = overrides.get("dataeyes_api_key", "test-key")
    s.dataeyes_llm_base_url = overrides.get("dataeyes_llm_base_url", "https://cloud.dataeyes.ai/v1")
    s.dataeyes_search_base_url = overrides.get(
        "dataeyes_search_base_url", "https://api.dataeyes.ai"
    )
    s.search_api_key = overrides.get("search_api_key", "test-key")
    s.request_timeout_seconds = 10
    s.litellm_master_key = overrides.get("litellm_master_key", "sk-test")
    s.litellm_base_url = overrides.get("litellm_base_url", "http://localhost:4000/v1")
    return s


# ---------------------------------------------------------------------------
# DataEyes model discovery
# ---------------------------------------------------------------------------


@respx.mock
def test_list_models_openai_envelope():
    settings = _mock_settings()
    respx.get("https://cloud.dataeyes.ai/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "id": "deepseek-v3-250324",
                        "object": "model",
                        "owned_by": "custom",
                        "supported_endpoint_types": ["openai"],
                    },
                    {
                        "id": "kimi-k2.5",
                        "object": "model",
                        "owned_by": "custom",
                        "supported_endpoint_types": ["openai"],
                    },
                ],
            },
        )
    )
    client = DataEyesClient(settings)
    models = client.list_models()
    assert len(models) == 2
    assert models[0].id == "deepseek-v3-250324"
    assert models[1].id == "kimi-k2.5"


@respx.mock
def test_list_models_dataeyes_envelope():
    """DataEyes sometimes returns {"data": [...]} without "object": "list"."""
    settings = _mock_settings()
    respx.get("https://cloud.dataeyes.ai/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "glm-5-turbo", "object": "model", "owned_by": "custom"},
                ]
            },
        )
    )
    client = DataEyesClient(settings)
    models = client.list_models()
    assert len(models) == 1
    assert models[0].id == "glm-5-turbo"


@respx.mock
def test_list_models_no_api_key_raises():
    settings = _mock_settings(dataeyes_api_key="")
    client = DataEyesClient(settings)
    with pytest.raises(RuntimeError, match="DATAEYES_API_KEY"):
        client.list_models()


@respx.mock
def test_list_models_401_raises():
    settings = _mock_settings()
    respx.get("https://cloud.dataeyes.ai/v1/models").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    client = DataEyesClient(settings)
    with pytest.raises(httpx.HTTPStatusError):
        client.list_models()


# ---------------------------------------------------------------------------
# Search normalization
# ---------------------------------------------------------------------------


def test_normalize_search_openai_webpages():
    payload = {
        "webPages": {
            "value": [
                {
                    "name": "Title",
                    "url": "https://example.com",
                    "snippet": "Info",
                    "datePublished": "2026-01-01",
                },
            ]
        }
    }
    result = normalize_search_payload("test query", payload, limit=5)
    assert result["query"] == "test query"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Title"
    assert result["results"][0]["url"] == "https://example.com"


def test_normalize_search_results_list():
    payload = {
        "results": [
            {"title": "A", "url": "https://a.com", "snippet": "aaa"},
            {"title": "B", "url": "https://b.com", "snippet": "bbb"},
        ]
    }
    result = normalize_search_payload("q", payload, limit=2)
    assert len(result["results"]) == 2
    assert result["results"][1]["title"] == "B"


def test_normalize_search_limit():
    payload = {
        "results": [
            {"title": str(i), "url": f"https://x.com/{i}", "snippet": "s"} for i in range(10)
        ]
    }
    result = normalize_search_payload("q", payload, limit=3)
    assert len(result["results"]) == 3


# ---------------------------------------------------------------------------
# Exception classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("401 Unauthorized - Invalid API Key", "auth_error"),
        ("invalid api key provided", "auth_error"),
        ("429 Too Many Requests - rate limit exceeded", "rate_limit"),
        ("timeout waiting for response", "timeout"),
        ("404 not found: model not available", "model_not_found"),
        ("unexpected json decode error in response", "bad_gateway_response"),
        ("some completely unknown problem", "unknown"),
    ],
)
def test_classify_exception(message, expected):
    assert classify_exception(Exception(message)) == expected


def test_classify_timeout_type():
    assert classify_exception(TimeoutError("timed out")) == "timeout"


# ---------------------------------------------------------------------------
# LLMCallResult shape
# ---------------------------------------------------------------------------


def test_llm_call_result_defaults():
    result = LLMCallResult(text="hello", raw={}, latency_ms_total=100)
    assert result.error_type is None
    assert result.error_message is None
    assert result.input_tokens is None
    assert result.extra == {}


# ---------------------------------------------------------------------------
# BenchmarkRunner smoke — fully mocked
# ---------------------------------------------------------------------------


def test_benchmark_runner_smoke_mocked(tmp_path):
    """Run BenchmarkRunner.run() with fully mocked dependencies — no DB or API needed."""
    from unittest.mock import MagicMock, patch

    from benchsvc.benchmarks import BenchmarkRunner
    from benchsvc.schemas import BenchmarkRunRequest

    settings = _mock_settings()
    settings.benchmark_version = "test"
    settings.allowlist = []
    settings.max_models_per_run = 10
    settings.artifact_storage_mode = "local"
    settings.local_artifact_dir = str(tmp_path)
    settings.repo_root = tmp_path
    settings.redacted_snapshot.return_value = {}
    settings.langfuse_public_key = ""
    settings.langfuse_secret_key = ""

    # Minimal schema file for json_schema case
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    import json

    (schema_dir / "benchmark_result.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "additionalProperties": True})
    )

    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    fake_run = MagicMock()
    fake_run.id = "test-run-id"

    def fake_add(obj):
        if hasattr(obj, "suite"):
            obj.id = "test-run-id"

    db.add.side_effect = fake_add
    db.refresh.side_effect = lambda obj: setattr(obj, "id", "test-run-id")

    good_llm = LLMCallResult(
        text='{"status":"ok","provider_test":"dataeyes","answer":42}',
        raw={"choices": []},
        latency_ms_total=500,
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
    )

    with (
        patch("benchsvc.benchmarks.DataEyesClient") as MockDE,
        patch("benchsvc.benchmarks.LiteLLMGateway") as MockGW,
        patch("benchsvc.benchmarks.ArtifactStore") as MockStore,
        patch("benchsvc.benchmarks.LangfuseRecorder") as MockLF,
    ):
        MockDE.return_value.list_models.return_value = [MagicMock(id="test-model")]
        MockGW.return_value.complete.return_value = good_llm
        MockStore.return_value.put_json.return_value = "file://test"
        MockStore.return_value.put_text.return_value = "file://test"
        MockLF.return_value.start_run_trace.return_value = "test-run-id"

        runner = BenchmarkRunner(settings, db)
        request = BenchmarkRunRequest(suite="smoke", models="auto", limit_models=1)
        response = runner.run(request)

    assert response.suite == "smoke"
    assert response.models_tested == 1
    assert len(response.results) == 1
    result = response.results[0]
    assert result.model == "dataeyes/test-model"
    assert result.score == 100.0
    assert result.json_valid is True
