"""Standalone proof-pack generator: analyze an AOI then render the PDF in one call.

    python scripts/generate_audit_pdf.py data/aois/example.geojson 2024 "Sample Audit"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli import analyze, report  # noqa: E402


def main():
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <aoi.geojson> <year> <client-label>")
        raise SystemExit(1)
    aoi_path, year, client = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    metrics_path = "data/outputs/metrics.json"
    out_path = "data/outputs/KhetMapper_Sample_Audit.pdf"

    analyze(aoi=aoi_path, year=year, out=metrics_path)
    report(metrics=metrics_path, client=client, out=out_path)


if __name__ == "__main__":
    main()
