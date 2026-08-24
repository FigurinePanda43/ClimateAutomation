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

# Suffixes des champs du formulaire « flux d'air » : une paire par climatiseur.
FLUX_H_SUFFIX = "__h"
FLUX_V_SUFFIX = "__v"


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


def _suggest(key: Any, value: Any) -> vol.Optional:
    """Champ optionnel pré-rempli avec la valeur courante (si elle existe)."""
    if value in (None, "", []):
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": value})


def _zone_schema(zone: dict[str, Any], default_name: str) -> vol.Schema:
    """Schéma d'édition d'une zone (nom, climatiseurs, capteur de température)."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ZONE_NAME,
                default=zone.get(CONF_ZONE_NAME) or default_name,
            ): str,
            vol.Optional(
                CONF_ZONE_CLIMATES,
                default=list(zone.get(CONF_ZONE_CLIMATES, [])),
            ): _climate_selector(),
            _suggest(
                CONF_ZONE_TEMP_SENSOR, zone.get(CONF_ZONE_TEMP_SENSOR)
            ): _sensor_selector(),
        }
    )


def _flux_schema(zones: dict[str, dict]) -> vol.Schema:
    """Schéma du mapping flux d'air, pré-rempli avec les associations connues."""
    fields: dict[Any, Any] = {}
    for zone in zones.values():
        flux_h = zone.get(CONF_ZONE_FLUX_H_MAP, {})
        flux_v = zone.get(CONF_ZONE_FLUX_V_MAP, {})
        for clim in zone.get(CONF_ZONE_CLIMATES, []):
            fields[
                _suggest(f"{clim}{FLUX_H_SUFFIX}", flux_h.get(clim))
            ] = _select_entity_selector()
            fields[
                _suggest(f"{clim}{FLUX_V_SUFFIX}", flux_v.get(clim))
            ] = _select_entity_selector()
    return vol.Schema(fields)


def _apply_flux_input(zones: dict[str, dict], user_input: dict[str, Any]) -> None:
    """Réécrit les mappings de flux des zones depuis la saisie du formulaire."""
    for zone in zones.values():
        flux_h: dict[str, str] = {}
        flux_v: dict[str, str] = {}
        for clim in zone.get(CONF_ZONE_CLIMATES, []):
            if h := user_input.get(f"{clim}{FLUX_H_SUFFIX}"):
                flux_h[clim] = h
            if v := user_input.get(f"{clim}{FLUX_V_SUFFIX}"):
                flux_v[clim] = v
        zone[CONF_ZONE_FLUX_H_MAP] = flux_h
        zone[CONF_ZONE_FLUX_V_MAP] = flux_v


