import pandas as pd
import pytest

from chicago_crime_downloader import write_frame


@pytest.mark.unit
def test_parquet_fallback_to_csv_when_no_engine(tmp_path, monkeypatch):
    # Force the helper to report "no parquet engine"
    monkeypatch.setattr("chicago_crime_downloader.io_utils._parquet_engine", lambda: None)

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    target = tmp_path / "chunk_0001.parquet"
    written = write_frame(df, target, out_format="parquet")

    # Should have written CSV instead and returned that path
    assert written.suffix == ".csv"
    assert written.exists()


@pytest.mark.unit
def test_write_frame_csv_gzip(tmp_path):
    df = pd.DataFrame({"a": [1], "b": ["x"]})
    target = tmp_path / "chunk_0001.csv.gz"
    written = write_frame(df, target, out_format="csv", compression="gzip")

    assert written.suffix == ".gz"
    assert written.exists()

