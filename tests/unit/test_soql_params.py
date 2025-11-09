from datetime import date
from data.download_data_v5 import soql_params_window, soql_params
import pytest
def _norm(s: str) -> str:
    return " ".join(s.split())
@pytest.mark.unit
def test_soql_params_window_daily_half_open():
    params = soql_params_window(
        offset=0,
        limit=50000,
        start_d=date(2025, 11, 5),   # no leading zero
        end_d=date(2025, 11, 5),     # no leading zero
        select=None
    )
    where = _norm(params["$where"])
    assert "Z" not in where  # no timezone suffix
    assert "date >=" in where and "date <" in where
    assert "2025-11-05T00:00:00.000" in where
    assert "2025-11-06T00:00:00.000" in where  # next day
@pytest.mark.unit
def test_soql_params_window_multi_day_monthly():
    params = soql_params_window(0, 1000, date(2020, 4, 1), date(2020, 4, 30), None)
    where = _norm(params["$where"])
    assert "2020-04-01T00:00:00.000" in where
    assert "2020-05-01T00:00:00.000" in where
@pytest.mark.unit
def test_soql_params_full_start_end():
    p = soql_params(0, 100, "2020-01-01", "2020-01-31", None)
    where = _norm(p["$where"])
    assert "2020-01-01T00:00:00.000" in where
    assert "2020-02-01T00:00:00.000" in where
@pytest.mark.unit
def test_soql_params_only_start():
    p = soql_params(0, 100, "2020-01-01", None, None)
    assert "date >=" in p["$where"]
    assert "T00:00:00.000" in p["$where"]
@pytest.mark.unit
def test_soql_params_only_end():
    p = soql_params(0, 100, None, "2020-01-31", None)
    assert "date <" in p["$where"]
    assert "2020-02-01T00:00:00.000" in p["$where"]
