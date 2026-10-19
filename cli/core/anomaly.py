"""Seasonal water anomaly from Sentinel-1.

Absolute water area can't tell a flood from ponds or normal monsoon wetting.
Instead, compare each pass with how often each pixel was water in the same
calendar weeks of earlier years (same orbit direction): water at a pixel
that is rarely wet at this time of year is anomalous.
"""
from datetime import date

import ee

from core import indices
from core.s1_sar_fusion import get_s1_composite
from core.validation import MIN_PASS_COVERAGE, _shift

CLIMATOLOGY_YEARS = 5
RARE_WATER_FREQUENCY = 0.2  # pixel was water in < 20% of same-season past passes
MIN_ANOMALY = 0.02          # never call less than 2% of the AOI anomalous a detection
Z = 3
MIN_WINDOW_DAYS = 24        # >= 2 passes per orbit at a 12-day revisit


def season_window(during):
    """The event window, padded symmetrically to at least MIN_WINDOW_DAYS."""
    lo, hi = during
    span = (date.fromisoformat(hi) - date.fromisoformat(lo)).days
    pad = max(0, (MIN_WINDOW_DAYS - span + 1) // 2)
    return [_shift(lo, -pad), _shift(hi, pad)]


def anomaly_threshold(history, floor=MIN_ANOMALY, z=Z):
    """max(floor, mean + z*sd) of past-year anomaly fractions (floor alone
    with fewer than 2 past values)."""
    if len(history) < 2:
        return floor
    mean = sum(history) / len(history)
    sd = (sum((v - mean) ** 2 for v in history) / (len(history) - 1)) ** 0.5
    return max(floor, mean + z * sd)


def _season(aoi, window, year, orbit):
    lo, hi = window
    shift = year - int(lo[:4])
    s1, _ = get_s1_composite(aoi, _shift(lo, years=shift), _shift(hi, 1, years=shift), orbit=orbit)
    return s1


def water_frequency(aoi, window, years, orbit):
    passes = ee.ImageCollection([])
    for y in years:
        passes = passes.merge(_season(aoi, window, y, orbit))
    return passes.map(indices.sar_water).mean().rename("freq")


def anomaly_fractions(passes, freq, aoi, scale):
    rare = freq.lt(RARE_WATER_FREQUENCY)

    def per_pass(img):
        water = indices.sar_water(img)
        anomalous = water.And(rare).updateMask(freq.mask()).rename("anomaly")
        covered = img.select("VV").mask().gt(0).unmask(0).rename("covered")
        r = ee.Image.cat(anomalous, covered).reduceRegion(
            ee.Reducer.mean(), aoi, scale, maxPixels=1e10, tileScale=4
        )
        return ee.Feature(None, {
            "date": img.date().format("YYYY-MM-dd"),
            "anomaly": r.get("anomaly"),
            "coverage": r.get("covered"),
        })

    feats = ee.FeatureCollection(passes.map(per_pass)).getInfo()["features"]
    rows = [f["properties"] for f in feats]
    return sorted(
        (r for r in rows if r.get("anomaly") is not None and (r.get("coverage") or 0) >= MIN_PASS_COVERAGE),
        key=lambda r: r["date"],
    )


def evaluate(event, aoi, orbit, scale):
    """Anomaly in the event's season window vs the previous CLIMATOLOGY_YEARS,
    with a leave-one-year-out noise estimate from those same years."""
    window = season_window(event["during"])
    year = int(window[0][:4])
    past = [year - k for k in range(1, CLIMATOLOGY_YEARS + 1)]

    event_rows = anomaly_fractions(
        _season(aoi, window, year, orbit), water_frequency(aoi, window, past, orbit), aoi, scale
    )
    history = []
    for y in past:
        others = [o for o in past if o != y]
        rows = anomaly_fractions(_season(aoi, window, y, orbit), water_frequency(aoi, window, others, orbit), aoi, scale)
        history += [r["anomaly"] for r in rows]

    threshold = anomaly_threshold(history)
    peak = max((r["anomaly"] for r in event_rows), default=None)
    return {
        "window": window,
        "climatology_years": past,
        "passes": event_rows,
        "history": history,
        "threshold": threshold,
        "peak": peak,
        "detected": None if peak is None else peak >= threshold,
    }
