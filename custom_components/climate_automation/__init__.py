"""Intégration Climate Automation."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_SOLAR_SENSOR,
    CONF_TEMPO_SENSOR,
    CONF_ZONES,
    DOMAIN,
    SETTING_FLUX_H,
    SETTING_FLUX_V,
)
from .coordinator import ClimateAutomationCoordinator
from .models import ZoneConfig

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TIME,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure l'intégration depuis une entrée de configuration."""
    data = {**entry.data, **entry.options}

    zones_raw: dict[str, dict] = data.get(CONF_ZONES, {})
    zones = {
        key: ZoneConfig.from_dict(key, zone_data)
        for key, zone_data in zones_raw.items()
    }

    coordinator = ClimateAutomationCoordinator(
        hass,
        entry_id=entry.entry_id,
        solar_sensor=data[CONF_SOLAR_SENSOR],
        tempo_sensor=data[CONF_TEMPO_SENSOR],
        zones=zones,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _async_cleanup_removed_climates(hass, entry, zones)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.async_setup_listeners()
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge une entrée de configuration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ClimateAutomationCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        coordinator.async_unload()
    return unload_ok


@callback
def _async_cleanup_removed_climates(
    hass: HomeAssistant, entry: ConfigEntry, zones: dict[str, ZoneConfig]
) -> None:
    """Supprime les entités des climatiseurs retirés de la configuration.

    Les zones sont modifiables après installation : quand une clim est retirée
    d'une zone, son capteur d'état calculé et son interrupteur d'activation
    n'ont plus de raison d'être et resteraient sinon indisponibles à jamais
    dans le registre.
    """
    slugs = {
        clim.split(".", 1)[-1] for zone in zones.values() for clim in zone.climates
    }
    prefixes = (f"{entry.entry_id}_computed_", f"{entry.entry_id}_enable_")
    valid = {f"{prefix}{slug}" for prefix in prefixes for slug in slugs}

    # Les sélecteurs de flux communs n'existent que si au moins une clim a une
    # entité select de flux associée.
    stale = set()
    for setting, attribute in (
        (SETTING_FLUX_H, "flux_h_map"),
        (SETTING_FLUX_V, "flux_v_map"),
    ):
        if not any(getattr(zone, attribute) for zone in zones.values()):
            stale.add(f"{entry.entry_id}_{setting}")

    registry = er.async_get(hass)
    for reg_entry in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        unique_id = reg_entry.unique_id
        obsolete_clim = unique_id.startswith(prefixes) and unique_id not in valid
        if obsolete_clim or unique_id in stale:
            _LOGGER.debug(
                "Suppression de %s (retiré de la configuration)",
                reg_entry.entity_id,
            )
            registry.async_remove(reg_entry.entity_id)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'entrée après modification des options."""
    await hass.config_entries.async_reload(entry.entry_id)
