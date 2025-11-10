import pytest

pytestmark = pytest.mark.integration

def test_cli_handles_429_then_succeeds(tmp_path, monkeypatch, capsys):
    """Test that CLI retries on 429 Rate Limited."""
    from tests.conftest import run_cli, FakeResp
    
    calls = {"n": 0}
    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResp(429, headers={"Retry-After": "0"})
        elif calls["n"] == 2:
            return FakeResp(200, [{"id": "C", "date": "2020-02-01T00:00:00.000"}])
        else:
            return FakeResp(200, [])

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    out_root = tmp_path / "raw_daily"
    argv = [
        "--mode", "daily",
        "--start-date", "2020-02-01",
        "--end-date", "2020-02-01",
        "--out-root", str(out_root),
        "--out-format", "csv",
        "--sleep", "0",
    ]
    run_cli(monkeypatch, "chicago_crime_downloader.cli", argv)
    assert calls["n"] >= 2
    
    # Check output in stdout
    captured = capsys.readouterr()
    assert "429 Rate limited" in captured.out or "Saved" in captured.out

