import tempfile
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

DISCLAIMER = (
    "Independent research output from an unfunded demo project. Not a validated "
    "collateral-verification or insurance product; figures below are satellite-"
    "observed estimates on available cloud-free revisit dates, not continuous "
    "monitoring or ground-truthed measurements."
)
SAR_CAVEAT = (
    "Radar water uses a fixed VV backscatter threshold not yet calibrated for this region: "
    "wind-roughened water can be missed, smooth bare soil can read as water."
)


def _dates(strings):
    # Real dates, not strings: matplotlib treats strings as categories, which
    # puts the NDVI and radar series on separate, unaligned x positions.
    return [datetime.strptime(d, "%Y-%m-%d") for d in strings]


def _draw_footer(c, lines, width):
    """Draw footer notes bottom-up, wrapped to the page width."""
    c.setFont("Helvetica-Oblique", 8)
    y = 2 * cm
    for text in reversed(lines):
        for line in reversed(simpleSplit(text, "Helvetica-Oblique", 8, width - 4 * cm)):
            c.drawString(2 * cm, y, line)
            y += 0.35 * cm
        y += 0.15 * cm


def _chart_png(ndvi_series, sar_series):
    fig, ax1 = plt.subplots(figsize=(6.5, 3))
    dates_ndvi = _dates(d for d, _ in ndvi_series)
    ax1.plot(dates_ndvi, [v for _, v in ndvi_series], color="#2E7D32", label="NDVI")
    ax1.set_ylabel("NDVI", color="#2E7D32")
    ax1.set_ylim(-0.2, 1)

    ax2 = ax1.twinx()
    dates_vv = _dates(d for d, _, _ in sar_series)
    ax2.plot(dates_vv, [vv for _, vv, _ in sar_series], color="#1565C0", label="VV (dB)")
    ax2.set_ylabel("Sentinel-1 VV backscatter (dB)", color="#1565C0")
    locator = mdates.AutoDateLocator()
    ax1.xaxis.set_major_locator(locator)
    ax1.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    fig.tight_layout()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, dpi=150)
    plt.close(fig)
    return tmp.name


def build_audit_pdf(metrics: dict, client: str, out_path: str):
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4

    # Page 1
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, height - 2 * cm, "Khet Mapper — Satellite Observation Summary")
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, height - 2.7 * cm, f"Client / reference: {client}")
    c.drawString(2 * cm, height - 3.2 * cm, f"AOI: {metrics['aoi_name']}")
    c.drawString(2 * cm, height - 3.7 * cm, f"Date range: {metrics['start']} to {metrics['end']}")
    c.drawString(
        2 * cm, height - 4.2 * cm,
        "Sensors: Copernicus Sentinel-2 L2A (COPERNICUS/S2_SR_HARMONIZED), "
        "Sentinel-1 GRD IW VV+VH",
    )

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, height - 5.2 * cm, "Parcel metrics (satellite-derived estimate)")
    c.setFont("Helvetica", 10)
    y = height - 5.9 * cm
    for label, value in [
        ("Delineated area", f"{metrics['area_ha']:.2f} ha ({metrics['area_bigha']:.2f} bigha)"),
        ("Delineated perimeter", f"{metrics['perimeter_m']:.0f} m"),
        ("Water surface, optical (S2 MNDWI > 0 in >= 30% of clear scenes)", f"{metrics['water_area_ha']:.2f} ha"),
    ] + ([(
        f"Water surface, radar (S1 VV < {metrics.get('sar_water_vv_db_max', -14)} dB in >= 30% of passes)",
        f"{metrics['water_area_ha_sar']:.2f} ha",
    )] if "water_area_ha_sar" in metrics else []):
        c.drawString(2.2 * cm, y, f"{label}: {value}")
        y -= 0.5 * cm

    _draw_footer(c, ([SAR_CAVEAT] if "water_area_ha_sar" in metrics else []) + [DISCLAIMER], width)
    c.showPage()

    # Page 2
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, height - 2 * cm, "Vegetation & inundation trajectory")
    chart_path = _chart_png(metrics["ndvi_series"], metrics["sar_series"])
    c.drawImage(chart_path, 2 * cm, height - 9 * cm, width=16 * cm, height=6 * cm)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, height - 10 * cm, "Exploratory flood-exposure flags (parcel-level, not GDIC's index)")
    c.setFont("Helvetica", 10)
    y = height - 10.7 * cm
    fraction = metrics.get("inundation_fraction", 0.4)
    c.drawString(
        2.2 * cm, y,
        f"Longest run with >= {fraction:.0%} of the parcel reading as water: "
        f"{metrics['inundation_days_observed']} days (flag threshold: {metrics['trigger_days']} days)",
    )
    by_sensor = metrics.get("inundation_days_by_sensor")
    if by_sensor:
        y -= 0.5 * cm
        c.drawString(
            2.2 * cm, y,
            f"Optical + radar revisits combined; optical alone: {by_sensor['optical']} days, "
            f"radar alone: {by_sensor['sar']} days",
        )
    y -= 0.6 * cm
    by_tier = metrics.get("inundation_days_by_tier", {})
    for tier, hit in metrics["trigger_flags"].items():
        days = f", {by_tier[tier]} days" if tier in by_tier else ""
        c.drawString(2.2 * cm, y, f"{tier}: {'flagged' if hit else 'not flagged'}{days} (threshold is a configurable research parameter)")
        y -= 0.5 * cm

    _draw_footer(c, [
        "GDIC's published WIBCI parametric trigger applies to upazila-wide inundation, "
        "not individual parcels; this flag is a research exploration of the same logic "
        "applied at parcel scale, not an insurance determination."
    ], width)
    c.showPage()
    c.save()
