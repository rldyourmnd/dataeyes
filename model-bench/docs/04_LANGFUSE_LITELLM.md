# Langfuse + LiteLLM Plan

## Goal

Every LLM call should be visible in Langfuse with:

- model name;
- provider/gateway;
- run_id/case_id/suite metadata;
- latency;
- token usage;
- cost when known;
- errors;
- benchmark scores.

## LiteLLM proxy mode

LiteLLM is the default gateway. FastAPI calls:

```text
http://localhost:4000/v1/chat/completions
```

with:

```http
Authorization: Bearer ${LITELLM_MASTER_KEY}
```

LiteLLM maps model aliases to DataEyes model IDs.

Example config entry:

```yaml
model_list:
  - model_name: dataeyes/gpt-5.1
    litellm_params:
      model: openai/gpt-5.1
      api_base: ${DATAEYES_LLM_BASE_URL}
      api_key: ${DATAEYES_API_KEY}
```

For OpenAI-compatible routing, keep `api_base` with `/v1` suffix.

## Langfuse callback in LiteLLM

Proxy config:

```yaml
litellm_settings:
  callbacks:
    - langfuse_otel
```

Required env:

```bash
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_OTEL_HOST=https://cloud.langfuse.com/api/public/otel
```

## App-level tracing

Use app-level Langfuse only for benchmark-level traces/spans and scores. Do not duplicate every token-level LLM event if LiteLLM already traces it.

Suggested attributes:

```python
metadata = {
    "run_id": run_id,
    "suite": suite,
    "case_id": case_id,
    "model": model,
    "provider": "dataeyes",
    "gateway": "litellm_proxy",
    "benchmark_version": "2026-06-09.1",
}
```

Suggested scores:

- `deterministic_score`
- `json_valid`
- `schema_valid`
- `tool_accuracy`
- `latency_score`
- `judge_score`
- `final_score`

## Cost handling

Do not invent model prices.

Priority:

1. Use usage/cost returned by integration if available.
2. Use Langfuse/LiteLLM known pricing if configured.
3. Use custom price env or config later.
4. Else set `estimated_cost_usd=null` and `cost_status="unknown"`.

## Trace grouping

For a benchmark run, use:

- `session_id=run_id`
- `user_id="benchmark"`
- tags: `benchmark`, `dataeyes`, suite, model

## Debugging

If Langfuse shows LiteLLM traces but not benchmark scores, app-level SDK is misconfigured. If benchmark scores appear but LLM calls do not, LiteLLM callback is misconfigured or calls bypass proxy.
