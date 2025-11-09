from datetime import date
from data.download_data_v5 import (
    run_windowed_mode, RunConfig, HttpConfig
)
import pytest

@pytest.mark.unit
def test_window_creates_no_empty_dir_when_zero_rows(tmp_path, monkeypatch, caplog):
    # Fake safe_request → always empty list
    monkeypatch.setattr("data.download_data_v5.safe_request", lambda *a, **k: [])

    cfg = RunConfig(
        mode="daily",
        out_root=tmp_path,
        out_format="csv",
        chunk_size=50000,
        max_chunks=None,
        start_date="2025-11-05",
        end_date="2025-11-05",
        select=None,
        columns_file=None,
    )
    http = HttpConfig()
    headers = {"User-Agent": "test"}

    # One daily window (2025-11-05)
    windows = [(date(2025, 11, 5), date(2025, 11, 5), "2025-11-05")]

    run_windowed_mode(cfg, http, headers, None, windows, "daily")

    base_dir = tmp_path / "daily" / "2025-11-05"
    # With lazy creation, directory should not exist if no rows returned
    assert not base_dir.exists()
