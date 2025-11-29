import json

import pandas as pd
import pytest

from chicago_crime_downloader.catalog import collect_manifests, discover_chunks, materialize_duckdb


@pytest.mark.unit
def test_discover_chunks_and_manifests(tmp_path):
    root = tmp_path / "daily"
    chunk_dir = root / "2025-01-01"
    chunk_dir.mkdir(parents=True)
    chunk_path = chunk_dir / "2025-01-01_chunk_0001.csv"
    chunk_path.write_text("id,date\n1,2025-01-01\n")

    manifest_path = chunk_dir / "2025-01-01_chunk_0001.manifest.json"
    manifest_path.write_text(json.dumps({"data_file": str(chunk_path), "rows": 1}))

    data_files, manifest_files = discover_chunks(tmp_path)

    assert data_files == [chunk_path]
    assert manifest_files == [manifest_path]

    manifests = collect_manifests(manifest_files)
    assert manifests and manifests[0]["data_file"] == str(chunk_path)


@pytest.mark.unit
def test_materialize_duckdb_roundtrip(tmp_path):
    duckdb = pytest.importorskip("duckdb")

    chunk_dir = tmp_path / "chunks"
    chunk_dir.mkdir()

    df_a = pd.DataFrame({"id": [1, 2], "value": ["a", "b"]})
    df_b = pd.DataFrame({"id": [3], "value": ["c"]})

    csv_a = chunk_dir / "chunk_0001.csv"
    csv_b = chunk_dir / "chunk_0002.csv"
    df_a.to_csv(csv_a, index=False)
    df_b.to_csv(csv_b, index=False)

    manifest_a = chunk_dir / "chunk_0001.manifest.json"
    manifest_b = chunk_dir / "chunk_0002.manifest.json"
    manifest_a.write_text(json.dumps({"data_file": str(csv_a), "rows": 2}))
    manifest_b.write_text(json.dumps({"data_file": str(csv_b), "rows": 1}))

    manifests = collect_manifests([manifest_a, manifest_b])

    database_path = tmp_path / "warehouse" / "test.duckdb"

    materialize_duckdb(
        [csv_a, csv_b],
        manifests,
        database=database_path,
        table="crimes",
        manifest_table="chunk_manifests",
        replace=True,
    )

    con = duckdb.connect(str(database_path))
    try:
        total_rows = con.execute("SELECT COUNT(*) FROM crimes").fetchone()[0]
        manifest_rows = con.execute("SELECT COUNT(*) FROM chunk_manifests").fetchone()[0]
    finally:
        con.close()

    assert total_rows == 3
    assert manifest_rows == 2
