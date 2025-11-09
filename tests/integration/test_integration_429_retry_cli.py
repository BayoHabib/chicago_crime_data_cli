import pytest

pytestmark = pytest.mark.integration

def test_cli_handles_429_then_succeeds(tmp_path, monkeypatch, fake_sleep):
    calls = {"n": 0}
    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            # 429 first with Retry-After header, then success with empty tail
            return __import__("tests.conftest").conftest.FakeResp(429, headers={"Retry-After": "1"})
        elif calls["n"] == 2:
            return __import__("tests.conftest").conftest.FakeResp(200, [{"id":"C","date":"2020-02-01T00:00:00.000"}])
        else:
            return __import__("tests.conftest").conftest.FakeResp(200, [])

    import data.download_data_v5 as mod
    monkeypatch.setattr(mod.requests, "get", fake_get)

    out_root = tmp_path / "raw_daily"
    argv = [
        "download_data_v5.py",
        "--mode", "daily",
        "--start-date", "2020-02-01",
        "--end-date",   "2020-02-01",
        "--out-root",   str(out_root),
        "--out-format", "csv",
        "--sleep", "0.0",
    ]
    __import__("tests.conftest").conftest.run_cli(monkeypatch, "data.download_data_v5", argv)

    # wrote first chunk after retry
    d = out_root / "daily" / "2020-02-01"
    assert (d / "2020-02-01_chunk_0001.csv").exists()
    # saw a backoff sleep at least once
    assert any(s >= 1 for s in fake_sleep)
