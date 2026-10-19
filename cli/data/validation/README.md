# Flood-detection validation, October 2026

Can the CLI see documented floods? Tested against 10 dated, sourced flood and
waterlogging events in Satkhira and Khulna (2024–2026), listed with their
sources in [`events.json`](events.json). The event list comes from a desk
review of BSS, BWDB/district statements and national and Bangla-language
press; its bounding boxes are deliberately broad search areas, not mapped
flood extents. Full per-pass numbers are in [`results.json`](results.json).
Reproduce with:

```
python scripts/validate_events.py
```

## Method (fixed before the first run)

For each event and each Sentinel-1 orbit direction:

- **Baseline:** median VV of the pre-event passes (≥ 36 days), water where
  VV < −14 dB. In shrimp-gher country, ponds are radar-dark before any flood,
  so the signal is *new* water, not total water.
- **New water:** per pass, the share of the box that is water now and was not
  in the baseline. Same-day frames are mosaicked; passes covering < 90% of the
  box are skipped.
- **Detected:** peak new water in the event window ≥ max(2%, 3× the largest
  new-water share any pre-event pass shows against its own baseline).
- **Control:** the same rule over the same calendar windows one year earlier.
- **Product flag:** what `analyze` reports — the longest run with ≥ 40% of
  the box wet, ≥ 14 days to flag — for the event period and the control year.

## Results

| Event | Setting | New water at peak (desc / asc) | Rule: detected? | Control year (desc / asc) | Product flag: event / control |
|---|---|---|---|---|---|
| Satkhira Sadar/Tala, Betna breach, Sep 2024 | rural | 12.8% / 11.0% | no / no (needed 14.6 / 12.8) | 5.1% / 6.0% | none / none |
| Khulna City, Sep 2024 | urban | 2.8% / 1.8% | no / no | no passes | none / none |
| Cyclone Remal, Satkhira, May 2024 | rural + forest | 11.5% / 8.4% | **yes** / no | 8.4% / 6.7% | none / none |
| Cyclone Remal, Khulna, May 2024 | rural + forest | 8.4% / 6.6% | **yes** / no | 4.6% / 4.6% | none / none |
| Bichhat breach, Mar 2025 | rural | 4.6% / no pass | no / – | 10.1% / 7.6% | FLAG / FLAG |
| Dargahpur ring-embankment, May 2025 | rural | no pass / 5.1% | – / no | 15.7% / 12.6% ¹ | FLAG / FLAG |
| Satkhira town, Jul 2025 | urban | no pass / 7.7% | – / no | – / 3.1% | none / none |
| Ashashuni, Jul 2025 | rural | 16.9% / 13.0% | **yes** / no | – / 8.6% | FLAG / FLAG |
| Satkhira town, Jul 2026 | urban | 6.9% / 10.3% | **yes** / **yes** | 12.4% / 14.2% ² | none / none |
| Khulna City, Jul 2026 | urban | 1.7% / 5.9% | no / no | 2.2% / 3.6% | none / none |

¹ Control window (May–Jun 2024) contains Cyclone Remal, which hit Ashashuni.
² Control window (Jul 2025) contains the documented Satkhira town waterlogging.

## What this shows

1. **The product's flood flag does not work.** It caught none of the 10
   events. It fires only where gher ponds already cover 45–60% of the box —
   and fires just as much in the control year (Bichhat 58 vs 56 days,
   Dargahpur 34 vs 31, Ashashuni 39 vs 25). An absolute "≥ 40% wet" rule
   measures how much of a place is ponds, not whether it flooded. Don't use
   it until it is replaced with a change-based flag.
2. **Radar new-water carries a real but weak signal.** Under the fixed rule,
   4 of 10 events are detected in at least one orbit, and two of those (both
   Remal) rest on a single pre-event pass, which makes the noise floor
   meaningless. The rule is too strict in the monsoon, when pre-event windows
   are themselves getting wetter: the Satkhira Sep 2024 flood, the largest in
   the set, shows 11–13% new water in both orbits — about twice the control
   year — and still falls just under its threshold.
3. **Compared with the control year (an exploratory reading, chosen after
   seeing the results):** new water is higher in the event than the control in
   9 of 14 orbit comparisons. Of the 5 where the control is higher, 3 have a
   documented flood inside the control window (notes ¹ and ²). The genuine
   misses are the **Bichhat breach** (4.6% vs 10.1% — at the scale of a 56 km²
   box, a ~600 ha breach doesn't stand out from normal pond-level change) and
   **Khulna City**.
4. **Urban waterlogging is mostly invisible to this method.** Khulna City
   fails in every run: shallow street water between buildings doesn't read as
   radar-dark water. Satkhira town is mixed.

## Limits

- Boxes are broad search areas, so a flood covering part of a box is diluted.
- Sentinel-1 passes are 12 days apart per orbit; short events (Khulna City
  floods lasted 1–3 days) fall between passes.
- One pre-event pass makes the noise floor zero (Remal, both districts).
- The −14 dB threshold was calibrated on one small AOI in 2024.
- Not compared with any mapped flood extent — only with reports that a flood
  happened somewhere in the box.

## What to change next

Replace the absolute flag with an anomaly: new water relative to the same
season in earlier years (several years of same-orbit passes from the same
weeks), so normal monsoon wetting and permanent ponds both drop out. Use
event-sized boxes where a breach location is known, and report urban
waterlogging as out of scope for radar alone.
