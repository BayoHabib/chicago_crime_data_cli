import pytest

pytestmark = pytest.mark.integration

def test_zero_rows_published_no_dir_created(tmp_path, monkeypatch, caplog):
    """Test that if a day has 0 rows, no directory is created."""
    from tests.conftest import FakeResp, run_cli

    def fake_get(url, params=None, headers=None, timeout=None):
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

    # Directory should not have been created since no data was returned
    assert not (out_root / "daily" / "2020-02-01").exists()

