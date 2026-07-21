"""Binary sensor platform for KBG Turf Risk - simple risk flags for automations."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
        PythiumHighRiskBinarySensor(manager, entry),
        DollarSpotActionThresholdBinarySensor(manager, entry),
        BrownPatchHighRiskBinarySensor(manager, entry),
        FusariumPatchHighRiskBinarySensor(manager, entry),
        RedThreadHighRiskBinarySensor(manager, entry),
        ChinchBugElevatedPressureBinarySensor(manager, entry),
    ]
    if manager.rain_entity:
        entities.append(IrrigationNeededBinarySensor(manager, entry))
    if manager.soil_moisture_entity:
        entities.append(SoilMoistureLowBinarySensor(manager, entry))
    async_add_entities(entities)


class _BaseTurfBinarySensor(BinarySensorEntity):
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

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


class PythiumHighRiskBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Pythium Blight High Risk"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_pythium_high_risk"

    @property
    def is_on(self) -> bool:
        return self._manager.pythium_high_risk


class DollarSpotActionThresholdBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Dollar Spot Action Threshold Exceeded"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_dollar_spot_action"

    @property
    def is_on(self) -> bool:
        risk = self._manager.dollar_spot_risk
        if not self._manager.dollar_spot_valid or risk is None:
            return False
        return risk >= DOLLAR_SPOT_ACTION_THRESHOLD


class BrownPatchHighRiskBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Brown Patch High Risk"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_brown_patch_high_risk"

    @property
    def is_on(self) -> bool:
        return self._manager.brown_patch_high_risk


class FusariumPatchHighRiskBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Fusarium Patch High Risk"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_fusarium_patch_high_risk"

    @property
    def is_on(self) -> bool:
        return self._manager.fusarium_patch_high_risk


class RedThreadHighRiskBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Red Thread High Risk"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_red_thread_high_risk"

    @property
    def is_on(self) -> bool:
        return self._manager.red_thread_high_risk


class ChinchBugElevatedPressureBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Chinch Bug Elevated Pressure"
    _attr_icon = "mdi:bug-outline"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_chinch_bug_elevated_pressure"

    @property
    def is_on(self) -> bool:
        return self._manager.chinch_bug_elevated_pressure


class IrrigationNeededBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Irrigation Needed"
    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_irrigation_needed"

    @property
    def is_on(self) -> bool:
        deficit = self._manager.irrigation_deficit_in
        return deficit is not None and deficit > 0


class SoilMoistureLowBinarySensor(_BaseTurfBinarySensor):
    _attr_name = "Soil Moisture Low"
    _attr_icon = "mdi:water-alert-outline"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_soil_moisture_low"

    @property
    def is_on(self) -> bool:
        return self._manager.soil_moisture_low
