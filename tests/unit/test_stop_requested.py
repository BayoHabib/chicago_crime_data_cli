from datetime import date
import data.download_data_v5 as mod
import pytest
@pytest.mark.unit
def test_stop_requested_breaks_window(monkeypatch, tmp_path):
    # One returning page but we signal stop before loop fetches the second
    monkeypatch.setattr(mod, "stop_requested", True)

    cfg = mod.RunConfig("daily", tmp_path, "csv", 50000, None, "2020-01-01", "2020-01-01", None, None)
    http = mod.HttpConfig()
    headers = {}

    # should exit cleanly without creating dirs
    mod.run_windowed_mode(cfg, http, headers, None, [(date(2020,1,1), date(2020,1,1), "2020-01-01")], "daily")
    assert not (tmp_path / "daily").exists()

    # reset global for other tests
    monkeypatch.setattr(mod, "stop_requested", False)
