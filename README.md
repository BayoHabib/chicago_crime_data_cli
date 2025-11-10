# 📊 Chicago Crime Downloader — Command-Line Guide

[![Test & Lint](https://github.com/BayoHabib/chicago_crime_data_cli/actions/workflows/test.yml/badge.svg)](https://github.com/BayoHabib/chicago_crime_data_cli/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Overview

The **Chicago Crime Downloader** is a production-ready, resumable command-line tool to fetch open crime data directly from the **City of Chicago Open Data API** (`ijzp-q8t2`).  
It improves over manual downloads or Kaggle dumps by providing **automatic retries**, **structured manifests**, and **deterministic partitioning (daily, weekly, monthly)** — all from the command line.

Unlike typical one-shot CSV downloads, this tool is:
- ✅ **Resumable** — restarts exactly where it left off.
- 🧩 **Modular** — works in daily, weekly, or monthly windows.
- 🧠 **Smart** — includes preflight checks, structured logs, and JSON manifests.
- ⚙️ **Configurable** — supports CSV or Parquet, user agents, and API tokens.
- 🧱 **Reproducible** — every file has a checksum and metadata manifest.

---

## 🧑‍💻 Installation

### 1️⃣ Requirements

- Python **3.11+**
- pip (latest)
- Optional: install Parquet engine (`pyarrow` or `fastparquet`)

### 2️⃣ Clone and install

CLI to download Chicago Crime data from Socrata with resumable chunking, manifests, and flexible layouts.

```bash
git clone https://github.com/<yourusername>/chicago-crime-downloader.git
cd chicago-crime-downloader
pip install -e .
```

This installs the console command:

```bash
chicago-crime-dl
```

or you can still run it directly as:

```bash
python data/download_data_v5.py
```

---

## ⚡ Quick Start

### Example: Download a single day (CSV)

```bash
chicago-crime-dl --mode daily --start-date 2020-01-10 --end-date 2020-01-10   --out-root data/raw_daily --out-format csv
```

Output:
```
data/raw_daily/daily/2020-01-10/2020-01-10_chunk_0001.csv
data/raw_daily/daily/2020-01-10/2020-01-10_chunk_0001.manifest.json
```

---

## 🧭 Command-Line Reference

### Basic Syntax

```bash
chicago-crime-dl [OPTIONS]
```

or

```bash
python data/download_data_v5.py [OPTIONS]
```

### Key Options

| Option | Description | Example |
|--------|--------------|----------|
| `--mode` | One of `full`, `monthly`, `weekly`, or `daily`. | `--mode daily` |
| `--start-date`, `--end-date` | Restrict downloads to a date range (YYYY-MM-DD). | `--start-date 2020-01-01 --end-date 2020-01-31` |
| `--chunk-size` | Number of rows per request (default: 50,000). | `--chunk-size 100000` |
| `--max-chunks` | Limit chunks in one run (useful for testing). | `--max-chunks 5` |
| `--out-root` | Output directory. | `--out-root data/raw_daily` |
| `--out-format` | `csv` or `parquet`. | `--out-format parquet` |
| `--select` | Comma-separated list of columns. | `--select id,date,primary_type,latitude,longitude` |
| `--columns-file` | Path to file listing columns (one per line). | `--columns-file columns.txt` |
| `--layout` | Directory layout: `nested`, `mode-flat`, `flat`, or `ymd`. | `--layout nested` |
| `--preflight` | Skips days with 0 rows (uses API `count(1)` precheck). | `--preflight` |

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

## 🔐 API Tokens

For higher rate limits, export a Socrata token:

```bash
export SOC_APP_TOKEN="YOUR_APP_TOKEN"
# or
export SOCRATA_APP_TOKEN="YOUR_APP_TOKEN"
```

Without a token, the downloader still works, but with limited speed.

---

## 🧾 Output Manifest Example

Each data file has a sidecar manifest with metadata:

```json
{
  "data_file": "2020-01-10_chunk_0001.csv",
  "rows": 1024,
  "sha256": "eb1a62d0...",
  "params": {"$limit": "50000", "$offset": "0"},
  "started_at": "2025-11-09T02:31:30",
  "duration_seconds": 1.42,
  "endpoint": "https://data.cityofchicago.org/resource/ijzp-q8t2.json",
  "version": 5
}
```

---

## 🧩 Advanced Examples

### 1️⃣ Monthly mode
```bash
chicago-crime-dl --mode monthly --start-date 2020-01-01 --end-date 2020-12-31   --out-root data/raw_monthly
```

### 2️⃣ Weekly mode
```bash
chicago-crime-dl --mode weekly --start-date 2020-01-01 --end-date 2020-03-31   --out-root data/raw_weekly
```

### 3️⃣ Full historical data
```bash
chicago-crime-dl --mode full --out-root data/raw_full --out-format parquet
```

### 4️⃣ Resume after interruption
```bash
chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-05   --out-root data/raw_daily
```
Resumes automatically by skipping existing chunks.

### 5️⃣ Select only specific columns
```bash
chicago-crime-dl --mode daily --start-date 2020-02-01 --end-date 2020-02-01   --select id,date,primary_type,latitude,longitude
```

---

## 🧠 Why Use This Tool Instead of Manual Downloads?

| Feature | Manual CSV Download | Kaggle Dataset | **This CLI Tool** |
|----------|--------------------|----------------|------------------|
| Up-to-date | ❌ Static | ❌ Often outdated | ✅ Always current (direct API) |
| Resumable | ❌ No | ❌ No | ✅ Yes |
| Incremental | ❌ No | ❌ No | ✅ Daily / Weekly / Monthly windows |
| Custom Columns | ❌ No | ✅ Somewhat | ✅ Full SoQL `$select` support |
| Parallelization | ❌ Manual | ❌ Manual | ✅ Built-in window logic |
| Logging | ❌ None | ✅ Some | ✅ Full structured logs + manifests |
| Robustness | ❌ Fragile | ⚠️ | ✅ Retries + backoff + token auth |
| Integration | ❌ | ❌ | ✅ Perfect for ETL / Airflow / Kubeflow / ML pipelines |

This makes it ideal for **data science pipelines**, **ETL automation**, and **reproducible analysis**.

---

## 🛠️ Troubleshooting

| Issue | Fix |
|-------|-----|
| **429 Too Many Requests** | Tool waits and retries automatically (exponential backoff). |
| **Empty folders** | Enable `--preflight` to skip days with zero data. |
| **Date format error** | Use `YYYY-MM-DD`; tool will auto-fix invalid days (e.g. April 31 → April 30). |
| **Parquet not written** | Install an engine: `pip install pyarrow` or `pip install fastparquet`. |

---

## ✅ Best Practices

- Always use API token for stable throughput.
- Keep logs (`--log-file`) and manifests for reproducibility.
- For production, prefer **mode-flat** layout for easier orchestration.
- Run tests regularly:
  ```bash
  pytest -m unit -q
  pytest -m integration -q
  ```

---

**Author:** Habib Bayo  
**License:** MIT  
**Version:** 5.0  
**Repository:** [https://github.com/<yourusername>/chicago-crime-downloader](https://github.com/<yourusername>/chicago-crime-downloader)
