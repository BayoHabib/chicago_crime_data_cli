#!/usr/bin/env python3
"""Convert downloaded chunks into a DuckDB database for analytics."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from chicago_crime_downloader.catalog import collect_manifests, discover_chunks, materialize_duckdb


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        default="data",
        help="Root directory containing downloaded chunk files (default: data).",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("warehouse/chicago_crime.duckdb"),
        help="Output DuckDB database path (default: warehouse/chicago_crime.duckdb).",
    )
    parser.add_argument(
        "--table",
        type=str,
        default="crimes",
        help="Target DuckDB table for combined rows (default: crimes).",
    )
    parser.add_argument(
        "--manifest-table",
        type=str,
        default="chunk_manifests",
        help="Optional DuckDB table name for manifest metadata (default: chunk_manifests).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop existing tables before loading new data.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    source_root = Path(args.source).expanduser().resolve()
    if not source_root.exists():
        parser.error(f"Source directory {source_root} does not exist.")

    data_files, manifest_files = discover_chunks(source_root)
    if not data_files:
        logging.error("No chunk files discovered under %s", source_root)
        return 1

    manifests = collect_manifests(manifest_files)

    logging.info(
        "Preparing to load %s data files (%s manifests) into %s",
        len(data_files),
        len(manifests),
        args.database,
    )

    try:
        materialize_duckdb(
            data_files,
            manifests,
            database=args.database,
            table=args.table,
            manifest_table=args.manifest_table,
            replace=args.replace,
            progress=lambda path: logging.info("Loaded %s", path),
        )
    except ImportError as exc:
        parser.error(
            "DuckDB is required for this script. Install the optional 'warehouse' extra: "
            "pip install 'chicago-crime-downloader[warehouse]'"
        )
    except Exception as exc:  # pragma: no cover - CLI guard
        logging.error("Failed to materialize DuckDB database: %s", exc)
        return 1

    logging.info("DuckDB materialization complete: %s", args.database)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
