# Architecture

## Goal

Build a minimal benchmark service that can compare every DataEyes-accessible model on:

- API availability.
- First-token and total latency.
- Tokens/sec.
- Token usage and cost where available.
- JSON/schema validity.
- Native tool/function calling or fallback tool plan quality.
- Agent task success over 5-10 steps.
- Error/retry/rate-limit behavior.
- Deterministic correctness and optional LLM-as-judge quality score.

## Design principle

Prefer **observable deterministic orchestration** over a complex agent framework. The benchmark itself is the product; every step must be traceable, timed, scored, and reproducible.

## Components

### FastAPI `benchsvc`

Responsibilities:

- Load env configuration.
- Discover models.
- Start sync benchmark runs.
- Call LiteLLM gateway or direct DataEyes fallback.
- Execute tools for the agent mini-scenario.
- Persist DB rows.
- Upload artifacts.
- Attach Langfuse scores/metadata.

### LiteLLM Proxy

Responsibilities:

- Normalize LLM API calls through an OpenAI-compatible interface.
- Centralize provider config.
- Emit Langfuse traces via callback.
- Support model hot-swap without changing app code.

### Direct DataEyes client

Responsibilities:

- `GET /v1/models` discovery.
- Optional direct `/v1/responses` diagnostics.
- DataEyes Search API calls.
- Helpful error details if LiteLLM fails.

### Langfuse

Responsibilities:

- LLM call tracing.
- Latency, token, cost visibility.
- Benchmark run spans.
- Model/case scores.
- Dataset/experiment tracking if later expanded.

### PostgreSQL

Responsibilities:

- Stable run metadata and queryable results.
- Store normalized summary only, not huge raw payloads.

Tables:

- `benchmark_runs`
- `model_results`
- `step_events`
- `artifacts`

### RustFS

Responsibilities:

- Store raw responses, reports, exports, discovery payloads.
- S3-compatible so it can be replaced by AWS S3/MinIO/etc.

## Request flow

```text
POST /benchmarks/run
  -> create benchmark_runs row
  -> discover models or use explicit list
  -> for each model:
       -> create Langfuse run span
       -> run selected cases synchronously
       -> for each case:
            -> call model via LiteLLM Proxy
            -> execute deterministic tools if requested
            -> capture usage/latency/errors
            -> score result
            -> write model_results and step_events
       -> upload raw JSON/report artifacts to RustFS
  -> return run summary
```

## Why not LangGraph by default?

LangGraph is useful for durable, stateful, long-running workflows. This MVP needs a 5-10 step synchronous benchmark with strict latency and score accounting. Plain Python gives:

- Less setup.
- Easier debugging.
- Easier mocking.
- Lower framework ambiguity.
- Precise per-step timing.

Future-compatible compromise:

- Represent agent state as a typed object.
- Keep each step as a pure-ish function.
- Later a LangGraph graph can wrap these steps without changing benchmark semantics.

## Core interfaces

```python
class LLMGateway:
    def complete(self, model: str, messages: list[dict], **kwargs) -> LLMResult: ...
    def stream_complete(self, model: str, messages: list[dict], **kwargs) -> LLMResult: ...

class ModelDiscovery:
    def list_models(self) -> list[ModelInfo]: ...

class BenchmarkRunner:
    def run_suite(self, suite: str, models: list[str]) -> BenchmarkRunSummary: ...

class ArtifactStore:
    def put_json(self, key: str, payload: dict) -> str: ...
```

## Operational modes

### Default day-1 mode

- Langfuse Cloud.
- Local Postgres via Docker.
- Local RustFS via Docker.
- Local LiteLLM Proxy via Docker.
- FastAPI running on host.

### Fallback mode

- Direct DataEyes API if LiteLLM proxy is down.
- Local filesystem artifacts if RustFS is down.
- Deterministic scoring only if judge model is unset.

## Cost model

Store costs as nullable fields:

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `cost_status`: `known | estimated | unknown | unavailable`

Use response usage and LiteLLM/Langfuse cost data where available. Do not fabricate prices.
