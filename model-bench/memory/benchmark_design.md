---
name: benchmark-design
description: Suite-ы, scoring-формулы, agent_mini шаги, метрики CaseResult
metadata:
  type: project
---

# Benchmark Design

## Suites (10) и их кейсы

`BenchmarkRunner._suite_cases()` → список case_id; `_run_case()` диспетчеризует на `_run_*`.

| Suite | Кейсы | max_tokens | Порог pass |
|---|---|---|---|
| `smoke` | `smoke_json_exact` | — | ≥80 |
| `json_schema` | `json_schema_vendor_readiness` | — | ≥80 |
| `tool_call` | `tool_call_web_and_ticket_plan` (→ agent_mini runner) | — | ≥70 |
| `agent_mini` | `agent_mini_vendor_readiness` | — | ≥70 |
| `latency_repeated` | `smoke_json_exact` ×3 | — | ≥80 |
| `standard` | smoke + json_schema + agent_mini | — | смешанный |
| `deep_eval` | `reasoning_multistep`, `code_generation`, `instruction_strict`, `long_context_qa` | (default) | ≥60 |
| `comprehensive` | smoke + json_schema + 4 кейса deep_eval | (default) | смешанный |
| `ultra_deep` | `ultra_reasoning`, `ultra_code_full`, `ultra_code_review`, `ultra_algorithms`, `ultra_long_context`, `ultra_system_design` | 16384–32768 | reasoning/long_ctx ≥50; остальные ≥40 |
| `fast` | `fast_reasoning`, `fast_code`, `fast_algorithms`, `fast_system_design` | 5000 | reasoning ≥50; code/algo ≥40; sysdesign ≥30 |

`BenchmarkRunRequest.suite` — Literal со всеми 10 значениями.

## Scoring (детерминированный, scoring.py)

- `score_smoke_json` (100): +40 JSON парсится, +40 точное `{"status":"ok","provider_test":"dataeyes","answer":42}`, +20 latency ≤15000ms.
- `score_json_schema` (в `_run_json_schema`): 100 если JSON+schema valid, 40 если JSON ok но schema invalid, 0 если не JSON. Схема `schemas/benchmark_result.schema.json` (Draft 2020-12).
- `score_agent_report` (100): JSON 15, факты `REQUIRED_AGENT_FACTS` 25, tools (web_search 8 + tickets 7), local ticket-signals 15, benchmark_matrix 10, risk_categories 10, recommendation 5, latency 5.
- `score_reasoning_multistep` / `score_code_generation` (AST-parse) / `score_instruction_strict` (IFEval-style констрейнты) / `score_long_context_qa` (needle-in-haystack + расчёты) — partial credit с зашитыми эталонными ответами.
- `score_ultra_*` — длинные задачи (15 связанных вопросов, async task queue, security-аудит ≥20 багов, 6 структур данных, длинный отчёт на 12 вопросов, system design). Скоринг устойчив к обрезке max_tokens (часть баллов считается по полному тексту, не только по JSON).
- `score_fast_code` / `score_fast_algorithms` — keyword + AST. `fast_reasoning`→`score_ultra_reasoning`, `fast_system_design`→`score_ultra_system_design`.
- `estimate_cost_usd` — по `VENDOR_PRICING` (~35 моделей, input/output за 1M токенов). Незнакомая → `unknown_model`.
- `aggregate_results` — passed/failed/errors, error_rate, avg_score, p50/p95 latency, total_estimated_cost_usd, cost_status.

## AgentMiniRunner — шаги

1. **plan** — LLM → `{"steps":[...]}` (3–6 шагов).
2. **web_search** — DataEyes Search API.
3. **read_support_tickets** — CSV `benchmarks/datasets/support_tickets.csv`.
4. **synthesis** — LLM(plan+search+tickets) → `VendorReadinessBenchmarkResult` JSON.
5. **write_report** — артефакт в S3/local.
6. **score_agent_report** — детерминированное scoring (`tool_call_count=3`).

## benchmark_result.schema.json (Draft 2020-12)

Required: `executive_summary` (≥20 chars), `required_facts` (≥3), `risk_categories` (≥3), `benchmark_matrix` (≥2; suite/purpose/metrics), `recommendation` (enum go|no-go|conditional-go), `next_actions` (≥2).

## CaseResult метрики

model, suite, case_id, status (passed|failed|error|skipped), score (0–100), latency_ms_total, latency_ms_first_token, input/output/total_tokens, tokens_per_second, estimated_cost_usd, cost_status, tool_call/error_count, json_valid, schema_valid, error_type, error_message, raw_artifact_uri, extra.

## Error types (classify_exception)

`auth_error`, `rate_limit`, `timeout`, `model_not_found`, `bad_gateway_response`, `unknown` (+ `invalid_json` из agent_mini).

## Artifacts layout (S3 / local)

```
runs/<run_id>/
  config_snapshot.json
  raw/<safe_model>__<case>.json      # smoke|reasoning|code|instruction|longctx|json_schema|agent_mini|ultra_*|fast_*
  search/<query-slug>.json
  reports/<title-slug>.md
  exports/summary.json | summary.md
```
`safe_name()` заменяет `/`→`__`, `:`→`_`, режет до 120 симв.
