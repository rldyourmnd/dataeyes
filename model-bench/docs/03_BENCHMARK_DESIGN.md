# Benchmark Design

## Benchmark suites

### 1. `smoke`

Purpose: confirm each model can answer through the gateway.

Checks:

- HTTP success.
- Non-empty text.
- Latency.
- Usage tokens if returned.
- Langfuse trace exists.

Prompt:

```text
Return exactly this JSON object with no markdown:
{"status":"ok","provider_test":"dataeyes","answer":42}
```

Score:

- JSON parse: 40 points.
- Exact fields: 40 points.
- Latency under configured threshold: 20 points.

### 2. `json_schema`

Purpose: test structured output reliability.

Task:

Given a short vendor evaluation note, return a JSON object matching `schemas/benchmark_result.schema.json`.

Checks:

- JSON parse.
- JSON schema validation.
- Required fields.
- No invented numeric cost if unavailable.

### 3. `tool_call`

Purpose: test native function calling when available, with JSON fallback.

Tools:

- `web_search(query: str)`
- `read_support_tickets()`
- `write_report(title: str, body_markdown: str)`

Checks:

- Correct tool selection.
- Valid tool args.
- Whether model can continue after tool result.
- Whether final report references tool evidence.

### 4. `agent_mini`

Purpose: 5-10 step agent benchmark that approximates a real integration task.

Scenario:

> You are evaluating a model-provider partnership. Use web search and local support tickets to produce a concise integration-readiness report. Identify endpoint risks, observability requirements, benchmark matrix, and a go/no-go recommendation.

Deterministic harness steps:

1. Ask model to produce a plan as JSON.
2. Validate plan has 3-6 steps.
3. Execute DataEyes web search tool for one query chosen by model.
4. Load local `support_tickets.csv`.
5. Ask model to synthesize facts and ticket risks into structured report JSON.
6. Validate report schema.
7. Score required facts and risk categories.
8. Optionally ask judge model to rate usefulness.
9. Upload raw artifacts.
10. Record Langfuse scores.

Required facts for golden scoring:

- Mentions model discovery/list endpoint or dynamic discovery.
- Separates LLM base URL from search API base URL.
- Mentions Langfuse traces/latency/cost visibility.
- Mentions function/tool calling or JSON fallback.
- Mentions retry/error/rate-limit handling.
- Includes a minimal benchmark matrix.

Required risk categories:

- Endpoint/base-url compatibility.
- Model availability/entitlements.
- Streaming/tool calling compatibility.
- Latency/cost variance.
- Observability gaps.

### 5. `latency_repeated`

Purpose: sample latency variance.

Method:

- Run same small prompt `N` times per model.
- Compute p50/p95/p99 total latency.
- Compute error rate.
- Compute tokens/sec if usage is returned.

## Metrics

Each case result must include:

```json
{
  "model": "string",
  "suite": "string",
  "case_id": "string",
  "status": "passed|failed|error|skipped",
  "score": 0.0,
  "latency_ms_total": 0,
  "latency_ms_first_token": null,
  "input_tokens": null,
  "output_tokens": null,
  "total_tokens": null,
  "tokens_per_second": null,
  "estimated_cost_usd": null,
  "cost_status": "known|estimated|unknown|unavailable",
  "tool_call_count": 0,
  "tool_error_count": 0,
  "json_valid": true,
  "schema_valid": true,
  "error_type": null,
  "error_message": null
}
```

## Scoring weights for `agent_mini`

| Area | Points |
|---|---:|
| JSON/schema validity | 15 |
| Required facts | 25 |
| Tool use correctness | 15 |
| Local data analysis | 15 |
| Benchmark matrix quality | 10 |
| Risk assessment | 10 |
| Recommendation clarity | 5 |
| Latency/reliability budget | 5 |

Total: 100.

## Judge model

LLM-as-judge is optional. Use only after deterministic checks. It should not replace schema/golden tests.

Judge output schema:

```json
{
  "score": 0,
  "reasoning_summary": "short explanation",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "flags": ["hallucination|missing_evidence|bad_json|unsafe|none"]
}
```

If `JUDGE_MODEL` is unset, skip judge and mark `judge_status="skipped"`.

## Model selection

Algorithm:

1. Call DataEyes `/v1/models`.
2. If `BENCHMARK_MODEL_ALLOWLIST` is set, filter to that list.
3. If request has `limit_models`, take first N after filtering.
4. If model metadata contains supported endpoint types, select compatible case path.
5. Continue on per-model errors.

## Reproducibility

- Store all prompts, tool results and raw responses as artifacts.
- Store benchmark version.
- Store env-derived config snapshot excluding secrets.
- Store model discovery payload.
