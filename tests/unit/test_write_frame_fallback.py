import pandas as pd
import pytest

from data.download_data_v5 import write_frame
@pytest.mark.unit
def test_parquet_fallback_to_csv_when_no_engine(tmp_path, monkeypatch):
    # Force the helper to report "no parquet engine"
    monkeypatch.setattr("data.download_data_v5._parquet_engine", lambda: None)

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    target = tmp_path / "chunk_0001.parquet"
    written = write_frame(df, target, out_format="parquet")

    # Should have written CSV instead and returned that path
    assert written.suffix == ".csv"
    assert written.exists()
