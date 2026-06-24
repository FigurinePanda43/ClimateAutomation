"""Config flow pour Climate Automation."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_SOLAR_SENSOR,
    CONF_TEMPO_SENSOR,
    CONF_ZONE_CLIMATES,
    CONF_ZONE_FLUX_H_MAP,
    CONF_ZONE_FLUX_V_MAP,
    CONF_ZONE_NAME,
    CONF_ZONE_TEMP_SENSOR,
    CONF_ZONES,
    DOMAIN,
    NUM_ZONES,
    ZONE_KEYS,
)


def _climate_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="climate", multiple=True)
    )


def _sensor_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", multiple=False)
    )


def _select_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="select", multiple=False)
    )


class ClimateAutomationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gère la configuration initiale."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._zones: dict[str, dict] = {}
        self._zone_index = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Étape 1 : capteurs globaux."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zone()

        schema = vol.Schema(
            {
                vol.Required(CONF_SOLAR_SENSOR): _sensor_selector(),
                vol.Required(CONF_TEMPO_SENSOR): _sensor_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Étapes 2..4 : configuration de chaque zone."""
        zone_key = ZONE_KEYS[self._zone_index]

        if user_input is not None:
            self._zones[zone_key] = {
                CONF_ZONE_NAME: user_input[CONF_ZONE_NAME],
                CONF_ZONE_CLIMATES: user_input.get(CONF_ZONE_CLIMATES, []),
                CONF_ZONE_TEMP_SENSOR: user_input.get(CONF_ZONE_TEMP_SENSOR),
            }
            self._zone_index += 1
            if self._zone_index < NUM_ZONES:
                return await self.async_step_zone()
            return await self.async_step_flux()

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_NAME, default=f"Zone {self._zone_index + 1}"): str,
                vol.Optional(CONF_ZONE_CLIMATES, default=[]): _climate_selector(),
                vol.Optional(CONF_ZONE_TEMP_SENSOR): _sensor_selector(),
            }
        )
        return self.async_show_form(
            step_id="zone",
            data_schema=schema,
            description_placeholders={"zone": str(self._zone_index + 1)},
        )

    async def async_step_flux(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dernière étape : mapping flux d'air (horizontal/vertical) par clim."""
        all_climates = [
            clim
            for zone in self._zones.values()
            for clim in zone[CONF_ZONE_CLIMATES]
        ]

        if user_input is not None or not all_climates:
            user_input = user_input or {}
            for zone in self._zones.values():
                flux_h: dict[str, str] = {}
                flux_v: dict[str, str] = {}
                for clim in zone[CONF_ZONE_CLIMATES]:
                    if h := user_input.get(f"{clim}__h"):
                        flux_h[clim] = h
                    if v := user_input.get(f"{clim}__v"):
                        flux_v[clim] = v
                zone[CONF_ZONE_FLUX_H_MAP] = flux_h
                zone[CONF_ZONE_FLUX_V_MAP] = flux_v

            self._data[CONF_ZONES] = self._zones
            return self.async_create_entry(
                title="Climate Automation", data=self._data
            )

        fields: dict[Any, Any] = {}
        for clim in all_climates:
            fields[vol.Optional(f"{clim}__h")] = _select_entity_selector()
            fields[vol.Optional(f"{clim}__v")] = _select_entity_selector()

        return self.async_show_form(
            step_id="flux", data_schema=vol.Schema(fields)
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return ClimateAutomationOptionsFlow(entry)


class ClimateAutomationOptionsFlow(OptionsFlow):
    """Permet de modifier les capteurs globaux après installation."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modifie les capteurs globaux (production solaire / Tempo)."""
        current = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            options = dict(self._entry.options)
            options.update(user_input)
            return self.async_create_entry(title="", data=options)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SOLAR_SENSOR,
                    default=current.get(CONF_SOLAR_SENSOR),
                ): _sensor_selector(),
                vol.Required(
                    CONF_TEMPO_SENSOR,
                    default=current.get(CONF_TEMPO_SENSOR),
                ): _sensor_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
