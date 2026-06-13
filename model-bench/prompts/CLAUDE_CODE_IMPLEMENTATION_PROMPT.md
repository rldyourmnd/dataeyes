# Prompt for Claude Code

You are implementing a compact benchmark service for testing DataEyes-hosted LLM models.

Read:

1. `CLAUDE.md`
2. `README.md`
3. `docs/01_ARCHITECTURE.md`
4. `docs/02_ONE_DAY_RUNBOOK.md`
5. `docs/03_BENCHMARK_DESIGN.md`
6. `docs/08_IMPLEMENTATION_TASKS.md`
7. `docs/09_ACCEPTANCE_CRITERIA.md`

Implement the MVP, preserving the no-overengineering constraint.

Primary output:

- Working FastAPI service.
- Dynamic model discovery.
- LiteLLM Proxy gateway.
- Langfuse traces and scores.
- PostgreSQL persistence.
- RustFS artifact storage.
- Smoke/JSON/agent mini benchmark suites.
- Mocked tests.

Do not add a frontend, queue, task scheduler, or complex framework unless every MVP task is already complete.
