#!/usr/bin/env python3
"""
Test all APsystems OpenAPI endpoints via the APSClient class.

Exercises:
  1. get_system_summary        – lifetime / today / month / year kWh
  2. get_system_energy_hourly  – hourly time-series for a given date
  3. get_inverters             – ECU + nested inverter UIDs
  4. get_inverter_energy       – per-inverter DC/AC power series

Usage:
  python test_all_endpoints.py --app-id ID --app-secret SECRET --sid SID [--base-url URL] [--date YYYY-MM-DD]
"""

import argparse
import asyncio
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

# Import api.py and const.py directly so we never trigger
# apsystems_openapi/__init__.py (which requires homeassistant).
_pkg_dir = Path(__file__).resolve().parent.parent / "apsystems_openapi"

def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_api_mod   = _load_module("aps_api",   _pkg_dir / "api.py")
_const_mod = _load_module("aps_const", _pkg_dir / "const.py")

APSClient        = _api_mod.APSClient
DEFAULT_BASE_URL = _const_mod.DEFAULT_BASE_URL


def pp(label: str, obj):
    """Pretty-print a section."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(obj, indent=2, default=str))


async def run(args):
    client = APSClient(
        app_id=args.app_id,
        app_secret=args.app_secret,
        sid=args.sid,
        base_url=args.base_url,
    )

    ok = 0
    fail = 0

    try:
        # ── 1. System Summary ──
        print("\n[1/4] Fetching system summary …")
        try:
            summary = await client.get_system_summary()
            pp("System Summary", summary)
            if isinstance(summary, dict) and summary.get("code") == 0:
                d = summary.get("data", {})
                print(f"\n  Today:    {d.get('today')} kWh")
                print(f"  Month:    {d.get('month')} kWh")
                print(f"  Year:     {d.get('year')} kWh")
                print(f"  Lifetime: {d.get('lifetime')} kWh")
                ok += 1
            else:
                print("  ⚠ Unexpected response (see above)")
                fail += 1
        except Exception as exc:
            print(f"  ✗ FAILED: {exc}")
            fail += 1

        # ── 2. Hourly Energy ──
        print(f"\n[2/4] Fetching hourly energy for {args.date} …")
        try:
            hourly = await client.get_system_energy_hourly(args.date)
            pp(f"Hourly Energy ({args.date})", hourly)
            if isinstance(hourly, dict) and hourly.get("code") == 0:
                series = hourly.get("data") or []
                total = None
                try:
                    total = round(sum(float(x) for x in series if x is not None), 3)
                except Exception:
                    pass
                print(f"\n  Data points: {len(series)}")
                if total is not None:
                    print(f"  Sum: {total} kWh")
                ok += 1
            else:
                print("  ⚠ Unexpected response (see above)")
                fail += 1
        except Exception as exc:
            print(f"  ✗ FAILED: {exc}")
            fail += 1

        # ── 3. Inverter List ──
        print("\n[3/4] Fetching inverter list …")
        inverter_uids = []
        try:
            inverters = await client.get_inverters()
            pp("Inverter List", inverters)
            if isinstance(inverters, dict) and inverters.get("code") == 0:
                # Extract UIDs – API nests them under "inverter" (singular)
                for ecu in (inverters.get("data") or []):
                    for inv in (ecu.get("inverter") or ecu.get("inverters") or []):
                        uid = inv.get("uid") or inv.get("inverter_uid")
                        if uid:
                            inverter_uids.append(uid)
                print(f"\n  Found {len(inverter_uids)} inverter(s): {inverter_uids}")
                ok += 1
            else:
                print("  ⚠ Unexpected response (see above)")
                fail += 1
        except Exception as exc:
            print(f"  ✗ FAILED: {exc}")
            fail += 1

        # ── 4. Per-Inverter Energy (minutely – used by HA integration) ──
        EXPECTED_MINUTELY_KEYS = {"dc_p1", "dc_p2", "ac_p1", "t"}
        EXPECTED_HOURLY_KEYS = {"e1", "e2"}
        if inverter_uids:
            # Test only the first inverter in both modes to conserve API budget
            test_uid = inverter_uids[0]

            # 4a. Minutely (what __init__.py + sensor.py use)
            print(f"\n[4/5] Fetching MINUTELY energy for inverter {test_uid} …")
            try:
                inv_min = await client.get_inverter_energy(test_uid, args.date, energy_level="minutely")
                data_keys = set(inv_min.get("data", {}).keys())
                pp(f"Minutely Energy – {test_uid} (keys: {sorted(data_keys)})", inv_min)
                if isinstance(inv_min, dict) and inv_min.get("code") == 0:
                    missing = EXPECTED_MINUTELY_KEYS - data_keys
                    if missing:
                        print(f"  ⚠ Missing expected keys: {missing}")
                        fail += 1
                    else:
                        print(f"  ✓ All expected keys present: {sorted(EXPECTED_MINUTELY_KEYS)}")
                        ok += 1
                else:
                    print(f"  ⚠ Unexpected response (see above)")
                    fail += 1
            except Exception as exc:
                print(f"  ✗ FAILED: {exc}")
                fail += 1

            # 4b. Hourly (for reference)
            print(f"\n[5/5] Fetching HOURLY energy for inverter {test_uid} …")
            try:
                inv_hr = await client.get_inverter_energy(test_uid, args.date, energy_level="hourly")
                data_keys = set(inv_hr.get("data", {}).keys())
                pp(f"Hourly Energy – {test_uid} (keys: {sorted(data_keys)})", inv_hr)
                if isinstance(inv_hr, dict) and inv_hr.get("code") == 0:
                    missing = EXPECTED_HOURLY_KEYS - data_keys
                    if missing:
                        print(f"  ⚠ Missing expected keys: {missing}")
                        fail += 1
                    else:
                        print(f"  ✓ All expected keys present: {sorted(EXPECTED_HOURLY_KEYS)}")
                        ok += 1
                else:
                    print(f"  ⚠ Unexpected response (see above)")
                    fail += 1
            except Exception as exc:
                print(f"  ✗ FAILED: {exc}")
                fail += 1
        else:
            print("\n[4/5] Skipped – no inverter UIDs discovered in step 3.")
            print("[5/5] Skipped – no inverter UIDs discovered in step 3.")

    finally:
        await client.close()

    # ── Summary ──
    total_tests = ok + fail
    print(f"\n{'='*60}")
    print(f"  RESULTS: {ok}/{total_tests} passed, {fail} failed")
    print(f"{'='*60}")
    return 0 if fail == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Test all APsystems OpenAPI endpoints")
    parser.add_argument("--app-id", required=True, help="APsystems App ID")
    parser.add_argument("--app-secret", required=True, help="APsystems App Secret")
    parser.add_argument("--sid", required=True, help="System ID")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date for energy queries (YYYY-MM-DD, default: today)")
    args = parser.parse_args()
    rc = asyncio.run(run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
