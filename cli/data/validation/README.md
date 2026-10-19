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

## Second method: seasonal anomaly

`python scripts/validate_anomaly.py` (results in
[`anomaly_results.json`](anomaly_results.json)). Rule fixed before running:

- **Climatology:** for each pixel, how often it was water (VV < −14 dB) in
  same-orbit passes from the same calendar weeks of the previous 5 years.
  The event window is padded to ≥ 24 days so each year has ≥ 2 passes.
- **Anomalous water:** water now where the pixel was water in < 20% of those
  past passes — permanent ghers and normal monsoon wetting drop out.
- **Detected:** peak anomaly ≥ max(2%, mean + 3 SD of the past years' own
  anomaly fractions, each scored leave-one-year-out).
- **Control:** the same rule one year earlier, against that year's own
  previous 5 years.

| Event | Anomaly peak (desc / asc) | Needed | Detected | Control year peak / detected |
|---|---|---|---|---|
| Satkhira Sadar/Tala, Sep 2024 | 8.3% / 6.9% | 6.0 / 5.4 | **yes / yes** | 0.8% / 1.4% — no / no |
| Khulna City, Sep 2024 | 1.8% / 1.5% | 2.9 / 3.3 | no / no | no / no |
| Remal, Satkhira, May 2024 | 5.5% / 4.0% | 5.1 / 5.5 | **yes** / no | 4.1% / 2.9% — no / no |
| Remal, Khulna, May 2024 | 3.5% / 2.5% | 3.7 / 6.1 | no / no | no / no |
| Bichhat breach, Mar 2025 | 1.5% / 0.8% | 3.6 / 4.7 | no / no | no / no |
| Dargahpur, May 2025 | 1.1% / 1.2% | 4.8 / 4.5 | no / no | 4.3% / 2.4% — **yes** ¹ / no |
| Satkhira town, Jul 2025 | 5.7% / 8.1% | 9.9 / 7.5 | no / **yes** | – / 1.5% — no data / no |
| Ashashuni, Jul 2025 | 2.1% / 4.4% | 6.3 / 4.1 | no / **yes** | – / 4.9% — no data / **yes** |
| Satkhira town, Jul 2026 | 2.2% / 1.9% | 9.1 / 10.4 | no / no | no / no |
| Khulna City, Jul 2026 | 2.0% / 2.6% | 4.2 / 5.7 | no / no | no / no |

¹ Control window (May–Jun 2024) contains Cyclone Remal.

**Reading:** also 4 of 10 events detected in at least one orbit, but a better
detector than the first method. The largest flood (Satkhira Sep 2024) is
caught in both orbits with a quiet control year; none of the hits rests on a
single-pass baseline; and the control fires in 2 of 18 orbit runs with data,
one of which is the real Remal flood. Ashashuni's hit is not specific (its
control year fires too). Small breaches inside large boxes, 1–3-day urban
floods in Khulna, and Satkhira town 2026 are missed. The last shows a known
weakness: the July 2025 flood sits inside the 2026 climatology, inflating
the noise estimate to 9–10%.

## What to change next

- **In the product:** replace the absolute ≥ 40% / 14-day flag with the
  seasonal anomaly, reported as a measured share of the parcel plus how it
  compares with past years — not a yes/no payout-style trigger. On these
  tests it detects the large rural floods and rarely fires without one; it
  does not detect small breaches or urban waterlogging.
- **Validation:** event-sized boxes where breach locations are known, and a
  mapped flood extent (e.g. a published Sentinel-1 flood map) for a
  pixel-level check instead of "a flood happened somewhere in this box".
- **Method:** exclude known past flood dates from the climatology.
