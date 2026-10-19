"""Score the seasonal-anomaly flood detector on the documented events, with
the same rule a year earlier as a control.

    python scripts/validate_anomaly.py [data/validation/events.json] [event_id ...]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ee  # noqa: E402

import config  # noqa: E402
from core.anomaly import evaluate  # noqa: E402
from core.validation import _scale_for, year_earlier  # noqa: E402


def _retry(fn, *a):
    for attempt in range(4):
        try:
            return fn(*a)
        except ee.EEException as e:
            if attempt == 3 or "concurrent" not in str(e).lower():
                raise
            time.sleep(30 * (attempt + 1))


def _pct(v):
    return "  –  " if v is None else f"{v:5.1%}"


def main():
    args = sys.argv[1:]
    events_path = args.pop(0) if args and args[0].endswith(".json") else "data/validation/events.json"
    only = set(args)
    if not config.EE_PROJECT:
        raise SystemExit("Set EE_PROJECT_ID to your Google Cloud project first.")
    ee.Initialize(project=config.EE_PROJECT)

    results = []
    for event in json.load(open(events_path))["events"]:
        if only and event["id"] not in only:
            continue
        print(f"… {event['id']}", flush=True)
        w, s, e, n = event["bbox"]
        aoi = ee.Geometry.Rectangle([w, s, e, n])
        scale = _scale_for(aoi)
        r = {k: event[k] for k in ("id", "name", "type", "setting", "confidence")}
        r.update(scale_m=scale, orbits={}, control_orbits={})
        for orbit in ("DESCENDING", "ASCENDING"):
            r["orbits"][orbit] = _retry(evaluate, event, aoi, orbit, scale)
            r["control_orbits"][orbit] = _retry(evaluate, year_earlier(event), aoi, orbit, scale)
        results.append(r)

    out = Path(events_path).with_name("anomaly_results.json")
    json.dump({"sar_water_vv_db_max": config.SAR_WATER_VV_DB_MAX, "results": results}, open(out, "w"), indent=2)

    verdict = {True: "YES", False: "no", None: "no data"}
    print(f"\n{'event':26} {'setting':12} {'orbit':5} {'n':>2} {'peak':>6} {'need':>6} {'detected':8} | control: {'peak':>6} {'need':>6} detected")
    for r in results:
        for orbit in ("DESCENDING", "ASCENDING"):
            o, c = r["orbits"][orbit], r["control_orbits"][orbit]
            print(f"{r['id']:26} {r['setting']:12} {orbit[:4]:5} {len(o['passes']):>2} {_pct(o['peak'])} {_pct(o['threshold'])} {verdict[o['detected']]:8} | "
                  f"         {_pct(c['peak'])} {_pct(c['threshold'])} {verdict[c['detected']]}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
