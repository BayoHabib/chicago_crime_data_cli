import json
from pathlib import Path

import pytest

from chicago_crime_downloader.cli import main


def _fail_download(*args, **kwargs):
    raise AssertionError("download should not run during materialize-only")


@pytest.mark.unit
def test_cli_materialize_only(tmp_path, monkeypatch):
    chunk_dir = tmp_path / "raw" / "daily" / "2025-01-01"
    chunk_dir.mkdir(parents=True)
    chunk_file = chunk_dir / "2025-01-01_chunk_0001.csv"
    chunk_file.write_text("id,date\n1,2025-01-01\n", encoding="utf-8")
    manifest_file = chunk_dir / "2025-01-01_chunk_0001.manifest.json"
    manifest_file.write_text(
        json.dumps({"data_file": str(chunk_file), "rows": 1}),
        encoding="utf-8",
    )

    captured = {}

    def fake_materialize(
        files,
        manifests,
        *,
        database,
        table,
        manifest_table,
        replace,
        column_types=None,
        all_varchar=None,
        progress=None,
    ):
        captured["files"] = list(files)
        captured["manifests"] = manifests or []
        captured["database"] = database
        captured["table"] = table
        captured["manifest_table"] = manifest_table
        captured["replace"] = replace
        captured["column_types"] = column_types or {}
        captured["all_varchar"] = all_varchar
        captured["progress"] = progress

    monkeypatch.setattr("chicago_crime_downloader.cli.materialize_duckdb", fake_materialize)
    monkeypatch.setattr("chicago_crime_downloader.cli.run_offset_mode", _fail_download)
    monkeypatch.setattr("chicago_crime_downloader.cli.run_windowed_mode", _fail_download)

    db_path = tmp_path / "warehouse.duckdb"

    main(
        [
            "--materialize-only",
            "--materialize-duckdb",
            str(db_path),
            "--materialize-source",
            str(tmp_path / "raw"),
            "--materialize-table",
            "crimes_test",
            "--materialize-manifest-table",
            "manifests_test",
            "--materialize-replace",
        ]
    )

    assert Path(captured["database"]) == db_path
    assert captured["table"] == "crimes_test"
    assert captured["manifest_table"] == "manifests_test"
    assert captured["replace"] is True
    assert captured["all_varchar"] is True
    assert captured["column_types"].get("beat") == "VARCHAR"
    assert len(captured["files"]) == 1
    assert len(captured["manifests"]) == 1
