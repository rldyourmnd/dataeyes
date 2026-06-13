---
name: status
description: Текущее состояние реализации dataeyes-model-bench — что реализовано и проверено
metadata:
  type: project
---

# Current Status (2026-06-13)

Проект входит в монорепо `dataeyes`: сервис живёт в `model-bench/`, документы КП — в `dataeyes-docs/`.
Раньше код описывался как «skeleton»; на деле он значительно опережает старые заметки — ниже актуальная картина по факту из кода и зелёных проверок.

## Реализовано и проверено

| Компонент | Статус |
|---|---|
| `Settings` + `.env` loading (pydantic-settings) | ✅ |
| `Makefile` (init/up/migrate/dev/test/fmt/clean) | ✅ |
| `docker-compose` (postgres:16 + rustfs + litellm; отдельная БД `litellm`) | ✅ |
| Alembic `0001_initial` (4 таблицы) + `0002` (`schema_valid` → nullable) | ✅ |
| SQLAlchemy models (`BenchmarkRun`/`ModelResult`/`StepEvent`/`Artifact`) | ✅ |
| FastAPI: `/health` (реальные проверки DB/LiteLLM/S3), `/models/discover`, `/benchmarks/cases`, `/benchmarks/run`, `/runs/{id}`, `/runs/{id}/export` | ✅ |
| `DataEyesClient.list_models()` / `.search()` | ✅ |
| `LiteLLMGateway.complete()` — hard wall-clock timeout, Claude system-prompt workaround, `reasoning_content` fallback, thinking-модели | ✅ |
| `BenchmarkRunner.run()` — параллельно по моделям (`ThreadPoolExecutor`≤5), per-model изоляция ошибок | ✅ |
| `AgentMiniRunner` (plan → web_search → tickets → synthesis → write_report) | ✅ |
| `scoring.py` — 15+ детерминированных scorer'ов + `VENDOR_PRICING` (~35 моделей) + `aggregate_results` | ✅ |
| `ArtifactStore` (S3/RustFS + local fallback) | ✅ |
| `LangfuseRecorder` — реальные spans + scores (Langfuse v4 / OTel) | ✅ |
| `run_final_bench.py` — прямой прогон без HTTP-сервера | ✅ |
| `scripts/generate_*_report.py`, `restore_frontier_run.py` — отчёты по прогонам | ✅ |
| Тесты (27): integration (respx-моки) + scoring + json_schema | ✅ `pytest` 27 passed |
| Линт `ruff` (E/F/I/UP/B; ignore E501/B008) | ✅ clean + formatted |

## Suites (10)

`smoke` · `json_schema` · `tool_call`(→agent_mini) · `agent_mini` · `latency_repeated` · `standard` · `deep_eval` · `comprehensive` · `ultra_deep` · `fast`. Детали и пороги — `mem:benchmark-design`.

## Не реализовано / возможные доработки

- **LLM-as-judge** — `use_judge` в запросе и `JUDGE_MODEL` пока не задействованы.
- **Streaming / first_token latency** — не измеряется (`latency_ms_first_token` всегда `None`).
- **`configs/benchmark.defaults.json`** — присутствует, но не загружается в `Settings`/runner (значения зашиты в коде и промптах).
- **`/models/discover`** — без кеша, всегда живой discovery.
- **per_model_retries / backoff** — не реализованы.

## Запуск (из `model-bench/`)

```bash
make init && make up && make migrate && make dev
python run_final_bench.py   # прямой прогон, suite=fast
```

## Известные мелочи (не блокеры)

- `db.py` создаёт `engine` на импорте → реальный запуск требует валидный `DATABASE_URL` (тесты мокают зависимости).
- Незнакомая провайдеру модель → `cost_status="unknown_model"` (цены не выдумываются).
- Несколько pre-existing pyright-замечаний по сужению типов в `scoring.py` (pyright не входит в гейты).
