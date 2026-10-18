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

This lives under `cli/` in the `khet-mapper` repo (alongside the
khetmapper.tech site). Clone the repo and run everything from inside `cli/`,
since paths like `data/aois/...` are relative to the current directory.

```
git clone https://github.com/iamnabid/khet-mapper.git
cd khet-mapper/cli
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Authenticate Earth Engine (one-time per machine)

```
earthengine authenticate
```

This opens a browser OAuth flow and stores a refresh token locally —
it does not set a Cloud project.

### Set EE_PROJECT_ID

Earth Engine's Python client requires an explicit Google Cloud project with
the Earth Engine API enabled; there's no usable default. Find yours at
either:

- **Earth Engine Code Editor** ([code.earthengine.google.com](https://code.earthengine.google.com)) — the project
  dropdown next to the logo, top-left. Use the **Project ID** (e.g.
  `my-project-123`), not the display name.
- **Google Cloud Console** ([console.cloud.google.com](https://console.cloud.google.com)) — the project picker's
  **ID** column, not **Name**.

Then set it for your shell:

```
# PowerShell
$env:EE_PROJECT_ID = "your-gcp-project-id"

# cmd.exe
set EE_PROJECT_ID=your-gcp-project-id

# bash
export EE_PROJECT_ID=your-gcp-project-id
```

## Usage

All three commands take their required arguments positionally (Typer CLI);
`--trigger-days`/`--out` are the only real flags, each with a default.

```
python cli.py composite data/aois/your_aoi.geojson 2024-06-01 2024-09-30 data/outputs/composite.tif
python cli.py analyze data/aois/your_aoi.geojson 2024 --trigger-days 14 --out data/outputs/metrics.json
python cli.py report data/outputs/metrics.json "Sample" --out data/outputs/KhetMapper_Sample_Audit.pdf
```

Run `python cli.py COMMAND --help` for the exact signature of any command.

`data/aois/` needs a real GeoJSON polygon for a parcel you're actually
mapping — fabricating GPS coordinates for a specific parcel would misrepresent
real land. `data/aois/satkhira_smoketest.geojson` is included as a working
example: a small (~310ha) crop of the real FAO GAUL Satkhira district
boundary, used only to smoke-test the pipeline end-to-end, not a claim about
any specific rice/aquaculture parcel.

`composite` starts an async Earth Engine export task and writes to your
Google Drive (`khetmapper_exports/` folder) once it completes server-side —
check task status with `ee.data.getTaskList()` if you need to confirm
completion from Python.

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
