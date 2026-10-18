import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

DISCLAIMER = (
    "Independent research output from an unfunded demo project. Not a validated "
    "collateral-verification or insurance product; figures below are satellite-"
    "observed estimates on available cloud-free revisit dates, not continuous "
    "monitoring or ground-truthed measurements."
)


def _chart_png(ndvi_series, sar_series):
    fig, ax1 = plt.subplots(figsize=(6.5, 3))
    dates_ndvi = [d for d, _ in ndvi_series]
    ax1.plot(dates_ndvi, [v for _, v in ndvi_series], color="#2E7D32", label="NDVI")
    ax1.set_ylabel("NDVI", color="#2E7D32")
    ax1.set_ylim(-0.2, 1)

    ax2 = ax1.twinx()
    dates_vv = [d for d, _, _ in sar_series]
    ax2.plot(dates_vv, [vv for _, vv, _ in sar_series], color="#1565C0", label="VV (dB)")
    ax2.set_ylabel("Sentinel-1 VV backscatter (dB)", color="#1565C0")

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
        ("Water surface area (MNDWI/AWEI occurrence threshold)", f"{metrics['water_area_ha']:.2f} ha"),
    ]:
        c.drawString(2.2 * cm, y, f"{label}: {value}")
        y -= 0.5 * cm

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(2 * cm, 2 * cm, DISCLAIMER)
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
    c.drawString(
        2.2 * cm, y,
        f"Observed inundation days (on available revisits, >= {metrics['trigger_days']} consecutive"
        f" satellite-observed days flagged): {metrics['inundation_days_observed']}",
    )
    y -= 0.6 * cm
    for tier, hit in metrics["trigger_flags"].items():
        c.drawString(2.2 * cm, y, f"{tier}: {'flagged' if hit else 'not flagged'} (threshold is a configurable research parameter)")
        y -= 0.5 * cm

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        2 * cm, 2 * cm,
        "GDIC's published WIBCI parametric trigger applies to upazila-wide inundation, "
        "not individual parcels; this flag is a research exploration of the same logic "
        "applied at parcel scale, not an insurance determination.",
    )
    c.showPage()
    c.save()
