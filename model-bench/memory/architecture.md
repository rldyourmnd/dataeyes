---
name: architecture
description: Компоненты, файловая структура, ключевые классы и интерфейсы benchsvc
metadata:
  type: project
---

# Architecture & Modules

Монорепо `dataeyes`: сервис в `model-bench/` (этот пакет), КП-документы в `dataeyes-docs/`.

## Компоненты системы

```
Client / curl / run_final_bench.py
    |
FastAPI benchsvc (model-bench/src/benchsvc/)
  |-- BenchmarkRunner       → run() → per-model (ThreadPoolExecutor≤5) → per-case
  |-- DataEyesClient        → list_models(), search()
  |-- LiteLLMGateway        → complete()  (hard timeout, Claude workaround, thinking)
  |-- AgentMiniRunner       → plan→web_search→tickets→synthesis→write_report
  |-- scoring.py            → 15+ scorer'ов + VENDOR_PRICING + aggregate_results
  |-- ArtifactStore         → S3/RustFS + local fallback
  |-- LangfuseRecorder      → реальные spans/scores (Langfuse v4 / OTel)
  |-- Settings              → pydantic-settings из .env
  |
  --> PostgreSQL (4 таблицы; LiteLLM держит отдельную БД `litellm`)
  --> RustFS s3://benchmark-artifacts/
  --> Langfuse Cloud (app-level SDK + LiteLLM callback langfuse_otel)
  --> LiteLLM Proxy :4000 --> DataEyes API (direct fallback для discovery/search)
```

## Файловая структура src/benchsvc/

| Файл | Ключевые классы/функции |
|---|---|
| `main.py` | FastAPI `app`; `health`, `discover_models`, `benchmark_cases`, `run_benchmark`, `get_run`, `export_run`, `render_markdown_summary` |
| `settings.py` | `Settings(BaseSettings)`, `get_settings()` (lru_cache), `redacted_snapshot()`, `is_thinking_model()`, `repo_root` |
| `models.py` | SQLAlchemy: `BenchmarkRun`, `ModelResult`, `StepEvent`, `Artifact` |
| `schemas.py` | Pydantic: `ModelInfo`, `DiscoverModelsResponse`, `BenchmarkRunRequest`, `CaseResult`, `BenchmarkRunResponse` |
| `db.py` | `engine` (на импорте), `SessionLocal`, `get_db()` |
| `llm_client.py` | `DataEyesClient`, `LiteLLMGateway`, `LLMCallResult`, `normalize_search_payload()`, `classify_exception()` |
| `benchmarks.py` | `BenchmarkRunner` (`run`, `_select_models`, `_suite_cases`, `_run_case` + ~19 `_run_*`), `safe_name()` |
| `agent.py` | `AgentMiniRunner.run()`, `AgentState` (Pydantic) |
| `scoring.py` | `extract_json`, `validate_schema`, `estimate_cost_usd`, `score_*` (smoke/agent/reasoning/code/instruction/long_context/ultra_*/fast_*), `aggregate_results` |
| `tools.py` | `BenchmarkTools`: `web_search()`, `read_support_tickets()`, `write_report()` |
| `storage.py` | `ArtifactStore`: `put_json/text/bytes()`, S3 + local fallback |
| `langfuse_tracing.py` | `LangfuseRecorder`: `start_run_trace`/`record_case_score`/`record_run_summary`/`flush` (v4 OTel) |
| `fixtures/buggy_service.py`, `fixtures/long_doc.py` | данные для `ultra_code_review` и `ultra_long_context` |
| `scripts/generate_litellm_config.py` | `main()` → `generated/litellm.config.yaml` |

Вне пакета: `run_final_bench.py` (прямой прогон), `scripts/generate_*_report.py` + `restore_frontier_run.py` (отчёты).

## DB таблицы

- `benchmark_runs` — UUID pk, suite, status, requested_models/config_snapshot/summary (JSONB, redacted)
- `model_results` — FK→run, model, suite, case_id, score (float), latency, tokens, tokens_per_second, estimated_cost_usd (Numeric 18,8), cost_status, json_valid, schema_valid (nullable), tool_call/error_count, error_*, raw_artifact_uri, extra
- `step_events` — FK→run/result, step_index, step_name, input/output/error (JSONB)
- `artifacts` — FK→run/result, kind, uri (s3:// или file://), content_type, size_bytes

## Alembic

- `0001_initial` — все 4 таблицы
- `0002_nullable_schema_valid` — `model_results.schema_valid` → nullable, server_default снят
- `alembic/env.py` берёт `database_url` из `Settings`

## Ключевые конвенции

- **Model prefix:** модели идут как `dataeyes/<model_id>` в LiteLLM Proxy; mapping → `openai/<model_id>` + `api_base=DATAEYES_LLM_BASE_URL`.
- **Secrets redaction:** `Settings.redacted_snapshot()` маскирует поля с `key`/`secret`/`password`.
- **S3 fallback:** при ошибке S3 `ArtifactStore` пишет в `./artifacts/` (бенчмарк не падает).
- **Resilience:** падение одной модели не валит прогон; жёсткий wall-clock timeout на каждый LLM-вызов; `reasoning_content` fallback для thinking-моделей с пустым `content`.
- **Cost:** `cost_status` ∈ ok/unknown_model/no_tokens — цены не выдумываются.

## Docker compose сервисы

- `postgres:16` — :5432, healthcheck pg_isready, init-multiple-dbs создаёт БД `litellm`
- `rustfs/rustfs:latest` — :9000 (S3 API)
- `ghcr.io/berriai/litellm:main-latest` — :4000, depends postgres healthy, монтирует `generated/litellm.config.yaml`
