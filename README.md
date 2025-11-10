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
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Check version
chicago-crime-dl --version

# Show help
chicago-crime-dl --help

# Run tests (if installed with [dev])
pytest -q
```

---

## 🚀 Quick Start

### Download a single day

```bash
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-10 \
  --end-date 2020-01-10 \
  --out-root ./data/raw_daily \
  --out-format csv
```

**Output:**
```
./data/raw_daily/
└── daily/
    └── 2020-01-10/
        ├── 2020-01-10_chunk_0001.csv
        └── 2020-01-10_chunk_0001.manifest.json
```

The manifest contains metadata:
```json
{
  "data_file": "2020-01-10_chunk_0001.csv",
  "rows": 1024,
  "sha256": "eb1a62d0...",
  "params": {"$limit": "50000", "$offset": "0"},
  "started_at": "2025-11-09T02:31:30",
  "duration_seconds": 1.42
}
```

### More Examples

```bash
# Full historical data (all records)
chicago-crime-dl --mode full --out-root ./data/raw --out-format parquet

# Month-by-month for 2020
chicago-crime-dl --mode monthly --start-date 2020-01-01 --end-date 2020-12-31 --out-root ./data/monthly

# Resume interrupted download (auto-detects existing chunks)
chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-31 --out-root ./data/raw_daily

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

Each downloaded chunk gets a JSON manifest sidecar with metadata:

**Example file layout**:
```
data/raw_daily/
├── daily/
│   ├── 2020-01-10/
│   │   ├── 2020-01-10_chunk_0001.csv
│   │   └── 2020-01-10_chunk_0001.manifest.json
│   ├── 2020-01-11/
│   │   ├── 2020-01-11_chunk_0001.csv
│   │   └── 2020-01-11_chunk_0001.manifest.json
```

**Manifest content**:
```json
{
  "data_file": "2020-01-10_chunk_0001.csv",
  "rows": 1024,
  "sha256": "eb1a62d0abc1234...",
  "params": {"$limit": "50000", "$offset": "0"},
  "started_at": "2025-11-09T02:31:30Z",
  "duration_seconds": 1.42,
  "endpoint": "https://data.cityofchicago.org/resource/ijzp-q8t2.json",
  "version": "0.5.0"
}
```

Use manifests to validate downloads or compute checksums in pipelines.

---

## 🧩 Advanced Usage

### Example 1: Monthly Partitioning with Full Year

```bash
chicago-crime-dl \
  --mode monthly \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --out-root data/raw_monthly \
  --out-format parquet
```

Output: 12 months as separate Parquet files in `data/raw_monthly/monthly/{2020-01,2020-02,...,2020-12}/`

### Example 2: Weekly Downloads with Custom Columns

```bash
chicago-crime-dl \
  --mode weekly \
  --start-date 2023-01-01 \
  --end-date 2023-03-31 \
  --select id,date,primary_type,latitude,longitude \
  --out-root data/raw_weekly
```

Output: ~13 weeks of data with only 5 columns to save storage.

### Example 3: Resume After Interruption

If the downloader stops unexpectedly, resume automatically:

```bash
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-01 \
  --end-date 2020-01-10 \
  --out-root data/raw_daily
```

Re-running this command skips existing chunks and continues from where it left off.

### Example 4: Flat Layout for Data Lakes

```bash
chicago-crime-dl \
  --mode daily \
  --start-date 2022-01-01 \
  --end-date 2022-01-31 \
  --layout flat \
  --out-root data/flat
```

Output: All files in a single directory (no nested structure).

### Example 5: Custom Chunk Size for Large Requests

```bash
chicago-crime-dl \
  --mode daily \
  --start-date 2015-01-01 \
  --end-date 2015-01-31 \
  --chunk-size 100000 \
  --out-root data/raw_large_chunks
```

Default is 50K rows/chunk. Larger chunks = faster download but higher memory.

### Example 6: Test Run with Limit

```bash
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-01 \
  --end-date 2020-01-05 \
  --max-chunks 2 \
  --out-root data/test
```

Downloads only first 2 chunks per day (100K rows) for testing pipelines.

---

## � Why Use This Tool?

