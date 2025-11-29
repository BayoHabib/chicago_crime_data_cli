#!/usr/bin/env python3
"""
Compatibility shim: preserve old import path used by tests.

This module re-exports symbols from chicago_crime_downloader and exposes
the old main() entrypoint for backward compatibility.

New code should import directly from chicago_crime_downloader.
"""

from chicago_crime_downloader import *  # noqa: F401, F403
from chicago_crime_downloader.cli import main

if __name__ == "__main__":
    main()
