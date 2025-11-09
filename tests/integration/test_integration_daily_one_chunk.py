import pytest
pytestmark = pytest.mark.integration

def test_daily_mode_writes_one_chunk(tmp_path, monkeypatch, fake_sleep):
    # Arrange: fake requests.get to return 1 page (1 row), then empty
    pages = [
        [{"id": "X1", "date": "2020-01-10T12:34:56.000", "primary_type": "THEFT"}],
        []
    ]
    def fake_get(url, params=None, headers=None, timeout=None):
        return __import__("tests.conftest").conftest.FakeResp(200, pages.pop(0))

    import data.download_data_v5 as mod
    monkeypatch.setenv("SOC_APP_TOKEN", "abc123")  # exercise header path
    monkeypatch.setattr(mod.requests, "get", fake_get)

    out_root = tmp_path / "raw_daily"
    argv = [
        "download_data_v5.py",
        "--mode", "daily",
        "--start-date", "2020-01-10",
        "--end-date",   "2020-01-10",
        "--chunk-size", "50000",
        "--out-root",   str(out_root),
        "--out-format", "csv",
        "--sleep",      "0.1",
        "--log-json"
    ]

    # Act
    mod = __import__("tests.conftest").conftest.run_cli(monkeypatch, "data.download_data_v5", argv)

    # Assert: data + manifest present; exactly one chunk
    day_dir = out_root / "daily" / "2020-01-10"
    data_file = day_dir / "2020-01-10_chunk_0001.csv"
    manifest_file = day_dir / "2020-01-10_chunk_0001.manifest.json"

    assert data_file.exists()
    assert manifest_file.exists()
    # no second chunk
    assert not (day_dir / "2020-01-10_chunk_0002.csv").exists()