| Aspect | Manual Downloads | Kaggle | **chicago-crime-dl** |
|--------|------------------|--------|---------------------|
| **Data freshness** | ⏳ Stale (manual) | ⏳ Often outdated | ✅ Real-time (direct API) |
| **Resumable** | ❌ No | ❌ No | ✅ Automatic resume on error |
| **Time windows** | ❌ All or nothing | ❌ All or nothing | ✅ Daily/weekly/monthly windows |
| **Custom columns** | ❌ No | ⚠️ Limited | ✅ Full SoQL `$select` |
| **Rate limiting** | ⚠️ Manual retry | ⚠️ Manual | ✅ Exponential backoff + token auth |
| **Logging** | ❌ None | ⚠️ Limited | ✅ Structured JSON logs + manifests |
| **Integration** | 🔧 Manual scripts | 🔧 Manual | ✅ ETL-ready (Airflow, dbt, etc.) |

**Ideal for**: CI/CD pipelines, ML training loops, data warehouses, reproducible research, and automated reporting.

---

## � Troubleshooting

### 429 Too Many Requests
The tool automatically retries with exponential backoff. If you continue seeing 429s, add an API token:
```bash
export SOC_APP_TOKEN="your_token"
chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-31
```

### Empty Directories Created
Use `--preflight` to skip days with zero records:
```bash
chicago-crime-dl --mode daily --preflight --start-date 2020-01-01 --end-date 2020-01-31
```

### Date Validation Error
Dates must be `YYYY-MM-DD`. The tool auto-corrects invalid days (e.g., April 31 → April 30).

### Parquet Not Writing
Install an engine: `pip install pyarrow` (recommended) or `pip install fastparquet`.

### Resume Not Working
Ensure you use the **same** `--out-root` and `--mode` as the original run. The tool counts existing chunks to determine resume point.

---

## ⚡ Best Practices

1. **Always use an API token** — 10x faster downloads with minimal setup
2. **Keep manifests** — Use JSON manifests for data lineage and validation
3. **Log everything** — Enable `--log-file` for debugging and auditing
4. **Test before production** — Use `--max-chunks 2` to validate pipeline logic
5. **Use mode-flat for orchestration** — Simpler for Airflow DAGs and CI/CD
6. **Parallelize by date** — Run multiple monthly downloads in parallel

Example production setup:
```bash
#!/bin/bash
# Download last 3 months in parallel
chicago-crime-dl --mode monthly --start-date 2024-09-01 --end-date 2024-11-30 \
  --layout mode-flat --log-file logs/download.log &
```

---

## � Documentation

| Document | Purpose |
|----------|---------|
| **[INSTALLATION.md](./INSTALLATION.md)** | Detailed setup guide (5 methods) + troubleshooting |
| **[docs/architecture/ARCHITECTURE.md](./docs/architecture/ARCHITECTURE.md)** | System design, layered architecture |
| **[docs/architecture/API.md](./docs/architecture/API.md)** | Complete API reference |
| **[CHANGELOG.md](./CHANGELOG.md)** | Release history and migration guides |
| **[CONTRIBUTING.md](./CONTRIBUTING.md)** | How to contribute code |
| **[docs/CHICAGO_DATA_RESOURCES.md](./docs/CHICAGO_DATA_RESOURCES.md)** | 40+ available Chicago datasets |
| **[docs/DEVELOPMENT_STRATEGY.md](./docs/DEVELOPMENT_STRATEGY.md)** | Roadmap v0.6.0-v1.0.0 & business plan |
| **[docs/FUTURE_ROADMAP.md](./docs/FUTURE_ROADMAP.md)** | Detailed vision for multi-dataset platform |

---

## �📚 Learn More

- **[Socrata Open Data](https://dev.socrata.com/)** — API documentation
- **[Chicago Crime Data](https://data.cityofchicago.org/api/views/ijzp-q8t2)** — Endpoint details
- **[Contributing](./CONTRIBUTING.md)** — How to contribute
- **[Architecture](./docs/architecture/)** — Design overview

---

## 📝 License & Attribution

**Author:** Habib Bayo  
**License:** [MIT](./LICENSE)  
**Version:** 0.5.0  
**Repository:** [BayoHabib/chicago_crime_data_cli](https://github.com/BayoHabib/chicago_crime_data_cli)
