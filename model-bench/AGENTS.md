# AGENTS.md — Codex CLI Instructions

> **Current state (2026-06-13):** the MVP is implemented and green — `pytest` 27 passed, `ruff` clean. The service lives in `model-bench/` inside the `dataeyes` monorepo. Implemented suites: `smoke`, `json_schema`, `tool_call`, `agent_mini`, `latency_repeated`, `standard`, `deep_eval`, `comprehensive`, `ultra_deep`, `fast`. Treat this file as the design contract when extending the service; the verified state lives in `memory/status.md`.

You are working on a service for benchmarking DataEyes-hosted LLM models through API.

## Objective

Build a minimal, working FastAPI service that benchmarks all available DataEyes models discovered from the user's API key. The service must trace all LLM calls and benchmark results in Langfuse, store run metadata in PostgreSQL, and store artifacts in RustFS/S3-compatible storage.

Avoid overengineering. No async queue. No Kubernetes. No UI. No elaborate LangChain stack. Build the smallest reliable system that can run today.

## Constraints

- Python 3.11+.
- FastAPI backend.
- PostgreSQL + Alembic migrations.
- RustFS S3-compatible storage.
- Langfuse Cloud first; self-host later via env.
- LiteLLM Proxy as default LLM gateway.
- Direct DataEyes fallback for `/v1/models`, `/v1/responses`, and diagnostics.
- `.env` is the only manual configuration surface.
- Benchmark scenario should be 5-10 agent steps.
- Must include tests and clear acceptance criteria.
- Must not hardcode model names as the canonical source of truth. Discover available models dynamically.

## Read First

1. `README.md`
2. `docs/01_ARCHITECTURE.md`
3. `docs/02_ONE_DAY_RUNBOOK.md`
4. `docs/03_BENCHMARK_DESIGN.md`
5. `docs/05_DATAEYES_INTEGRATION.md`
6. `docs/08_IMPLEMENTATION_TASKS.md`
7. `docs/09_ACCEPTANCE_CRITERIA.md`

## Implementation Order

1. Make `.env` loading robust in `src/benchsvc/settings.py`.
2. Make Docker Compose start Postgres, RustFS, and LiteLLM Proxy.
3. Implement DB models and Alembic migration.
4. Implement DataEyes model discovery.
5. Implement LiteLLM client with Langfuse tracing enabled.
6. Implement sync benchmark runner.
7. Implement deterministic agent mini-scenario.
8. Implement scoring: schema validity, golden checks, tool accuracy, latency, tokens, cost, error handling.
9. Add optional LLM-as-judge.
10. Write integration tests that can run without real API keys by mocking HTTP calls.
11. Update README with exact commands that worked.

## Required Endpoints

- `GET /health`
- `GET /models/discover`
- `GET /benchmarks/cases`
- `POST /benchmarks/run`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/export`

## Quality Bar

- The app must start with `uvicorn benchsvc.main:app --reload`.
- `pytest` must pass.
- API errors must be explicit and useful.
- Benchmark run must continue when one model fails.
- Every model result must include a stable error object if failed.
- Langfuse trace metadata must include provider, model, suite, run_id, case_id.

## Do Not Do

- Do not build a frontend.
- Do not add Celery, Redis, Temporal, or background workers.
- Do not make the benchmark depend on a fragile live website only; use live web search as a tool, but keep deterministic local checks.
- Do not assume DataEyes model names. Use discovery.
- Do not bury configuration in YAML except LiteLLM's generated/proxy config. User-editable config belongs in `.env`.
