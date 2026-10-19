import json
from datetime import date

import ee
import typer
from rich import print as rprint

import config
from core import indices
from core.flood_runs import longest_flagged_run, merge_observations
from core.pdf_generator import build_audit_pdf
from core.s1_sar_fusion import get_s1_composite
from core.s2_compositor import get_s2_composite, mostly_clear
from core.sar_calibration import compare_pairs, summarize

app = typer.Typer()


def _init_ee():
    if not config.EE_PROJECT:
        raise typer.BadParameter(
            "Set EE_PROJECT_ID (env var) to your Google Cloud project before running."
        )
    ee.Initialize(project=config.EE_PROJECT)


def _load_aoi(path: str) -> ee.Geometry:
    with open(path) as f:
        geojson = json.load(f)
    geometry = geojson.get("geometry", geojson)
    return ee.Geometry(geometry)


@app.command()
def composite(aoi: str, start: str, end: str, out: str):
    _init_ee()
    aoi_geom = _load_aoi(aoi)
    _, s2_image = get_s2_composite(aoi_geom, start, end)
    _, s1_image = get_s1_composite(aoi_geom, start, end)
    combined = s2_image.addBands(s1_image)

    task = ee.batch.Export.image.toDrive(
        image=combined,
        description=f"khetmapper_composite_{date.today().isoformat()}",
        folder="khetmapper_exports",
        fileNamePrefix=out.rsplit("/", 1)[-1].replace(".tif", ""),
        region=aoi_geom,
        scale=10,
        maxPixels=1e9,
    )
    task.start()
    rprint(f"[green]Export task started:[/green] {task.id} — check Google Drive folder 'khetmapper_exports'.")


def _series_getinfo(image_collection, band, aoi_geom):
    def to_feature(img):
        value = img.select(band).reduceRegion(ee.Reducer.mean(), aoi_geom, 10).get(band)
        return ee.Feature(None, {"date": img.date().format("YYYY-MM-dd"), "value": value})

    features = ee.FeatureCollection(image_collection.map(to_feature)).getInfo()
    out = []
    for f in features["features"]:
        props = f["properties"]
        if props.get("value") is not None:
            out.append((props["date"], props["value"]))
    return sorted(out, key=lambda t: t[0])


