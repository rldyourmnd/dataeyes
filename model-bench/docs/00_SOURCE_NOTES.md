# Source Notes

Дата проверки источников: 2026-06-09.

Эти заметки нужны агенту, чтобы не гадать и не хардкодить неверные endpoint-ы.

## DataEyes

Primary docs/home:

- https://dataeyes.ai/
- https://doc.dataeyes.ai/

Observed/documented facts:

- DataEyes positions itself as a unified interface/API platform for many LLM models.
- LLM API base URL is documented as `https://cloud.dataeyes.ai`.
- Backup LLM base URLs are documented as `https://cloud-cn.dataeyes.ai` and `https://cloud-hk.dataeyes.ai`.
- Some OpenAI-compatible clients/plugins require `/v1`, so app config should default to `https://cloud.dataeyes.ai/v1` for OpenAI-compatible clients.
- Search/Reader API base URL is documented separately as `https://api.dataeyes.ai`.
- Authorization is via Bearer token.
- Model discovery endpoint is documented as `GET /v1/models`.
- DataEyes docs include OpenAI-compatible chat/completions, OpenAI Responses API style endpoints, streaming, function calling, Anthropic-compatible and Gemini-compatible interfaces.
- DataEyes docs include network search through Responses API tools and a Search API endpoint `GET /v1/search`.

Engineering implications:

- Never hardcode the model catalog as truth. Discover models with `/v1/models` using the user's API key.
- Keep a `DATAEYES_LLM_BASE_URL` env var.
- Keep a separate `DATAEYES_SEARCH_BASE_URL` env var.
- Make `/v1` suffix explicit in config.
- Capture raw discovery output as a run artifact for audit/debugging.

## LiteLLM

Primary docs:

- https://docs.litellm.ai/

Observed/documented facts:

- LiteLLM Proxy is an OpenAI-compatible gateway for routing calls to many LLMs.
- Proxy configs can map `model_name` to provider-specific params.
- For OpenAI-compatible providers, LiteLLM uses `model: openai/<model>` plus `api_base` and `api_key`.
- If an OpenAI-compatible endpoint fails with not found, LiteLLM docs specifically warn to confirm the `api_base` has a `/v1` postfix.
- LiteLLM supports callbacks and Langfuse OTEL callback configuration through `litellm_settings.callbacks: ["langfuse_otel"]`.

Engineering implications:

- Generate LiteLLM proxy config from discovered DataEyes models or from explicit allowlist env.
- Default gateway URL for app: `http://localhost:4000/v1`.
- Keep `LITELLM_MASTER_KEY` for local proxy auth.
- Use Langfuse callback at proxy level to capture all model calls.

## Langfuse

Primary docs:

- https://langfuse.com/docs

Observed/documented facts:

- Langfuse supports traces, observations/generations, token usage, cost tracking, scores, datasets and experiments.
- Langfuse Python SDK v4 is OpenTelemetry-native.
- Langfuse can receive token usage and cost from integration payloads, infer cost from model pricing, or use custom model definitions.
- LiteLLM integration can send traces to Langfuse using OTEL callback.

Engineering implications:

- Use proxy-level Langfuse tracing for LLM calls.
- Use app-level Langfuse SDK only for run/case/model spans and scores.
- Set metadata: `run_id`, `case_id`, `suite`, `model`, `provider`, `gateway`, `benchmark_version`.
- Do not rely on provider pricing always being known; store `cost_status` as `known`, `estimated`, or `unknown`.

## FastAPI, PostgreSQL, Alembic

Primary docs:

- https://fastapi.tiangolo.com/
- https://hub.docker.com/_/postgres
- https://alembic.sqlalchemy.org/

Engineering implications:

- Use FastAPI APIRouter structure but keep service small.
- Use PostgreSQL official Docker image locally.
- Use Alembic for migrations.
- Keep DB schema simple: runs, model_results, step_events, artifacts.

## RustFS

Primary docs:

- https://rustfs.com/
- https://github.com/rustfs/rustfs
- https://hub.docker.com/r/rustfs/rustfs

Observed/documented facts:

- RustFS is S3-compatible object storage.
- Docker quickstart exposes an S3-compatible service and console.
- Default local credentials may be `rustfsadmin` / `rustfsadmin`, but production credentials must be replaced.

Engineering implications:

- Use boto3 S3 client against `RUSTFS_ENDPOINT_URL`.
- Store artifacts under keys like `runs/{run_id}/...`.
- Provide local filesystem fallback if RustFS is unavailable during first run.
