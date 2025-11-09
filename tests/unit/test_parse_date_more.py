from datetime import date
import pytest
import data.download_data_v5 as mod
@pytest.mark.unit
def test_parse_date_clamp_role(caplog):
    d = mod.parse_date("2020-02-31", role="end-date")
    assert d == date(2020,2,29)
    assert any("end-date 2020-02-31 is out of range" in rec.message for rec in caplog.records)
@pytest.mark.unit
def test_parse_date_bad_format():
    with pytest.raises(ValueError):
        mod.parse_date("20-02-31", role="start-date")
