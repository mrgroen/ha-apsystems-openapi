from __future__ import annotations
from datetime import date as dt_date, datetime as dt_datetime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfTemperature,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import now as dt_now
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    sid = entry.data["sid"]

    entities = [
        APSLifetimeEnergySensor(coordinator, sid),
        APSTodayEnergySensor(coordinator, sid),
    ]

    # Create per-inverter sensors from discovered inverter list
    for inv in coordinator.data.get("inverters", []):
        entities.append(APSInverterPowerSensor(coordinator, sid, inv))
        entities.append(APSInverterDCPowerCh1Sensor(coordinator, sid, inv))
        entities.append(APSInverterDCPowerCh2Sensor(coordinator, sid, inv))
        entities.append(APSInverterDCVoltageCh1Sensor(coordinator, sid, inv))
        entities.append(APSInverterDCVoltageCh2Sensor(coordinator, sid, inv))
        entities.append(APSInverterDCCurrentCh1Sensor(coordinator, sid, inv))
        entities.append(APSInverterDCCurrentCh2Sensor(coordinator, sid, inv))
        entities.append(APSInverterACVoltageSensor(coordinator, sid, inv))
        entities.append(APSInverterFrequencySensor(coordinator, sid, inv))
        entities.append(APSInverterTemperatureSensor(coordinator, sid, inv))

    async_add_entities(entities)

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

class APSLifetimeEnergySensor(APSBaseEntity, RestoreEntity):
    """Monotonic lifetime kWh for Energy dashboard."""

    _attr_name = "Total Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, sid: str):
        super().__init__(coordinator, sid, "total_energy")
        self._last_valid_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last known value on HA restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                val = float(last_state.state)
                if val > 0:
                    self._last_valid_value = val
            except (TypeError, ValueError):
                pass

    @property
    def native_value(self) -> StateType:
        summary = self.coordinator.data.get("summary", {})
        if summary and summary.get("code") == 0:
            data = summary.get("data", {})
            try:
                val = float(data.get("lifetime"))
                if val > 0:
                    self._last_valid_value = val
                    return val
            except (TypeError, ValueError):
                pass
        return self._last_valid_value

    @property
    def extra_state_attributes(self):
        summary = self.coordinator.data.get("summary", {}).get("data", {}) or {}
        hourly = self.coordinator.data.get("hourly", {}) or {}
        solar_active = self.coordinator.data.get("solar_active", True)

        return {
            "today_kwh": _safe_float(summary.get("today")),
            "month_kwh": _safe_float(summary.get("month")),
            "year_kwh": _safe_float(summary.get("year")),
            "hourly_kwh": hourly.get("data"),
            "hourly_date": self.coordinator.data.get("date"),
            "source": "APsystems OpenAPI",
            "solar_hours_active": solar_active,
            "status": "Solar hours" if solar_active else "Night hours (cached data)"
        }

class APSTodayEnergySensor(APSBaseEntity, RestoreEntity):
    """Non-monotonic daily energy (kWh); resets each day at midnight."""

    _attr_name = "Today Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, sid: str):
        super().__init__(coordinator, sid, "today_energy")
        self._last_valid_value: float | None = None
        self._last_date: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last known value on HA restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._last_valid_value = float(last_state.state)
            except (TypeError, ValueError):
                pass
            if last_state.attributes:
                self._last_date = last_state.attributes.get("hourly_date")

    @property
    def last_reset(self) -> dt_datetime | None:
        """Return start of today as the last reset point."""
        local = dt_now()
        return local.replace(hour=0, minute=0, second=0, microsecond=0)

    @property
    def native_value(self) -> StateType:
        today = dt_now().date().isoformat()

        # Reset at midnight when the real date moves past our cached date
        if self._last_date and self._last_date != today:
            self._last_valid_value = 0.0
            self._last_date = today

        # Only use coordinator data if it's from today
        data_date = self.coordinator.data.get("date")
        if data_date == today:
            # Try to compute from hourly data
            hourly = self.coordinator.data.get("hourly", {})
            if hourly and hourly.get("code") == 0:
                series = hourly.get("data") or []
                try:
                    total = round(sum(float(x) for x in series if x is not None), 3)
                    if total > 0:
                        self._last_valid_value = total
                        self._last_date = today
                        return total
                except (TypeError, ValueError):
                    pass

            # Fallback to summary "today" field
            summary = self.coordinator.data.get("summary", {})
            if summary and summary.get("code") == 0:
                data = summary.get("data", {})
                today_val = _safe_float(data.get("today"))
                if today_val is not None and today_val > 0:
                    self._last_valid_value = today_val
                    self._last_date = today
                    return today_val

        # Return cached value (persists through night until midnight)
        if self._last_date is None:
            self._last_date = today
        return self._last_valid_value if self._last_valid_value is not None else 0.0

    @property
    def extra_state_attributes(self):
        hourly = self.coordinator.data.get("hourly", {}) or {}
        solar_active = self.coordinator.data.get("solar_active", True)

        return {
            "hourly_kwh": hourly.get("data"),
            "hourly_date": self._last_date or self.coordinator.data.get("date"),
            "solar_hours_active": solar_active,
            "status": "Solar hours" if solar_active else "Night hours (cached data)"
        }

