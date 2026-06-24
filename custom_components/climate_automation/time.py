"""Entités time de Climate Automation (horaires de chauffe)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DEFAULT_HEURE_START_NORMAL,
    DEFAULT_HEURE_START_ROUGE,
    DEFAULT_HEURE_STOP_ROUGE_MATIN,
    DOMAIN,
    SETTING_START_NORMAL,
    SETTING_START_ROUGE,
    SETTING_STOP_ROUGE_MATIN,
)
from .coordinator import ClimateAutomationCoordinator
from .entity import ZoneEntity
from .models import ZoneConfig

_TIME_SETTINGS: tuple[tuple[str, str, str, time, bool], ...] = (
    (
        SETTING_START_ROUGE,
        "Heure début (jour rouge)",
        "mdi:clock-start",
        DEFAULT_HEURE_START_ROUGE,
        True,
    ),
    (
        SETTING_START_NORMAL,
        "Heure début (jour normal)",
        "mdi:clock-start",
        DEFAULT_HEURE_START_NORMAL,
        False,
    ),
    (
        SETTING_STOP_ROUGE_MATIN,
        "Heure fin matinée rouge",
        "mdi:clock-end",
        DEFAULT_HEURE_STOP_ROUGE_MATIN,
        True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les entités time."""
    coordinator: ClimateAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TimeEntity] = []
    for zone in coordinator.zones.values():
        for key, name, icon, default, on_main_device in _TIME_SETTINGS:
            entity_name = f"{zone.name} {name}" if on_main_device else name
            entities.append(
                ZoneTime(
                    coordinator,
                    zone,
                    key,
                    entity_name,
                    icon,
                    default,
                    on_main_device=on_main_device,
                )
            )

    async_add_entities(entities)


class ZoneTime(ZoneEntity, TimeEntity, RestoreEntity):
    """Réglage horaire d'une zone."""

    def __init__(
        self,
        coordinator: ClimateAutomationCoordinator,
        zone: ZoneConfig,
        setting_key: str,
        name: str,
        icon: str,
        default: time,
        on_main_device: bool = False,
    ) -> None:
        super().__init__(coordinator, zone, on_main_device=on_main_device)
        self._setting_key = setting_key
        self._attr_unique_id = f"{coordinator.entry_id}_{zone.key}_{setting_key}"
        self._attr_name = name
        self._attr_icon = icon

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            try:
                parts = [int(p) for p in last.state.split(":")]
                value = time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
            except (ValueError, IndexError):
                return
            setattr(self.coordinator.settings[self.zone.key], self._setting_key, value)

    @property
    def native_value(self) -> time:
        return getattr(self.coordinator.settings[self.zone.key], self._setting_key)

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_zone_setting(
            self.zone.key, self._setting_key, value
        )
        self.async_write_ha_state()
