from datetime import date, timedelta

import pytest

from chicago_crime_downloader.soql import week_windows

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2020, 1, 10), date(2020, 1, 10)),
        (date(2020, 1, 8), date(2020, 1, 21)),
        (date(2020, 1, 6), date(2020, 1, 12)),
        (date(2020, 12, 30), date(2021, 1, 5)),
    ],
)
def test_week_windows_cover_only_requested_dates(start, end):
    windows = week_windows(start, end)
    actual_days = [
        window_start + timedelta(days=offset)
        for window_start, window_end, _ in windows
        for offset in range((window_end - window_start).days + 1)
    ]
    expected_days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]

    assert actual_days == expected_days
    assert all(window_start <= window_end for window_start, window_end, _ in windows)


def test_partial_week_keeps_aligned_window_id():
    assert week_windows(date(2020, 1, 10), date(2020, 1, 10)) == [
        (date(2020, 1, 10), date(2020, 1, 10), "2020-W02")
    ]
