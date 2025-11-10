from datetime import date

import pytest

import chicago_crime_downloader.runners as runners_mod
from chicago_crime_downloader import HttpConfig, RunConfig, run_windowed_mode


@pytest.mark.unit
def test_stop_requested_breaks_window(tmp_path):
    # Set stop_requested flag before running
    runners_mod.stop_requested = True
    try:
        cfg = RunConfig(
            "daily",
            tmp_path,
            "csv",
            50000,
            None,
            "2020-01-01",
            "2020-01-01",
            None,
            None,
        )
        http = HttpConfig()
        headers = {}

        # should exit cleanly without creating dirs
        run_windowed_mode(
            cfg,
            http,
            headers,
            None,
            [(date(2020, 1, 1), date(2020, 1, 1), "2020-01-01")],
            "daily",
        )
        assert not (tmp_path / "daily").exists()
    finally:
        runners_mod.stop_requested = False

