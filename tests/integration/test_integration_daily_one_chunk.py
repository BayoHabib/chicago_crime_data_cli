import pytest

pytestmark = pytest.mark.integration

def test_daily_one_chunk(tmp_path, monkeypatch, capsys):
    """Test daily mode downloads a single day with one chunk."""
    from pathlib import Path

    from tests.conftest import FakeResp, run_cli

    def fake_get(url, params=None, headers=None, timeout=None):
        # Return a single chunk worth of rows
        rows = [{"id": f"ID{i:04d}", "date": "2020-02-01T00:00:00.000"} for i in range(100)]
        return FakeResp(200, rows)

    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setenv("SOC_APP_TOKEN", "abc123")

    out_root = Path(tmp_path) / "raw_daily"
    argv = [
        "--mode", "daily",
        "--start-date", "2020-02-01",
        "--end-date", "2020-02-01",
        "--out-root", str(out_root),
        "--out-format", "csv",
        "--sleep", "0",
    ]
    run_cli(monkeypatch, "chicago_crime_downloader.cli", argv)

    # Default layout inference: "raw_daily" ends with "daily" -> mode-flat layout
    # So: out_root/mode_label/window_id_chunk
    assert (out_root / "daily").exists()
    csv_files = list((out_root / "daily").glob("*.csv"))
    assert len(csv_files) > 0

