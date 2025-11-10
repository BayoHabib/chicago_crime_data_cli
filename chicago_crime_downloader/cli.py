"""CLI: thin argparse wrapper that wires to modular runners."""
from __future__ import annotations
import argparse
import sys
import logging
import signal
from pathlib import Path
from datetime import date

from .config import RunConfig, HttpConfig
from .logging_utils import setup_logging
from .http_client import headers_with_token
from .runners import run_offset_mode, run_windowed_mode
from .soql import parse_date, month_windows, day_windows, week_windows

import chicago_crime_downloader.runners as runners_mod


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
    """Main CLI entrypoint."""
    ap = argparse.ArgumentParser(
        description="Resumable Chicago Crime downloader (SoQL + Token) — v5."
    )
    ap.add_argument(
        "--mode",
        choices=["full", "monthly", "weekly", "daily"],
        default="full",
        help="full: single $offset run; monthly: per-month windows; weekly: per-week windows; daily: per-day windows.",
    )

    ap.add_argument("--chunk-size", type=int, default=50000, help="Rows per chunk.")
    ap.add_argument("--max-chunks", type=int, default=None, help="[full mode] Optional cap on chunks this run.")
    ap.add_argument("--start-date", type=str, default=None, help="YYYY-MM-DD (optional)")
    ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD (optional)")

    ap.add_argument("--out-root", type=Path, default=Path("data/raw"), help="Root output directory.")
    ap.add_argument(
        "--out-format",
        choices=["csv", "parquet"],
        default="csv",
        help="Output file format.",
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
    args = ap.parse_args(args=argv)

    setup_logging(args.log_file, args.log_json)

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
        chunk_size=args.chunk_size,
        max_chunks=args.max_chunks,
        start_date=args.start_date,
        end_date=args.end_date,
        select=select,
        columns_file=args.columns_file,
    )
    cfg.preflight = args.preflight
    cfg.layout = inferred_layout

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


if __name__ == "__main__":
    main()
