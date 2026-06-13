# One-Day Runbook

## Phase 0 — Keys and environment

Copy env:

```bash
cp configs/.env.example .env
```

Required values:

```bash
DATAEYES_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Optional values:

```bash
DATAEYES_SEARCH_API_KEY=... # if separate from DATAEYES_API_KEY
JUDGE_MODEL=...             # if you want LLM-as-judge
BENCHMARK_MODEL_ALLOWLIST=  # comma-separated override if discovery returns too many models
```

## Phase 1 — Infrastructure

```bash
make init
make up
```

Expected services:

- Postgres: `localhost:5432`
- RustFS S3 API/console: `localhost:9000`
- LiteLLM Proxy: `localhost:4000`

## Phase 2 — DB migration

```bash
make migrate
```

Expected result: Alembic creates initial tables.

## Phase 3 — FastAPI

```bash
make dev
```

Health check:

```bash
curl http://localhost:8000/health
```

## Phase 4 — Model discovery

```bash
curl http://localhost:8000/models/discover | jq
```

Expected:

- list of available models; or
- explicit auth/base-url error.

If discovery fails:

1. Confirm `DATAEYES_API_KEY`.
2. Confirm `DATAEYES_LLM_BASE_URL=https://cloud.dataeyes.ai/v1`.
3. Try backup base URL with `/v1` suffix.
4. Confirm provider account balance/entitlements.

## Phase 5 — LiteLLM Proxy config

Generate or refresh proxy config from env/discovery:

```bash
make litellm-config
make restart-litellm
```

Then test proxy:

```bash
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

## Phase 6 — Smoke benchmark

Run on three discovered models first:

```bash
curl -X POST http://localhost:8000/benchmarks/run \
  -H 'Content-Type: application/json' \
  -d '{"suite":"smoke","models":"auto","limit_models":3}' | jq
```

Check:

- FastAPI response.
- DB rows.
- Langfuse traces.
- RustFS artifacts.

## Phase 7 — Agent mini benchmark

```bash
curl -X POST http://localhost:8000/benchmarks/run \
  -H 'Content-Type: application/json' \
  -d '{"suite":"agent_mini","models":"auto","limit_models":5}' | jq
```

## Phase 8 — Full available-model run

Only after smoke passes:

```bash
curl -X POST http://localhost:8000/benchmarks/run \
  -H 'Content-Type: application/json' \
  -d '{"suite":"standard","models":"auto","limit_models":null}' | jq
```

## Phase 9 — Export

```bash
curl -X POST http://localhost:8000/runs/<RUN_ID>/export | jq
```

Expected artifact:

```text
runs/<RUN_ID>/summary.json
runs/<RUN_ID>/summary.md
runs/<RUN_ID>/raw/*.json
```

## Troubleshooting checklist

### No Langfuse traces

- Check `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.
- Confirm LiteLLM config has `callbacks: ["langfuse_otel"]`.
- Confirm LLM calls are actually routed through LiteLLM proxy.
- Flush Langfuse SDK at the end of sync runs.

### LiteLLM 404 or model not found

- Confirm model mapping uses `openai/<actual-dataeyes-model-id>`.
- Confirm `api_base` ends with `/v1`.
- Confirm discovered model supports the endpoint type used.

### Cost is empty

This is acceptable on day 1. Store tokens and `cost_status="unknown"`. Add custom pricing later.

### Web search fails

- Confirm `DATAEYES_SEARCH_BASE_URL=https://api.dataeyes.ai`.
- Confirm search key if separate.
- Agent benchmark should degrade gracefully and still run deterministic local-data checks.
