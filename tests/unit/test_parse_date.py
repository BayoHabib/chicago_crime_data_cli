import pytest
from datetime import date
from data.download_data_v5 import parse_date
@pytest.mark.unit
def test_parse_date_ok():
    assert parse_date("2020-04-30", role="end-date") == date(2020, 4, 30)
@pytest.mark.unit
def test_parse_date_clamps_eom_and_warns(caplog):
    d = parse_date("2020-04-31", role="end-date")
    assert d == date(2020, 4, 30)
    # one warning logged
    assert any("out of range; using 2020-04-30" in rec.message for rec in caplog.records)
@pytest.mark.unit
def test_parse_date_invalid_format_raises():
    with pytest.raises(ValueError):
        parse_date("2020/04/30", role="end-date")
