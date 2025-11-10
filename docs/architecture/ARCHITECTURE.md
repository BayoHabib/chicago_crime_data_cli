# Architecture Overview

## Project Structure

**chicago-crime-downloader** is organized as a modular, single-command CLI tool with clear separation of concerns.

```
chicago_crime_downloader/
├── __init__.py                 # Public API exports
├── cli.py                      # Argument parsing, layout inference, main entry point
├── config.py                   # HttpConfig, RunConfig dataclasses
├── http_client.py              # HTTP requests, token mgmt, rate limit handling
├── io_utils.py                 # File I/O, manifests, path logic, resume
├── logging_utils.py            # JSON structured logging
├── runners.py                  # Orchestration logic (offset & windowed modes)
├── soql.py                     # SoQL query builders, date parsing, windows
└── version.py                  # Version string (0.5.0)

tests/
├── conftest.py                 # Shared test fixtures
├── unit/                       # 18 unit tests (~1-2 functions each)
└── integration/                # 5 end-to-end tests (real CLI invocation)

docs/
├── architecture/               # This folder
│   └── ARCHITECTURE.md         # This file
└── TODO_REFACTOR.md            # Completed Phase 0-6 checklist
```

## Layered Architecture

The system follows a **layered, bottom-up dependency model**:

```
┌─────────────────────────────────────────────────────────────┐
│ cli.py (User Interface)                                     │
│ - argparse for CLI parsing                                  │
│ - Layout inference logic                                    │
│ - SIGINT handler for graceful shutdown                      │
└────────────────────┬────────────────────────────────────────┘
                     │ depends on
┌────────────────────▼────────────────────────────────────────┐
│ runners.py (Orchestration)                                  │
│ - run_offset_mode() — single paginated download             │
│ - run_windowed_mode() — loop over time windows              │
│ - stop_requested flag for interrupt handling                │
└────────────────────┬────────────────────────────────────────┘
                     │ depends on
         ┌───────────┴───────────┐
         │ depends on            │ depends on
┌────────▼────────────────────┐ ┌───────────▼──────────────────┐
│ soql.py (Query Building)    │ │ io_utils.py (File I/O)       │
│ - parse_date()              │ │ - write_frame()              │
│ - soql_params()             │ │ - write_manifest()           │
│ - month_windows()           │ │ - make_paths()               │
│ - day_windows()             │ │ - resume_index()             │
│ - week_windows()            │ │ - Layout-aware path logic    │
└────────────────────┬────────┘ └───────────┬──────────────────┘
                     │                      │ depends on
                     │                ┌─────┴──────────────────┐
                     │                │ depends on             │
┌────────────────────▼──────────────────────▼──────────────────┐
│ http_client.py (HTTP Layer)                                 │
│ - safe_request() — GET with exponential backoff             │
│ - headers_with_token() — SOC_APP_TOKEN lookup               │
│ - probe_count_for_day() — SoQL count(1) query               │
└────────────────────┬───────────────────────────────────────┘
                     │ depends on
┌────────────────────▼───────────────────────────────────────┐
│ config.py (Configuration)                                  │
│ - HttpConfig (timeout, retries, sleep, user_agent)         │
│ - RunConfig (mode, dates, paths, formats)                  │
│ - BASE_URL constant                                        │
└────────────────────┬───────────────────────────────────────┘
                     │ depends on
┌────────────────────▼───────────────────────────────────────┐
│ logging_utils.py (Logging)                                 │
│ - JsonFormatter — ISO8601 + structured JSON                │
│ - setup_logging() — console + file setup                   │
└─────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

### `config.py` — Configuration

**Purpose**: Define all configurable parameters as typed dataclasses.

```python
@dataclass
class HttpConfig:
    timeout: int = 30              # Request timeout in seconds
    retries: int = 5               # Exponential backoff attempts
    sleep: float = 0.1             # Base sleep for backoff
    user_agent: str = "..."        # HTTP User-Agent header

@dataclass
class RunConfig:
    mode: Literal["full", "monthly", "weekly", "daily"]
    start_date: date | None = None
    end_date: date | None = None
    out_root: Path = Path("data/raw")
    out_format: Literal["csv", "parquet"] = "csv"
    chunk_size: int = 50000
    max_chunks: int | None = None
    select: str | None = None      # SoQL $select parameter
    columns_file: Path | None = None
    layout: str = "nested"
    preflight: bool = False        # Skip zero-row days
    log_file: Path | None = None
