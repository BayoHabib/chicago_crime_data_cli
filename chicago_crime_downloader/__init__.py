"""Package public exports."""
from .catalog import collect_manifests, discover_chunks, materialize_duckdb
from .config import (
    BASE_URL,
    DEFAULT_CHUNK,
    DEFAULT_RETRIES,
    DEFAULT_SLEEP,
    DEFAULT_TIMEOUT,
    HttpConfig,
    RunConfig,
)
from .http_client import headers_with_token, probe_count_for_day, safe_request
from .io_utils import (
    ensure_dir,
    make_paths,
    resume_index,
    resume_index_for_layout,
    sha256_of_file,
    write_frame,
    write_manifest,
)
from .logging_utils import JsonFormatter, setup_logging
from .runners import run_offset_mode, run_windowed_mode, stop_requested
from .soql import (
    day_windows,
    month_windows,
    parse_date,
    soql_params,
    soql_params_window,
    week_windows,
)
from .version import __version__

__all__ = [
    "__version__",
    "HttpConfig",
    "RunConfig",
    "BASE_URL",
    "DEFAULT_CHUNK",
    "DEFAULT_TIMEOUT",
    "DEFAULT_RETRIES",
    "DEFAULT_SLEEP",
    "setup_logging",
    "JsonFormatter",
    "headers_with_token",
    "safe_request",
    "probe_count_for_day",
    "parse_date",
    "soql_params",
    "soql_params_window",
    "month_windows",
    "day_windows",
    "week_windows",
    "write_frame",
    "write_manifest",
    "sha256_of_file",
    "ensure_dir",
    "make_paths",
    "resume_index",
    "resume_index_for_layout",
    "discover_chunks",
    "collect_manifests",
    "materialize_duckdb",
    "run_offset_mode",
    "run_windowed_mode",
    "stop_requested",
]
