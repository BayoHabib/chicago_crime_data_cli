# Public API Reference

## Overview

The `chicago_crime_downloader` package provides a modular API for building custom download pipelines beyond the CLI.

```python
from chicago_crime_downloader import (
    HttpConfig, RunConfig,
    safe_request, headers_with_token, probe_count_for_day,
    parse_date, soql_params, month_windows, day_windows, week_windows,
    write_frame, write_manifest, make_paths, resume_index,
    run_offset_mode, run_windowed_mode,
    JsonFormatter, setup_logging,
    main,
)
```

---

## Configuration Classes

### `HttpConfig`

```python
@dataclass
class HttpConfig:
    timeout: int = 30
    retries: int = 5
    sleep: float = 0.1
    user_agent: str = "chicago-crime-downloader/0.5.0"
```

**Purpose**: HTTP request configuration.

**Attributes**:
- `timeout`: Request timeout in seconds (default: 30)
- `retries`: Number of retry attempts on 429 rate limit (default: 5)
- `sleep`: Base sleep duration for exponential backoff (default: 0.1 seconds)
- `user_agent`: Custom User-Agent header

**Example**:
```python
config = HttpConfig(timeout=60, retries=10, sleep=0.5)
```

---

### `RunConfig`

```python
@dataclass
class RunConfig:
    mode: Literal["full", "monthly", "weekly", "daily"]
    start_date: date | None = None
    end_date: date | None = None
    out_root: Path = Path("data/raw")
    out_format: Literal["csv", "parquet"] = "csv"
    chunk_size: int = 50000
    max_chunks: int | None = None
    select: str | None = None
    columns_file: Path | None = None
    layout: str = "nested"
    preflight: bool = False
    log_file: Path | None = None
```

**Purpose**: Download run configuration.

**Attributes**:
- `mode`: Partitioning strategy (`full`, `monthly`, `weekly`, or `daily`)
- `start_date`: Start of date range (optional)
- `end_date`: End of date range (inclusive, optional)
- `out_root`: Output directory root (default: `data/raw`)
- `out_format`: Output format (`csv` or `parquet`, default: `csv`)
- `chunk_size`: Rows per request (default: 50,000)
- `max_chunks`: Maximum chunks per window (optional, for testing)
- `select`: Comma-separated SoQL columns to select (optional)
- `columns_file`: File path with column names, one per line (optional)
- `layout`: Directory layout strategy (`nested`, `mode-flat`, `flat`, `ymd`, default: `nested`)
- `preflight`: Skip zero-row days with `count(1)` query (default: `False`)
- `log_file`: Path to structured JSON log file (optional)

**Example**:
```python
from datetime import date
from pathlib import Path

config = RunConfig(
    mode="daily",
    start_date=date(2020, 1, 1),
    end_date=date(2020, 1, 31),
    out_root=Path("data/raw_daily"),
    out_format="parquet",
    preflight=True,
    log_file=Path("logs/download.log"),
)
```

---

## HTTP Functions

### `safe_request(url, **kwargs) -> list[dict[str, Any]]`

```python
def safe_request(
    url: str,
    params: dict[str, str] | None = None,
    **kwargs
) -> list[dict[str, Any]]:
```

Perform HTTP GET request with automatic retry on rate limits.

**Parameters**:
- `url`: Full URL endpoint
- `params`: Query parameters dict (optional)
- `**kwargs`: Additional arguments passed to `requests.get()` (e.g., `headers`, `timeout`)

**Returns**: Parsed JSON as `list[dict[str, Any]]`

**Raises**: 
- `HTTPError`: On non-429 errors after retries
- `Timeout`: On timeout

**Behavior**:
- Automatically retries on HTTP 429 (Too Many Requests)
- Exponential backoff: $T = 2^{attempt} \times \text{HttpConfig.sleep}$
- Respects `HttpConfig.timeout` and `HttpConfig.retries`
- Sets `User-Agent` header

**Example**:
```python
from chicago_crime_downloader import safe_request

url = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
params = {"$limit": "1000", "$offset": "0"}

data = safe_request(url, params=params)
print(f"Got {len(data)} rows")
```

