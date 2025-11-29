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


@pytest.mark.unit
def test_materialize_duckdb_type_overrides(tmp_path):
    duckdb = pytest.importorskip("duckdb")

    chunk_dir = tmp_path / "chunks"
    chunk_dir.mkdir()

    csv_path = chunk_dir / "chunk.csv"
    csv_path.write_text("beat,value\n0611,test\n", encoding="utf-8")

    database_path = tmp_path / "warehouse" / "test.duckdb"

    materialize_duckdb(
        [csv_path],
        [],
        database=database_path,
        table="crimes",
        manifest_table=None,
        replace=True,
        column_types={"beat": "VARCHAR"},
        all_varchar=False,
    )

    con = duckdb.connect(str(database_path))
    try:
        description = con.execute("DESCRIBE crimes").fetchall()
        type_map = {row[0]: row[1] for row in description}
        row = con.execute("SELECT beat FROM crimes").fetchone()
    finally:
        con.close()

    assert type_map["beat"] == "VARCHAR"
    assert row == ("0611",)


@pytest.mark.unit
def test_materialize_duckdb_aligns_column_order(tmp_path):
    duckdb = pytest.importorskip("duckdb")

    chunk_dir = tmp_path / "chunks"
    chunk_dir.mkdir()

    csv_a = chunk_dir / "chunk_a.csv"
    csv_b = chunk_dir / "chunk_b.csv"
    csv_a.write_text("id,beat,x_coordinate\n1,0611,1904872\n", encoding="utf-8")
    csv_b.write_text("beat,id,x_coordinate\n0712,2,1905000\n", encoding="utf-8")

    database_path = tmp_path / "warehouse" / "test.duckdb"

    materialize_duckdb(
        [csv_a, csv_b],
        [],
        database=database_path,
        table="crimes",
        manifest_table=None,
        replace=True,
        column_types={"beat": "VARCHAR", "x_coordinate": "VARCHAR"},
        all_varchar=False,
    )

    con = duckdb.connect(str(database_path))
    try:
        rows = con.execute(
            "SELECT id, beat, x_coordinate FROM crimes ORDER BY id"
        ).fetchall()
        description = con.execute("DESCRIBE crimes").fetchall()
    finally:
        con.close()

    type_map = {row[0]: row[1] for row in description}
    assert type_map["beat"] == "VARCHAR"
    assert type_map["x_coordinate"] == "VARCHAR"
    assert rows == [(1, "0611", "1904872"), (2, "0712", "1905000")]
