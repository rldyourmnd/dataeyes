# Implementation Tasks

## Milestone 1 — Project bootstrap

- [ ] Ensure `pyproject.toml` has all dependencies.
- [ ] Ensure package import path works: `python -c "import benchsvc"`.
- [ ] Add `.env` loading from repo root.
- [ ] Implement `Settings` with validation and redacted snapshot.
- [ ] Implement `make init`, `make up`, `make dev`, `make test`.

Acceptance:

```bash
python -m compileall src
pytest -q
```

## Milestone 2 — Docker infrastructure

- [ ] Make Postgres start on `localhost:5432`.
- [ ] Make RustFS start on `localhost:9000`.
- [ ] Make LiteLLM proxy start on `localhost:4000`.
- [ ] Confirm `.env` variables are passed to compose.
- [ ] Provide a generated LiteLLM config path.

Acceptance:

```bash
docker compose ps
curl http://localhost:4000/health || true
```

## Milestone 3 — Database

- [ ] Implement SQLAlchemy models.
- [ ] Implement initial Alembic migration.
- [ ] Implement DB session dependency.
- [ ] Implement create/update run helpers.

Acceptance:

```bash
make migrate
```

## Milestone 4 — DataEyes model discovery

- [ ] Implement `DataEyesClient.list_models()` using `httpx`.
- [ ] Normalize multiple response envelopes.
- [ ] Add timeout and useful errors.
- [ ] Add `/models/discover` endpoint.
- [ ] Store raw payload as artifact when called from benchmark run.

Acceptance:

```bash
curl http://localhost:8000/models/discover | jq
```

## Milestone 5 — LiteLLM config generation

- [ ] Implement `src/benchsvc/scripts/generate_litellm_config.py`.
- [ ] Generate aliases for discovered or allowlisted models.
- [ ] Add callback `langfuse_otel`.
- [ ] Add Makefile target.

Acceptance:

```bash
make litellm-config
cat generated/litellm.config.yaml
```

## Milestone 6 — LLM gateway

- [ ] Implement OpenAI-compatible client pointed at LiteLLM Proxy.
- [ ] Add direct DataEyes fallback for diagnostics.
- [ ] Capture latency, usage, raw response, error type.
- [ ] Support simple non-streaming first.
- [ ] Add streaming measurement if time allows.

Acceptance:

- One smoke call succeeds through LiteLLM.
- Failure returns structured error.

## Milestone 7 — Benchmark cases

- [ ] Implement `smoke`.
- [ ] Implement `json_schema`.
- [ ] Implement `tool_call` native or fallback.
- [ ] Implement `agent_mini`.
- [ ] Implement `standard` as smoke + json_schema + agent_mini.

Acceptance:

```bash
curl -X POST http://localhost:8000/benchmarks/run \
  -H 'Content-Type: application/json' \
  -d '{"suite":"smoke","models":"auto","limit_models":1}'
```

## Milestone 8 — Tools

- [ ] Implement `web_search()` using DataEyes Search API.
- [ ] Implement `read_support_tickets()`.
- [ ] Implement `write_report()` to artifact store.
- [ ] Validate tool args with Pydantic.

Acceptance:

- Agent mini uses web_search at least once.
- Tool errors are recorded but do not crash entire run.

## Milestone 9 — Scoring

- [ ] Implement JSON parse score.
- [ ] Implement JSON schema score.
- [ ] Implement golden fact score.
- [ ] Implement risk category score.
- [ ] Implement latency score.
- [ ] Implement optional LLM judge.

Acceptance:

```bash
pytest tests/test_scoring.py -q
```

## Milestone 10 — Langfuse

- [ ] Ensure LiteLLM callback sends traces.
- [ ] Add app-level run/case spans.
- [ ] Add scores to Langfuse.
- [ ] Flush SDK at run end.

Acceptance:

- Langfuse Cloud shows at least one trace for a smoke run.
- Scores appear with run metadata.

## Milestone 11 — Artifacts/export

- [ ] Implement S3-compatible upload with RustFS.
- [ ] Implement local fallback.
- [ ] Upload raw responses and summary reports.
- [ ] Implement `POST /runs/{run_id}/export`.

Acceptance:

- A run produces `summary.json` and `summary.md` artifact.

## Milestone 12 — Final hardening

- [ ] Mock tests for discovery and benchmark run.
- [ ] Helpful error messages.
- [ ] README exact commands.
- [ ] No secrets printed.
- [ ] Basic type hints.

Final acceptance:

```bash
make test
make dev
curl http://localhost:8000/health
```
