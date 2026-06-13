# Acceptance Criteria

## Functional

- [ ] FastAPI starts locally.
- [ ] Postgres starts locally.
- [ ] RustFS starts locally.
- [ ] LiteLLM Proxy starts locally.
- [ ] `/health` returns `status=ok` or clear dependency states.
- [ ] `/models/discover` calls DataEyes and normalizes models.
- [ ] `/benchmarks/cases` returns suite metadata.
- [ ] `/benchmarks/run` executes synchronously and returns result summary.
- [ ] Per-model failure does not stop the whole run.
- [ ] `/runs/{run_id}` returns persisted run data.
- [ ] `/runs/{run_id}/export` writes artifacts.

## Observability

- [ ] Langfuse shows LLM call traces.
- [ ] Langfuse metadata includes run_id, suite, case_id, model.
- [ ] Langfuse has deterministic score for each result.
- [ ] Token usage is captured when provider returns it.
- [ ] Cost is captured or explicitly marked unknown.

## Benchmark quality

- [ ] Smoke suite checks exact JSON.
- [ ] JSON schema suite validates against schema.
- [ ] Tool-call suite tests native or fallback tool call behavior.
- [ ] Agent mini suite performs 5-10 steps.
- [ ] Agent mini uses live web search.
- [ ] Agent mini analyzes local support tickets.
- [ ] Agent mini produces structured report.
- [ ] Deterministic scoring covers required facts/risk categories.
- [ ] LLM-as-judge is optional and clearly marked.

## Engineering quality

- [ ] `.env` is the main user-editable config.
- [ ] Secrets are redacted from logs and DB snapshots.
- [ ] Tests run without real API keys.
- [ ] Code has no hardcoded API keys.
- [ ] Code does not hardcode the canonical model catalog.
- [ ] Errors are classified.
- [ ] README contains exact commands.

## Cutline for day 1

Must have:

- FastAPI.
- Discovery.
- Smoke benchmark.
- Langfuse traces.
- Postgres rows.
- At least local artifact output.
- Tests.

Can defer:

- Streaming first-token measurement.
- Full cost pricing map.
- LangGraph runner.
- Self-hosted Langfuse compose.
- UI dashboard.
- Advanced concurrency.
