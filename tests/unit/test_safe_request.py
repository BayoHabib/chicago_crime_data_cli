import time
import pytest

import data.download_data_v5 as mod

class _Resp:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or []
        self.headers = headers or {}
    def raise_for_status(self):
        if 400 <= self.status_code:
            raise Exception(f"{self.status_code} Client Error")
    def json(self):
        return self._payload
@pytest.mark.unit
def test_safe_request_retries_on_429(monkeypatch):
    calls = {"n": 0}
    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp(429, headers={"Retry-After": "1"})
        return _Resp(200, payload=[{"ok": True}])

    sleeps = []
    monkeypatch.setattr(mod.requests, "get", fake_get)
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    http = mod.HttpConfig(timeout=5, retries=3, sleep=0.0, user_agent="t")
    out = mod.safe_request({"$limit":"1"}, {"UA":"t"}, http)
    assert out == [{"ok": True}]
    assert calls["n"] == 2
    assert any(s >= 1 for s in sleeps)  # backed off at least once
@pytest.mark.unit
def test_safe_request_stops_after_retries(monkeypatch):
    def always_400(url, **kw):
        return _Resp(400)
    monkeypatch.setattr(mod.requests, "get", always_400)

    http = mod.HttpConfig(timeout=5, retries=2, sleep=0.0, user_agent="t")
    with pytest.raises(Exception):
        mod.safe_request({"$limit":"1"}, {"UA":"t"}, http)
