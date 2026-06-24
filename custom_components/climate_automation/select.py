"""Entités select de Climate Automation (modes HVAC/ventilation, flux d'air).

Ces réglages sont communs aux 3 zones : une seule entité pilote les zones à
la fois (pas de distinction par zone).
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DEFAULT_FAN_MODE,
    DEFAULT_HVAC_MODE,
    DOMAIN,
    FAN_MODE_OPTIONS,
    HVAC_MODE_OPTIONS,
    SETTING_FAN_MODE,
    SETTING_FLUX_H,
    SETTING_FLUX_V,
    SETTING_HVAC_MODE,
)
from .coordinator import ClimateAutomationCoordinator
from .entity import ClimateAutomationEntity


def _flux_options(hass: HomeAssistant, select_entities: list[str]) -> list[str]:
    """Récupère les options de flux depuis les entités select sous-jacentes."""
    for entity in select_entities:
        state = hass.states.get(entity)
        if state is not None:
            options = state.attributes.get("options")
            if options:
                return list(options)
    return []


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les entités select (une seule par réglage, commune aux 3 zones)."""
    coordinator: ClimateAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SelectEntity] = [
        GlobalSelect(
            coordinator,
            SETTING_HVAC_MODE,
            "Mode de fonctionnement",
            "mdi:hvac",
            HVAC_MODE_OPTIONS,
            DEFAULT_HVAC_MODE,
        ),
        GlobalSelect(
            coordinator,
            SETTING_FAN_MODE,
            "Mode de ventilation",
            "mdi:fan",
            FAN_MODE_OPTIONS,
            DEFAULT_FAN_MODE,
        ),
    ]

    all_flux_h = [v for zone in coordinator.zones.values() for v in zone.flux_h_map.values()]
    flux_h_options = _flux_options(hass, all_flux_h)
    if flux_h_options:
        entities.append(
            GlobalSelect(
                coordinator,
                SETTING_FLUX_H,
                "Flux d'air horizontal",
                "mdi:arrow-left-right",
                flux_h_options,
                flux_h_options[0],
            )
        )

    all_flux_v = [v for zone in coordinator.zones.values() for v in zone.flux_v_map.values()]
    flux_v_options = _flux_options(hass, all_flux_v)
    if flux_v_options:
        entities.append(
            GlobalSelect(
                coordinator,
                SETTING_FLUX_V,
                "Flux d'air vertical",
                "mdi:arrow-up-down",
                flux_v_options,
                flux_v_options[0],
            )
        )

    async_add_entities(entities)


class GlobalSelect(ClimateAutomationEntity, SelectEntity, RestoreEntity):
    """Réglage à choix commun aux 3 zones."""

    def __init__(
        self,
        coordinator: ClimateAutomationCoordinator,
        setting_key: str,
        name: str,
        icon: str,
        options: list[str],
        default: str,
    ) -> None:
        super().__init__(coordinator)
        self._setting_key = setting_key
        self._attr_unique_id = f"{coordinator.entry_id}_{setting_key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_options = options
        # Initialise la valeur par défaut dans les réglages du coordinator.
        setattr(coordinator.global_settings, setting_key, default)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state in self._attr_options:
                setattr(self.coordinator.global_settings, self._setting_key, last.state)

    @property
    def current_option(self) -> str | None:
        return getattr(self.coordinator.global_settings, self._setting_key)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_global_setting(self._setting_key, option)
        self.async_write_ha_state()
