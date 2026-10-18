import json
from datetime import date, datetime, timedelta

import ee
import typer
from rich import print as rprint

import config
from core import indices
from core.pdf_generator import build_audit_pdf
from core.s1_sar_fusion import get_s1_composite
from core.s2_compositor import get_s2_composite

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

    s2_collection, _ = get_s2_composite(aoi_geom, start, end)
    s1_collection, _ = get_s1_composite(aoi_geom, start, end)

    ndvi_series = _series_getinfo(s2_collection.map(lambda img: indices.ndvi(img).copyProperties(img, ["system:time_start"])), "NDVI", aoi_geom)
    vv_series = _series_getinfo(s1_collection, "VV", aoi_geom)
    sar_series = [(d, vv, None) for d, vv in vv_series]

    water_mask = indices.water_occurrence_mask(s2_collection)
    area_img = ee.Image.pixelArea().divide(10000)
    water_area_ha = area_img.updateMask(water_mask).reduceRegion(
        ee.Reducer.sum(), aoi_geom, 10, maxPixels=1e9
    ).get("area").getInfo()

    area_ha = aoi_geom.area().divide(10000).getInfo()
    perimeter_m = aoi_geom.perimeter().getInfo()

    water_flags_by_date = [(d, v) for d, v in _series_getinfo(
        s2_collection.map(lambda img: indices.mndwi(img).gt(0).rename("MNDWI").copyProperties(img, ["system:time_start"])),
        "MNDWI", aoi_geom,
    )]
    inundation_days_observed = _longest_flagged_run(water_flags_by_date, min_fraction=0.4)

    metrics = {
        "aoi_name": aoi,
        "start": start,
        "end": end,
        "area_ha": area_ha,
        "area_bigha": area_ha / 0.1338,
        "perimeter_m": perimeter_m,
        "water_area_ha": water_area_ha or 0.0,
        "ndvi_series": ndvi_series,
        "sar_series": sar_series,
        "trigger_days": trigger_days,
        "inundation_days_observed": inundation_days_observed,
        "trigger_flags": {
            tier: inundation_days_observed >= trigger_days
            for tier in config.TRIGGER_AREA_FRACTIONS
        },
    }
    with open(out, "w") as f:
        json.dump(metrics, f, indent=2)
    rprint(f"[green]Wrote metrics to {out}[/green]")


def _longest_flagged_run(date_value_pairs, min_fraction):
    """Longest span between consecutive satellite observations where the
    AOI's flagged-water fraction stayed above min_fraction. This counts
    calendar days between revisits, not continuous ground-truthed flooding —
    satellites don't observe every day."""
    flagged_dates = [
        datetime.strptime(d, "%Y-%m-%d") for d, v in date_value_pairs if v >= min_fraction
    ]
    if not flagged_dates:
        return 0
    flagged_dates.sort()
    longest = 1
    run_start = flagged_dates[0]
    prev = flagged_dates[0]
    for d in flagged_dates[1:]:
        if (d - prev) <= timedelta(days=16):  # S2 revisit cadence tolerance
            longest = max(longest, (d - run_start).days + 1)
        else:
            run_start = d
        prev = d
    return longest


@app.command()
def report(metrics: str, client: str, out: str = "data/outputs/KhetMapper_Sample_Audit.pdf"):
    with open(metrics) as f:
        metrics_dict = json.load(f)
    build_audit_pdf(metrics_dict, client, out)
    rprint(f"[green]Wrote PDF to {out}[/green]")


if __name__ == "__main__":
    app()