def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-inverter power sensor
# ---------------------------------------------------------------------------

class APSInverterPowerSensor(APSBaseEntity):
    """AC output power of a single micro-inverter (latest reading)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, sid: str, inverter_info: dict):
        self._uid = inverter_info["uid"]
        self._inv_type = inverter_info.get("type", "Unknown")
        self._eid = inverter_info.get("eid", "")
        super().__init__(coordinator, sid, f"inverter_{self._uid}_power")
        self._attr_name = "Power"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._uid)},
            "manufacturer": "APsystems",
            "name": f"Inverter {self._uid}",
            "model": self._inv_type,
            "via_device": (DOMAIN, self._sid),
        }

    # -- helpers --

    @staticmethod
    def _latest(series):
        """Return the last non-null numeric value in a list."""
        for v in reversed(series or []):
            try:
                f = float(v)
                if f == f:  # skip NaN
                    return round(f, 1)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _peak(series):
        """Return the peak numeric value in a list."""
        try:
            vals = [float(x) for x in (series or []) if x is not None]
            return round(max(vals), 1) if vals else None
        except (TypeError, ValueError):
            return None

    # -- HA properties --

    @property
    def native_value(self) -> StateType:
        energy = self.coordinator.data.get("inverter_energy", {}).get(self._uid, {})
        return self._latest(energy.get("ac_p1"))

    @property
    def extra_state_attributes(self):
        energy = self.coordinator.data.get("inverter_energy", {}).get(self._uid, {})

        dc_p1 = energy.get("dc_p1", [])
        dc_p2 = energy.get("dc_p2", [])
        ac_p = energy.get("ac_p1", [])
        times = energy.get("t", [])

        return {
            "inverter_uid": self._uid,
            "inverter_type": self._inv_type,
            "ecu_id": self._eid,
            "dc_channel1_power_w": self._latest(dc_p1),
            "dc_channel2_power_w": self._latest(dc_p2),
            "dc_channel1_peak_w": self._peak(dc_p1),
            "dc_channel2_peak_w": self._peak(dc_p2),
            "ac_power_peak_w": self._peak(ac_p),
            "hourly_ac_power": ac_p,
            "hourly_dc_p1": dc_p1,
            "hourly_dc_p2": dc_p2,
            "hourly_times": times,
            "data_date": self.coordinator.data.get("inverter_energy_date"),
        }


# ---------------------------------------------------------------------------
# Per-inverter base for single-field sensors
# ---------------------------------------------------------------------------

class _APSInverterFieldSensor(APSBaseEntity):
    """Base for inverter sensors that read a single minutely field."""

    _field_key: str = ""  # API data key, e.g. "dc_v1"

    def __init__(self, coordinator, sid: str, inverter_info: dict, suffix: str, name: str):
        self._uid = inverter_info["uid"]
        self._inv_type = inverter_info.get("type", "Unknown")
        self._eid = inverter_info.get("eid", "")
        super().__init__(coordinator, sid, f"inverter_{self._uid}_{suffix}")
        self._attr_name = name

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._uid)},
            "manufacturer": "APsystems",
            "name": f"Inverter {self._uid}",
            "model": self._inv_type,
            "via_device": (DOMAIN, self._sid),
        }

    @property
    def native_value(self) -> StateType:
        energy = self.coordinator.data.get("inverter_energy", {}).get(self._uid, {})
        series = energy.get(self._field_key, [])
        for v in reversed(series or []):
            try:
                f = float(v)
                if f == f:
                    return round(f, 2)
            except (TypeError, ValueError):
                continue
        return None


class APSInverterDCPowerCh1Sensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _field_key = "dc_p1"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "dc_power_ch1", "DC Power Ch1")


class APSInverterDCPowerCh2Sensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _field_key = "dc_p2"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "dc_power_ch2", "DC Power Ch2")


class APSInverterDCVoltageCh1Sensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _field_key = "dc_v1"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "dc_voltage_ch1", "DC Voltage Ch1")


class APSInverterDCVoltageCh2Sensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _field_key = "dc_v2"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "dc_voltage_ch2", "DC Voltage Ch2")


class APSInverterDCCurrentCh1Sensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _field_key = "dc_i1"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "dc_current_ch1", "DC Current Ch1")


class APSInverterDCCurrentCh2Sensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _field_key = "dc_i2"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "dc_current_ch2", "DC Current Ch2")


class APSInverterACVoltageSensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _field_key = "ac_v1"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "ac_voltage", "AC Voltage")


class APSInverterFrequencySensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.FREQUENCY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _field_key = "ac_f"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "frequency", "Frequency")


class APSInverterTemperatureSensor(_APSInverterFieldSensor):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _field_key = "ac_t"

    def __init__(self, coordinator, sid, inv):
        super().__init__(coordinator, sid, inv, "temperature", "Temperature")
