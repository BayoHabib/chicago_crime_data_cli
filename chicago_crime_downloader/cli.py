"""CLI: thin argparse wrapper that wires to modular runners."""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
from datetime import date
from pathlib import Path

import chicago_crime_downloader.runners as runners_mod

from .catalog import (
    collect_manifests,
    default_type_overrides,
    discover_chunks,
    materialize_duckdb,
)
from .config import HttpConfig, RunConfig
from .http_client import headers_with_token
from .logging_utils import setup_logging
from .runners import run_offset_mode, run_windowed_mode
from .soql import day_windows, month_windows, parse_date, week_windows


def _sigint_handler(signum, frame):
    """Handle SIGINT by setting module-level flag."""
    runners_mod.stop_requested = True
    logging.warning("CTRL-C received; will stop after current chunk.")


signal.signal(signal.SIGINT, _sigint_handler)


def load_select(select: str | None, columns_file: Path | None) -> str | None:
    """Load column selection from --select or --columns-file."""
    if columns_file:
        cols = [
            ln.strip()
            for ln in columns_file.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        if cols:
            return ",".join(cols)
    if select:
        return ",".join([c.strip() for c in select.split(",") if c.strip()])
    return None


def main(argv: list[str] | None = None) -> None:
    """Run the CLI with parsed arguments."""
    ap = argparse.ArgumentParser(
        description="Resumable Chicago Crime downloader (SoQL + Token) — v5."
    )
    ap.add_argument(
        "--mode",
        choices=["full", "monthly", "weekly", "daily"],
        default="full",
        help=(
            "full: single $offset run; monthly: per-month windows; "
            "weekly: per-week windows; daily: per-day windows."
        ),
    )

    ap.add_argument(
        "--chunk-size", type=int, default=50000, help="Rows per chunk."
    )
    ap.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="[full mode] Optional cap on chunks this run.",
    )
    ap.add_argument("--start-date", type=str, default=None, help="YYYY-MM-DD (optional)")
    ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD (optional)")

    ap.add_argument(
        "--out-root", type=Path, default=Path("data/raw"), help="Root output directory."
    )
    ap.add_argument(
        "--out-format",
        choices=["csv", "parquet"],
        default="csv",
        help="Output file format.",
    )

    ap.add_argument(
        "--compression",
        type=str,
        default=None,
        help=(
            "Optional compression codec. "
            "CSV: gzip. Parquet: snappy, gzip, brotli, zstd, lz4."
        ),
    )

    ap.add_argument(
        "--select",
        type=str,
        default=None,
        help="Comma-separated columns to project at source.",
    )
    ap.add_argument(
        "--columns-file",
        type=Path,
        default=None,
        help="Text file with one column name per line.",
    )

    ap.add_argument(
        "--http-timeout",
        type=int,
        default=300,
        help="HTTP timeout seconds.",
    )
    ap.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="HTTP retries on failure.",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Sleep seconds between successful chunks.",
    )
    ap.add_argument(
        "--user-agent",
        type=str,
        default="crime-downloader/1.0 (+mlops)",
    )

    ap.add_argument("--log-file", type=str, default=None, help="Optional log file path.")
    ap.add_argument("--log-json", action="store_true", help="Emit JSON logs.")

    ap.add_argument(
        "--preflight",
        action="store_true",
        help="Enable a daily preflight 'count(1)' check and skip days with 0 published rows.",
    )

    ap.add_argument(
        "--layout",
        choices=["nested", "mode-flat", "flat", "ymd"],
        default=None,
        help=(
            "Optional output layout. "
            "nested=<root>/<mode>/<window>, "
            "mode-flat=<root>/<mode>, "
            "flat=<root>, "
            "ymd=<root>/<mode>/<yyyy>/<mm>/<dd>."
        ),
    )
    ap.add_argument(
        "--materialize-duckdb",
        type=Path,
        default=None,
        help="Optional DuckDB database path to materialize downloaded chunks into.",
    )
    ap.add_argument(
        "--materialize-source",
        type=Path,
        default=None,
        help="Root directory to scan for chunk files (default: out-root).",
    )
    ap.add_argument(
        "--materialize-table",
        type=str,
        default="crimes",
        help="DuckDB table name for consolidated rows (default: crimes).",
    )
    ap.add_argument(
        "--materialize-manifest-table",
        type=str,
        default="chunk_manifests",
        help=(
            "DuckDB table name for manifest metadata (default: chunk_manifests). "
            "Provide an empty string to skip manifest loading."
        ),
    )
    ap.add_argument(
        "--materialize-replace",
        action="store_true",
        help="Drop existing DuckDB tables before loading new data.",
    )
    ap.add_argument(
        "--materialize-only",
        action="store_true",
        help="Skip downloading and only materialize existing chunk files.",
    )
    ap.add_argument(
        "--materialize-types",
        type=Path,
        default=None,
        help="Path to JSON file containing DuckDB column type overrides.",
    )
    ap.add_argument(
        "--materialize-keep-types",
        action="store_true",
        help="Allow DuckDB to infer types instead of forcing all columns to TEXT.",
    )
    args = ap.parse_args(args=argv)

    setup_logging(args.log_file, args.log_json)

    if args.materialize_only and not args.materialize_duckdb:
        logging.error("--materialize-only requires --materialize-duckdb")
        sys.exit(2)

    compression = args.compression.lower() if args.compression else None
    if compression == "none":
        compression = None

    if args.out_format == "csv":
        valid_csv = {None, "gzip"}
        if compression not in valid_csv:
            logging.error("Unsupported compression %s for CSV. Use 'gzip' or omit.", compression)
            sys.exit(2)
    else:
        valid_parquet = {None, "snappy", "gzip", "brotli", "zstd", "lz4"}
        if compression not in valid_parquet:
            logging.error(
                "Unsupported compression %s for parquet. "
                "Choose snappy/gzip/brotli/zstd/lz4 or omit.",
                compression,
            )
            sys.exit(2)

    http = HttpConfig(
        timeout=args.http_timeout,
        retries=args.max_retries,
        sleep=args.sleep,
        user_agent=args.user_agent,
    )

    if args.layout is None:
        root_name = args.out_root.name.lower()
        inferred_layout = "mode-flat" if root_name.endswith(args.mode) else "nested"
    else:
        inferred_layout = args.layout

    select = load_select(args.select, args.columns_file)

    cfg = RunConfig(
        mode=args.mode,
        out_root=args.out_root,
        out_format=args.out_format,
        compression=compression,
        chunk_size=args.chunk_size,
        max_chunks=args.max_chunks,
        start_date=args.start_date,
        end_date=args.end_date,
        select=select,
        columns_file=args.columns_file,
    )
    cfg.preflight = args.preflight
    cfg.layout = inferred_layout

    materialize_requested = args.materialize_duckdb is not None

    if not args.materialize_only:
        headers = headers_with_token(http)

        if cfg.mode == "full":
            run_offset_mode(cfg, http, headers, select)
        else:
            start_d = parse_date(cfg.start_date, role="start-date") or date(2001, 1, 1)
            end_d = parse_date(cfg.end_date, role="end-date") or date.today()

            if start_d > end_d:
                logging.error("start-date is after end-date.")
                sys.exit(2)

            if cfg.mode == "monthly":
                wins = month_windows(start_d, end_d)
                run_windowed_mode(cfg, http, headers, select, wins, "monthly")
            elif cfg.mode == "weekly":
                wins = week_windows(start_d, end_d)
                run_windowed_mode(cfg, http, headers, select, wins, "weekly")
            else:
                wins = day_windows(start_d, end_d)
                run_windowed_mode(cfg, http, headers, select, wins, "daily")
    elif not materialize_requested:
        logging.warning("Nothing to do: --materialize-only specified without a database path.")

    if materialize_requested:
        _materialize_from_args(args)


