# DataEyes Model Benchmark (`model-bench`)

Рабочий FastAPI-сервис для бенчмаркинга frontier-моделей, доступных через **DataEyes** OpenAI-compatible API: качество, latency, throughput, JSON-validity, tool calling, стоимость и трассировка в **Langfuse**.

> Это пакет `model-bench/` внутри монорепо [`dataeyes`](../README.md). Коммерческие документы — в [`dataeyes-docs/`](../dataeyes-docs/).

Статус: MVP реализован и зелёный (`pytest` 27 passed, `ruff` clean). Актуальная картина — `memory/status.md`.

## Архитектура

```text
Client / curl / run_final_bench.py
        |
FastAPI benchsvc (src/benchsvc/)
  |-- BenchmarkRunner — синхронный, параллельно по моделям (ThreadPoolExecutor ≤5), без очереди
  |-- DataEyes discovery: GET /v1/models (динамически, без хардкода моделей)
  |-- LiteLLM Proxy — единый OpenAI-compatible вход; direct DataEyes fallback для discovery/search
  |-- AgentMiniRunner — детерминированный агент: plan → web_search → tickets → synthesis → report
  |-- scoring.py — 15+ детерминированных scorer'ов + оценка стоимости
  |-- Langfuse — app-level spans/scores (v4/OTel) + LiteLLM callback langfuse_otel
  |
  |--> PostgreSQL + Alembic: benchmark_runs, model_results, step_events, artifacts
  |--> RustFS (S3-compatible): raw responses, reports, exports (fallback в ./artifacts/)
  |--> Langfuse Cloud: traces, latency, tokens, cost, scores
```

## Suites

| Suite | Что проверяет |
|---|---|
| `smoke` | Точный JSON + latency |
| `json_schema` | Structured output против JSON Schema |
| `tool_call` | Tool calling (→ agent_mini runner) |
| `agent_mini` | 5-шаговый агент vendor-readiness |
| `latency_repeated` | p50/p95 latency (smoke ×3) |
| `standard` | smoke + json_schema + agent_mini |
| `deep_eval` | reasoning, code-gen, strict-instructions, long-context QA |
| `comprehensive` | smoke + json_schema + 4 кейса deep_eval |
| `ultra_deep` | длинные задачи: reasoning×15, async queue, security-аудит, структуры данных, long-context, system design |
| `fast` | компактные reasoning/code/algorithms/system-design (max_tokens=5000) |

Детали и пороги прохождения — `memory/benchmark_design.md`.

## API

- `GET /health` — реальные проверки DB / LiteLLM / artifact storage
- `GET /models/discover` — динамический список моделей по ключу (или понятная ошибка)
- `GET /benchmarks/cases` — описания suites/кейсов
- `POST /benchmarks/run` — запуск прогона
- `GET /runs/{run_id}` — результаты прогона
- `POST /runs/{run_id}/export` — экспорт summary (JSON + Markdown) в artifact storage

## Быстрый старт

```bash
cd model-bench
cp configs/.env.example .env     # заполнить DATAEYES_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
make init                        # venv + pip install -e ".[dev]"
make up                          # docker compose: postgres + rustfs + litellm
make migrate                     # alembic upgrade head
make dev                         # uvicorn benchsvc.main:app --reload :8000
```

Проверка discovery и прогон:

```bash
curl http://localhost:8000/models/discover

curl -X POST http://localhost:8000/benchmarks/run \
  -H 'Content-Type: application/json' \
  -d '{"suite":"smoke","models":"auto","limit_models":3}'
```

Прямой прогон без HTTP-сервера (suite `fast`):

```bash
python run_final_bench.py
```

## Конфигурация

`.env` — **единственная** поверхность ручной конфигурации (шаблон: `configs/.env.example`). Минимум: `DATAEYES_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. Полный список — `memory/config_env.md`. Список моделей **не захардкожен**: сервис делает discovery через `/v1/models` и тестирует модели, доступные вашему ключу.

## Качество

```bash
make test    # pytest -q  (27 тестов; integration на respx-моках — без реальных ключей)
make fmt     # ruff check --fix + ruff format
```

CI (GitHub Actions): тесты + ruff на Python 3.11/3.12, CodeQL, gitleaks, Dependabot — см. `../.github/`.

## Архитектурные решения

- **Pure Python orchestrator**, не LangGraph по умолчанию (сценарий 5–10 шагов, синхронный API, точные latency/cost/scoring).
- **LiteLLM Proxy** как основной gateway (единый OpenAI-compatible вход + Langfuse callbacks + быстрая замена провайдеров).
- **Direct DataEyes fallback** для discovery `/v1/models` и search.
- **PostgreSQL + Alembic** только для metadata/results; **RustFS** только для артефактов; **Langfuse Cloud** для трассировки (self-host позже через env).

Дополнительно: `docs/` (архитектура, runbook, benchmark design, интеграции, acceptance criteria), `prompts/` (исходные промпты).
