# LLM-as-Judge Rubric

Judge the model output as an integration-readiness report.

Return JSON only:

```json
{
  "score": 0,
  "reasoning_summary": "short explanation",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "flags": ["hallucination|missing_evidence|bad_json|unsafe|none"]
}
```

Score from 0 to 100.

## Criteria

- 0-20: JSON/schema validity and formatting.
- 0-20: Correct integration facts: model discovery, base URLs, auth, endpoint compatibility.
- 0-15: Observability: Langfuse traces, latency, tokens, cost, scores.
- 0-15: Benchmark design: smoke, schema, tool calling, agent task, latency.
- 0-15: Risk analysis: rate limits, model availability, tool calling, streaming, cost unknowns.
- 0-10: Actionability: clear next steps, runbook, go/no-go recommendation.
- 0-5: Evidence quality: references tool/search/ticket evidence.

Do not reward invented prices, unsupported claims, or vague generic advice.
