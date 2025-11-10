"""SoQL helpers: date parsing, bounds, parameter builders for offset and windowed modes."""
from __future__ import annotations

import calendar
import logging
import re
from datetime import date, datetime, timedelta


def _last_day_of_month(y: int, m: int) -> int:
    """Get last day of month."""
    return calendar.monthrange(y, m)[1]


def parse_date(d: str | None, *, role: str = "date") -> date | None:
    """Parse YYYY-MM-DD with end-of-month clamp and informative warning."""
    if not d:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        raise ValueError(f"Invalid {role!r} format {d!r}. Expected YYYY-MM-DD.")
    y, m, day = map(int, d.split("-"))
    last = _last_day_of_month(y, m)
    if day > last:
        logging.warning(
            f"⚠️  {role} {d} is out of range; using {y:04d}-{m:02d}-{last:02d} instead."
        )
        day = last
    return date(y, m, day)


def _soql_day_bounds(d: date) -> tuple[str, str]:
    """Return ISO8601 strings WITHOUT timezone for a half-open day window."""
    start = f"{d:%Y-%m-%d}T00:00:00.000"
    end_next = f"{(d + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
    return start, end_next


def soql_params(
    offset: int,
    limit: int,
    start_date: str | None,
    end_date: str | None,
    select: str | None,
) -> dict[str, str]:
    """Build SoQL parameters for offset-based pagination."""
    params = {"$limit": str(limit), "$offset": str(offset), "$order": "date desc"}
    if select:
        params["$select"] = select
    if start_date and end_date:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        s_iso, _ = _soql_day_bounds(sd)
        e_next_iso = f"{(ed + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
        params["$where"] = f"date >= '{s_iso}' AND date < '{e_next_iso}'"
    elif start_date:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        s_iso, _ = _soql_day_bounds(sd)
        params["$where"] = f"date >= '{s_iso}'"
    elif end_date:
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        e_next_iso = f"{(ed + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
        params["$where"] = f"date < '{e_next_iso}'"
    return params


def soql_params_window(
    offset: int,
    limit: int,
    start_d: date,
    end_d: date,
    select: str | None,
) -> dict[str, str]:
    """Build SoQL parameters for windowed queries."""
    s_iso, _ = _soql_day_bounds(start_d)
    e_next_iso = f"{(end_d + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"

    params = {
        "$limit": str(limit),
        "$offset": str(offset),
        "$order": "date desc",
        "$where": f"date >= '{s_iso}' AND date < '{e_next_iso}'",
    }
    if select:
        params["$select"] = select
    return params


def month_windows(start: date, end: date) -> list[tuple[date, date, str]]:
    """Generate month-based windows."""
    wins = []
    cur = date(start.year, start.month, 1)
    next_m = (date(end.year, end.month, 1) + timedelta(days=32)).replace(day=1)
    last_end = next_m - timedelta(days=1)
    while cur <= last_end:
        nm = (cur + timedelta(days=32)).replace(day=1)
        cur_end = nm - timedelta(days=1)
        if cur_end > end:
            cur_end = end
        win_id = f"{cur.year:04d}-{cur.month:02d}"
        win_start = max(cur, start)
        wins.append((win_start, cur_end, win_id))
        cur = nm
    return wins


def day_windows(start: date, end: date) -> list[tuple[date, date, str]]:
    """Generate day-based windows."""
    days = []
    cur = start
    while cur <= end:
        dstr = cur.strftime("%Y-%m-%d")
        days.append((cur, cur, dstr))
        cur += timedelta(days=1)
    return days


def week_windows(start: date, end: date) -> list[tuple[date, date, str]]:
    """Generate week-based windows (ISO week, Monday-Sunday)."""
    wins = []
    cur = start - timedelta(days=start.weekday())  # align to Monday
    while cur <= end:
        week_start = cur
        week_end = min(cur + timedelta(days=6), end)
        wid = f"{week_start:%Y}-W{week_start.isocalendar().week:02d}"
        wins.append((week_start, week_end, wid))
        cur += timedelta(days=7)
    return wins
