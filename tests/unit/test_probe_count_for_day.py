from datetime import date
from data.download_data_v5 import probe_count_for_day
import pytest

class _Resp:
    def __init__(self, json_payload): self._j=json_payload
    def raise_for_status(self): return
    def json(self): return self._j

@pytest.mark.unit
def test_probe_count_for_day_builds_half_open(monkeypatch):
    captured = {}
    def fake_get(url, params=None, headers=None, timeout=60):
        captured["params"] = params
        return _Resp([{"count_1": "42"}])

    monkeypatch.setattr("data.download_data_v5.requests.get", fake_get)

    cnt = probe_count_for_day(date(2025, 10, 12), headers={"User-Agent": "x"})
    assert cnt == 42
    where = captured["params"]["$where"]
    assert "date >= '2025-10-12T00:00:00.000'" in where
    assert "date < '2025-10-13T00:00:00.000'" in where
