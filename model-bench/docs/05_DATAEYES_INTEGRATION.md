# DataEyes Integration Notes

## Env variables

```bash
DATAEYES_API_KEY=...
DATAEYES_LLM_BASE_URL=https://cloud.dataeyes.ai/v1
DATAEYES_LLM_BASE_URL_BACKUP_CN=https://cloud-cn.dataeyes.ai/v1
DATAEYES_LLM_BASE_URL_BACKUP_HK=https://cloud-hk.dataeyes.ai/v1
DATAEYES_SEARCH_BASE_URL=https://api.dataeyes.ai
DATAEYES_SEARCH_API_KEY= # optional; defaults to DATAEYES_API_KEY if empty
```

## Authentication

Use Bearer token:

```http
Authorization: Bearer ${DATAEYES_API_KEY}
Content-Type: application/json
```

## Model discovery

Request:

```http
GET ${DATAEYES_LLM_BASE_URL}/models
Authorization: Bearer ${DATAEYES_API_KEY}
```

Because `DATAEYES_LLM_BASE_URL` includes `/v1`, this maps to:

```text
https://cloud.dataeyes.ai/v1/models
```

Implementation detail:

- Accept both OpenAI-style `{"object":"list","data":[...]}` and DataEyes-style `{"success":true,"data":[...]}` envelopes.
- Persist raw discovery payload as `runs/<run_id>/discovery/models.json`.
- Normalize each model into:

```json
{
  "id": "string",
  "object": "model|null",
  "owned_by": "string|null",
  "supported_endpoint_types": ["chat_completions", "responses"],
  "raw": {}
}
```

## Completion paths

Default:

- App -> LiteLLM Proxy -> DataEyes OpenAI-compatible endpoint.

Fallback diagnostics:

- Direct `POST /v1/responses` for models that advertise Responses API support.
- Direct chat completions if needed.

## Search tool

Use DataEyes Search API for live web search:

```http
GET ${DATAEYES_SEARCH_BASE_URL}/v1/search?q=<query>
Authorization: Bearer ${DATAEYES_SEARCH_API_KEY or DATAEYES_API_KEY}
```

Normalize results:

```json
{
  "query": "string",
  "results": [
    {
      "title": "string",
      "url": "string",
      "snippet": "string",
      "published_at": "string|null",
      "score": 0.0
    }
  ]
}
```

## Function calling strategy

Use two modes:

### Native tool calling

When model/gateway supports function calling:

- Pass tools with JSON schema.
- Execute tool call.
- Feed tool output back to model.
- Score tool args and final output.

### JSON fallback

If native tool calling fails:

- Ask model to return:

```json
{
  "tool_name": "web_search",
  "arguments": {"query": "..."}
}
```

- Execute the selected tool.
- Continue.
- Mark `tool_mode="json_fallback"`.

This allows testing both model quality and provider compatibility.

## Errors to classify

- `auth_error`
- `rate_limit`
- `timeout`
- `model_not_found`
- `unsupported_endpoint`
- `bad_gateway_response`
- `invalid_json`
- `schema_error`
- `tool_error`
- `unknown`

## Request headers to capture

Store non-sensitive headers if useful:

- request id;
- rate limit headers;
- retry-after;
- content type.

Never store API keys.
