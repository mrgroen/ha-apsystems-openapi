#!/usr/bin/env python3
"""
APsystems DS3-L health checker (per-channel power) - Optimized version

- Auth: X-CA-* signature per APsystems OpenAPI manual
- Data: /user/api/v2/systems/inverters/{sid} to discover UIDs
        /user/api/v2/systems/{sid}/devices/inverter/energy/{uid}?energy_level=minutely&date_range=YYYY-MM-DD
- Flags: channel mismatch & flat-line
- Optimization: Rotating schedule to minimize API calls
- Special handling for single-panel microinverters

Usage:
  python apsys_health.py --app-id ... --app-secret ... --sid ... [--date 2025-08-09] [--base-url https://api.apsystemsema.com]
  
  # Check all inverters (override rotation)
  python apsys_health.py --app-id ... --app-secret ... --sid ... --check-all
  
  # Specify single-panel UIDs
  python apsys_health.py --app-id ... --app-secret ... --sid ... --single-panel-uids 703000421262
"""

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import statistics
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests


def _last_segment(path: str) -> str:
    s = path.strip("/").split("/")
    return s[-1]


def _now_ms() -> str:
    # APsystems examples show timestamp in milliseconds. (Community confirmations)
    return str(int(time.time() * 1000))


def _sign(
    method: str,
    path: str,
    app_id: str,
    app_secret: str,
    timestamp_ms: str,
    nonce: str,
    algo: str = "HmacSHA256",
) -> str:
    """
    stringToSign = X-CA-Timestamp + "/" + X-CA-Nonce + "/" + X-CA-AppId + "/" + RequestPath + "/" + HTTPMethod + "/" + X-CA-Signature-Method
    Signature = Base64(HMAC(algo, app_secret, stringToSign))
    """
    request_path_name = _last_segment(path)
    string_to_sign = f"{timestamp_ms}/{nonce}/{app_id}/{request_path_name}/{method.upper()}/{algo}"
    digestmod = hashlib.sha256 if algo == "HmacSHA256" else hashlib.sha1
    sig = hmac.new(app_secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod).digest()
    return base64.b64encode(sig).decode("utf-8")


class APSClient:
    def __init__(self, base_url: str, app_id: str, app_secret: str, algo: str = "HmacSHA256"):
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self.algo = algo

    def _headers(self, method: str, path: str) -> Dict[str, str]:
        ts = _now_ms()
        nonce = uuid.uuid4().hex  # 32 chars
        sig = _sign(method, path, self.app_id, self.app_secret, ts, nonce, self.algo)
        return {
            "X-CA-AppId": self.app_id,
            "X-CA-Timestamp": ts,
            "X-CA-Nonce": nonce,
            "X-CA-Signature-Method": self.algo,
            "X-CA-Signature": sig,
        }

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> dict:
        url = f"{self.base_url}{'' if path.startswith('/') else '/'}{path}"
        headers = self._headers("GET", path)
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "code" in data and data["code"] != 0:
            raise RuntimeError(f"API returned code {data['code']}: {data}")
        return data.get("data", data)

    # --- API wrappers ---

    def get_inverters(self, sid: str) -> List[Dict]:
        # /user/api/v2/systems/inverters/{sid}
        path = f"/user/api/v2/systems/inverters/{sid}"
        items = self._get(path)
        # Normalize into a flat list of {'eid':..., 'uid':..., 'type':...}
        out = []
        for ecu in items:
            eid = ecu.get("eid")
            for inv in ecu.get("inverter", []):
                out.append({"eid": eid, "uid": inv.get("uid"), "type": inv.get("type")})
        return out

    def get_inverter_minutely(self, sid: str, uid: str, day: str) -> dict:
        # /user/api/v2/systems/{sid}/devices/inverter/energy/{uid}
        path = f"/user/api/v2/systems/{sid}/devices/inverter/energy/{uid}"
        params = {"energy_level": "minutely", "date_range": day}
        return self._get(path, params=params)


# ---- Cache Management ----