```

**Key design**: Immutable dataclasses provide type safety and clear intent.

---

### `http_client.py` — HTTP Communication

**Purpose**: Encapsulate all HTTP logic, including retry strategy and token management.

**Functions**:

```python
def safe_request(url: str, **kwargs) -> list[dict[str, Any]]:
    """
    GET with automatic exponential backoff on 429 (rate limit).
    - Retries up to HttpConfig.retries times
    - Sleeps 2^attempt * HttpConfig.sleep seconds
    - Returns parsed JSON (list of objects)
    """

def headers_with_token() -> dict[str, str]:
    """
    Check environment for SOC_APP_TOKEN or SOCRATA_APP_TOKEN.
    Returns headers dict with Authorization header if found.
    """

def probe_count_for_day(date: date) -> int:
    """
    SoQL count(1) query to check if a day has records.
    Used by --preflight to skip zero-row days.
    """
```

**Key features**:
- Exponential backoff: $T = 2^{attempt} \times base\_sleep$
- Token lookup from environment
- Type-safe return values
- `# type: ignore[no-any-return]` on r.json() (line 42) for mypy compatibility

---

### `soql.py` — Query Building & Date Logic

**Purpose**: Build SoQL (Socrata Query Language) queries and manage date windows.

**Functions**:

```python
def parse_date(date_str: str) -> date:
    """
    Parse YYYY-MM-DD with auto-clamping.
    - "2020-04-31" → datetime.date(2020, 4, 30)  # Auto-clamp to EOM
    - Validates format, raises ValueError on invalid input
    """

def soql_params(offset: int, limit: int, select: str | None = None) -> dict[str, str]:
    """
    Build SoQL offset-mode query parameters.
    Returns: {"$offset": "1000", "$limit": "50000", "$select": "id,date,..."}
    """

def soql_params_window(start: date, end: date, select: str | None = None) -> dict[str, str]:
    """
    Build SoQL time-window query parameters.
    Returns: {"$where": "date >= ... AND date <= ...", "$select": "..."}
    """

def month_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Generate monthly windows: (2020-01-01, 2020-01-31), (2020-02-01, ...), ..."""

def day_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Generate daily windows: (2020-01-01, 2020-01-01), (2020-01-02, ...), ..."""

def week_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Generate weekly windows starting on Mondays."""
```

**Key design**: Pure functions with no I/O. Immutable date logic for testability.

---

### `io_utils.py` — File I/O & Path Logic

**Purpose**: Handle all file system operations and layout-aware paths.

**Functions**:

```python
def write_frame(df: pd.DataFrame, out_path: Path, format: Literal["csv", "parquet"]) -> None:
    """
    Write DataFrame to file with fallback.
    - CSV: Always works
    - Parquet: Try pyarrow, fall back to CSV if no engine
    - # type: ignore[call-overload] on df.to_parquet() (line 35) for mypy
    """

def write_manifest(manifest_dict: dict, manifest_path: Path) -> None:
    """Write JSON manifest sidecar with metadata (rows, SHA256, params, timing, etc.)"""

def make_paths(date: date, chunk_idx: int, layout: str, mode: str, out_root: Path) -> tuple[Path, Path]:
    """
    Compute output paths based on layout strategy.
    
    Layouts:
    - nested: out_root/mode/date/YYYY-MM-DD_chunk_NNNN.csv
    - mode-flat: out_root/YYYY-MM-DD_chunk_NNNN.csv
    - flat: out_root_mode_YYYY-MM-DD_chunk_NNNN.csv
    - ymd: out_root/mode/YYYY/MM/DD/YYYY-MM-DD_chunk_NNNN.csv
    
    Returns: (data_path, manifest_path)
    """

def resume_index(date: date, layout: str, mode: str, out_root: Path) -> int:
    """
    Count existing chunks for a date to determine resume point.
    Used to continue after interruption without re-fetching.
    """
```

**Key design**: Layout inference logic is data-driven (string matching). Provides both data and manifest paths atomically.

---

### `runners.py` — Orchestration

**Purpose**: Coordinate the download loop and window iteration.

**Global State**:
```python
stop_requested: bool = False  # Set by SIGINT handler
```

