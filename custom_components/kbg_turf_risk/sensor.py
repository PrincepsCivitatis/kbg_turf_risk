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
        BrownPatchRiskHoursSensor(manager, entry),
        FusariumPatchRiskHoursSensor(manager, entry),
        RedThreadRiskHoursSensor(manager, entry),
        ChinchBugConsecutiveDaysSensor(manager, entry),
    ]
    if manager.rain_entity:
        entities.append(IrrigationDeficitSensor(manager, entry))
    if manager.soil_moisture_entity:
        entities.append(SoilMoistureSensor(manager, entry))
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


class BrownPatchRiskHoursSensor(_BaseTurfSensor):
    _attr_name = "Brown Patch Risk Hours (today)"
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:weather-pouring"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_brown_patch_risk_hours"

    @property
    def native_value(self) -> float:
        return round(self._manager.brown_patch_risk_hours_today, 2)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "model": "Extension-guidance sustained-hours threshold (Rhizoctonia solani)",
            "criteria": "Temp >= 20C with >=10 cumulative hours of RH >= 95% in a day",
            "high_risk": self._manager.brown_patch_high_risk,
        }


class FusariumPatchRiskHoursSensor(_BaseTurfSensor):
    _attr_name = "Fusarium Patch Risk Hours (today)"
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:weather-snowy-rainy"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_fusarium_patch_risk_hours"

    @property
    def native_value(self) -> float:
        return round(self._manager.fusarium_patch_risk_hours_today, 2)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "model": "Extension-guidance sustained-hours threshold (Microdochium nivale)",
            "criteria": "Temp 0-15C with >=10 cumulative hours of RH >= 90% in a day",
            "high_risk": self._manager.fusarium_patch_high_risk,
        }


class RedThreadRiskHoursSensor(_BaseTurfSensor):
    _attr_name = "Red Thread Risk Hours (today)"
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:weather-fog"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_red_thread_risk_hours"

    @property
    def native_value(self) -> float:
        return round(self._manager.red_thread_risk_hours_today, 2)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "model": "Extension-guidance sustained-hours threshold (Laetisaria fuciformis)",
            "criteria": "Temp 15-25C with >=12 cumulative hours of RH >= 90% in a day",
            "high_risk": self._manager.red_thread_high_risk,
            "note": "Weather-side criteria only; red thread is also strongly favored by low nitrogen, which this integration cannot measure.",
        }


class ChinchBugConsecutiveDaysSensor(_BaseTurfSensor):
    _attr_name = "Chinch Bug Pressure (consecutive hot/dry days)"
    _attr_icon = "mdi:bug-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_chinch_bug_consecutive_days"

    @property
    def native_value(self) -> int:
        return self._manager.chinch_bug_consecutive_days

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "model": "Extension-guidance heuristic (hairy chinch bug, Blissus spp.)",
            "criteria": "Consecutive days with max temp > 29.4C (85F); also requires < 2mm rain that day if a rain sensor is configured",
            "elevated_pressure": self._manager.chinch_bug_elevated_pressure,
            "rain_sensor_configured": bool(self._manager.rain_entity),
        }


class IrrigationDeficitSensor(_BaseTurfSensor):
    _attr_name = "Irrigation Deficit (7-day)"
    _attr_native_unit_of_measurement = "in"
    _attr_icon = "mdi:sprinkler-variant"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_irrigation_deficit"

    @property
    def native_value(self):
        return self._manager.irrigation_deficit_in

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "target_in_per_week": self._manager.irrigation_target_in,
            "days_of_rain_data": self._manager.irrigation_days_of_data,
            "note": (
                "Positive = shortfall (inches still needed this week from rain + irrigation "
                "combined to meet the target); negative = surplus. Target follows standard "
                "cool-season turf extension guidance (~1-1.5in/week)."
            ),
        }


class SoilMoistureSensor(_BaseTurfSensor):
    _attr_name = "Soil Moisture"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:water-percent"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_soil_moisture"

    @property
    def native_value(self):
        return self._manager.soil_moisture_pct

    @property
    def extra_state_attributes(self) -> dict:
        return {"low_threshold_pct": self._manager.soil_moisture_low_pct}