def get_cached_inverters(client: APSClient, sid: str, cache_dir: str = ".apsys_cache", max_age_days: int = 30) -> List[Dict]:
    """Get inverters from cache if fresh, otherwise fetch and cache."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = Path(cache_dir) / f"inverters_{sid}.json"
    
    # Check cache freshness
    if cache_file.exists():
        cache_mtime = dt.datetime.fromtimestamp(cache_file.stat().st_mtime)
        if (dt.datetime.now() - cache_mtime).days < max_age_days:
            print(f"Using cached inverter list (age: {(dt.datetime.now() - cache_mtime).days} days)")
            with open(cache_file) as f:
                return json.load(f)
    
    # Fetch fresh data
    print("Fetching fresh inverter list (cache expired or missing)")
    invs = client.get_inverters(sid)
    with open(cache_file, 'w') as f:
        json.dump(invs, f, indent=2)
    return invs


# ---- Rotation Schedule ----

def get_inverters_for_today(all_inverters: List[Dict], check_all: bool = False, rotation_days: int = 3) -> List[Dict]:
    """
    Rotate through inverters, checking ~1/3 each day.
    This gives each inverter a check every 3 days.
    """
    if check_all:
        return all_inverters
    
    # Use day of year for consistent rotation
    day_of_year = dt.date.today().timetuple().tm_yday
    
    # Sort UIDs for consistent ordering
    sorted_invs = sorted(all_inverters, key=lambda x: x.get("uid", ""))
    
    # Determine which batch to check today
    batch_size = len(sorted_invs) // rotation_days
    remainder = len(sorted_invs) % rotation_days
    
    batch_num = day_of_year % rotation_days
    start_idx = batch_num * batch_size + min(batch_num, remainder)
    
    # Add 1 to batch_size for the first 'remainder' batches to distribute evenly
    if batch_num < remainder:
        end_idx = start_idx + batch_size + 1
    else:
        end_idx = start_idx + batch_size
    
    return sorted_invs[start_idx:end_idx]


# ---- Single Panel Detection ----

def parse_single_panel_uids(uid_specs: List[str]) -> Set[str]:
    """
    Parse single-panel UID specifications.
    Input: ['703000433609'] 
    Output: {'703000433609-1', '703000433609-2'} (both channels marked as single-panel config)
    """
    single_panel_uids = set()
    for spec in uid_specs:
        if '-' in spec:
            # Full UID specified
            single_panel_uids.add(spec)
        else:
            # Base UID specified, add both channels
            single_panel_uids.add(f"{spec}-1")
            single_panel_uids.add(f"{spec}-2")
    return single_panel_uids


def detect_active_channel(dc_p1: List[float], dc_p2: List[float], threshold: float = 10.0) -> Optional[int]:
    """
    Detect which channel has a panel attached (for single-panel configs).
    Returns: 1 for channel 1, 2 for channel 2, None if unclear
    """
    # Check max power on each channel
    p1_max = max((p for p in dc_p1 if p == p), default=0)  # p == p filters NaN
    p2_max = max((p for p in dc_p2 if p == p), default=0)
    
    # Count samples above threshold
    p1_active_samples = sum(1 for p in dc_p1 if p == p and p > threshold)
    p2_active_samples = sum(1 for p in dc_p2 if p == p and p > threshold)
    
    # Determine active channel
    if p1_max > threshold and p2_max < threshold:
        return 1
    elif p2_max > threshold and p1_max < threshold:
        return 2
    elif p1_active_samples > 10 and p2_active_samples < 5:
        return 1
    elif p2_active_samples > 10 and p1_active_samples < 5:
        return 2
    
    return None  # Can't determine or both active


# ---- Health heuristics ----

def rolling_mismatch_flags(
    p1: List[float],
    p2: List[float],
    times: List[str],
    pct_drop: float = 0.25,         # 25%
    min_watts: float = 150.0,       # ignore low-signal periods
    min_consecutive: int = 15,      # minutes
) -> List[Tuple[str, str]]:
    """
    Returns list of (start_time, end_time) windows where |p1 - p2|/max(p1,p2) >= pct_drop
    and both channels >= min_watts for >= min_consecutive consecutive samples.
    """
    assert len(p1) == len(p2) == len(times)
    bad = []
    start = None
    for i, (a, b, t) in enumerate(zip(p1, p2, times)):
        high = max(a, b)
        low = min(a, b)
        good_power = (a >= min_watts) and (b >= min_watts)
        mismatch = (high > 0) and ((high - low) / high >= pct_drop)
        if good_power and mismatch:
            if start is None:
                start = i
        else:
            if start is not None:
                if i - start >= min_consecutive:
                    bad.append((times[start], times[i - 1]))
                start = None
    if start is not None and len(times) - start >= min_consecutive:
        bad.append((times[start], times[-1]))
    return bad


def flatline_flags(
    channel: List[float],
    peer_sum: List[float],
    times: List[str],
    near_zero: float = 5.0,
    peer_min: float = 150.0,
    min_consecutive: int = 15,
) -> List[Tuple[str, str]]:
    """
    Flags windows where channel ~0 while peers (same inverter) are producing.
    peer_sum can be dc_p1+dc_p2 or ac_p as a proxy.
    """
    assert len(channel) == len(peer_sum) == len(times)
    bad = []
    start = None
    for i, (c, s) in enumerate(zip(channel, peer_sum)):
        cond = (c <= near_zero) and (s >= peer_min)
        if cond:
            if start is None:
                start = i
        else:
            if start is not None:
                if i - start >= min_consecutive:
                    bad.append((times[start], times[i - 1]))
                start = None
    if start is not None and len(times) - start >= min_consecutive:
        bad.append((times[start], times[-1]))
    return bad


def parse_float_list(xs) -> List[float]:
    # API returns strings; be robust against nulls
    out = []
    for x in xs or []:
        try:
            out.append(float(x))
        except Exception:
            out.append(float("nan"))
    return out


def analyze_inverter(uid: str, blob: dict, single_panel_uids: Set[str] = None) -> Dict:
    """
    Expects keys (when energy_level=minutely): t, dc_p1, dc_p2, ac_p (W).
    Handles single-panel configurations properly.
    """
    single_panel_uids = single_panel_uids or set()
    is_single_panel = uid in single_panel_uids
    
    t = blob.get("t") or blob.get("time") or []
    dc_p1 = parse_float_list(blob.get("dc_p1"))
    dc_p2 = parse_float_list(blob.get("dc_p2"))
    ac_p = parse_float_list(blob.get("ac_p1") or blob.get("ac_p"))

    # If lists differ in length, pad/truncate safely
    n = min(len(t), len(dc_p1), len(dc_p2))
    t, dc_p1, dc_p2 = t[:n], dc_p1[:n], dc_p2[:n]
    ac_p = ac_p[:n] if ac_p else [a + b for a, b in zip(dc_p1, dc_p2)]

    # Detect active channel for single-panel configs
    active_channel = None
    if is_single_panel:
        active_channel = detect_active_channel(dc_p1, dc_p2)
    
    # Heuristics - adjust for single-panel configs
    if is_single_panel:
        # No mismatch detection for single-panel units
        mismatch = []
        
        if active_channel == 1:
            # Only check channel 1 for flatline (channel 2 is expected to be flat)
            flat1 = flatline_flags(dc_p1, ac_p, t)
            flat2 = []
        elif active_channel == 2:
            # Only check channel 2 for flatline (channel 1 is expected to be flat)
            flat1 = []
            flat2 = flatline_flags(dc_p2, ac_p, t)
        else:
            # Can't determine active channel, skip flatline detection
            flat1 = flat2 = []
    else:
        # Normal dual-channel analysis
        mismatch = rolling_mismatch_flags(dc_p1, dc_p2, t)
        flat1 = flatline_flags(dc_p1, [a + b for a, b in zip(dc_p1, dc_p2)], t)
        flat2 = flatline_flags(dc_p2, [a + b for a, b in zip(dc_p1, dc_p2)], t)

    # Stats snapshot for context
    def pct_of_peak(series):
        clean = [x for x in series if x == x]  # drop NaNs
        return (max(clean) if clean else 0.0)

    return {
        "uid": uid,
        "points": n,
        "p1_peak_W": round(pct_of_peak(dc_p1), 1),
        "p2_peak_W": round(pct_of_peak(dc_p2), 1),
        "ac_peak_W": round(pct_of_peak(ac_p), 1),
        "mismatch_windows": mismatch,
        "flat_p1_windows": flat1,
        "flat_p2_windows": flat2,
        "is_single_panel": is_single_panel,
        "active_channel": active_channel,
    }


# ---- Issue History Tracking ----

class IssueTracker:
    """Track historical issues to enable adaptive checking in future versions."""
    
    def __init__(self, cache_dir: str = ".apsys_cache"):
        self.cache_dir = Path(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.history_file = self.cache_dir / "issue_history.json"
        self.load_history()
    
    def load_history(self):
        try:
            with open(self.history_file) as f:
                self.history = json.load(f)
        except FileNotFoundError:
            self.history = {}
    
    def save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def record_check(self, uid: str, date: str, issues: List[str]):
        """Record issues found for an inverter on a given date."""
        if uid not in self.history:
            self.history[uid] = []
        
        entry = {"date": date, "issues": issues}
        self.history[uid].append(entry)
        
        # Keep only last 30 days
        cutoff = (dt.datetime.now() - dt.timedelta(days=30)).strftime("%Y-%m-%d")
        self.history[uid] = [e for e in self.history[uid] if e["date"] >= cutoff]
        
        self.save_history()
    
    def get_recent_issues(self, uid: str, days: int = 7) -> List[Dict]:
        """Get recent issues for an inverter."""
        if uid not in self.history:
            return []
        
        cutoff = (dt.datetime.now() - dt.timedelta(days=days)).strftime("%Y-%m-%d")
        return [e for e in self.history[uid] if e["date"] >= cutoff and e["issues"]]


def send_email_alert(config: Dict, subject: str, body: str, html_body: Optional[str] = None):
    """Send email alert using SMTP."""
    if not config.get("enabled"):
        return
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["from_addr"]
        msg["To"] = config["to_addr"]
        
        # Add plain text part
        msg.attach(MIMEText(body, "plain"))
        
        # Add HTML part if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        
        # Send via SMTP
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            if config.get("use_tls"):
                server.starttls()
            if config.get("smtp_user") and config.get("smtp_pass"):
                server.login(config["smtp_user"], config["smtp_pass"])
            server.send_message(msg)
            
        print(f"📧 Alert email sent to {config['to_addr']}")
    except Exception as e:
        print(f"⚠️  Failed to send email alert: {e}")


def format_alert_email(reports: List[Dict], day: str, total_checked: int, total_inverters: int) -> Tuple[str, str]:
    """Format alert email with issue details."""
    issues_by_type = {"mismatch": [], "flat_p1": [], "flat_p2": []}
    
    for report in reports:
        uid = report["uid"]
        if report["mismatch_windows"]:
            for w in report["mismatch_windows"]:
                issues_by_type["mismatch"].append(f"{uid}: {w[0]} → {w[1]}")
        if report["flat_p1_windows"]:
            for w in report["flat_p1_windows"]:
                issues_by_type["flat_p1"].append(f"{uid}: {w[0]} → {w[1]}")
        if report["flat_p2_windows"]:
            for w in report["flat_p2_windows"]:
                issues_by_type["flat_p2"].append(f"{uid}: {w[0]} → {w[1]}")
    
    # Plain text version
    text_body = f"""APsystems Health Check Alert - {day}

