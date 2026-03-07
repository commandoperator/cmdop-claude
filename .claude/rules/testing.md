# Testing Rules

- pytest with fixtures, no unittest
- Mock external services (SDKRouter, subprocess) in unit tests
- Use tmp_path for filesystem tests, monkeypatch for env/cwd
- E2E tests in tests/e2e/ — separate mocked and real LLM tests
- Real LLM tests require SDKROUTER_API_KEY, skip with pytest.skip if missing
