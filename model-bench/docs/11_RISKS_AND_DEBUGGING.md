# Risks and Debugging

## Risk: DataEyes exposes multiple compatibility surfaces

Mitigation:

- Use env for base URL.
- Default OpenAI-compatible clients to `/v1` suffix.
- Keep direct fallback diagnostics.
- Record supported endpoint types if model metadata returns them.

## Risk: Some models support Responses API but not chat completions

Mitigation:

- Model discovery should inspect `supported_endpoint_types`.
- MVP may skip unsupported cases with `status="skipped"`.
- Later implement direct `/v1/responses` route.

## Risk: LiteLLM model mapping fails

Mitigation:

- Generate config from discovery.
- Prefix OpenAI-compatible models with `openai/<model_id>`.
- Keep `api_base` ending in `/v1`.
- Test `GET /v1/models` through proxy.

## Risk: Langfuse cost is missing

Mitigation:

- Store token usage separately.
- Mark cost as unknown rather than fabricating.
- Later add custom model price map.

## Risk: Web search introduces nondeterminism

Mitigation:

- Use local support tickets for deterministic checks.
- Store search results as artifacts.
- Make web search one part of score, not the whole score.

## Risk: Too many models make run slow/expensive

Mitigation:

- Use `limit_models` for smoke.
- Use `BENCHMARK_MODEL_ALLOWLIST`.
- Add `MAX_MODELS_PER_RUN` env.
- Add per-model timeout.

## Risk: Provider rate limits

Mitigation:

- Synchronous sequential default.
- Configurable retries with exponential backoff.
- Capture `retry_after` and `rate_limit` headers.
- Stop full run if global auth/billing error is detected.

## Risk: Agent framework slows day-1 implementation

Mitigation:

- Start with plain Python.
- Preserve typed state for future LangGraph.
