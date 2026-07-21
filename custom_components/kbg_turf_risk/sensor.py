"""Sensor platform for KBG Turf Risk."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATE, DOLLAR_SPOT_ACTION_THRESHOLD
from .manager import TurfRiskManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: TurfRiskManager = hass.data[DOMAIN][entry.entry_id]

    entities = [
        GddCumulativeSensor(manager, entry),
        GddTodaySensor(manager, entry),
        DollarSpotRiskSensor(manager, entry),
        PythiumRiskHoursSensor(manager, entry),
    ]
    async_add_entities(entities)


class _BaseTurfSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, manager: TurfRiskManager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Custom",
            model="KBG Turf Risk",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATE}_{self._entry.entry_id}",
                self._handle_update,
            )
        )

    def _handle_update(self) -> None:
        self.async_write_ha_state()


class GddCumulativeSensor(_BaseTurfSensor):
    _attr_name = "GDD Cumulative"
    _attr_icon = "mdi:sprout"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_gdd_cumulative"

    @property
    def native_value(self) -> float:
        return round(self._manager.gdd_cumulative_c + self._manager.current_gdd_today_c, 1)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "base_temp_c": round(self._manager.gdd_base_c, 2),
            "note": "Base 0C (32F) cool-season GDD, resettable via kbg_turf_risk.reset_gdd",
        }


class GddTodaySensor(_BaseTurfSensor):
    _attr_name = "GDD Today (in progress)"
    _attr_icon = "mdi:calendar-today"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_gdd_today"

    @property
    def native_value(self) -> float:
        return round(self._manager.current_gdd_today_c, 1)


class DollarSpotRiskSensor(_BaseTurfSensor):
    _attr_name = "Dollar Spot Risk"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:chart-bell-curve"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_dollar_spot_risk"

    @property
    def native_value(self):
        if not self._manager.dollar_spot_valid:
            return None
        return self._manager.dollar_spot_risk

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "model": "Smith-Kerns (Smith & Kerns, 2018, PLOS ONE)",
            "action_threshold_pct": DOLLAR_SPOT_ACTION_THRESHOLD,
            "valid": self._manager.dollar_spot_valid,
            "note": (
                "Requires 5 full days of history. Model is not validated when the "
                "5-day average temperature is below 10C or above 35C."
            ),
        }


class PythiumRiskHoursSensor(_BaseTurfSensor):
    _attr_name = "Pythium Blight Risk Hours (today)"
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:weather-pouring"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_pythium_risk_hours"

    @property
    def native_value(self) -> float:
        return round(self._manager.pythium_risk_hours_today, 2)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "model": "Nutter-Shane (Nutter, Cole & Schein, 1983, Plant Disease 67:1126-1138)",
            "criteria": "Max temp > 30C, followed by >=14h of RH > 90% while temp stays > 20C",
            "high_risk": self._manager.pythium_high_risk,
        }
