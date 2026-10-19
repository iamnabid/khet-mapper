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

## How `analyze` finds water

Two independent water signals, one per sensor:

- **Optical** — Sentinel-2 MNDWI > 0 on cloud-masked pixels. Accurate on
  clear days, blind under monsoon cloud. Scenes where less than half the AOI
  survives the cloud mask (`OPTICAL_MIN_CLEAR_FRACTION`) are skipped: their
  few remaining pixels are mostly cloud edges and shadow.
- **Radar** — Sentinel-1 VV backscatter below `SAR_WATER_VV_DB_MAX`
  (−14 dB, in `config.py`) after speckle filtering. Calm water
  reflects the radar pulse away from the satellite, so it reads dark, cloud
  or no cloud.

Each gives a water area (pixels wet in ≥ 30% of that sensor's scenes) and a
per-pass "fraction of the parcel that's water" series. For flood runs the
two series are merged by date (the wetter reading wins on a shared date),
and a run ends at the first dry pass or a gap longer than
`FLOOD_RUN_MAX_GAP_DAYS`. Each trigger tier uses its own area fraction
(40% / 50%). `metrics.json` keeps the per-sensor results, so you can see how
much each sensor contributed.

### Calibrating the radar threshold

```
python cli.py calibrate data/aois/your_aoi.geojson 2024
```

pairs every Sentinel-1 pass with a ≥ 80%-clear Sentinel-2 scene taken within
3 days, treats optical water as the reference, and reports for each candidate
threshold the radar water fraction and pixel overlap (IoU) with optical water.

On the Satkhira smoke-test AOI for 2024 it found 9 pairs (3 dry-season, 6
Sep–Dec). −14 dB scored best (mean IoU 0.47); −16 dB, a common published
value, scored 0.36 and found only a quarter to half of the water optical saw
in Sep–Oct. Agreement is moderate, not tight: wind-roughened water reads too
bright (missed), smooth bare soil too dark (false water), and flooded rice
with plants above the water can brighten through double-bounce. There were
no clear optical scenes in Jun–Aug to calibrate the peak monsoon against.
Re-run `calibrate` for any other site or year.

### Satkhira 2024 result

With these settings the smoke-test AOI reads 4–8% water in the dry season,
rising to 22–30% on radar passes in Jun–Sep (when optical has no usable scene
from Jun 2 to Sep 7), then falling back by November. Water area: 47.6 ha
optical, 54.9 ha radar, of 310 ha. No flood-run flag: water never covered
40% of the AOI. None of this has been checked against ground records yet.

### Validation against documented floods

`scripts/validate_events.py` checks detection against 10 dated, sourced
flood and waterlogging events in Satkhira and Khulna, 2024–2026. Results and
method: [`data/validation/README.md`](data/validation/README.md). In short:
**the ≥ 40% / 14-day flood flag caught none of them** and fires in
pond-dominated areas with no flood, so it is not a flood detector. Radar
"new water against a pre-event baseline" carries a real but weak signal (4 of
10 detected under the pre-set rule), and urban waterlogging is mostly
invisible to it.

## Tests

The flood-run logic and PDF generation have offline tests (no Earth Engine
account needed):

```
pip install pytest
python -m pytest tests
```

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