---

### `headers_with_token() -> dict[str, str]`

```python
def headers_with_token() -> dict[str, str]:
```

Build HTTP headers with optional Socrata API token.

**Returns**: Dictionary of headers (`User-Agent`, `Authorization` if token found)

**Behavior**:
- Checks environment variables `SOC_APP_TOKEN` and `SOCRATA_APP_TOKEN` (in order)
- If found, adds `Authorization: Basic <token>` header
- If not found, returns only `User-Agent` header

**Example**:
```python
import os
from chicago_crime_downloader import headers_with_token

os.environ["SOC_APP_TOKEN"] = "abc123def456"
headers = headers_with_token()
print(headers)
# Output: {"User-Agent": "chicago-crime-downloader/0.5.0", "Authorization": "Basic abc123def456"}
```

---

### `probe_count_for_day(date: date) -> int`

```python
def probe_count_for_day(date: date) -> int:
```

Query API for row count on a specific day (preflight check).

**Parameters**:
- `date`: Date to query (datetime.date object)

**Returns**: Row count for that day

**Behavior**:
- Constructs SoQL `count(1)` query
- Uses `safe_request()` with exponential backoff
- Returns 0 if day has no records

**Example**:
```python
from datetime import date
from chicago_crime_downloader import probe_count_for_day

count = probe_count_for_day(date(2020, 1, 10))
print(f"2020-01-10 has {count} crime records")
```

---

## Query Building Functions

### `parse_date(date_str: str) -> date`

```python
def parse_date(date_str: str) -> date:
```

Parse ISO 8601 date string with automatic end-of-month clamping.

**Parameters**:
- `date_str`: Date string in `YYYY-MM-DD` format

**Returns**: `datetime.date` object

**Raises**: `ValueError` if format is invalid

**Behavior**:
- Parses `YYYY-MM-DD` strictly
- Auto-clamps invalid day-of-month to EOM (e.g., April 31 → April 30)
- Raises on invalid year/month

**Example**:
```python
from chicago_crime_downloader import parse_date

d1 = parse_date("2020-01-15")  # Returns: date(2020, 1, 15)
d2 = parse_date("2020-04-31")  # Returns: date(2020, 4, 30) [auto-clamp]

try:
    d3 = parse_date("2020-13-01")  # Raises: ValueError
except ValueError:
    print("Invalid month!")
```

---

### `soql_params(offset: int, limit: int, select: str | None = None) -> dict[str, str]`

```python
def soql_params(
    offset: int,
    limit: int,
    select: str | None = None
) -> dict[str, str]:
```

Build SoQL query parameters for offset-based pagination.

**Parameters**:
- `offset`: Number of rows to skip (0-based)
- `limit`: Number of rows to return
- `select`: Comma-separated column names (optional)

**Returns**: Dictionary of SoQL parameters

**Example**:
```python
from chicago_crime_downloader import soql_params

params = soql_params(0, 1000, select="id,date,primary_type")
print(params)
# Output: {'$offset': '0', '$limit': '1000', '$select': 'id,date,primary_type'}
```

---

### `month_windows(start: date, end: date) -> Iterator[tuple[date, date]]`

```python
def month_windows(
    start: date,
    end: date
) -> Iterator[tuple[date, date]]:
```

Generate monthly time windows from start to end date (inclusive).

**Parameters**:
- `start`: Start date
- `end`: End date

**Yields**: Tuples of (window_start, window_end) for each month

**Example**:
```python
from datetime import date
from chicago_crime_downloader import month_windows

for start, end in month_windows(date(2020, 1, 15), date(2020, 3, 10)):
    print(f"{start} to {end}")
# Output:
# 2020-01-15 to 2020-01-31
# 2020-02-01 to 2020-02-29
# 2020-03-01 to 2020-03-10
```

---

### `day_windows(start: date, end: date) -> Iterator[tuple[date, date]]`

```python
def day_windows(
    start: date,
    end: date
) -> Iterator[tuple[date, date]]:
```

Generate daily time windows from start to end date (inclusive).

**Parameters**:
- `start`: Start date
- `end`: End date

**Yields**: Tuples of (window_start, window_end) for each day

**Example**:
```python
from datetime import date
from chicago_crime_downloader import day_windows

for start, end in day_windows(date(2020, 1, 1), date(2020, 1, 3)):
    print(f"{start}")
# Output:
# 2020-01-01
# 2020-01-02
# 2020-01-03
```

---

### `week_windows(start: date, end: date) -> Iterator[tuple[date, date]]`

```python
def week_windows(
    start: date,
    end: date
) -> Iterator[tuple[date, date]]:
```

Generate weekly time windows starting on Mondays.

**Parameters**:
- `start`: Start date
- `end`: End date

**Yields**: Tuples of (window_start, window_end) for each Monday-Sunday week

**Example**:
```python
from datetime import date
from chicago_crime_downloader import week_windows

for start, end in week_windows(date(2020, 1, 6), date(2020, 1, 20)):
    print(f"{start} to {end}")
# Output:
# 2020-01-06 to 2020-01-12 (Mon-Sun)
# 2020-01-13 to 2020-01-19 (Mon-Sun)
```

---

## File I/O Functions

### `write_frame(df: pd.DataFrame, out_path: Path, format: Literal["csv", "parquet"]) -> None`

```python
def write_frame(
    df: pd.DataFrame,
    out_path: Path,
    format: Literal["csv", "parquet"]
) -> None:
```

Write pandas DataFrame to file with automatic fallback.

**Parameters**:
- `df`: DataFrame to write
- `out_path`: Output file path (`.csv` or `.parquet`)
- `format`: Output format (`csv` or `parquet`)

**Behavior**:
- CSV: Always works (uses pandas built-in)
- Parquet: Tries `pyarrow`, falls back to CSV if no engine installed
- Creates parent directories if missing

**Raises**: `IOError` on write failure

**Example**:
```python
import pandas as pd
from pathlib import Path
from chicago_crime_downloader import write_frame

df = pd.DataFrame({"id": [1, 2, 3], "date": ["2020-01-01"] * 3})

# Write as CSV
write_frame(df, Path("output.csv"), "csv")

# Write as Parquet (or fallback to CSV)
write_frame(df, Path("output.parquet"), "parquet")
```

---

### `write_manifest(manifest_dict: dict, manifest_path: Path) -> None`

```python
def write_manifest(
    manifest_dict: dict,
    manifest_path: Path
) -> None:
```

Write JSON manifest sidecar file with download metadata.

**Parameters**:
- `manifest_dict`: Metadata dict (rows, SHA256, params, timing, etc.)
- `manifest_path`: Output file path (`.manifest.json`)

**Behavior**:
- Writes pretty-printed JSON (indentation 2)
- Creates parent directories if missing
- Atomic write (no partial files on crash)

**Example manifest**:
```json
{
  "data_file": "2020-01-10_chunk_0001.csv",
  "rows": 1024,
  "sha256": "eb1a62d0abc123...",
  "params": {"$limit": "50000", "$offset": "0"},
  "started_at": "2025-11-09T02:31:30Z",
  "duration_seconds": 1.42,
  "endpoint": "https://data.cityofchicago.org/resource/ijzp-q8t2.json",
  "version": "0.5.0"
}
```

---

### `make_paths(date: date, chunk_idx: int, layout: str, mode: str, out_root: Path) -> tuple[Path, Path]`

```python
def make_paths(
    date: date,
    chunk_idx: int,
    layout: str,
    mode: str,
    out_root: Path
) -> tuple[Path, Path]:
```

Compute output paths based on layout strategy.

**Parameters**:
- `date`: Date for this chunk
- `chunk_idx`: Chunk index (0-based)
- `layout`: Layout strategy (`nested`, `mode-flat`, `flat`, `ymd`)
- `mode`: Partitioning mode (`daily`, `weekly`, `monthly`, `full`)
- `out_root`: Output root directory

**Returns**: Tuple of (data_path, manifest_path)

**Layout Examples** (with `out_root=data/raw`, `mode=daily`, `date=2020-01-10`, `chunk_idx=0`):

| Layout | Data Path | Manifest Path |
|--------|-----------|---------------|
| `nested` | `data/raw/daily/2020-01-10/2020-01-10_chunk_0001.csv` | `...manifest.json` |
| `mode-flat` | `data/raw/2020-01-10_chunk_0001.csv` | `...manifest.json` |
| `flat` | `data/raw_daily_2020-01-10_chunk_0001.csv` | `...manifest.json` |
| `ymd` | `data/raw/daily/2020/01/10/2020-01-10_chunk_0001.csv` | `...manifest.json` |

**Example**:
```python
from datetime import date
from pathlib import Path
from chicago_crime_downloader import make_paths

data_path, manifest_path = make_paths(
    date=date(2020, 1, 10),
    chunk_idx=0,
    layout="nested",
    mode="daily",
    out_root=Path("data/raw")
)
print(data_path)       # data/raw/daily/2020-01-10/2020-01-10_chunk_0001.csv
print(manifest_path)   # data/raw/daily/2020-01-10/2020-01-10_chunk_0001.manifest.json
```

---

### `resume_index(date: date, layout: str, mode: str, out_root: Path) -> int`

```python
def resume_index(
    date: date,
    layout: str,
    mode: str,
    out_root: Path
) -> int:
```

Count existing chunks for a date to determine resume point.

**Parameters**:
- `date`: Date to check
- `layout`: Layout strategy
- `mode`: Partitioning mode
- `out_root`: Output root directory

**Returns**: Number of existing chunks (0 if none found)

**Example**:
```python
from datetime import date
from pathlib import Path
from chicago_crime_downloader import resume_index

# After downloading 3 chunks for 2020-01-10
idx = resume_index(
    date=date(2020, 1, 10),
    layout="nested",
    mode="daily",
    out_root=Path("data/raw")
)
print(idx)  # 3 (next chunk will be 0004)
```

---

## Runner Functions

### `run_offset_mode(http_config: HttpConfig, run_config: RunConfig) -> None`

```python
def run_offset_mode(
    http_config: HttpConfig,
    run_config: RunConfig
) -> None:
```

Single paginated download with offset-limit pagination.

**Parameters**:
- `http_config`: HTTP configuration
- `run_config`: Run configuration (includes date range for WHERE clause)

**Behavior**:
- Loops through chunks (offset=0, 50K, 100K, ...) until no more rows
- Respects `--max-chunks` limit
- Breaks on `stop_requested` flag (SIGINT)
- Writes CSV/Parquet + manifest for each chunk

**Example**:
```python
from datetime import date
from chicago_crime_downloader import HttpConfig, RunConfig, run_offset_mode

http_config = HttpConfig(timeout=60, retries=5)
run_config = RunConfig(
    mode="daily",
    start_date=date(2020, 1, 10),
    end_date=date(2020, 1, 10),
    out_root=Path("data/raw")
)

run_offset_mode(http_config, run_config)
```

---

### `run_windowed_mode(http_config: HttpConfig, run_config: RunConfig, window_gen: Callable[[date, date], Iterator[tuple[date, date]]]) -> None`

```python
def run_windowed_mode(
    http_config: HttpConfig,
    run_config: RunConfig,
    window_gen: Callable[[date, date], Iterator[tuple[date, date]]]
) -> None:
```

Multi-window download orchestration.

**Parameters**:
- `http_config`: HTTP configuration
- `run_config`: Run configuration
- `window_gen`: Window generator (e.g., `day_windows`, `month_windows`)

**Behavior**:
- Iterates over date windows
- For each window, calls `run_offset_mode()`
- Skips zero-row windows if `preflight=True`
- Handles resume automatically (skips existing chunks)
- Breaks on `stop_requested` flag (SIGINT)

**Example**:
```python
from datetime import date
from chicago_crime_downloader import (
    HttpConfig, RunConfig, run_windowed_mode, day_windows
)

http_config = HttpConfig(timeout=60)
run_config = RunConfig(
    mode="daily",
    start_date=date(2020, 1, 1),
    end_date=date(2020, 1, 10),
    out_root=Path("data/raw_daily"),
    preflight=True  # Skip zero-row days
)

run_windowed_mode(http_config, run_config, day_windows)
```

