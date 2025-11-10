import pytest

pytestmark = pytest.mark.integration

def test_full_mode_resumes_from_chunk_index(tmp_path, monkeypatch, caplog):
    """Test that full mode resumes from the last chunk index."""
    from tests.conftest import FakeResp, run_cli

    call_count = {"n": 0}
    def fake_get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            rows = [{"id": f"ID{i:04d}", "date": "2020-02-01T00:00:00.000"} for i in range(50000)]
            return FakeResp(200, rows)
        else:
            return FakeResp(200, [])

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    out_root = tmp_path / "raw_full"
    argv = [
        "--mode", "full",
        "--out-root", str(out_root),
        "--out-format", "csv",
        "--max-chunks", "1",
        "--sleep", "0",
    ]
    run_cli(monkeypatch, "chicago_crime_downloader.cli", argv)

    assert call_count["n"] >= 1
    assert (out_root / "full" / "all").exists()

