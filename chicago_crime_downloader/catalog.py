"""Utilities for materializing downloaded chunks into analytic stores."""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pandas as pd

MANIFEST_SUFFIX = ".manifest.json"

# Columns that should be persisted as text based on the Chicago crime data dictionary.
# Using VARCHAR preserves leading zeros and categorical semantics (e.g., beat, district).
DEFAULT_TYPE_OVERRIDES: dict[str, str] = {
    "block": "VARCHAR",
    "case_number": "VARCHAR",
    "iucr": "VARCHAR",
    "primary_type": "VARCHAR",
    "description": "VARCHAR",
    "location_description": "VARCHAR",
    "beat": "VARCHAR",
    "district": "VARCHAR",
    "ward": "VARCHAR",
    "community_area": "VARCHAR",
    "fbi_code": "VARCHAR",
    "x_coordinate": "VARCHAR",
    "y_coordinate": "VARCHAR",
    "location": "VARCHAR",
}


def default_type_overrides() -> dict[str, str]:
    """Return a copy of the default DuckDB type overrides."""
    return dict(DEFAULT_TYPE_OVERRIDES)


def _is_chunk_file(path: Path) -> bool:
    """Return True when *path* looks like a data chunk file."""
    if not path.is_file():
        return False
    suffixes = path.suffixes
    if not suffixes:
        return False
    if suffixes[-1] == ".parquet":
        return True
    if suffixes[-1] == ".csv":
        return True
    if len(suffixes) >= 2 and suffixes[-2:] == [".csv", ".gz"]:
        return True
    return False


def discover_chunks(root: Path) -> tuple[list[Path], list[Path]]:
    """Return sorted lists of chunk data files and manifest files."""
    data_files: list[Path] = []
    manifest_files: list[Path] = []
    for path in root.rglob("*"):
        if _is_chunk_file(path):
            data_files.append(path)
        elif path.name.endswith(MANIFEST_SUFFIX):
            manifest_files.append(path)
    data_files.sort()
    manifest_files.sort()
    return data_files, manifest_files


def load_manifest(path: Path) -> dict[str, object]:
    """Load a manifest JSON file and inject helper metadata."""
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    payload["manifest_path"] = str(path)
    payload["manifest_dir"] = str(path.parent)
    payload.setdefault("data_file", os.fspath(path))
    return payload


def collect_manifests(paths: Iterable[Path]) -> list[dict[str, object]]:
    """Read a sequence of manifest files into dictionaries."""
    manifests: list[dict[str, object]] = []
    for path in paths:
        try:
            manifests.append(load_manifest(path))
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.warning("Unable to read manifest %s: %s", path, exc)
    return manifests


def _duckdb_identifier(name: str) -> str:
    """Quote *name* for use as a DuckDB identifier."""
    try:
        import duckdb  # type: ignore[import-not-found]  # imported lazily

        escape_identifier = getattr(duckdb, "escape_identifier", None)
        if escape_identifier:
            return cast(str, escape_identifier(name))
    except Exception:  # pragma: no cover - defensive fallback
        pass

    escaped = name.replace("\"", "\"\"")
    return f'"{escaped}"'


def _read_relation(
    con,
    path: Path,
    *,
    all_varchar: bool,
    column_types: Mapping[str, str] | None,
):
    """Return a DuckDB relation for *path* or ``None`` if unsupported."""
    suffixes = path.suffixes
    if not suffixes:
        return None
    if suffixes[-1] == ".parquet":
        return con.read_parquet(str(path))
    if suffixes[-1] == ".csv" or (len(suffixes) >= 2 and suffixes[-2:] == [".csv", ".gz"]):
        options: dict[str, object] = {"sample_size": -1}
        if all_varchar:
            options["all_varchar"] = True

        reader = getattr(con, "read_csv_auto", None)
        if reader is None:
            reader = getattr(con, "read_csv", None)
        if reader is None:
            raise AttributeError("DuckDB connection missing CSV reader")

        relation = reader(str(path), **options)
        if column_types:
            projections: list[str] = []
            applied_override = False
            for column in relation.columns:
                identifier = _duckdb_identifier(column)
                override = column_types.get(column)
                if override:
                    projections.append(f"CAST({identifier} AS {override}) AS {identifier}")
                    applied_override = True
                else:
                    projections.append(identifier)
            if applied_override:
                relation = relation.project(", ".join(projections))
        return relation
    return None


