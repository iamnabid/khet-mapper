"""Flood-run counting over satellite revisits. Pure Python (no Earth Engine)
so it can be unit-tested offline."""
from datetime import datetime


def merge_observations(*series):
    """Merge per-sensor (date, water_fraction) series into one series with a
    single value per date. When two observations share a date (two S1 frames,
    or an S2 and S1 pass on the same day) the wetter one wins: radar sees
    through cloud, and optical fractions are over clear pixels only."""
    by_date = {}
    for s in series:
        for d, v in s:
            if v is None:
                continue
            by_date[d] = max(v, by_date.get(d, v))
    return sorted(by_date.items())


def longest_flagged_run(date_value_pairs, min_fraction, max_gap_days=16):
    """Longest span of consecutive observations where the AOI's water fraction
    stayed at or above min_fraction. A run ends at the first observation below
    the threshold, or when the gap to the next observation exceeds
    max_gap_days (nothing seen in between, so we can't claim it stayed wet).

    This counts calendar days between revisits, not continuous ground-truthed
    flooding — satellites don't observe every day."""
    obs = sorted(
        (datetime.strptime(d, "%Y-%m-%d"), v) for d, v in date_value_pairs if v is not None
    )
    longest = 0
    run_start = prev = None
    for d, v in obs:
        if v < min_fraction:
            run_start = None
        elif run_start is None or (d - prev).days > max_gap_days:
            run_start = d
        if run_start is not None:
            longest = max(longest, (d - run_start).days + 1)
        prev = d
    return longest
