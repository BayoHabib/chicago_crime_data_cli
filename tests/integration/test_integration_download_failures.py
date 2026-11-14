import json

import pytest
import requests

import chicago_crime_downloader.cli as cli
import chicago_crime_downloader.runners as runners

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_stop_flag(monkeypatch):
    monkeypatch.setattr(runners, "stop_requested", False)
    monkeypatch.setattr("time.sleep", lambda seconds: None)


def response(status, payload=None):
    result = requests.Response()
    result.status_code = status
    result.url = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
    result.headers["Retry-After"] = "0"
    result._content = json.dumps([] if payload is None else payload).encode()
    return result


def arguments(tmp_path, mode, *, preflight=False):
    argv = [
        "--mode", mode,
        "--start-date", "2020-01-10",
        "--end-date", "2020-01-10",
        "--out-root", str(tmp_path / "raw"),
        "--max-retries", "2",
        "--sleep", "0",
    ]
    if preflight:
        argv.append("--preflight")
    return argv


@pytest.mark.parametrize("mode", ["full", "daily", "weekly", "monthly", "preflight"])
@pytest.mark.parametrize("failure", [400, 500, 429, "timeout"])
def test_cli_download_failure_exits_nonzero(tmp_path, monkeypatch, mode, failure):
    calls = []

    def failing_get(*args, **kwargs):
        calls.append(kwargs["params"])
        if failure == "timeout":
            raise requests.Timeout("simulated timeout")
        return response(failure)

    def unexpected_materialization(*args, **kwargs):
        pytest.fail("failed downloads must not trigger materialization")

    monkeypatch.setattr(requests, "get", failing_get)
    monkeypatch.setattr(cli, "_materialize_from_args", unexpected_materialization)
    argv = arguments(tmp_path, "daily" if mode == "preflight" else mode,
                     preflight=mode == "preflight")
    argv.extend(["--materialize-duckdb", str(tmp_path / "warehouse.duckdb")])

    with pytest.raises(SystemExit) as error:
        cli.main(argv)

    assert error.value.code == 1
    assert len(calls) == 2
    assert not list(tmp_path.rglob("*.csv"))
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("mode", ["full", "daily", "preflight"])
def test_empty_successful_response_is_not_an_error(tmp_path, monkeypatch, mode):
    payload = [{"count_1": "0"}] if mode == "preflight" else []
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response(200, payload))

    cli.main(arguments(tmp_path, "daily" if mode == "preflight" else mode,
                       preflight=mode == "preflight"))

    assert not list(tmp_path.rglob("*.csv"))


@pytest.mark.parametrize("mode", ["full", "daily"])
def test_failure_preserves_completed_chunks(tmp_path, monkeypatch, mode):
    def get_first_chunk_then_fail(*args, **kwargs):
        if kwargs["params"]["$offset"] == "0":
            return response(200, [{"id": "1", "date": "2020-01-10T12:00:00.000"}])
        return response(500)

    monkeypatch.setattr(requests, "get", get_first_chunk_then_fail)
    argv = arguments(tmp_path, mode) + ["--chunk-size", "1"]

    with pytest.raises(SystemExit) as error:
        cli.main(argv)

    assert error.value.code == 1
    chunks = list(tmp_path.rglob("*.csv"))
    manifests = list(tmp_path.rglob("*.manifest.json"))
    assert len(chunks) == len(manifests) == 1
    assert json.loads(manifests[0].read_text())["rows"] == 1


def test_weekly_cli_sends_only_requested_dates(tmp_path, monkeypatch):
    queries = []

    def capture_query(*args, **kwargs):
        queries.append(kwargs["params"])
        return response(200)

    monkeypatch.setattr(requests, "get", capture_query)

    cli.main(arguments(tmp_path, "weekly"))

    assert len(queries) == 1
    assert queries[0]["$where"] == (
        "date >= '2020-01-10T00:00:00.000' AND date < '2020-01-11T00:00:00.000'"
    )
