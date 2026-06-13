from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str
    object: str | None = None
    owned_by: str | None = None
    supported_endpoint_types: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class DiscoverModelsResponse(BaseModel):
    provider: str = "dataeyes"
    base_url: str
    count: int
    models: list[ModelInfo]
    error: dict[str, Any] | None = None


class BenchmarkRunRequest(BaseModel):
    suite: Literal[
        "smoke",
        "json_schema",
        "tool_call",
        "agent_mini",
        "latency_repeated",
        "standard",
        "deep_eval",
        "comprehensive",
        "ultra_deep",
        "fast",
    ] = "smoke"
    models: Literal["auto"] | list[str] = "auto"
    limit_models: int | None = None
    timeout_seconds: int | None = None
    use_judge: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseResult(BaseModel):
    model: str
    suite: str
    case_id: str
    status: Literal["passed", "failed", "error", "skipped"]
    score: float = 0.0
    latency_ms_total: int | None = None
    latency_ms_first_token: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    tokens_per_second: float | None = None
    estimated_cost_usd: float | None = None
    cost_status: str = "unknown"
    tool_call_count: int = 0
    tool_error_count: int = 0
    json_valid: bool = False
    schema_valid: bool | None = None
    error_type: str | None = None
    error_message: str | None = None
    raw_artifact_uri: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRunResponse(BaseModel):
    run_id: str
    status: Literal["completed", "partial", "failed", "running"]
    suite: str
    models_tested: int
    summary: dict[str, Any]
    results: list[CaseResult]
