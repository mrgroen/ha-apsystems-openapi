from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now, as_local

from .const import DOMAIN, PLATFORMS, DEFAULT_BASE_URL
from .api import APSClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    data = entry.data  # <— fix
    session = async_get_clientsession(hass)

    client = APSClient(
        app_id=data["app_id"],
        app_secret=data["app_secret"],
        sid=data["sid"],
        base_url=data.get("base_url", DEFAULT_BASE_URL),
        session=session,
    )

    async def _async_update():
        try:
            # 1) lifetime/today/month/year
            summary = await client.get_system_summary()
            if summary.get("code") != 0:
                raise UpdateFailed(f"APsystems summary error: {summary}")

            # 2) today's hourly series
            date_str = as_local(now()).date().isoformat()
            hourly = await client.get_system_energy_hourly(date_str)
            if hourly.get("code") != 0:
                _LOGGER.warning("APsystems hourly error: %s", hourly)
                hourly = {"code": 0, "data": []}  # degrade gracefully

            return {"summary": summary, "hourly": hourly, "date": date_str}

        except Exception as e:
            raise UpdateFailed(str(e)) from e

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_coordinator",
        update_method=_async_update,
        update_interval=timedelta(seconds=int(data.get("scan_interval", 1800))),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded
