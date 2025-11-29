diff --git a/README.md b/README.md
index 3a12558f2fe5bdad7febf95a0f5347a9c0857631..db7f8e53056c1503eed9fd3bc8c66721af90d147 100644
--- a/README.md
+++ b/README.md
@@ -1,45 +1,46 @@
 # 📊 Chicago Crime Downloader
 
 [![Test & Lint](https://github.com/BayoHabib/chicago_crime_data_cli/actions/workflows/test.yml/badge.svg)](https://github.com/BayoHabib/chicago_crime_data_cli/actions)
 [![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
 [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
 [![Version](https://img.shields.io/badge/version-0.5.0-green.svg)](https://github.com/BayoHabib/chicago_crime_data_cli/releases/tag/v0.5.0)
 
 Production-ready, modular CLI tool to download Chicago crime data from the **City of Chicago Open Data API** with automatic resumption, retries, and flexible partitioning.
 
 ## 🎯 Key Features
 
 - ✅ **Resumable** — Restart exactly where it left off (tracks chunk index)
 - 🧩 **Modular Architecture** — 9 clean packages with full type hints
 - 🧠 **Smart Preflight** — Detects zero-row days before downloading (saves bandwidth)
 - 📦 **Multiple Formats** — CSV or Parquet (with automatic fallback)
 - � **Cross-Platform** — Windows, macOS, Linux (tested via GitHub Actions)
 - 🔄 **Automatic Retry** — Exponential backoff on rate limits (HTTP 429)
 - 🏷️ **Structured Logs** — JSON manifests with checksums, timing, metadata
 - 🔐 **Token Support** — Socrata API tokens for higher rate limits
 - 🧱 **Reproducible** — Every file has SHA256 hash + parameter tracking
+- 🗜️ **Smaller Outputs** — Optional gzip for CSV and codec selection for Parquet
 
 ---
 
 ## � Installation
 
 ### Requirements
 - **Python 3.11** or higher
 - pip (latest)
 - Optional: `pyarrow` or `fastparquet` for Parquet export
 
 ### From PyPI (Recommended)
 
 ```bash
 pip install chicago-crime-downloader
 chicago-crime-dl --help
 ```
 
 ### From Source
 
 ```bash
 git clone https://github.com/BayoHabib/chicago_crime_data_cli.git
 cd chicago_crime_data_cli
 pip install -e .
 
 # Or with dev dependencies for testing
@@ -109,85 +110,96 @@ chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-31 --ou
 
 # Select specific columns
 chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-01 \
   --select id,date,primary_type,latitude,longitude
 ```
 
 ---
 
 ## 📖 Command-Line Reference
 
 ### Syntax
 
 ```bash
 chicago-crime-dl [OPTIONS]
 ```
 
 ### Core Options
 
 | Option | Type | Default | Description |
 |--------|------|---------|-------------|
 | `--mode` | `full`/`monthly`/`weekly`/`daily` | `full` | Partitioning strategy |
 | `--start-date` | `YYYY-MM-DD` | — | Start of date range |
 | `--end-date` | `YYYY-MM-DD` | — | End of date range (inclusive) |
 | `--out-root` | path | `data/raw` | Output root directory |
 | `--out-format` | `csv`/`parquet` | `csv` | Export format |
+| `--compression` | codec | `none` | `gzip` for CSV; `snappy`/`gzip`/`brotli`/`zstd`/`lz4` for Parquet (engine-dependent) |
 | `--chunk-size` | integer | 50000 | Rows per request |
 | `--max-chunks` | integer | ∞ | Limit chunks per run (for testing) |
 
 ### Advanced Options
 
 | Option | Description |
 |--------|-------------|
 | `--select` | Comma-separated columns: `id,date,primary_type,latitude,longitude` |
 | `--columns-file` | File with column names (one per line) |
 | `--layout` | Directory layout: `nested` (default), `mode-flat`, `flat`, or `ymd` |
 | `--preflight` | Skip days with zero rows (checks via `count(1)` first) |
 | `--log-file` | Path to structured JSON log file |
 
 ### Environment Variables
 
 | Variable | Purpose |
 |----------|---------|
 | `SOC_APP_TOKEN` | Socrata API token (for higher rate limits) |
 | `SOCRATA_APP_TOKEN` | Alternative token variable name |
 
 ---
 
 ## 🗂️ Layout Options
 
 | Layout | Example Output |
 |--------|----------------|
 | **nested** *(default)* | `data/raw_daily/daily/2020-01-10/2020-01-10_chunk_0001.csv` |
 | **mode-flat** | `data/raw_daily/2020-01-10_chunk_0001.csv` |
 | **flat** | `data/raw_daily_daily_2020-01-10_chunk_0001.csv` |
 | **ymd** | `data/raw_daily/daily/2020/01/10/2020-01-10_chunk_0001.csv` |
 
 Automatic inference:
 - If `out-root` ends with mode name (`raw_daily` → daily), uses **mode-flat**.
 - Else defaults to **nested**.
 
+## 💾 Storage tips
+
+- For the smallest footprint and fastest reloads, use **Parquet** with a native engine (`pyarrow` or `fastparquet`).
+- If you need CSV compatibility, enable gzip compression to shrink files dramatically:
+
+```bash
+chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-03 \
+  --out-root ./data/csv_gzip --out-format csv --compression gzip
+```
+
 ---
 
 ## 🔐 API Tokens & Rate Limits
 
 The Socrata API enforces rate limits. Use a free Socrata app token to significantly increase throughput:
 
 **Get a token**: https://data.cityofchicago.org/account/login
 
 **Export it**:
 ```bash
 export SOC_APP_TOKEN="YOUR_APP_TOKEN"
 # or
 export SOCRATA_APP_TOKEN="YOUR_APP_TOKEN"
 ```
 
 **Typical rate limits**:
 - **Without token**: ~300 requests/minute
 - **With token**: ~2000-5000 requests/minute
 
 > **Tip**: Chicago Crime has 500K+ records. With a token, monthly downloads are ~30 seconds. Without, they may take 5+ minutes.
 
 ---
 
 ## 📦 Output Structure & Manifests
 
