import os
import pytest
from chicago_crime_downloader import headers_with_token, HttpConfig

@pytest.mark.unit
def test_headers_with_token_env(monkeypatch):
    monkeypatch.setenv("SOC_APP_TOKEN", "abc123")
    h = headers_with_token(HttpConfig())
    assert h.get("X-App-Token") == "abc123"
    assert "User-Agent" in h