---

## Logging Functions

### `JsonFormatter`

```python
class JsonFormatter(logging.Formatter):
```

Custom logging formatter for structured JSON output.

**Features**:
- ISO 8601 timestamps (`2025-11-09T02:31:30Z`)
- Structured JSON with `level`, `message`, `timestamp` fields
- Compatible with ELK Stack, Datadog, CloudWatch

**Example**:
```python
import logging
from chicago_crime_downloader import JsonFormatter

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)

logger.info("Starting download", extra={"date": "2020-01-10"})
# Output: {"timestamp": "2025-11-09T02:31:30Z", "level": "INFO", "message": "Starting download", "date": "2020-01-10"}
```

---

### `setup_logging(log_level: int = logging.INFO, log_file: Path | None = None) -> None`

```python
def setup_logging(
    log_level: int = logging.INFO,
    log_file: Path | None = None
) -> None:
```

Configure root logger with console and optional file handlers.

**Parameters**:
- `log_level`: Logging level (default: `logging.INFO`)
- `log_file`: Optional file path for file handler

**Behavior**:
- Console handler: Always DEBUG+ (verbose)
- File handler (if provided): Respects `log_level`
- Both use `JsonFormatter`

**Example**:
```python
from pathlib import Path
from chicago_crime_downloader import setup_logging

setup_logging(log_level=logging.DEBUG, log_file=Path("logs/download.log"))
```

---

## CLI Function

### `main(argv: list[str] | None = None) -> None`

```python
def main(argv: list[str] | None = None) -> None:
```

Main CLI entrypoint with argument parsing.

**Parameters**:
- `argv`: Command-line arguments (default: `sys.argv[1:]`)

**Behavior**:
1. Parse arguments via argparse
2. Infer layout if not specified
3. Setup logging
4. Validate dates
5. Call appropriate runner (offset or windowed mode)
6. Handle SIGINT gracefully

**Example**:
```python
from chicago_crime_downloader import main

# Programmatically call CLI
main(["--mode", "daily", "--start-date", "2020-01-01", "--end-date", "2020-01-31"])

# Or from shell
# $ chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-31
```

---

## Custom Pipeline Example

```python
from datetime import date
from pathlib import Path
from chicago_crime_downloader import (
    HttpConfig, RunConfig, run_windowed_mode, day_windows, setup_logging
)
import logging

# Setup logging
setup_logging(
    log_level=logging.DEBUG,
    log_file=Path("logs/custom_pipeline.log")
)

# Configure HTTP
http_config = HttpConfig(
    timeout=60,
    retries=10,
    sleep=0.5  # Longer backoff for stability
)

# Configure run
run_config = RunConfig(
    mode="daily",
    start_date=date(2015, 1, 1),
    end_date=date(2015, 12, 31),
    out_root=Path("data/raw_2015"),
    out_format="parquet",
    select="id,date,primary_type,latitude,longitude",  # Save space
    layout="mode-flat",  # Flat for data lake
    preflight=True,  # Skip zero-row days
    log_file=Path("logs/download.log")
)

# Run
run_windowed_mode(http_config, run_config, day_windows)

print("Download complete!")
```

---

## Error Handling

All functions may raise the following exceptions:

| Exception | Cause | Handling |
|-----------|-------|----------|
| `HTTPError` | HTTP error after retries | Catch and log, consider resuming |
| `Timeout` | Request timeout | Check network, retry with longer timeout |
| `ValueError` | Invalid date format or parameters | Validate inputs before calling |
| `IOError` | File write failure | Check disk space and permissions |
| `KeyError` | Missing environment variables | Set `SOC_APP_TOKEN` if needed |

**Example**:
```python
try:
    from chicago_crime_downloader import safe_request
    data = safe_request("https://api.example.com/data", params={"$limit": "1000"})
except Timeout:
    print("Request timed out")
except HTTPError as e:
    print(f"HTTP error: {e.response.status_code}")
```

---

## References

- **Module Documentation**: See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **GitHub Repository**: https://github.com/BayoHabib/chicago_crime_data_cli
- **Socrata API**: https://dev.socrata.com/
