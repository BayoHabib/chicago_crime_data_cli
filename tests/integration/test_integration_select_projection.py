import pytest

pytestmark = pytest.mark.integration

def test_column_projection_with_select(tmp_path, monkeypatch, caplog):
    """Test that --select applies column projection."""
    from tests.conftest import FakeResp, run_cli

    captured = {}
    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        rows = [{"id": "A", "date": "2020-02-01T00:00:00.000"}]
        return FakeResp(200, rows)

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    out_root = tmp_path / "raw_daily"
    argv = [
        "--mode", "daily",
        "--start-date", "2020-02-01",
        "--end-date", "2020-02-01",
        "--out-root", str(out_root),
        "--out-format", "csv",
        "--select", "id,date",
        "--sleep", "0",
    ]
    run_cli(monkeypatch, "chicago_crime_downloader.cli", argv)

    assert captured.get("params", {}).get("$select") == "id,date"

