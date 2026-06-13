# CLAUDE.md — Claude Code Instructions

> **Current state (2026-06-13):** MVP implemented and green — `pytest` 27 passed, `ruff` clean; every "Done means" item below is satisfied at code level (live infra still needs your `.env` keys + `make up`). The service lives in `model-bench/` inside the `dataeyes` monorepo; commercial docs live in `dataeyes-docs/`. Suites now span `smoke` … `ultra_deep`/`fast`. Verified state: `memory/status.md`. Keep the Mission and Non-negotiables below as the design contract.

## Mission

Implement a compact benchmark repo for testing DataEyes-hosted frontier models via API. Optimize for a same-day working setup with Langfuse traces, cost/latency stats, and basic quality scoring.

## Non-negotiables

- FastAPI service.
- PostgreSQL + Alembic.
- RustFS/S3-compatible artifact storage.
- Langfuse Cloud instrumentation.
- LiteLLM Proxy gateway plus direct DataEyes fallback.
- `.env` as the main config surface.
- Synchronous benchmark execution; no worker queue.
- Dynamic model discovery via DataEyes `/v1/models`.
- Agent benchmark with 5-10 deterministic steps.

## Recommended implementation style

Use plain Python orchestration first. Keep state as a typed dataclass/Pydantic model so a LangGraph runner can be added later, but do not introduce LangGraph unless the MVP is already green.

Prefer clear functions over framework magic:

- `discover_models()`
- `run_case_for_model()`
- `run_suite()`
- `score_result()`
- `record_langfuse_score()`
- `persist_run()`
- `upload_artifact()`

## Done means

- `make up` starts infrastructure.
- `make migrate` creates tables.
- `make dev` starts FastAPI.
- `curl /models/discover` works with real key.
- `curl /benchmarks/run` executes smoke suite on at least one model.
- Langfuse contains traces and scores.
- `pytest` passes.
- README documents the exact commands.
