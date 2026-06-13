---
name: config-env
description: Обязательные и опциональные .env переменные, Settings класс, поверхность конфигурации
metadata:
  type: project
---

# Config & Env Surface

## Обязательные (без них не работает)

```bash
DATAEYES_API_KEY=...           # Bearer токен для DataEyes API
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Ключевые опциональные

```bash
DATAEYES_LLM_BASE_URL=https://cloud.dataeyes.ai/v1     # default
DATAEYES_LLM_BASE_URL_BACKUP_CN=https://cloud-cn.dataeyes.ai/v1
DATAEYES_LLM_BASE_URL_BACKUP_HK=https://cloud-hk.dataeyes.ai/v1
DATAEYES_SEARCH_BASE_URL=https://api.dataeyes.ai        # default
DATAEYES_SEARCH_API_KEY=       # если не задан — использует DATAEYES_API_KEY
DATAEYES_DEFAULT_MODEL=        # fallback для generate_litellm_config без discovery

BENCHMARK_MODEL_ALLOWLIST=     # comma-separated, фильтр моделей
MAX_MODELS_PER_RUN=50          # default
JUDGE_MODEL=                   # зарезервировано под LLM-judge (пока не задействован)
THINKING_MODELS=claude,deepseek,kimi,qwq   # substrings (case-insensitive) для extended thinking
THINKING_BUDGET_TOKENS=0       # бюджет thinking-токенов; 0 = thinking выключен

LITELLM_BASE_URL=http://localhost:4000/v1   # default
LITELLM_MASTER_KEY=sk-local-litellm-change-me
LANGFUSE_OTEL_HOST=https://cloud.langfuse.com/api/public/otel

DATABASE_URL=postgresql+psycopg://benchmark:benchmark@localhost:5432/benchmark
ARTIFACT_STORAGE_MODE=s3       # или "local"
RUSTFS_ENDPOINT_URL=http://localhost:9000
RUSTFS_ACCESS_KEY=rustfsadmin
RUSTFS_SECRET_KEY=rustfsadmin
RUSTFS_BUCKET=benchmark-artifacts

REQUEST_TIMEOUT_SECONDS=90
APP_HOST=0.0.0.0
APP_PORT=8000
BENCHMARK_VERSION=2026-06-09.1
```

## Settings класс (src/benchsvc/settings.py)

- `BaseSettings` + pydantic-settings, читает из `.env` в корне репо
- `get_settings()` — `@lru_cache`, используется везде через DI
- `settings.redacted_snapshot()` — маскирует key/secret/password
- `settings.allowlist` — property → `list[str]` из BENCHMARK_MODEL_ALLOWLIST
- `settings.search_api_key` — property, fallback на dataeyes_api_key
- `settings.repo_root` — `Path(__file__).parents[2]` (корень репо)

## Важные конвенции

- `.env` — **единственная** поверхность ручной конфигурации
- Никаких hardcode API ключей в коде
- `DATAEYES_LLM_BASE_URL` должен заканчиваться на `/v1` (validator `ensure_no_trailing_slash` убирает лишний слэш)
- LiteLLM config генерируется в `generated/litellm.config.yaml` (gitignored)
- `configs/.env.example` — шаблон, `cp configs/.env.example .env`