def _prune_flux_maps(zone: dict[str, Any]) -> None:
    """Supprime les associations de flux des climatiseurs retirés de la zone."""
    climates = set(zone.get(CONF_ZONE_CLIMATES, []))
    for map_key in (CONF_ZONE_FLUX_H_MAP, CONF_ZONE_FLUX_V_MAP):
        current = zone.get(map_key, {})
        zone[map_key] = {
            clim: entity for clim, entity in current.items() if clim in climates
        }


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

        return self.async_show_form(
            step_id="zone",
            data_schema=_zone_schema({}, f"Zone {self._zone_index + 1}"),
            description_placeholders={"zone": str(self._zone_index + 1)},
        )

    async def async_step_flux(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dernière étape : mapping flux d'air (horizontal/vertical) par clim."""
        has_climates = any(
            zone.get(CONF_ZONE_CLIMATES) for zone in self._zones.values()
        )

        if user_input is not None or not has_climates:
            _apply_flux_input(self._zones, user_input or {})
            self._data[CONF_ZONES] = self._zones
            return self.async_create_entry(
                title="Climate Automation", data=self._data
            )

        return self.async_show_form(
            step_id="flux", data_schema=_flux_schema(self._zones)
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return ClimateAutomationOptionsFlow(entry)


class ClimateAutomationOptionsFlow(OptionsFlow):
    """Permet de tout reconfigurer après installation.

    Capteurs globaux, composition de chaque zone (nom, climatiseurs, capteur de
    température) et associations de flux d'air sont modifiables à tout moment
    depuis « Configurer » sur l'intégration.
    """

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        # Copie de travail des zones : modifiée étape par étape, puis persistée.
        self._zones: dict[str, dict] = {
            key: dict(zone) for key, zone in self._current_zones().items()
        }
        self._zone_key: str | None = None

    # ------------------------------------------------------------------ utils
    def _current(self) -> dict[str, Any]:
        """Configuration effective (data écrasée par options)."""
        return {**self._entry.data, **self._entry.options}

    def _current_zones(self) -> dict[str, dict]:
        """Zones stockées, complétées pour les clés manquantes."""
        stored: dict[str, dict] = self._current().get(CONF_ZONES, {}) or {}
        zones: dict[str, dict] = {}
        for index, key in enumerate(ZONE_KEYS):
            zone = dict(stored.get(key, {}))
            zone.setdefault(CONF_ZONE_NAME, f"Zone {index + 1}")
            zone.setdefault(CONF_ZONE_CLIMATES, [])
            zone.setdefault(CONF_ZONE_TEMP_SENSOR, None)
            zone.setdefault(CONF_ZONE_FLUX_H_MAP, {})
            zone.setdefault(CONF_ZONE_FLUX_V_MAP, {})
            zones[key] = zone
        return zones

    def _save(self, extra: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Persiste zones (+ éventuels capteurs) dans les options de l'entrée."""
        options = dict(self._entry.options)
        options.update(extra or {})
        options[CONF_ZONES] = self._zones
        return self.async_create_entry(title="", data=options)

    # ------------------------------------------------------------------- menu
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Menu principal : que souhaite-t-on modifier ?"""
        summary = "\n".join(
            "- {name} : {climates}".format(
                name=zone[CONF_ZONE_NAME],
                climates=", ".join(zone[CONF_ZONE_CLIMATES]) or "aucun climatiseur",
            )
            for zone in self._zones.values()
        )
        return self.async_show_menu(
            step_id="init",
            menu_options=["sensors", "zone_1", "zone_2", "zone_3", "flux"],
            description_placeholders={"zones": summary},
        )

    # --------------------------------------------------------------- capteurs
    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modifie les capteurs globaux (production solaire / Tempo)."""
        if user_input is not None:
            return self._save(user_input)

        current = self._current()
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
        return self.async_show_form(step_id="sensors", data_schema=schema)

    # ------------------------------------------------------------------ zones
    async def async_step_zone_1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modifie la zone 1."""
        return await self._async_step_zone("zone_1", user_input)

    async def async_step_zone_2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modifie la zone 2."""
        return await self._async_step_zone("zone_2", user_input)

    async def async_step_zone_3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modifie la zone 3."""
        return await self._async_step_zone("zone_3", user_input)

    async def _async_step_zone(
        self, zone_key: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Formulaire commun d'édition d'une zone."""
        index = ZONE_KEYS.index(zone_key)
        zone = self._zones[zone_key]

        if user_input is not None:
            zone[CONF_ZONE_NAME] = user_input[CONF_ZONE_NAME]
            zone[CONF_ZONE_CLIMATES] = list(user_input.get(CONF_ZONE_CLIMATES, []))
            zone[CONF_ZONE_TEMP_SENSOR] = user_input.get(CONF_ZONE_TEMP_SENSOR)
            # Les climatiseurs retirés ne doivent plus traîner dans les flux.
            _prune_flux_maps(zone)
            self._zone_key = zone_key
            return await self.async_step_zone_flux()

        return self.async_show_form(
            step_id=zone_key,
            data_schema=_zone_schema(zone, f"Zone {index + 1}"),
            description_placeholders={
                "zone": str(index + 1),
                "name": zone[CONF_ZONE_NAME],
            },
        )

    async def async_step_zone_flux(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Associe les flux d'air des climatiseurs de la zone qu'on vient d'éditer."""
        zone_key = self._zone_key or ZONE_KEYS[0]
        zone = self._zones[zone_key]

        if user_input is not None:
            _apply_flux_input({zone_key: zone}, user_input)
            return self._save()

        if not zone[CONF_ZONE_CLIMATES]:
            return self._save()

        return self.async_show_form(
            step_id="zone_flux",
            data_schema=_flux_schema({zone_key: zone}),
            description_placeholders={"name": zone[CONF_ZONE_NAME]},
        )

    # ------------------------------------------------------------------- flux
    async def async_step_flux(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modifie les associations de flux d'air de tous les climatiseurs."""
        if user_input is not None:
            _apply_flux_input(self._zones, user_input)
            return self._save()

        has_climates = any(
            zone[CONF_ZONE_CLIMATES] for zone in self._zones.values()
        )
        if not has_climates:
            return self.async_abort(reason="no_climates")

        return self.async_show_form(
            step_id="flux", data_schema=_flux_schema(self._zones)
        )
