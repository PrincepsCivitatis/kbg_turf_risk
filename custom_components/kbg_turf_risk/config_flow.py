"""Config flow for KBG Turf Risk."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TEMP_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_RAIN_SENSOR,
    CONF_SOIL_MOISTURE_SENSOR,
    CONF_GDD_BASE_F,
    CONF_IRRIGATION_TARGET_IN,
    CONF_SOIL_MOISTURE_LOW_PCT,
    DEFAULT_NAME,
    DEFAULT_GDD_BASE_F,
    DEFAULT_IRRIGATION_TARGET_IN,
    DEFAULT_SOIL_MOISTURE_LOW_PCT,
)


class KbgTurfRiskConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KBG Turf Risk."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_TEMP_SENSOR): selector.selector(
                    {"entity": {"domain": "sensor", "device_class": "temperature"}}
                ),
                vol.Required(CONF_HUMIDITY_SENSOR): selector.selector(
                    {"entity": {"domain": "sensor", "device_class": "humidity"}}
                ),
                vol.Optional(CONF_RAIN_SENSOR): selector.selector(
                    {"entity": {"domain": "sensor", "device_class": "precipitation"}}
                ),
                vol.Optional(CONF_SOIL_MOISTURE_SENSOR): selector.selector(
                    {"entity": {"domain": "sensor", "device_class": "moisture"}}
                ),
                vol.Required(CONF_GDD_BASE_F, default=DEFAULT_GDD_BASE_F): vol.Coerce(float),
                vol.Required(
                    CONF_IRRIGATION_TARGET_IN, default=DEFAULT_IRRIGATION_TARGET_IN
                ): vol.Coerce(float),
                vol.Required(
                    CONF_SOIL_MOISTURE_LOW_PCT, default=DEFAULT_SOIL_MOISTURE_LOW_PCT
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
