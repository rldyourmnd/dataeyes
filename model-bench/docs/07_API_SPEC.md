# API Spec

## `GET /health`

Response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok|error|unknown",
  "artifact_storage": "ok|error|unknown",
  "litellm_proxy": "ok|error|unknown"
}
```

## `GET /models/discover`

Query params:

- `refresh`: boolean, default true.
- `include_raw`: boolean, default false.

Response:

```json
{
  "provider": "dataeyes",
  "base_url": "https://cloud.dataeyes.ai/v1",
  "count": 0,
  "models": [
    {
      "id": "string",
      "supported_endpoint_types": ["chat_completions", "responses"],
      "owned_by": "string|null"
    }
  ],
  "error": null
}
```

## `GET /benchmarks/cases`

Response:

```json
{
  "suites": ["smoke", "json_schema", "tool_call", "agent_mini", "latency_repeated", "standard"],
  "cases": [
    {"case_id":"smoke_json_exact","suite":"smoke","description":"..."}
  ]
}
```

## `POST /benchmarks/run`

Request:

```json
{
  "suite": "smoke",
  "models": "auto",
  "limit_models": 3,
  "timeout_seconds": 120,
  "use_judge": false,
  "metadata": {}
}
```

`models` may be:

```json
"auto"
```

or:

```json
["dataeyes/gpt-5.1", "dataeyes/deepseek-v3.2"]
```

Response:

```json
{
  "run_id": "uuid",
  "status": "completed|partial|failed",
  "suite": "smoke",
  "models_tested": 3,
  "summary": {
    "passed": 2,
    "failed": 1,
    "error_rate": 0.333,
    "avg_score": 74.5,
    "p50_latency_ms_total": 1234,
    "p95_latency_ms_total": 2400,
    "total_estimated_cost_usd": null,
    "cost_status": "unknown"
  },
  "results": [
    {
      "model": "string",
      "case_id": "string",
      "status": "passed",
      "score": 96.0,
      "latency_ms_total": 1234,
      "error_type": null
    }
  ]
}
```

## `GET /runs/{run_id}`

Response: full normalized run summary from PostgreSQL.

## `POST /runs/{run_id}/export`

Response:

```json
{
  "run_id": "uuid",
  "artifacts": [
    {"kind":"summary_json","uri":"s3://benchmark-artifacts/runs/.../summary.json"},
    {"kind":"summary_md","uri":"s3://benchmark-artifacts/runs/.../summary.md"}
  ]
}
```

## HTTP semantics

- A model failure should not fail the entire run unless every model fails before any result is recorded.
- Endpoint-level failure returns `500` with structured error.
- Per-model errors return `200` run response with `status="partial"`.
