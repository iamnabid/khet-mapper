# Khet Mapper CLI

Sentinel-2 + Sentinel-1 pipeline for exploring rice/aquaculture parcels in
coastal Bangladesh. Scaffolded from the Stage 2 spec in `HOW_TO_PROCEED.md`
(the Gemini-authored commercialization plan), with the technical bugs a
Codex fact-check found in that spec fixed before any code was written:

- `S2_SR_HARMONIZED` (L2A) has no B10 — removed. QA60 bits 10/11 are cloud
  flags, not spectral thresholds, and are masked out between 2022 and
  Feb 2024 — `s2_compositor.py` treats "flag unavailable" as "don't filter
  on it" instead of discarding that whole window.
- GEE's `S1_GRD` is already calibrated, terrain-corrected, and in dB —
  `s1_sar_fusion.py` does not reapply `10*log10()`.
- AWEI (no-shadow) needs B12, which the original spec dropped — fixed in
  `indices.py`.
- `allNonZero` over an MNDWI stack only keeps *permanent* water, dropping
  seasonal ponds — replaced with an occurrence-fraction threshold.
- The boundary buffer is a small configurable knob, not a fixed 5px/~50m
  value that can merge adjacent ponds/canals.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set EE_PROJECT_ID=your-gcp-project-id
```

Earth Engine is already authenticated on this machine (`earthengine
authenticate` was run previously); only `EE_PROJECT_ID` needs setting.

## Usage

```
python cli.py composite --aoi data/aois/your_aoi.geojson --start 2024-06-01 --end 2024-09-30 --out data/outputs/composite.tif
python cli.py analyze --aoi data/aois/your_aoi.geojson --year 2024 --trigger-days 14 --out data/outputs/metrics.json
python cli.py report --metrics data/outputs/metrics.json --client "Sample" --out data/outputs/KhetMapper_Sample_Audit.pdf
```

`data/aois/` needs a real GeoJSON polygon — none is bundled, since fabricating
GPS coordinates for a specific parcel would misrepresent real land.

## Deliberately not implemented here

The original plan's PDF called "collateral verification," exact settlement
timelines (14-20 days), and "18 days earlier than manual adjusters" are
unvalidated performance claims — nothing in this pipeline or the existing
site's NDVI-reconstruction benchmark establishes them. `pdf_generator.py`
reports what's actually measured (area, observed water occurrence, NDVI/SAR
trend) with that caveat printed on the page, matching the honest framing
the live khetmapper.tech site already uses ("free, independent demo, not a
funded product").

The flood-exposure thresholds (14-day / 40–50% area) are kept as
*configurable* parameters for exploring the same logic GDIC's WIBCI index
uses — but GDIC's actual index triggers on upazila-wide inundation, not a
single parcel, so a flag here is a research exploration, not an insurance
determination.
