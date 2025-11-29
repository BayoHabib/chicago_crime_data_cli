"""Utilities for materializing downloaded chunks into analytic stores."""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import cast

import pandas as pd

MANIFEST_SUFFIX = ".manifest.json"


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


def _reader_sql(path: Path) -> tuple[str, list[str]] | None:
    """Return a DuckDB reader expression and parameters for *path*."""
    suffixes = path.suffixes
    if not suffixes:
        return None
    if suffixes[-1] == ".parquet":
        return "read_parquet(?)", [str(path)]
    if suffixes[-1] == ".csv":
        return "read_csv_auto(?, SAMPLE_SIZE=-1)", [str(path)]
    if len(suffixes) >= 2 and suffixes[-2:] == [".csv", ".gz"]:
        return "read_csv_auto(?, SAMPLE_SIZE=-1)", [str(path)]
    return None


def materialize_duckdb(
    files: Sequence[Path],
    manifests: Sequence[dict[str, object]] | None,
    *,
    database: Path,
    table: str = "crimes",
    manifest_table: str | None = "chunk_manifests",
    replace: bool = False,
    progress: Callable[[Path], None] | None = None,
) -> None:
    """Load chunk files into a DuckDB table alongside manifest metadata."""
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

        first_insert = True
        inserted = 0
        for path in files:
            reader = _reader_sql(path)
            if reader is None:
                continue
            sql, params = reader
            action = "CREATE" if first_insert and not existing else "INSERT"
            if action == "CREATE":
                con.execute(f"CREATE TABLE {table_ident} AS SELECT * FROM {sql}", params)
                existing = True
                first_insert = False
            else:
                con.execute(f"INSERT INTO {table_ident} SELECT * FROM {sql}", params)
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
