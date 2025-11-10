from datetime import date

import pytest

from chicago_crime_downloader import probe_count_for_day


@pytest.mark.unit
def test_probe_count_for_day_builds_half_open(monkeypatch):
    captured = {}

    def fake_safe_request(params, headers, http):
        captured["params"] = params
        return [{"count_1": "42"}]

    # Monkeypatch safe_request where it's used
    monkeypatch.setattr("chicago_crime_downloader.http_client.safe_request", fake_safe_request)

    cnt = probe_count_for_day(date(2025, 10, 12), headers={"User-Agent": "x"})
    assert cnt == 42
    where = captured["params"]["$where"]
    assert "date >= '2025-10-12T00:00:00.000'" in where
    assert "date < '2025-10-13T00:00:00.000'" in where

