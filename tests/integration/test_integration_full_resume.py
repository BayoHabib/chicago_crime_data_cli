import pytest
import json
pytestmark = pytest.mark.integration

def test_full_mode_resume(tmp_path, monkeypatch):
    # Prepare existing chunk + manifest
    base_dir = tmp_path / "raw" / "full" / "all"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "chunk_0001.csv").write_text("id,date\nA,2020-01-01T00:00:00.000\n", encoding="utf-8")
    (base_dir / "chunk_0001.manifest.json").write_text(
        json.dumps({"rows": 1, "data_file": str(base_dir / "chunk_0001.csv")}), encoding="utf-8"
    )

    # Next call should start at offset=chunk_size and write chunk_0002
    pages = [
        [{"id":"B","date":"2020-01-02T01:00:00.000"}],
        []
    ]
    def fake_get(url, params=None, headers=None, timeout=None):
        return __import__("tests.conftest").conftest.FakeResp(200, pages.pop(0))

    import data.download_data_v5 as mod
    monkeypatch.setattr(mod.requests, "get", fake_get)

    argv = [
        "download_data_v5.py",
        "--mode", "full",
        "--chunk-size", "50000",
        "--out-root", str(tmp_path / "raw"),
        "--out-format", "csv"
    ]

    __import__("tests.conftest").conftest.run_cli(monkeypatch, "data.download_data_v5", argv)

    assert (base_dir / "chunk_0002.csv").exists()
    assert (base_dir / "chunk_0002.manifest.json").exists()
