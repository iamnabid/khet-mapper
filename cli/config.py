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
# water: calm water reflects radar away from the sensor. Published thresholds
# for open water mostly fall between about -15 and -20 dB; -16 is a starting
# point, not a value calibrated for Khulna/Satkhira. Wind-roughened water can
# read brighter (missed), and smooth bare soil or tarmac darker (false water).
SAR_WATER_VV_DB_MAX = -16
FLOOD_RUN_MAX_GAP_DAYS = 16  # longest revisit gap a flood run may span (S2 ~5 d, S1 ~12 d)
WATER_BOUNDARY_BUFFER_PX = 1  # ~10-20m at S2/S1 resolution; keep small to avoid merging adjacent ponds

# Trigger thresholds are configurable knobs for exploring flood exposure, not a
# verified insurance product spec — GDIC's published WIBCI index triggers on
# upazila-wide inundation, not individual parcels.
TRIGGER_CONSECUTIVE_DAYS = 14
TRIGGER_AREA_FRACTIONS = {"tier1": 0.40, "tier2": 0.50}