def _materialize_from_args(args: argparse.Namespace) -> None:
    """Run DuckDB materialization based on parsed CLI arguments."""
    source_root = (args.materialize_source or args.out_root).resolve()
    db_path = (
        args.materialize_duckdb.resolve()
        if isinstance(args.materialize_duckdb, Path)
        else args.materialize_duckdb
    )

    if not source_root.exists():
        logging.error("Materialization source does not exist: %s", source_root)
        sys.exit(2)

    try:
        data_files, manifest_files = discover_chunks(source_root)
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Failed to scan %s for chunk files: %s", source_root, exc)
        sys.exit(1)

    if not data_files:
        logging.warning(
            "No chunk files found under %s; skipping DuckDB materialization.",
            source_root,
        )
        return

    manifest_table = (args.materialize_manifest_table or "").strip()
    manifests = collect_manifests(manifest_files) if manifest_table else []

    type_overrides = default_type_overrides()
    overrides_path: Path | None = args.materialize_types
    if overrides_path is not None:
        overrides_path = overrides_path.expanduser().resolve()
        if not overrides_path.exists():
            logging.error("Type overrides file does not exist: %s", overrides_path)
            sys.exit(2)
        try:
            payload = json.loads(overrides_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", overrides_path, exc)
            sys.exit(2)
        except Exception as exc:  # pragma: no cover - defensive
            logging.error("Unable to read %s: %s", overrides_path, exc)
            sys.exit(2)
        if not isinstance(payload, dict):
            logging.error(
                "Expected a JSON object mapping column names to types in %s",
                overrides_path,
            )
            sys.exit(2)
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                logging.error(
                    "Materialize types map must use string keys and values (%s)",
                    overrides_path,
                )
                sys.exit(2)
            type_overrides[key] = value

    all_varchar = not args.materialize_keep_types
    overrides_map = type_overrides if type_overrides else None

    try:
        materialize_duckdb(
            data_files,
            manifests if manifest_table else None,
            database=db_path,
            table=args.materialize_table,
            manifest_table=manifest_table or None,
            replace=args.materialize_replace,
            column_types=overrides_map,
            all_varchar=all_varchar,
        )
    except ImportError:
        logging.error(
            "DuckDB dependency missing. Install "
            "'chicago-crime-downloader[warehouse]' to enable materialization."
        )
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - CLI guard
        logging.error("DuckDB materialization failed: %s", exc)
        sys.exit(1)

    logging.info(
        "DuckDB materialization complete: %s (chunks=%d, manifests=%d)",
        db_path,
        len(data_files),
        len(manifest_files),
    )


if __name__ == "__main__":
    main()
