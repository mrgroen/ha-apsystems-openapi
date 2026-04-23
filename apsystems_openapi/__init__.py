from __future__ import annotations
import logging
from datetime import timedelta
import asyncio
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now, as_local
from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.helpers.event import async_track_point_in_utc_time

from .const import DOMAIN, PLATFORMS, DEFAULT_BASE_URL
from .api import APSClient

import time as _time

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

    # Store the last fetched data for use during night hours
    last_data = {"summary": None, "hourly": None, "date": None}
    solar_active = {"is_active": False}

    # Inverter tracking state
    inverter_cache = {
        "list": None,                # parsed list of inverter dicts
        "list_fetched_ts": 0,        # epoch when list was last fetched
        "energy": {},                # uid -> energy data dict
        "energy_date": None,         # date string of last fetch
    }

    # Summary tracking state (fetched once per day near end of solar hours)
    summary_cache = {
        "data": None,
        "fetched_date": None,   # date string of last fetch
    }

    # Batch power tracking state (fetched once per day at 11 PM)
    batch_power_cache = {
        "data": {},             # eid -> {time: [...], power: {uid-ch: [...]}}
        "fetched_date": None,   # date string of last fetch
    }

    def update_solar_state():
        """Check if we're currently in solar hours (30 min after sunrise to sunset)."""
        from homeassistant.util.dt import now as dt_now
        from homeassistant.helpers.sun import get_astral_event_date
        import datetime

        current_time = dt_now()
        today = current_time.date()

        # Get sunrise and sunset for today
        sunrise = get_astral_event_date(hass, "sunrise", today)
        sunset = get_astral_event_date(hass, "sunset", today)

        if sunrise and sunset:
            # Add 30 minute buffer after sunrise (panels need time to ramp up)
            sunrise_with_buffer = sunrise + timedelta(minutes=30)
            solar_active["is_active"] = sunrise_with_buffer <= current_time <= sunset
            solar_active["sunset"] = sunset
            _LOGGER.debug(
                "Solar state updated: active=%s (current=%s, start=%s, end=%s)",
                solar_active["is_active"], current_time, sunrise_with_buffer, sunset
            )
        else:
            # Fallback if sun calculation fails
            hour = current_time.hour
            solar_active["is_active"] = 7 <= hour <= 20

    async def refresh_inverter_list():
        """Fetch the inverter list from the API (called by button or first run)."""
        try:
            inv_resp = await client.get_inverters()
            if isinstance(inv_resp, dict) and inv_resp.get("code") == 0:
                raw = inv_resp.get("data", [])
                parsed = []
                for ecu in (raw if isinstance(raw, list) else []):
                    eid = ecu.get("eid")
                    for inv in ecu.get("inverter", []):
                        parsed.append({
                            "eid": eid,
                            "uid": inv.get("uid"),
                            "type": inv.get("type"),
                        })
                inverter_cache["list"] = parsed
                inverter_cache["list_fetched_ts"] = _time.time()
                _LOGGER.info("Discovered %d inverter(s)", len(parsed))
                return parsed
            else:
                _LOGGER.warning("Inverter list API error: %s", inv_resp)
        except Exception as exc:
            _LOGGER.warning("Error fetching inverter list: %s", exc)
        if inverter_cache["list"] is None:
            inverter_cache["list"] = []
        return inverter_cache["list"]

    async def refresh_inverter_energy():
        """Fetch energy data for all inverters (called by button or daily schedule)."""
        date_str = as_local(now()).date().isoformat()
        inv_energy = {}
        for inv in (inverter_cache["list"] or []):
            uid = inv["uid"]
            try:
                resp = await client.get_inverter_energy(uid, date_str, energy_level="minutely")
                if isinstance(resp, dict) and resp.get("code") == 0:
                    inv_energy[uid] = resp.get("data", {})
                elif isinstance(resp, dict) and resp.get("code") == 1001:
                    _LOGGER.debug("No energy data yet for inverter %s (code 1001)", uid)
                else:
                    _LOGGER.warning("Inverter energy error for %s: %s", uid, resp)
            except Exception as exc:
                _LOGGER.warning("Failed to fetch energy for inverter %s: %s", uid, exc)
        inverter_cache["energy"] = inv_energy
        inverter_cache["energy_date"] = date_str
        _LOGGER.info("Inverter energy fetched for %s (%d inverters)", date_str, len(inv_energy))
        return inv_energy

    async def refresh_batch_power():
        """Fetch batch power data for all ECUs (one call per ECU, covers all inverters)."""
        date_str = as_local(now()).date().isoformat()
        # Group inverters by ECU
        ecus = set()
        for inv in (inverter_cache["list"] or []):
            eid = inv.get("eid")
            if eid:
                ecus.add(eid)
        batch_data = {}
        for eid in ecus:
            try:
                resp = await client.get_inverter_batch_power(eid, date_str)
                if isinstance(resp, dict) and resp.get("code") == 0:
                    batch_data[eid] = resp.get("data", {})
                else:
                    _LOGGER.warning("Batch power error for ECU %s: %s", eid, resp)
            except Exception as exc:
                _LOGGER.warning("Failed to fetch batch power for ECU %s: %s", eid, exc)
        batch_power_cache["data"] = batch_data
        batch_power_cache["fetched_date"] = date_str
        _LOGGER.info("Batch power fetched for %s (%d ECUs)", date_str, len(batch_data))
        # Push updated data into the coordinator so sensors see it immediately
        if coordinator.data is not None:
            coordinator.data["batch_power"] = batch_power_cache["data"]
            coordinator.data["batch_power_date"] = batch_power_cache["fetched_date"]
            coordinator.async_set_updated_data(coordinator.data)
        return batch_data

    async def _async_update():
        """Fetch data from API only during solar hours."""
        try:
            update_solar_state()
            now_ts = _time.time()

            # ── Discover inverters on first run only ──
            if inverter_cache["list"] is None:
                await refresh_inverter_list()

            # ── Night-time path: return cached data ──
            if not solar_active["is_active"]:
                _LOGGER.debug("Outside solar hours, returning cached data")
                if last_data["summary"]:
                    cached = dict(last_data)
                    cached["solar_active"] = False
                    cached.setdefault("inverters", inverter_cache["list"] or [])
                    cached.setdefault("inverter_energy", inverter_cache["energy"])
                    cached.setdefault("inverter_energy_date", inverter_cache["energy_date"])
                    cached.setdefault("batch_power", batch_power_cache["data"])
                    cached.setdefault("batch_power_date", batch_power_cache["fetched_date"])
                    return cached
                return {
                    "summary": None,
                    "hourly": None,
                    "date": as_local(now()).date().isoformat(),
                    "solar_active": False,
                    "inverters": inverter_cache["list"] or [],
                    "inverter_energy": inverter_cache["energy"],
                    "inverter_energy_date": inverter_cache["energy_date"],
                    "batch_power": batch_power_cache["data"],
                    "batch_power_date": batch_power_cache["fetched_date"],
                }

            # ── Solar-hours: fetch hourly (every cycle) ──
            date_str = as_local(now()).date().isoformat()
            hourly = await client.get_system_energy_hourly(date_str)
            if hourly.get("code") != 0:
                _LOGGER.warning("APsystems hourly error: %s", hourly)
                hourly = {"code": 0, "data": []}

            # ── Summary: fetch once per day near end of solar hours ──
            need_summary = summary_cache["data"] is None  # first run
            if not need_summary and summary_cache["fetched_date"] != date_str:
                # Haven't fetched today yet — wait until last cycle before sunset
                sunset_time = solar_active.get("sunset")
                current_time = as_local(now())
                if sunset_time and current_time + timedelta(seconds=scan_interval) >= sunset_time:
                    need_summary = True
                    _LOGGER.debug("Near end of solar day, fetching daily summary")
            if need_summary:
                summary = await client.get_system_summary()
                if summary.get("code") != 0:
                    _LOGGER.warning("APsystems summary error: %s", summary)
                    if summary_cache["data"] is None:
                        raise UpdateFailed(f"APsystems summary error: {summary}")
                else:
                    summary_cache["data"] = summary
                    summary_cache["fetched_date"] = date_str
                    _LOGGER.info("Daily summary fetched for %s", date_str)

            result = {"summary": summary_cache["data"], "hourly": hourly, "date": date_str, "solar_active": True}

            # ── Inverter energy: fetch once per day at 12:30 ──
            current_time = as_local(now())
            past_1230 = current_time.hour > 12 or (current_time.hour == 12 and current_time.minute >= 30)
            if past_1230 and inverter_cache["energy_date"] != date_str:
                await refresh_inverter_energy()

            result["inverters"] = inverter_cache["list"] or []
            result["inverter_energy"] = inverter_cache["energy"]
            result["inverter_energy_date"] = inverter_cache["energy_date"]
            result["batch_power"] = batch_power_cache["data"]
            result["batch_power_date"] = batch_power_cache["fetched_date"]

            last_data.update(result)
            return result
        except Exception as e:
            raise UpdateFailed(str(e)) from e

    # Default 30-minute interval (~960 API calls/month with 6 inverters)
    scan_interval = int(data.get("scan_interval", 1800))  # Default 30 minutes
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_coordinator",
        update_method=_async_update,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    # Set up sunrise/sunset event listeners to trigger updates
    async def handle_sun_event(event):
        """Handle sunrise/sunset events."""
        _LOGGER.info("Sun event triggered: %s", event)
        update_solar_state()
        if solar_active["is_active"]:
            # Trigger an immediate update when entering solar hours
            await coordinator.async_request_refresh()

    # Track sunrise event (with 30 minute delay)
    async def schedule_sunrise_update(now_time):
        """Schedule update 30 minutes after sunrise."""
        sunrise_time = get_astral_event_next(hass, "sunrise")
        if sunrise_time:
            delayed_sunrise = sunrise_time + timedelta(minutes=30)
            async_track_point_in_utc_time(hass, handle_sun_event, delayed_sunrise)
            _LOGGER.info("Scheduled update for 30 min after sunrise: %s", delayed_sunrise)

    # Track sunset event
    async def schedule_sunset_update(now_time):
        """Schedule update at 30 minutes after sunset."""
        sunset_time = get_astral_event_next(hass, "sunset")
        if sunset_time:
            delayed_sunset = sunset_time + timedelta(minutes=30)
            async_track_point_in_utc_time(hass, handle_sun_event, delayed_sunset)
            _LOGGER.info("Scheduled update for 30 minutes after sunset: %s", delayed_sunset)

    # Schedule batch power fetch at 11 PM daily
    async def schedule_batch_power(now_time):
        """Schedule batch power fetch at 11 PM local time, re-scheduling for the next day."""
        import datetime
        local_now = as_local(now())
        target = local_now.replace(hour=23, minute=0, second=0, microsecond=0)
        if local_now >= target:
            target += timedelta(days=1)
        async def _run_batch(event):
            await refresh_batch_power()
            # Re-schedule for the next day
            await schedule_batch_power(now())
        async_track_point_in_utc_time(hass, _run_batch, target)
        _LOGGER.info("Scheduled batch power fetch at %s", target)

    # Schedule midnight coordinator refresh to reset daily sensors
    async def schedule_midnight_refresh(now_time):
        """Schedule a coordinator refresh at midnight to reset daily sensors."""
        local_now = as_local(now())
        target = local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        async def _run_midnight(event):
            _LOGGER.info("Midnight refresh: resetting daily sensor data")
            await coordinator.async_request_refresh()
            await schedule_midnight_refresh(now())
        async_track_point_in_utc_time(hass, _run_midnight, target)
        _LOGGER.info("Scheduled midnight refresh at %s", target)

    # Schedule the initial sun events
    await schedule_sunrise_update(now())
    await schedule_sunset_update(now())
    await schedule_batch_power(now())
    await schedule_midnight_refresh(now())

    # Store everything needed for sensors and button
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "refresh_inverter_list": refresh_inverter_list,
        "refresh_inverter_energy": refresh_inverter_energy,
        "refresh_batch_power": refresh_batch_power,
        "sun_handlers": {
            "sunrise": schedule_sunrise_update,
            "sunset": schedule_sunset_update
        }
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded
