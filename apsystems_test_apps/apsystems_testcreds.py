!/usr/bin/env python3
import asyncio
import aiohttp
import time
import uuid
import hmac
import hashlib
import base64
import argparse
from datetime import date

# ---- USER DEFAULTS (override via CLI) ----
APP_ID     = "YOUR_APP_ID"
APP_SECRET = "YOUR_APP_SECRET"
SID        = "YOUR_SYSTEM_ID"
BASE_URL   = "https://api.apsystemsema.com:9282"  # Change if your region differs
# ------------------------------------------

SIG_METHOD = "HmacSHA256"

def build_headers(app_id: str, app_secret: str, path: str, method: str = "GET"):
    """Sign ONLY the last path segment per APsystems manual."""
    ts = str(int(time.time() * 1000))  # milliseconds
    nonce = uuid.uuid4().hex
    request_path_to_sign = path.rsplit("/", 1)[-1]
    s2s = "/".join([ts, nonce, app_id, request_path_to_sign, method.upper(), SIG_METHOD])

    sig = base64.b64encode(
        hmac.new(app_secret.encode(), s2s.encode(), hashlib.sha256).digest()
    ).decode()

    return {
        "Content-Type": "application/json",
        "X-CA-AppId": app_id,
        "X-CA-Timestamp": ts,
        "X-CA-Nonce": nonce,
        "X-CA-Signature-Method": SIG_METHOD,
        "X-CA-Signature": sig,
    }

async def get_json(session: aiohttp.ClientSession, url: str, headers: dict, params: dict | None = None):
    async with session.get(url, headers=headers, params=params) as resp:         
        text = await resp.text()
        try:
            data = await resp.json()
        except Exception:
            return resp.status, {"non_json": text}
        return resp.status, data

async def main():
    parser = argparse.ArgumentParser(description="APsystems OpenAPI credential + endpoint test")
    parser.add_argument("--app-id", default=APP_ID)
    parser.add_argument("--app-secret", default=APP_SECRET)
    parser.add_argument("--sid", default=SID)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD for hourly test (default: today)")
    args = parser.parse_args()

    summary_path = f"/user/api/v2/systems/summary/{args.sid}"
    hourly_path  = f"/user/api/v2/systems/energy/{args.sid}"

    async with aiohttp.ClientSession() as session:
        # ---- Summary (lifetime/today/month/year) ----
        sum_headers = build_headers(args.app_id, args.app_secret, summary_path, "GET")
        status, payload = await get_json(session, args.base_url + summary_path, sum_headers)

        if isinstance(payload, dict) and payload.get("code") == 0:
            d = payload.get("data", {})
            print("Summary OK (code:0)")
            print(f"   Today:    {d.get('today')} kWh")
            print(f"   Month:    {d.get('month')} kWh")
            print(f"   Year:     {d.get('year')} kWh")
            print(f"   Lifetime: {d.get('lifetime')} kWh")
        else:
            print(f"Summary ERROR (HTTP {status}): {payload}")
            # If summary fails, hourly likely will too; continue anyway.

        # ---- Hourly (per-day series) ----
        hr_headers = build_headers(args.app_id, args.app_secret, hourly_path, "GET")
        params = {"energy_level": "hourly", "date_range": args.date}
        status, payload = await get_json(session, args.base_url + hourly_path, hr_headers, params=params)

        if isinstance(payload, dict) and payload.get("code") == 0:
            series = payload.get("data") or []
            total = None
            print("-----")
            try:
                total = round(sum(float(x) for x in series if x is not None), 3)
            except Exception:
                pass
            print(f"Hourly OK (code:0) for {args.date}")
            print(f"   Points: {len(series)}  Example: {series[:5]}")
            if total is not None:
                print(f"   Sum today: {total} kWh")
        else:
            # Common: { "code": 5000 } when hourly data isn't available yet or transient
            print("-----")
            print(f"Hourly ERROR (HTTP {status}) for {args.date}: {payload}")

if __name__ == "__main__":
    asyncio.run(main())
