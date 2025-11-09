import pytest
pytestmark = pytest.mark.integration
def test_daily_mode_zero_rows_creates_no_dir(tmp_path, monkeypatch):
    # Always empty
    def fake_get(url, params=None, headers=None, timeout=None):
        return __import__("tests.conftest").conftest.FakeResp(200, [])

    import data.download_data_v5 as mod
    monkeypatch.setattr(mod.requests, "get", fake_get)

    out_root = tmp_path / "raw_daily"
    argv = [
        "download_data_v5.py",
        "--mode", "daily",
        "--start-date", "2025-11-05",
        "--end-date",   "2025-11-05",
        "--out-root",   str(out_root),
        "--out-format", "csv",
    ]

    __import__("tests.conftest").conftest.run_cli(monkeypatch, "data.download_data_v5", argv)

    assert not (out_root / "daily" / "2025-11-05").exists()
