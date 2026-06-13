# Prompt for Codex CLI

Implement this repository into a working same-day MVP.

Read `AGENTS.md`, then implement tasks in `docs/08_IMPLEMENTATION_TASKS.md`. Use the architecture in `docs/01_ARCHITECTURE.md` and benchmark spec in `docs/03_BENCHMARK_DESIGN.md`.

Critical requirements:

- Use `.env` as the only user-edited configuration file.
- Keep benchmark execution synchronous.
- Discover models dynamically from DataEyes `GET /v1/models`.
- Route LLM calls through LiteLLM Proxy by default.
- Keep direct DataEyes fallback for discovery and diagnostics.
- Instrument LiteLLM and app-level events in Langfuse.
- Persist runs/results in PostgreSQL using Alembic.
- Store reports/raw responses in RustFS/S3.
- Include deterministic scoring and optional LLM-as-judge.
- Make tests pass without real API keys by mocking external calls.

Start by running:

```bash
python --version
ls -la
find . -maxdepth 3 -type f | sort
```

Then implement incrementally. After each major step run:

```bash
pytest -q
python -m compileall src
```

End by updating `README.md` with exact commands and any known limitations.