**Functions**:

```python
def run_offset_mode(
    http_config: HttpConfig,
    run_config: RunConfig
) -> None:
    """
    Single paginated download (offset-limit).
    - Loops through 50K-row chunks
    - Respects --max-chunks limit for testing
    - Breaks on stop_requested (SIGINT)
    """

def run_windowed_mode(
    http_config: HttpConfig,
    run_config: RunConfig,
    window_gen: Callable[[date, date], Iterator[tuple[date, date]]]
) -> None:
    """
    Multi-window download loop.
    - Iterates over date windows (daily/weekly/monthly)
    - For each window, calls run_offset_mode()
    - Skips zero-row windows if --preflight enabled
    - Handles resume automatically
    """
```

**Key design**: Generator-based window logic for memory efficiency. Global `stop_requested` flag allows SIGINT to break the loop cleanly.

---

### `logging_utils.py` — Structured Logging

**Purpose**: Provide JSON-formatted structured logs.

**Classes**:

```python
class JsonFormatter(logging.Formatter):
    """
    Custom formatter that outputs ISO8601 timestamp + structured JSON.
    
    Example output:
    {"timestamp": "2025-11-09T02:31:30Z", "level": "INFO", "message": "Downloaded 1024 rows"}
    """

def setup_logging(log_level: int = logging.INFO, log_file: Path | None = None) -> None:
    """
    Configure root logger with console + optional file handler.
    - Console: Always verbose (DEBUG+)
    - File: Respects log_level parameter
    """
```

**Key design**: Structured output enables ELK-stack and Datadog integration for production deployments.

---

### `cli.py` — User Interface

**Purpose**: Parse arguments, infer layout, and orchestrate the download.

**Functions**:

```python
def main(argv: list[str] | None = None) -> None:
    """
    Main CLI entrypoint.
    1. Parse arguments via argparse
    2. Infer layout if not specified
    3. Set up logging
    4. Validate dates
    5. Call appropriate runner (offset or windowed mode)
    6. Handle SIGINT gracefully
    """
```

**Layout Inference**:
```python
if out_root.endswith(mode):
    layout = "mode-flat"  # e.g., --out-root data/raw_daily → mode=daily → mode-flat
else:
    layout = "nested"     # default
```

**Key design**: Single responsibility — just parse and delegate. All logic is in modules below.

---

### `version.py` — Version

**Purpose**: Single source of truth for version number.

```python
__version__ = "0.5.0"
```

Used by:
- `pyproject.toml` (via dynamic versioning)
- `chicago-crime-dl --version`
- Package metadata

---

### `__init__.py` — Public API

**Purpose**: Define the public package interface.

```python
from .version import __version__
from .config import HttpConfig, RunConfig
from .http_client import safe_request, headers_with_token, probe_count_for_day
from .soql import parse_date, soql_params, month_windows, day_windows, week_windows
from .io_utils import write_frame, write_manifest, make_paths, resume_index
from .runners import run_offset_mode, run_windowed_mode
from .logging_utils import JsonFormatter, setup_logging
from .cli import main

__all__ = [
    "__version__",
    "HttpConfig", "RunConfig",
    "safe_request", "headers_with_token", "probe_count_for_day",
    "parse_date", "soql_params", "month_windows", "day_windows", "week_windows",
    "write_frame", "write_manifest", "make_paths", "resume_index",
    "run_offset_mode", "run_windowed_mode",
    "JsonFormatter", "setup_logging",
    "main",
]
```

---

## Execution Flow

### User Command
```bash
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-10 \
  --end-date 2020-01-12 \
  --out-root data/raw_daily
```

### Execution Sequence

```
1. cli.main(argv)
   ├─ Parse arguments → RunConfig
   ├─ Infer layout: "nested" (out-root doesn't end with "daily")
   ├─ setup_logging()
   ├─ Validate dates (parse_date)
   │
   └─ Call run_windowed_mode() with day_windows generator
      │
      ├─ Window 1: (2020-01-10, 2020-01-10)
      │  ├─ If preflight: probe_count_for_day() [HTTP GET with SoQL count]
      │  └─ run_offset_mode()
      │     └─ Loop chunks (offset=0, 50K, 100K, ...)
      │        ├─ safe_request(url, params=soql_params(...))
      │        │  ├─ HTTP GET with headers_with_token()
      │        │  └─ Retry with exponential backoff on 429
      │        ├─ write_frame(df, format="csv")
      │        └─ write_manifest(metadata_dict)
      │
      ├─ Window 2: (2020-01-11, 2020-01-11) [same loop]
      ├─ Window 3: (2020-01-12, 2020-01-12) [same loop]
      │
      └─ Check stop_requested (SIGINT) after each window
```

