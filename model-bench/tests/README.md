# Tests

Day-1 test target:

```bash
pytest -q
```

Tests should not require real DataEyes, Langfuse, LiteLLM, Postgres, or RustFS credentials unless explicitly marked integration.

Required test classes for the implementing agent:

- scoring unit tests;
- JSON schema validation tests;
- DataEyes discovery parser tests with mocked HTTP;
- LiteLLM gateway error-classification tests;
- FastAPI endpoint smoke tests with mocked runner.
