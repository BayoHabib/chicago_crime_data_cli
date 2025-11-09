# Chicago Crime ETL

CLI to download Chicago Crime data from Socrata with resumable chunking, manifests, and flexible layouts.

## Install
```bash
pip install .
# or editable
pip install -e .
# parquet extras
pip install -e .[parquet]
🧭 Command-Line Usage
1️⃣ Basic Syntax
chicago-crime-dl [OPTIONS]


or equivalently (legacy):

python data/download_data_v5.py [OPTIONS]

2️⃣ Main Options
Option	Description	Example
--mode	Defines the download mode. One of: full, monthly, weekly, or daily.	--mode daily
--start-date, --end-date	Restrict downloads to a date range (YYYY-MM-DD).	--start-date 2020-01-01 --end-date 2020-01-31
--chunk-size	Number of rows per chunk (default: 50,000).	--chunk-size 100000
--max-chunks	Limit the number of chunks for one run (full mode only).	--max-chunks 10
--out-root	Root folder for output data.	--out-root data/raw_daily
--out-format	Output format: csv or parquet.	--out-format parquet
--select	Comma-separated list of columns to fetch.	--select id,date,primary_type,latitude,longitude
--columns-file	Text file listing column names (one per line).	--columns-file columns.txt
--layout	Directory layout: nested, mode-flat, flat, ymd. (Optional — inferred automatically.)	--layout mode-flat
3️⃣ Layout Modes
Layout	Example Output Path (for --mode daily, --out-root data/raw_daily)
nested (default)	data/raw_daily/daily/2020-01-10/2020-01-10_chunk_0001.csv
mode-flat	data/raw_daily/2020-01-10_chunk_0001.csv
flat	data/raw_daily_daily_2020-01-10_chunk_0001.csv
ymd	data/raw_daily/daily/2020/01/10/2020-01-10_chunk_0001.csv

When not specified, layout is inferred:

If out-root ends with the mode name (e.g. raw_daily), use mode-flat.

Otherwise, default to nested.

4️⃣ HTTP Options
Option	Description	Default
--http-timeout	Timeout per request (seconds).	300
--max-retries	Max retry attempts on failure.	4
--sleep	Delay (seconds) between chunks to stay polite.	1.0
--user-agent	Custom user agent string.	"crime-downloader/1.0 (+mlops)"

You can also set an environment variable for higher rate limits:

export SOC_APP_TOKEN="YOUR_APP_TOKEN"
# or
export SOCRATA_APP_TOKEN="YOUR_APP_TOKEN"

5️⃣ Logging
Option	Description
--log-file	Save logs to a file.
--log-json	Emit logs as structured JSON (useful for monitoring).

Example:

chicago-crime-dl --mode daily --start-date 2020-01-10 --end-date 2020-01-10 \
  --out-root data/raw_daily --log-file logs/dl_2020-01-10.log --log-json

6️⃣ Preflight Checks
Flag	Description
--preflight	Enables a per-day check (count(1)) before downloading. Skips days with 0 rows published.

This makes daily or backtesting jobs faster by avoiding empty days.

7️⃣ Examples
🟢 Full dataset (resumable)
chicago-crime-dl --mode full --out-root data/raw_full --out-format parquet

🟢 Monthly chunks for 2020
chicago-crime-dl --mode monthly --start-date 2020-01-01 --end-date 2020-12-31 --out-root data/raw_monthly

🟢 Weekly data (Jan–Mar 2020)
chicago-crime-dl --mode weekly --start-date 2020-01-01 --end-date 2020-03-31 --out-root data/raw_weekly

🟢 Daily downloads with column selection
chicago-crime-dl --mode daily --start-date 2020-01-10 --end-date 2020-01-12 \
  --out-root data/raw_daily --select id,date,primary_type,latitude,longitude

🟢 Resume after interruption

Re-run the same command — existing chunks are skipped automatically:

chicago-crime-dl --mode daily --start-date 2020-01-10 --end-date 2020-01-12 \
  --out-root data/raw_daily

8️⃣ Output Structure

Each run produces:

Data file(s): *.csv or *.parquet

Manifest file(s): JSON metadata for each chunk

{
  "data_file": "2020-01-10_chunk_0001.csv",
  "rows": 1024,
  "sha256": "...",
  "params": {"$limit": "50000", "$offset": "0"},
  "started_at": "2025-11-09T02:31:30",
  "duration_seconds": 1.42,
  "endpoint": "https://data.cityofchicago.org/resource/ijzp-q8t2.json",
  "version": 5
}

9️⃣ Troubleshooting
Issue	Fix
Rate limit (429)	Tool automatically retries with exponential backoff. You can reduce --chunk-size or add --sleep.
Empty output	Try --preflight to check if data exists for those dates.
Invalid date	Tool will adjust invalid days (e.g. 2020-04-31 → 2020-04-30) and log a warning.
Parquet not written	Install an engine: pip install pyarrow or pip install fastparquet. Otherwise falls back to CSV.
🔍 Summary for Users

Use --mode to control time granularity (full/monthly/weekly/daily).

Use --layout to control folder structure (nested vs flat).

Use --select or --columns-file to limit columns for speed.

Use --preflight to skip empty days.

Logs + manifests ensure reproducibility and resumability.