---

## Testing Strategy

### Unit Tests (18 tests)

Each module has dedicated unit tests with **no I/O or HTTP**:

```
test_headers_with_token.py      # Token loading from env
test_parse_date.py              # Date parsing & clamping (3 tests)
test_parse_date_more.py         # Role-based clamping (2 tests)
test_probe_count_for_day.py      # SoQL query building
test_resume_index.py            # Chunk counting
test_safe_request.py            # Retry logic (2 tests)
test_soql_params.py             # Query parameters (5 tests)
test_stop_requested.py          # SIGINT flag
test_windowed_lazy_dirs.py      # No empty dirs on zero-row
test_write_frame_fallback.py    # Parquet fallback
```

**Patterns**:
- Mock HTTP responses via `FakeResp` fixture
- Mock filesystem with temporary directories
- No external API calls

### Integration Tests (5 tests)

**Real CLI invocation** via `run_cli` fixture:

```
test_integration_429_retry_cli.py      # Rate limit handling
test_integration_daily_one_chunk.py     # Basic daily download
test_integration_daily_zero_rows_no_dir.py  # Zero-row skipping
test_integration_full_resume.py         # Resume after interruption
test_integration_select_projection.py   # Column selection
```

**Pattern**: Mock HTTP layer, run CLI with real argument parsing, validate output.

---

## Code Quality

### Type Checking (mypy)

```
$ mypy chicago_crime_downloader/ --ignore-missing-imports --disable-error-code=import-untyped
Success: no issues found
```

**Type Ignore Pragmas** (known limitations):

```python
# http_client.py:42
return r.json()  # type: ignore[no-any-return]
# Reason: requests.Response.json() returns Any, but we assert list[dict[str, Any]]

# io_utils.py:35
df.to_parquet(path, engine=engine)  # type: ignore[call-overload]
# Reason: pandas type stubs don't capture engine as str | None correctly
```

### Linting (ruff)

```
$ ruff check chicago_crime_downloader/
All checks passed!
```

**Rules**: E (errors), F (Pyflakes), W (warnings), I (import order), UP (upgrades), D (docstrings)

---

## Backward Compatibility

### Legacy Script Shim

`data/download_data_v5.py` (11 lines):

```python
#!/usr/bin/env python3
"""Legacy entry point for backward compatibility."""

import sys
from chicago_crime_downloader.cli import main

if __name__ == "__main__":
    main(sys.argv[1:])
```

**Why**: Existing deployments may call `python data/download_data_v5.py`. Shim ensures compatibility.

---

## Deployment

### Installation

```bash
# PyPI
pip install chicago-crime-downloader

# Development
git clone https://github.com/BayoHabib/chicago_crime_data_cli.git
cd chicago_crime_data_cli
pip install -e ".[dev]"
```

### Console Scripts

```toml
[project.scripts]
chicago-crime-dl = "chicago_crime_downloader.cli:main"
```

Installed as `/usr/local/bin/chicago-crime-dl` or equivalent.

---

## Future Enhancements

Potential improvements for future versions:

1. **Parallel window downloads** — Use `asyncio` or `ThreadPoolExecutor` to parallelize by date window
2. **Streaming JSON output** — Emit NDJSON for real-time consumption
3. **Incremental snapshots** — Auto-detect schema changes and version outputs
4. **S3/GCS upload** — Direct cloud storage writing
5. **Dask/Ray integration** — Distributed processing for 10+ year datasets
6. **Web UI dashboard** — Visualize download progress and data quality

---

## References

- **Socrata Open Data API**: https://dev.socrata.com/
- **Chicago Crime Data**: https://data.cityofchicago.org/api/views/ijzp-q8t2
- **Project Repository**: https://github.com/BayoHabib/chicago_crime_data_cli
- **Contributing**: [CONTRIBUTING.md](../../CONTRIBUTING.md)
