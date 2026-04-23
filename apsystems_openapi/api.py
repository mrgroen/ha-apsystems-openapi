import base64, hmac, hashlib, time, uuid, aiohttp, logging, json
#from urllib.parse import urlencode

_LOGGER = logging.getLogger(__name__)

def _build_signature(app_id, app_secret, path, method):
    ts = str(int(time.time() * 1000))        # milliseconds
    nonce = uuid.uuid4().hex                 # 32-char hex
    sig_method = "HmacSHA256"
    # <-- sign ONLY the last path segment (e.g., "summary" or "energy")
    request_path_to_sign = path.rsplit("/", 1)[-1]
    s2s = "/".join([ts, nonce, app_id, request_path_to_sign, method.upper(), sig_method])
    sig = base64.b64encode(hmac.new(app_secret.encode(), s2s.encode(), hashlib.sha256).digest()).decode()
    headers = {
        "Content-Type": "application/json",
        "X-CA-AppId": app_id,
        "X-CA-Timestamp": ts,
        "X-CA-Nonce": nonce,
        "X-CA-Signature-Method": sig_method,
        "X-CA-Signature": sig,
    }
    return headers, s2s

class APSClient:
    def __init__(self, app_id, app_secret, sid, base_url, session: aiohttp.ClientSession | None = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.sid = sid
        self.base_url = base_url.rstrip("/")
        self._session = session or aiohttp.ClientSession()
        self._owns_session = session is None # track ownership

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, params: dict | None = None):
        url = self.base_url + path
        headers, s2s = _build_signature(self.app_id, self.app_secret, path, "GET")
        # Helpful debug line:
        _LOGGER.debug("APS GET %s params=%s s2s_preview=%s…", path, params, s2s[:60])
        async with self._session.get(url, headers=headers, params=params) as r:
            txt = await r.text()
            _LOGGER.debug("APS %s → %s %s", url, r.status, txt[:500])
            r.raise_for_status()
            return json.loads(txt)

    async def get_system_summary(self):
        return await self._get(f"/user/api/v2/systems/summary/{self.sid}")

    async def get_system_energy_hourly(self, date_str: str):
        # NOTE: put query params in ?…, do NOT include them in signature
        return await self._get(
            f"/user/api/v2/systems/energy/{self.sid}",
            params={"energy_level": "hourly", "date_range": date_str},
        )

    async def get_inverters(self):
        """Get list of inverters (ECUs + nested inverter UIDs) for this system."""
        return await self._get(f"/user/api/v2/systems/inverters/{self.sid}")

    async def get_inverter_energy(self, uid: str, date_str: str, energy_level: str = "hourly"):
        """Get per-inverter energy/power data (dc_p1, dc_p2, ac_p, time series)."""
        return await self._get(
            f"/user/api/v2/systems/{self.sid}/devices/inverter/energy/{uid}",
            params={"energy_level": energy_level, "date_range": date_str},
        )

    async def get_inverter_batch_power(self, eid: str, date_str: str):
        """Get power telemetry for ALL inverters under an ECU in one call."""
        return await self._get(
            f"/user/api/v2/systems/{self.sid}/devices/inverter/batch/energy/{eid}",
            params={"energy_level": "power", "date_range": date_str},
        )
