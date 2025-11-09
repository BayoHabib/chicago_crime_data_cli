import os
import data.download_data_v5 as mod
import pytest
@pytest.mark.unit
def test_headers_with_token_env(monkeypatch):
    monkeypatch.setenv("SOC_APP_TOKEN", "abc123")
    h = mod.headers_with_token(mod.HttpConfig())
    assert h.get("X-App-Token") == "abc123"
    assert "User-Agent" in h
