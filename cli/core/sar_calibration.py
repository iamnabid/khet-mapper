"""Pick a Sentinel-1 water threshold for an AOI by checking it against
near-simultaneous clear Sentinel-2 scenes, where optical water (MNDWI > 0)
is the reference."""
import ee

from core import indices
from core.s1_sar_fusion import get_s1_composite
from core.s2_compositor import get_s2_composite, with_clear_fraction


def compare_pairs(aoi, start, end, thresholds, max_days=3, min_clear=0.8):
    """For every S1 pass with a mostly-clear S2 scene within max_days, return
    the optical water fraction and, per threshold, the SAR water fraction and
    the pixel IoU against optical water — both over pixels clear in S2."""
    s2, _ = get_s2_composite(aoi, start, end)
    s1, _ = get_s1_composite(aoi, start, end)
    clear_s2 = with_clear_fraction(s2, aoi).filter(ee.Filter.gte("clear_fraction", min_clear))
    pairs = ee.Join.saveBest("s2", "time_diff").apply(
        s1, clear_s2,
        ee.Filter.maxDifference(max_days * 86400000, "system:time_start", None, "system:time_start"),
    )

    def stats(s1_img):
        s2_img = ee.Image(s1_img.get("s2"))
        optical = indices.optical_water(s2_img)
        props = {
            "s1_date": s1_img.date().format("YYYY-MM-dd"),
            "s2_date": s2_img.date().format("YYYY-MM-dd"),
            "clear_fraction": s2_img.get("clear_fraction"),
            "optical": optical.reduceRegion(ee.Reducer.mean(), aoi, 10).get("is_water"),
        }
        for t in thresholds:
            sar = indices.sar_water(s1_img, t).updateMask(optical.mask())
            r = ee.Image.cat(
                sar.rename("sar"), sar.And(optical).rename("both"), sar.Or(optical).rename("either")
            ).reduceRegion(ee.Reducer.mean(), aoi, 10)
            props[f"sar_{t}"] = r.get("sar")
            props[f"iou_{t}"] = ee.Number(r.get("both")).divide(r.get("either"))
        return ee.Feature(None, props)

    features = ee.FeatureCollection(ee.ImageCollection(pairs).map(stats)).getInfo()["features"]
    return sorted((f["properties"] for f in features), key=lambda p: p["s1_date"])


def summarize(rows, thresholds):
    """Mean IoU and mean absolute water-fraction error per threshold, plus
    the threshold with the best mean IoU (None if there are no pairs)."""
    if not rows:
        return {}, None
    summary = {
        t: {
            "mean_iou": sum(r[f"iou_{t}"] for r in rows) / len(rows),
            "mean_abs_error": sum(abs(r[f"sar_{t}"] - r["optical"]) for r in rows) / len(rows),
        }
        for t in thresholds
    }
    best = max(thresholds, key=lambda t: summary[t]["mean_iou"])
    return summary, best
