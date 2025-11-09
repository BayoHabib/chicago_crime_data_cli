import pytest
import data.download_data_v5 as mod
@pytest.mark.unit
def test_resume_index_counts_existing(tmp_path):
    d = tmp_path / "daily" / "2020-01-01"
    d.mkdir(parents=True, exist_ok=True)
    # mix of parquet/csv
    (d / "2020-01-01_chunk_0001.csv").write_text("a,b\n1,2\n")
    (d / "2020-01-01_chunk_0002.parquet").write_text("dummy")
    (d / "something_else.txt").write_text("ignore")
    assert mod.resume_index(d, "2020-01-01") == 2
