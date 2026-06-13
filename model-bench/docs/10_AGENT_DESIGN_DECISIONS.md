# Agent Design Decisions

## Selected day-1 approach

Use a plain Python deterministic agent harness.

Why:

- User wants fast working setup, not overengineering.
- Scenario is 5-10 steps.
- Benchmarking needs precise per-step latency and scoring.
- Tool errors must be measured, not hidden behind framework retries.
- Easier for Codex/Claude Code to implement correctly in one day.

## Optional LangGraph path

Keep the state model compatible with a graph later:

```python
class AgentState(BaseModel):
    run_id: str
    case_id: str
    model: str
    objective: str
    plan: list[dict] = []
    tool_results: list[dict] = []
    draft_report: dict | None = None
    final_report: dict | None = None
    errors: list[dict] = []
```

Later graph nodes:

- `plan`
- `search`
- `load_local_data`
- `synthesize`
- `score`
- `export`

## Benchmark agent prompt shape

System:

```text
You are an integration benchmark agent. Follow instructions exactly. Prefer verifiable facts. Return valid JSON only when asked. If you need a tool, request exactly one tool call.
```

Plan request:

```text
Create a 3-6 step plan to evaluate DataEyes model-provider readiness using web search and local support tickets. Return JSON only.
```

Synthesis request:

```text
Using the web search snippets and support-ticket data below, produce a structured integration-readiness report matching this schema: ...
```

## Tool execution policy

- Model proposes tool call.
- Harness validates args.
- Harness executes tool.
- Harness provides result back.
- Harness records tool accuracy.

This isolates model reasoning quality from tool execution reliability.

## Tool-call modes

1. Native function calling.
2. JSON fallback.
3. No-tool degraded mode for models that cannot tool-call.

All modes are scored separately.

## Avoiding benchmark fragility

Live web search can vary. Therefore:

- Required golden checks should include architecture-level facts, not exact snippets.
- Local support tickets are deterministic.
- Store web search results as artifacts.
- Score web usage as evidence quality, not exact URL matching.
