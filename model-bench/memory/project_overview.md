---
name: project-overview
description: Миссия, tech stack, Makefile-команды и done-критерии проекта dataeyes-model-bench
metadata:
  type: project
---

# dataeyes-model-bench — Project Overview

**Расположение:** монорепо `dataeyes` → сервис в `model-bench/` (этот пакет), КП-документы в `dataeyes-docs/`.

**Миссия:** компактный benchmark-репо для тестирования DataEyes-hosted frontier моделей через API за один день. FastAPI-сервис, трассировки Langfuse, cost/latency статистика, базовый quality scoring. Реализовано 10 suites (от `smoke` до `ultra_deep`/`fast`), 15+ детерминированных scorer'ов, поддержка thinking-моделей. См. `mem:status`, `mem:benchmark-design`.

## Tech Stack

- Python 3.11+, FastAPI + uvicorn
- PostgreSQL 16 + SQLAlchemy 2 + Alembic (migrations)
- RustFS (S3-compatible artifact storage) — docker image `rustfs/rustfs:latest`
- LiteLLM Proxy (`ghcr.io/berriai/litellm:main-latest`) — OpenAI-compatible gateway
- DataEyes API: OpenAI-compatible endpoints + `/v1/models` discovery
- Langfuse Cloud (трассировки через LiteLLM callback `langfuse_otel` + app-level SDK)
- httpx (direct DataEyes calls), openai SDK (LiteLLM Proxy calls), boto3 (S3/RustFS)
- pydantic-settings для Settings, jsonschema для валидации
- pytest + respx + ruff

## Makefile команды

```bash
make init          # venv + pip install -e ".[dev]"
make litellm-config  # генерирует generated/litellm.config.yaml
make up            # docker compose up -d (postgres + rustfs + litellm)
make down
make restart-litellm
make migrate       # alembic upgrade head
make dev           # uvicorn benchsvc.main:app --reload :8000
make test          # pytest -q
make fmt           # ruff check + format
make clean
```

## Done-критерии (MVP)

- `make up` поднимает infra
- `make migrate` создаёт таблицы
- `make dev` стартует FastAPI
- `curl /models/discover` → список моделей по реальному ключу
- `curl /benchmarks/run` → smoke suite на ≥1 модели
- Langfuse содержит traces и scores
- `pytest` зелёный
- README документирует команды

**Why:** задача «за один день». LangGraph не добавлять до зелёного MVP.
