# dataeyes

Монорепозиторий для бенчмаркинга frontier-LLM, доступных через **DataEyes** OpenAI-compatible API, и сопутствующих документов.

[![CI](https://github.com/rldyourmnd/dataeyes/actions/workflows/ci.yml/badge.svg)](https://github.com/rldyourmnd/dataeyes/actions/workflows/ci.yml)
[![CodeQL](https://github.com/rldyourmnd/dataeyes/actions/workflows/codeql.yml/badge.svg)](https://github.com/rldyourmnd/dataeyes/actions/workflows/codeql.yml)
[![gitleaks](https://github.com/rldyourmnd/dataeyes/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/rldyourmnd/dataeyes/actions/workflows/gitleaks.yml)

## Структура

| Каталог | Назначение |
|---|---|
| [`model-bench/`](model-bench/) | FastAPI-сервис бенчмарка: discovery моделей, 10 suites, детерминированный scoring, Langfuse-трассировка, PostgreSQL + RustFS. |
| [`dataeyes-docs/`](dataeyes-docs/) | Коммерческое предложение (КП) и документы по DataEyes. |

## Быстрый старт

```bash
cd model-bench
cp configs/.env.example .env     # заполнить DATAEYES_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
make init && make up && make migrate && make dev
```

Подробности — в [`model-bench/README.md`](model-bench/README.md).

## CI/CD (бесплатно для публичного репо)

- **CI** — `ruff check` + `ruff format --check` + `pytest` на Python 3.11/3.12.
- **CodeQL** — статический анализ безопасности (Python).
- **gitleaks** — поиск секретов в коммитах и истории.
- **Dependabot** — еженедельные обновления pip- и GitHub-Actions-зависимостей.

Workflows — в [`.github/`](.github/). Секреты (`.env`) не коммитятся (см. `.gitignore`).

## Лицензия

Лицензия не задана. Для публичного проекта рекомендуется добавить `LICENSE` (например MIT/Apache-2.0) по вашему выбору.
