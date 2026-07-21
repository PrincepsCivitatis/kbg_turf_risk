"""The KBG Turf Risk integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_TEMP_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_GDD_BASE_F,
    DEFAULT_GDD_BASE_F,
)
from .manager import TurfRiskManager

PLATFORMS = ["sensor", "binary_sensor"]

SERVICE_RESET_GDD = "reset_gdd"
SERVICE_RESET_GDD_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KBG Turf Risk from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    manager = TurfRiskManager(
        hass,
        entry.entry_id,
        temp_entity=entry.data[CONF_TEMP_SENSOR],
        humidity_entity=entry.data[CONF_HUMIDITY_SENSOR],
        gdd_base_f=entry.data.get(CONF_GDD_BASE_F, DEFAULT_GDD_BASE_F),
    )
    await manager.async_setup()
    hass.data[DOMAIN][entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _handle_reset_gdd(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id", entry.entry_id)
        target_manager = hass.data[DOMAIN].get(target_entry_id)
        if target_manager is not None:
            await target_manager.async_reset_gdd()

    if not hass.services.has_service(DOMAIN, SERVICE_RESET_GDD):
        hass.services.async_register(
            DOMAIN, SERVICE_RESET_GDD, _handle_reset_gdd, schema=SERVICE_RESET_GDD_SCHEMA
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager: TurfRiskManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_unload()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_RESET_GDD)
    return unload_ok
