"""Run flood detection against documented events and write a results file.

    python scripts/validate_events.py [data/validation/events.json] [event_id ...]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ee  # noqa: E402

import config  # noqa: E402
from core.validation import validate_event  # noqa: E402


def _pct(v):
    return "  –  " if v is None else f"{v:5.1%}"


def main():
    args = sys.argv[1:]
    events_path = args.pop(0) if args and args[0].endswith(".json") else "data/validation/events.json"
    only = set(args)
    if not config.EE_PROJECT:
        raise SystemExit("Set EE_PROJECT_ID to your Google Cloud project first.")
    ee.Initialize(project=config.EE_PROJECT)

    events = json.load(open(events_path))["events"]
    results = []
    for event in events:
        if only and event["id"] not in only:
            continue
        print(f"… {event['id']}", flush=True)
        for attempt in range(4):
            try:
                r = validate_event(event)
                break
            except ee.EEException as e:
                # Earth Engine throttles bursts ("Too many concurrent aggregations").
                if attempt == 3 or "concurrent" not in str(e).lower():
                    raise
                time.sleep(30 * (attempt + 1))
        r.update({k: event[k] for k in ("name", "type", "setting", "confidence")})
        results.append(r)

    out = Path(events_path).with_name("results.json")
    json.dump({"sar_water_vv_db_max": config.SAR_WATER_VV_DB_MAX, "results": results}, open(out, "w"), indent=2)

    print(f"\n{'event':26} {'setting':12} {'orbit':5} {'pre':>3}/{'dur':<3} {'pre wet':>7} {'dur wet':>7} {'new peak':>8} {'need':>6}  detected  | product flag: event / year before")
    for r in results:
        for orbit, o in r["orbits"].items():
            det = {True: "YES", False: "no", None: "no data"}[o["detected"]]
            p, c = r["product"], r["product_control"]
            print(f"{r['id']:26} {r['setting']:12} {orbit[:4]:5} {o['n_pre']:>3}/{o['n_during']:<3} "
                  f"{_pct(o['pre_water_mean'])}   {_pct(o['during_water_max'])}  {_pct(o['new_water_peak'])}  {_pct(o['new_water_threshold'])}  {det:8}  | "
                  f"{'FLAG' if p['flagged'] else 'none'} ({p['longest_run_days']} d) / control yr {'FLAG' if c['flagged'] else 'none'} ({c['longest_run_days']} d)")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
