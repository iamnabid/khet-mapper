import os

EE_PROJECT = os.environ.get("EE_PROJECT_ID")  # set this to your GCP project id before running

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_PROB_COLLECTION = "COPERNICUS/S2_CLOUD_PROBABILITY"
S1_COLLECTION = "COPERNICUS/S1_GRD"

CLOUD_PROB_MAX = 40  # % — scenes/pixels above this probability are masked out
S2_BANDS = ["B2", "B3", "B4", "B5", "B8", "B11", "B12"]

SPECKLE_FILTER_RADIUS_M = 30  # S1 speckle smoothing, not reapplied calibration
WATER_OCCURRENCE_MIN_FRACTION = 0.3  # fraction of cloud-free scenes classified as water to count a pixel as "water" (permanent + seasonal)
# Sentinel-1 VV backscatter (dB, after speckle filter) below this reads as open
# water: calm water reflects radar away from the sensor. Chosen with
# `cli.py calibrate` on the Satkhira smoke-test AOI, 2024: against 9 near-
# simultaneous clear Sentinel-2 scenes, -14 dB gave the best pixel overlap
# with optical water (mean IoU 0.47; -16 dB, a common published value, gave
# 0.36 and undercounted wet-season water). Agreement is moderate, and
# calibrated on one AOI and year — re-run `calibrate` for other sites.
SAR_WATER_VV_DB_MAX = -14
# Optical scenes where less of the AOI than this survives the cloud mask are
# left out of per-scene series: the few remaining pixels are often cloud
# edges or shadow, which read as 60-100% "water" in the 2024 Satkhira run.
OPTICAL_MIN_CLEAR_FRACTION = 0.5
FLOOD_RUN_MAX_GAP_DAYS = 16  # longest revisit gap a flood run may span (S2 ~5 d, S1 ~12 d)
WATER_BOUNDARY_BUFFER_PX = 1  # ~10-20m at S2/S1 resolution; keep small to avoid merging adjacent ponds

# Trigger thresholds are configurable knobs for exploring flood exposure, not a
# verified insurance product spec — GDIC's published WIBCI index triggers on
# upazila-wide inundation, not individual parcels.
TRIGGER_CONSECUTIVE_DAYS = 14
TRIGGER_AREA_FRACTIONS = {"tier1": 0.40, "tier2": 0.50}
