"""Check flood detection against documented events (data/validation/events.json).

For each event and Sentinel-1 orbit direction: a pre-event baseline water
mask (median VV of the pre-window passes below the water threshold), then
per pass the AOI fraction that is water and the fraction that is NEW water
(water now, not water in the baseline). In gher/pond landscapes ponds are
already radar-dark before any flood, so new water is the informative signal.
"""
from datetime import date, timedelta

import ee

import config
from core import indices
from core.flood_runs import longest_flagged_run, merge_observations
from core.s1_sar_fusion import get_s1_composite
from core.s2_compositor import get_s2_composite, mostly_clear
from core.series import series_getinfo, water_fraction_series

MIN_BASELINE_DAYS = 36  # ~3 passes per orbit at a 12-day revisit
MIN_PASS_COVERAGE = 0.9  # skip radar passes that see less than this share of the AOI
MIN_NEW_WATER = 0.02  # never call less than 2% of the AOI newly wet a detection
NOISE_FACTOR = 3


def detection(pre_new, during_new, min_floor=MIN_NEW_WATER, factor=NOISE_FACTOR):
    """Decide whether the during-event passes show more new water than the
    pre-event passes do against their own baseline. Returns
    (detected, threshold, peak) — detected is None without data."""
    if not during_new:
        return None, None, None
    noise = max(pre_new) if pre_new else 0.0
    threshold = max(min_floor, factor * noise)
    peak = max(during_new)
    return peak >= threshold, threshold, peak


def _shift(d, days=0, years=0):
    x = date.fromisoformat(d)
    return (x.replace(year=x.year + years) + timedelta(days=days)).isoformat()


def with_baseline(event):
    """Stretch the pre window back to MIN_BASELINE_DAYS so the baseline and
    its noise floor come from several passes, not one."""
    pre_lo, pre_hi = event["pre"]
    return dict(event, pre=[min(pre_lo, _shift(pre_hi, -MIN_BASELINE_DAYS)), pre_hi])


def control_window(event):
    """Same calendar span one year earlier (not guaranteed flood-free)."""
    return [_shift(event["pre"][0], years=-1), _shift(event["post"][1], years=-1)]


def _phase(d, event):
    for name in ("pre", "during", "post"):
        lo, hi = event[name]
        if lo <= d <= hi:
            return name
    return None


def _scale_for(aoi):
    # 10 m for small AOIs; 30 m keeps district-scale boxes within EE limits.
    return 10 if aoi.area().getInfo() < 100e6 else 30


def sar_passes(event, aoi, orbit, scale):
    start, end = event["pre"][0], event["post"][1]
    s1, _ = get_s1_composite(aoi, start, end, orbit=orbit)
    pre = s1.filterDate(event["pre"][0], ee.Date(event["pre"][1]).advance(1, "day"))
    if pre.size().getInfo() == 0:
        return [], 0
    baseline_water = indices.sar_water(pre.median())

    def per_pass(img):
        water = indices.sar_water(img)
        new = water.And(baseline_water.Not()).rename("new")
        covered = img.select("VV").mask().gt(0).unmask(0).rename("covered")
        # One reduction for all three bands; mean() honours each band's own mask.
        r = ee.Image.cat(water, new, covered).reduceRegion(
            ee.Reducer.mean(), aoi, scale, maxPixels=1e10, tileScale=4
        )
        return ee.Feature(None, {
            "date": img.date().format("YYYY-MM-dd"),
            "water": r.get("is_water"),
            "new": r.get("new"),
            "coverage": r.get("covered"),
        })

    feats = ee.FeatureCollection(s1.map(per_pass)).getInfo()["features"]
    rows = []
    for f in feats:
        p = f["properties"]
        if p.get("water") is None or (p.get("coverage") or 0) < MIN_PASS_COVERAGE:
            continue
        p["phase"] = _phase(p["date"], event)
        rows.append(p)
    return sorted(rows, key=lambda r: r["date"]), pre.size().getInfo()


def product_flag(start, end, aoi, scale):
    """What `analyze` would report over [start, end]: the longest run with
    >= 40% of the AOI wet, from optical + descending radar combined."""
    s2_all, _ = get_s2_composite(aoi, start, end)
    s1, _ = get_s1_composite(aoi, start, end)
    optical = water_fraction_series(mostly_clear(s2_all, aoi, scale=scale), indices.optical_water, aoi, scale)
    sar = water_fraction_series(s1, indices.sar_water, aoi, scale)
    fraction = min(config.TRIGGER_AREA_FRACTIONS.values())
    days = longest_flagged_run(merge_observations(optical, sar), fraction, config.FLOOD_RUN_MAX_GAP_DAYS)
    return {
        "longest_run_days": days,
        "flagged": days >= config.TRIGGER_CONSECUTIVE_DAYS,
        "optical_scenes_used": len(optical),
        "max_water_fraction": max((v for _, v in optical + sar), default=None),
    }


def year_earlier(event):
    return dict(event, **{k: [_shift(d, years=-1) for d in event[k]] for k in ("pre", "during", "post")})


def _orbit_summary(event, aoi, orbit, scale):
    rows, n_pre = sar_passes(event, aoi, orbit, scale)
    pre_new = [r["new"] for r in rows if r["phase"] == "pre"]
    during = [r for r in rows if r["phase"] == "during"]
    detected, threshold, peak = detection(pre_new, [r["new"] for r in during])
    return {
        "passes": rows,
        "n_pre": n_pre,
        "n_during": len(during),
        "pre_water_mean": sum(r["water"] for r in rows if r["phase"] == "pre") / len(pre_new) if pre_new else None,
        "during_water_max": max((r["water"] for r in during), default=None),
        "new_water_threshold": threshold,
        "new_water_peak": peak,
        "peak_date": max(during, key=lambda r: r["new"])["date"] if during else None,
        "detected": detected,
    }


def validate_event(event):
    """Detection over the event windows, and the same rule over the same
    calendar windows a year earlier: if the control also 'detects', the
    signal is seasonal wetting, not this flood."""
    event = with_baseline(event)
    w, s, e, n = event["bbox"]
    aoi = ee.Geometry.Rectangle([w, s, e, n])
    scale = _scale_for(aoi)
    control = year_earlier(event)
    result = {"id": event["id"], "scale_m": scale, "pre_window": event["pre"], "orbits": {}, "control_orbits": {}}
    for orbit in ("DESCENDING", "ASCENDING"):
        result["orbits"][orbit] = _orbit_summary(event, aoi, orbit, scale)
        c = _orbit_summary(control, aoi, orbit, scale)
        result["control_orbits"][orbit] = {k: v for k, v in c.items() if k != "passes"}
    result["product"] = product_flag(event["pre"][0], event["post"][1], aoi, scale)
    result["product_control"] = dict(product_flag(*control_window(event), aoi, scale), window=control_window(event))
    return result
