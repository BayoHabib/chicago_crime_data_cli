import csv
import pytest
pytestmark = pytest.mark.integration
def test_select_projection_affects_output_columns(tmp_path, monkeypatch):
    # The API returns extra cols, but we pass --select to keep a subset
    payload = [
        {"id":"K1","date":"2020-03-01T10:00:00.000","primary_type":"THEFT","latitude":"41.9","longitude":"-87.6","extra":"x"}
    ]
    def fake_get(url, params=None, headers=None, timeout=None):
        # enforce that our soql has $select limited columns
        assert "id" in (params.get("$select") or "")
        return __import__("tests.conftest").conftest.FakeResp(200, payload if "offset=0" or True else [])

    import data.download_data_v5 as mod
    monkeypatch.setattr(mod.requests, "get", fake_get)

    out_root = tmp_path / "raw_daily"
    argv = [
        "download_data_v5.py",
        "--mode", "daily",
        "--start-date", "2020-03-01",
        "--end-date",   "2020-03-01",
        "--out-root",   str(out_root),
        "--out-format", "csv",
        "--select", "id,date,primary_type,latitude,longitude",
    ]
    __import__("tests.conftest").conftest.run_cli(monkeypatch, "data.download_data_v5", argv)

    f = out_root / "daily" / "2020-03-01" / "2020-03-01_chunk_0001.csv"
    rows = f.read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    # Ensure only projected columns are written
    assert header == ["id","date","primary_type","latitude","longitude"]