def materialize_duckdb(
    files: Sequence[Path],
    manifests: Sequence[dict[str, object]] | None,
    *,
    database: Path,
    table: str = "crimes",
    manifest_table: str | None = "chunk_manifests",
    replace: bool = False,
    column_types: Mapping[str, str] | None = None,
    all_varchar: bool = True,
    progress: Callable[[Path], None] | None = None,
) -> None:
    """
    Load chunk files into a DuckDB table alongside manifest metadata.

    Args:
        files: Ordered chunk data files to load.
        manifests: Optional manifest payloads to persist.
        database: Destination DuckDB database path.
        table: Primary table to append data.
        manifest_table: Optional table for manifest metadata.
        replace: Drop existing tables before inserting.
        column_types: DuckDB column overrides (e.g., {"beat": "VARCHAR"}).
        all_varchar: When true, force CSV readers to treat every column as text.
        progress: Optional callback invoked after each file is processed.

    """
    if not files:
        raise ValueError("No chunk files supplied")

    import duckdb  # type: ignore[import-not-found]  # imported lazily

    database.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database))
    try:
        table_ident = _duckdb_identifier(table)
        manifest_ident = _duckdb_identifier(manifest_table) if manifest_table else None

        if replace:
            con.execute(f"DROP TABLE IF EXISTS {table_ident}")
            if manifest_ident:
                con.execute(f"DROP TABLE IF EXISTS {manifest_ident}")

        existing_row = con.execute(
            "SELECT COUNT(*) FROM duckdb_tables WHERE lower(table_name) = lower(?)",
            [table],
        ).fetchone()
        existing = bool(existing_row[0] if existing_row else 0)

        inserted = 0
        target_columns: list[str] | None = None
        type_overrides = dict(column_types) if column_types else None
        for path in files:
            relation = _read_relation(
                con,
                path,
                all_varchar=all_varchar,
                column_types=type_overrides,
            )
            if relation is None:
                continue
            current_columns = list(relation.columns)
            if target_columns is None:
                target_columns = current_columns
            elif current_columns != target_columns:
                projection_parts: list[str] = []
                missing: list[str] = []
                for column in target_columns:
                    if column in relation.columns:
                        projection_parts.append(_duckdb_identifier(column))
                    else:
                        missing.append(column)
                if missing:
                    raise ValueError(
                        "Missing expected columns in relation: "
                        + ", ".join(missing)
                    )
                relation = relation.project(", ".join(projection_parts))
            if not existing and inserted == 0:
                creator = getattr(relation, "create_table", None)
                if creator is None:
                    creator = getattr(relation, "to_table", None)
                if creator is None:
                    raise AttributeError("DuckDB relation missing table creation helper")
                creator(table)
                existing = True
            else:
                relation.insert_into(table)
            if progress:
                progress(path)
            inserted += 1

        if inserted == 0:
            raise ValueError("No supported chunk files were processed")

        if manifests and manifest_ident:
            manifest_df = pd.DataFrame(manifests)
            if not manifest_df.empty:
                con.register("_manifests", manifest_df)
                con.execute(
                    f"CREATE TABLE IF NOT EXISTS {manifest_ident} AS "
                    "SELECT * FROM _manifests WHERE 1=0"
                )
                if replace:
                    con.execute(f"DELETE FROM {manifest_ident}")
                con.execute(f"INSERT INTO {manifest_ident} SELECT * FROM _manifests")
                con.unregister("_manifests")
    finally:
        con.close()
