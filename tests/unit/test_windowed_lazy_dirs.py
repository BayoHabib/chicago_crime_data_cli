from datetime import date

import pytest

from chicago_crime_downloader import HttpConfig, RunConfig, run_windowed_mode


@pytest.mark.unit
def test_window_creates_no_empty_dir_when_zero_rows(tmp_path, monkeypatch, caplog):
    # Fake safe_request → always empty list
    def fake_safe_request(*a, **k):
        return []

    monkeypatch.setattr("chicago_crime_downloader.runners.safe_request", fake_safe_request)

    cfg = RunConfig(
        mode="daily",
        out_root=tmp_path,
        out_format="csv",
        compression=None,
        chunk_size=50000,
        max_chunks=None,
        start_date="2025-11-05",
        end_date="2025-11-05",
        select=None,
        columns_file=None,
    )
    cfg.layout = "nested"

    http = HttpConfig(timeout=60, retries=1, sleep=0.0, user_agent="t")
    headers = {"User-Agent": "t"}
    wins = [(date(2025, 11, 5), date(2025, 11, 5), "2025-11-05")]

    run_windowed_mode(cfg, http, headers, None, wins, "daily")

    # Should NOT have created a subdirectory because no data was written
    assert not (tmp_path / "daily").exists()

