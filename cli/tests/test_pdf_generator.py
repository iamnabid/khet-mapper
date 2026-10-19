from core.pdf_generator import build_audit_pdf

BASE = {
    "aoi_name": "data/aois/test.geojson",
    "start": "2024-01-01",
    "end": "2024-12-31",
    "area_ha": 12.5,
    "area_bigha": 12.5 / 0.1338,
    "perimeter_m": 1500.0,
    "water_area_ha": 3.2,
    "ndvi_series": [("2024-01-10", 0.3), ("2024-03-10", 0.7)],
    "sar_series": [("2024-01-12", -12.0, None), ("2024-03-12", -17.5, None)],
    "trigger_days": 14,
    "inundation_days_observed": 20,
    "trigger_flags": {"tier1": True, "tier2": False},
}


def test_pdf_from_current_metrics(tmp_path):
    metrics = dict(
        BASE,
        water_area_ha_sar=4.1,
        sar_water_vv_db_max=-16,
        inundation_fraction=0.4,
        inundation_days_by_sensor={"optical": 1, "sar": 20},
        inundation_days_by_tier={"tier1": 20, "tier2": 8},
    )
    out = tmp_path / "audit.pdf"
    build_audit_pdf(metrics, "Test", str(out))
    assert out.read_bytes().startswith(b"%PDF")


def test_pdf_from_older_metrics_without_radar_water(tmp_path):
    out = tmp_path / "audit.pdf"
    build_audit_pdf(BASE, "Test", str(out))
    assert out.read_bytes().startswith(b"%PDF")
