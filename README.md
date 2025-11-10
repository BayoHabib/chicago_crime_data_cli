# Chicago Crime ETL

[![Test & Lint](https://github.com/BayoHabib/chicago_crime_data_cli/actions/workflows/test.yml/badge.svg)](https://github.com/BayoHabib/chicago_crime_data_cli/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

CLI to download Chicago Crime data from Socrata with resumable chunking, manifests, and flexible layouts.

## Install
```bash
pip install .
# or editable
pip install -e .
# parquet extras
pip install -e .[parquet]