@app.command()
def analyze(aoi: str, year: int, trigger_days: int = config.TRIGGER_CONSECUTIVE_DAYS, out: str = "data/outputs/metrics.json"):
    _init_ee()
    aoi_geom = _load_aoi(aoi)
    start, end = f"{year}-01-01", f"{year}-12-31"

    s2_all, _ = get_s2_composite(aoi_geom, start, end)
    s2_collection = mostly_clear(s2_all, aoi_geom)
    s1_collection, _ = get_s1_composite(aoi_geom, start, end)

    ndvi_series = _series_getinfo(s2_collection.map(lambda img: indices.ndvi(img).copyProperties(img, ["system:time_start"])), "NDVI", aoi_geom)
    vv_series = _series_getinfo(s1_collection, "VV", aoi_geom)
    sar_series = [(d, vv, None) for d, vv in vv_series]

    def water_fraction_series(collection, classify):
        flags = collection.map(lambda img: classify(img).copyProperties(img, ["system:time_start"]))
        return _series_getinfo(flags, "is_water", aoi_geom)

    def water_area_ha(collection, classify):
        mask = indices.water_occurrence_mask(collection, classify=classify)
        area = ee.Image.pixelArea().divide(10000).updateMask(mask).reduceRegion(
            ee.Reducer.sum(), aoi_geom, 10, maxPixels=1e9
        ).get("area").getInfo()
        return area or 0.0

    area_ha = aoi_geom.area().divide(10000).getInfo()
    perimeter_m = aoi_geom.perimeter().getInfo()

    optical_water = water_fraction_series(s2_collection, indices.optical_water)
    sar_water = water_fraction_series(s1_collection, indices.sar_water)
    combined_water = merge_observations(optical_water, sar_water)

    def run(series, fraction):
        return longest_flagged_run(series, fraction, config.FLOOD_RUN_MAX_GAP_DAYS)

    inundation_days_by_tier = {
        tier: run(combined_water, fraction) for tier, fraction in config.TRIGGER_AREA_FRACTIONS.items()
    }
    headline_fraction = min(config.TRIGGER_AREA_FRACTIONS.values())

    metrics = {
        "aoi_name": aoi,
        "start": start,
        "end": end,
        "area_ha": area_ha,
        "area_bigha": area_ha / 0.1338,
        "perimeter_m": perimeter_m,
        "water_area_ha": water_area_ha(s2_collection, indices.optical_water),
        "water_area_ha_sar": water_area_ha(s1_collection, indices.sar_water),
        "sar_water_vv_db_max": config.SAR_WATER_VV_DB_MAX,
        "optical_min_clear_fraction": config.OPTICAL_MIN_CLEAR_FRACTION,
        "ndvi_series": ndvi_series,
        "sar_series": sar_series,
        "water_fraction_series_optical": optical_water,
        "water_fraction_series_sar": sar_water,
        "trigger_days": trigger_days,
        "inundation_fraction": headline_fraction,
        "inundation_days_observed": run(combined_water, headline_fraction),
        "inundation_days_by_sensor": {
            "optical": run(optical_water, headline_fraction),
            "sar": run(sar_water, headline_fraction),
        },
        "inundation_days_by_tier": inundation_days_by_tier,
        "trigger_flags": {
            tier: days >= trigger_days for tier, days in inundation_days_by_tier.items()
        },
    }
    with open(out, "w") as f:
        json.dump(metrics, f, indent=2)
    rprint(f"[green]Wrote metrics to {out}[/green]")


@app.command()
def calibrate(
    aoi: str,
    year: int,
    thresholds: str = "-12,-13,-14,-15,-16,-17,-18",
    max_days: int = 3,
    min_clear: float = 0.8,
):
    """Compare Sentinel-1 water thresholds against near-simultaneous clear
    Sentinel-2 scenes and suggest the best one for SAR_WATER_VV_DB_MAX."""
    _init_ee()
    aoi_geom = _load_aoi(aoi)
    ts = [int(t) for t in thresholds.split(",")]
    rows = compare_pairs(aoi_geom, f"{year}-01-01", f"{year}-12-31", ts, max_days, min_clear)
    if not rows:
        rprint(f"[yellow]No S1 pass had an S2 scene within {max_days} days with >= {min_clear:.0%} clear sky.[/yellow]")
        raise typer.Exit(1)

    rprint(f"S1 date     S2 date     clear  optical | SAR water fraction at {ts} dB")
    for r in rows:
        sar = " ".join(f"{r[f'sar_{t}']:.2f}" for t in ts)
        rprint(f"{r['s1_date']}  {r['s2_date']}  {r['clear_fraction']:.2f}   {r['optical']:.2f}   | {sar}")
    summary, best = summarize(rows, ts)
    rprint("\nthreshold  mean IoU  mean |SAR - optical|")
    for t in ts:
        rprint(f"{t:>6} dB   {summary[t]['mean_iou']:.3f}     {summary[t]['mean_abs_error']:.3f}")
    rprint(
        f"\n[green]Best mean IoU: {best} dB[/green] (current SAR_WATER_VV_DB_MAX: {config.SAR_WATER_VV_DB_MAX} dB)"
        f" — based on {len(rows)} date pairs; few or only dry-season pairs make this a weak estimate."
    )


@app.command()
def report(metrics: str, client: str, out: str = "data/outputs/KhetMapper_Sample_Audit.pdf"):
    with open(metrics) as f:
        metrics_dict = json.load(f)
    build_audit_pdf(metrics_dict, client, out)
    rprint(f"[green]Wrote PDF to {out}[/green]")


if __name__ == "__main__":
    app()
