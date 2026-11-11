"""Intégration Climate Automation."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_SOLAR_SENSOR,
    CONF_TEMPO_SENSOR,
    CONF_ZONES,
    DOMAIN,
)
from .coordinator import ClimateAutomationCoordinator
from .entity import main_device_info, zone_device_info
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

    _async_register_devices(hass, entry, zones)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.async_setup_listeners()
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


@callback
def _async_register_devices(
    hass: HomeAssistant, entry: ConfigEntry, zones: dict[str, ZoneConfig]
) -> None:
    """Enregistre l'appareil principal et les zones avant de créer les entités.

    Chaque zone est rattachée à l'appareil principal par son identifiant dans
    le registre (``via_device_id``) et non plus par ``via_device`` dans le
    ``DeviceInfo`` des entités, refusé par Home Assistant 2026.11.
    """
    dev_reg = dr.async_get(hass)
    main_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, **main_device_info(entry.entry_id)
    )
    for zone in zones.values():
        zone_device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id, **zone_device_info(entry.entry_id, zone)
        )
        if zone_device.via_device_id != main_device.id:
            dev_reg.async_update_device(zone_device.id, via_device_id=main_device.id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge une entrée de configuration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ClimateAutomationCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        coordinator.async_unload()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'entrée après modification des options."""
    await hass.config_entries.async_reload(entry.entry_id)