ISSUES DETECTED:
"""
    
    if issues_by_type["mismatch"]:
        text_body += f"\n⚠️  CHANNEL MISMATCH (>25% difference):\n"
        for issue in issues_by_type["mismatch"]:
            text_body += f"   • {issue}\n"
    
    if issues_by_type["flat_p1"]:
        text_body += f"\n⚠️  CHANNEL 1 FLATLINE:\n"
        for issue in issues_by_type["flat_p1"]:
            text_body += f"   • {issue}\n"
    
    if issues_by_type["flat_p2"]:
        text_body += f"\n⚠️  CHANNEL 2 FLATLINE:\n"
        for issue in issues_by_type["flat_p2"]:
            text_body += f"   • {issue}\n"
    
    text_body += f"""
SUMMARY:
• Inverters checked: {total_checked} of {total_inverters}
• Total issues found: {sum(len(v) for v in issues_by_type.values())}
• Date checked: {day}

This is an automated alert from the APsystems health checker.
"""
    
    # HTML version
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            h2 {{ color: #d97706; }}
            .issue-type {{ margin: 20px 0; }}
            .issue-list {{ background: #fef3c7; padding: 10px; border-radius: 5px; }}
            .issue-item {{ margin: 5px 0; padding: 5px; }}
            .summary {{ background: #f3f4f6; padding: 15px; border-radius: 5px; margin-top: 20px; }}
            .footer {{ color: #6b7280; font-size: 0.9em; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h1>🔋 APsystems Health Check Alert</h1>
        <p>Issues detected on <strong>{day}</strong></p>
    """
    
    if issues_by_type["mismatch"]:
        html_body += """
        <div class="issue-type">
            <h2>⚠️ Channel Mismatch Issues</h2>
            <div class="issue-list">
                <p>Channels differ by >25% while both producing >150W:</p>
        """
        for issue in issues_by_type["mismatch"]:
            html_body += f"<div class='issue-item'>• {issue}</div>"
        html_body += "</div></div>"
    
    if issues_by_type["flat_p1"]:
        html_body += """
        <div class="issue-type">
            <h2>⚠️ Channel 1 Flatline Issues</h2>
            <div class="issue-list">
        """
        for issue in issues_by_type["flat_p1"]:
            html_body += f"<div class='issue-item'>• {issue}</div>"
        html_body += "</div></div>"
    
    if issues_by_type["flat_p2"]:
        html_body += """
        <div class="issue-type">
            <h2>⚠️ Channel 2 Flatline Issues</h2>
            <div class="issue-list">
        """
        for issue in issues_by_type["flat_p2"]:
            html_body += f"<div class='issue-item'>• {issue}</div>"
        html_body += "</div></div>"
    
    html_body += f"""
        <div class="summary">
            <h3>Summary</h3>
            <ul>
                <li>Inverters checked: <strong>{total_checked}</strong> of {total_inverters}</li>
                <li>Total issues found: <strong>{sum(len(v) for v in issues_by_type.values())}</strong></li>
                <li>Date checked: <strong>{day}</strong></li>
            </ul>
        </div>
        <div class="footer">
            <p>This is an automated alert from the APsystems health checker.</p>
        </div>
    </body>
    </html>
    """
    
    return text_body, html_body


def load_email_config(config_file: str = None) -> Dict:
    """Load email configuration from file or environment variables."""
    config = {
        "enabled": False,
        "smtp_host": "localhost",
        "smtp_port": 587,
        "use_tls": True,
        "smtp_user": None,
        "smtp_pass": None,
        "from_addr": "apsystems-monitor@localhost",
        "to_addr": None
    }
    
    # Try loading from config file
    if config_file and Path(config_file).exists():
        with open(config_file) as f:
            file_config = json.load(f)
            config.update(file_config.get("email", {}))
    
    # Override with environment variables if present
    env_mapping = {
        "APSYS_EMAIL_ENABLED": ("enabled", lambda x: x.lower() == "true"),
        "APSYS_SMTP_HOST": ("smtp_host", str),
        "APSYS_SMTP_PORT": ("smtp_port", int),
        "APSYS_SMTP_TLS": ("use_tls", lambda x: x.lower() == "true"),
        "APSYS_SMTP_USER": ("smtp_user", str),
        "APSYS_SMTP_PASS": ("smtp_pass", str),
        "APSYS_EMAIL_FROM": ("from_addr", str),
        "APSYS_EMAIL_TO": ("to_addr", str)
    }
    
    for env_key, (config_key, converter) in env_mapping.items():
        if env_key in os.environ:
            config[config_key] = converter(os.environ[env_key])
    
    # Email is enabled if we have a recipient
    if config["to_addr"]:
        config["enabled"] = True
    
    return config
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--app-secret", required=True)
    ap.add_argument("--sid", required=True)
    ap.add_argument("--date", help="YYYY-MM-DD (defaults to yesterday in local time)")
    ap.add_argument("--base-url", default="https://api.apsystemsema.com", 
                    help="e.g., https://api.apsystemsema.com:9282")
    ap.add_argument("--check-all", action="store_true", 
                    help="Check all inverters (override rotation schedule)")
    ap.add_argument("--rotation-days", type=int, default=3,
                    help="Number of days to rotate through all inverters (default: 3)")
    ap.add_argument("--single-panel-uids", nargs="*", default=[],
                    help="Base UIDs for single-panel microinverters (e.g., 703000433609)")
    ap.add_argument("--cache-dir", default=".apsys_cache",
                    help="Directory for cache files")
    args = ap.parse_args()

    if args.date:
        day = args.date
    else:
        day = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")

    # Parse single-panel UIDs
    single_panel_uids = parse_single_panel_uids(args.single_panel_uids)
    if single_panel_uids:
        print(f"Single-panel configuration UIDs: {sorted(single_panel_uids)}")

    client = APSClient(args.base_url, args.app_id, args.app_secret)
    tracker = IssueTracker(args.cache_dir)

    # 1) Get inverters (cached)
    invs = get_cached_inverters(client, args.sid, args.cache_dir)
    if not invs:
        print("No inverters found. Check SID or permissions.")
        return

    # 2) Determine which inverters to check today
    todays_inverters = get_inverters_for_today(invs, args.check_all, args.rotation_days)
    
    print(f"System {args.sid}: {len(invs)} total inverters")
    print(f"Checking {len(todays_inverters)} inverters today for {day}")
    if not args.check_all:
        print(f"(Rotation schedule: each inverter checked every {args.rotation_days} days)")
    print()

    # Show which inverters are being checked
    checked_uids = {inv["uid"] for inv in todays_inverters}
    skipped_uids = {inv["uid"] for inv in invs} - checked_uids
    if skipped_uids and not args.check_all:
        print(f"Today's batch: {', '.join(sorted(checked_uids)[:5])}...")
        print(f"Skipping (scheduled for other days): {', '.join(sorted(skipped_uids)[:5])}...")
        print()

    any_flags = False
    total_api_calls = 0
    
    for inv in todays_inverters:
        uid = inv["uid"]
        try:
            data = client.get_inverter_minutely(args.sid, uid, day)
            total_api_calls += 1
        except Exception as e:
            print(f"[{uid}] error fetching data: {e}")
            continue

        report = analyze_inverter(uid, data, single_panel_uids)
        
        # Format output based on whether it's single-panel
        if report["is_single_panel"]:
            active = report.get("active_channel")
            if active:
                print(f"Inverter {uid} (SINGLE-PANEL on ch{active}): ", end="")
                print(f"peak p{active}={report[f'p{active}_peak_W']} W, ac={report['ac_peak_W']} W  (points={report['points']})")
            else:
                print(f"Inverter {uid} (SINGLE-PANEL): peak p1={report['p1_peak_W']} W, p2={report['p2_peak_W']} W, ac={report['ac_peak_W']} W")
        else:
            print(f"Inverter {uid}: peak p1={report['p1_peak_W']} W, p2={report['p2_peak_W']} W, ac={report['ac_peak_W']} W  (points={report['points']})")

        # Collect issues for tracking
        issues = []
        
        if report["mismatch_windows"]:
            any_flags = True
            issues.append("mismatch")
            for w in report["mismatch_windows"]:
                print(f"  ⚠️  Channel mismatch >25% [{w[0]} → {w[1]}]")

        if report["flat_p1_windows"]:
            any_flags = True
            issues.append("flat_p1")
            for w in report["flat_p1_windows"]:
                print(f"  ⚠️  P1 flat-line [{w[0]} → {w[1]}] while peer producing")

        if report["flat_p2_windows"]:
            any_flags = True
            issues.append("flat_p2")
            for w in report["flat_p2_windows"]:
                print(f"  ⚠️  P2 flat-line [{w[0]} → {w[1]}] while peer producing")

        if not issues:
            print("  ✓  No issues detected by heuristics.")
        
        # Track issues for this inverter
        tracker.record_check(uid, day, issues)
        
        # Show recent history if there are issues
        if issues:
            recent = tracker.get_recent_issues(uid, days=7)
            if len(recent) > 1:
                print(f"  📊 Recent issues: {len(recent)} occurrences in past 7 days")

        print()

    print("-" * 60)
    if not any_flags:
        print("✅ All checked inverters are healthy for the selected day.")
    else:
        print("⚠️  Some issues detected. See details above.")
    
    print(f"\n📊 Summary:")
    print(f"  - Total inverters: {len(invs)}")
    print(f"  - Checked today: {len(todays_inverters)}")
    print(f"  - API calls used: {total_api_calls} (plus 1 if inverter list wasn't cached)")
    
    if not args.check_all:
        next_batch_day = (dt.date.today() + dt.timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"  - Next batch: {next_batch_day} (different set of inverters)")
        
        # Estimate monthly usage
        monthly_calls = (30 // args.rotation_days) * len(invs) + 1  # +1 for monthly inverter list refresh
        print(f"  - Estimated monthly API calls: ~{monthly_calls}")

if __name__ == "__main__":
    main()