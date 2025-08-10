from __future__ import annotations
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import StateType

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    sid = entry.data["sid"]

    async_add_entities([
        APSLifetimeEnergySensor(coordinator, sid),
        APSTodayEnergySensor(coordinator, sid),
    ])

class APSBaseEntity(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, sid: str, name_suffix: str):
        super().__init__(coordinator)
        self._sid = sid
        self._attr_unique_id = f"{sid}_{name_suffix}"

    @property
    def device_info(self):
        # Ensures a device tile appears in the UI
        return {
            "identifiers": {(DOMAIN, self._sid)},
            "manufacturer": "APsystems",
            "name": f"APsystems {self._sid}",
        }

class APSLifetimeEnergySensor(APSBaseEntity):
    """Monotonic lifetime kWh for Energy dashboard."""

    _attr_name = "Total Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, sid: str):
        super().__init__(coordinator, sid, "total_energy")

    @property
    def native_value(self) -> StateType:
        summary = self.coordinator.data.get("summary", {})
        if summary and summary.get("code") == 0:
            data = summary.get("data", {})
            try:
                return float(data.get("lifetime"))
            except (TypeError, ValueError):
                return None
        return None

    @property
    def extra_state_attributes(self):
        summary = self.coordinator.data.get("summary", {}).get("data", {}) or {}
        hourly = self.coordinator.data.get("hourly", {}) or {}
        return {
            "today_kwh": _safe_float(summary.get("today")),
            "month_kwh": _safe_float(summary.get("month")),
            "year_kwh": _safe_float(summary.get("year")),
            "hourly_kwh": hourly.get("data"),
            "hourly_date": self.coordinator.data.get("date"),
            "source": "APsystems OpenAPI",
        }

class APSTodayEnergySensor(APSBaseEntity):
    """Non-monotonic daily energy (kWh); resets each day."""

    _attr_name = "Today Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, sid: str):
        super().__init__(coordinator, sid, "today_energy")

    @property
    def native_value(self) -> StateType:
        hourly = self.coordinator.data.get("hourly", {})
        if hourly and hourly.get("code") == 0:
            series = hourly.get("data") or []
            try:
                return round(sum(float(x) for x in series if x is not None), 3)
            except (TypeError, ValueError):
                return None
        return None

    @property
    def extra_state_attributes(self):
        hourly = self.coordinator.data.get("hourly", {}) or {}
        return {
            "hourly_kwh": hourly.get("data"),
            "hourly_date": self.coordinator.data.get("date"),
        }

def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None
