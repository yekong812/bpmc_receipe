import pytest


@pytest.fixture(autouse=True)
def disable_paid_external_calls(monkeypatch):
    # Unit/integration tests never inherit a developer's paid LLM configuration.
    monkeypatch.setenv("RECEIPT_LLM_ENABLED", "false")
