# Database and Storage

## PostgreSQL schema

### `benchmark_runs`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| created_at | timestamptz | default now |
| completed_at | timestamptz nullable | |
| suite | text | smoke/json_schema/tool_call/agent_mini/standard |
| status | text | running/completed/failed/partial |
| requested_models | jsonb | request payload |
| discovered_models_count | int | |
| config_snapshot | jsonb | secrets redacted |
| summary | jsonb | aggregate stats |

### `model_results`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | FK benchmark_runs |
| model | text | model id/alias |
| suite | text | |
| case_id | text | |
| status | text | passed/failed/error/skipped |
| score | float | 0-100 |
| latency_ms_total | int nullable | |
| latency_ms_first_token | int nullable | |
| input_tokens | int nullable | |
| output_tokens | int nullable | |
| total_tokens | int nullable | |
| tokens_per_second | float nullable | |
| estimated_cost_usd | numeric nullable | |
| cost_status | text | known/estimated/unknown/unavailable |
| json_valid | bool | |
| schema_valid | bool | |
| tool_call_count | int | |
| tool_error_count | int | |
| error_type | text nullable | |
| error_message | text nullable | |
| raw_artifact_uri | text nullable | |
| created_at | timestamptz | |

### `step_events`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | FK |
| model_result_id | UUID nullable | FK |
| step_index | int | |
| step_name | text | |
| status | text | |
| latency_ms | int nullable | |
| input | jsonb nullable | redacted |
| output | jsonb nullable | possibly summarized |
| error | jsonb nullable | |
| created_at | timestamptz | |

### `artifacts`

| Column | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| run_id | UUID | FK |
| model_result_id | UUID nullable | FK |
| kind | text | raw_response/report/export/discovery |
| uri | text | s3://... or file://... |
| content_type | text | application/json,text/markdown,text/csv |
| size_bytes | bigint nullable | |
| created_at | timestamptz | |

## RustFS layout

```text
s3://benchmark-artifacts/
  runs/
    <run_id>/
      discovery/
        models.json
      raw/
        <model>__<case_id>.json
      reports/
        <model>__agent_report.md
      exports/
        summary.json
        summary.md
        results.csv
```

## Local fallback

If RustFS is unavailable:

```text
./artifacts/runs/<run_id>/...
```

Set `ARTIFACT_STORAGE_MODE=local` to force fallback.

## Redaction

Never persist:

- API keys;
- authorization headers;
- Langfuse secret key;
- full environment dump.

Persist config snapshot only after redaction.
