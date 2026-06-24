"""Interrupteurs de Climate Automation : activation de zone et de clim."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, MONTH_LABELS, SETTING_ACTIVE, SETTING_SOLAR_ONLY
from .coordinator import ClimateAutomationCoordinator
from .entity import ClimateAutomationEntity, ZoneEntity
from .models import ZoneConfig


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les interrupteurs."""
    coordinator: ClimateAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []
    for month, label in MONTH_LABELS:
        entities.append(MonthActiveSwitch(coordinator, month, label))
    for zone in coordinator.zones.values():
        entities.append(ZoneActiveSwitch(coordinator, zone))
        entities.append(ZoneSolarOnlySwitch(coordinator, zone))
        for clim in zone.climates:
            entities.append(ClimEnableSwitch(coordinator, zone, clim))

    async_add_entities(entities)


class MonthActiveSwitch(ClimateAutomationEntity, SwitchEntity, RestoreEntity):
    """Active ou désactive le chauffage pour un mois donné (commun aux 3 zones)."""

    _attr_icon = "mdi:calendar-month"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: ClimateAutomationCoordinator, month: int, label: str
    ) -> None:
        super().__init__(coordinator)
        self._month = month
        self._attr_unique_id = f"{coordinator.entry_id}_month_active_{month}"
        self._attr_name = f"Chauffage actif — {label}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            await self.coordinator.async_set_month_active(
                self._month, last.state == "on"
            )

    @property
    def is_on(self) -> bool:
        return self._month in self.coordinator.global_settings.active_months

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_month_active(self._month, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_month_active(self._month, False)
        self.async_write_ha_state()


class ZoneActiveSwitch(ZoneEntity, SwitchEntity, RestoreEntity):
    """Active ou désactive entièrement une zone."""

    _attr_icon = "mdi:home-thermometer"

    def __init__(
        self, coordinator: ClimateAutomationCoordinator, zone: ZoneConfig
    ) -> None:
        super().__init__(coordinator, zone)
        self._attr_unique_id = f"{coordinator.entry_id}_{zone.key}_{SETTING_ACTIVE}"
        self._attr_name = "Zone active"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.coordinator.settings[self.zone.key].active = last.state == "on"

    @property
    def is_on(self) -> bool:
        return self.coordinator.settings[self.zone.key].active

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_zone_setting(
            self.zone.key, SETTING_ACTIVE, True
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_zone_setting(
            self.zone.key, SETTING_ACTIVE, False
        )
        self.async_write_ha_state()


class ZoneSolarOnlySwitch(ZoneEntity, SwitchEntity, RestoreEntity):
    """Force la zone à suivre uniquement l'asservissement solaire.

    Quand activé, mois actifs / plage horaire / logique Tempo sont ignorés :
    la zone applique en continu confort/éco/off selon ses seuils de
    production solaire, 24h/24. Le hors-gel reste actif par-dessus.
    """

    _attr_icon = "mdi:solar-power"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: ClimateAutomationCoordinator, zone: ZoneConfig
    ) -> None:
        super().__init__(coordinator, zone)
        self._attr_unique_id = (
            f"{coordinator.entry_id}_{zone.key}_{SETTING_SOLAR_ONLY}"
        )
        self._attr_name = "Forcer logique solaire uniquement"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.coordinator.settings[self.zone.key].solar_only = last.state == "on"

    @property
    def is_on(self) -> bool:
        return self.coordinator.settings[self.zone.key].solar_only

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_zone_setting(
            self.zone.key, SETTING_SOLAR_ONLY, True
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_zone_setting(
            self.zone.key, SETTING_SOLAR_ONLY, False
        )
        self.async_write_ha_state()


class ClimEnableSwitch(ZoneEntity, SwitchEntity, RestoreEntity):
    """Active/désactive une clim dans l'automatisation.

    Activer : la clim converge immédiatement vers l'état voulu par sa zone.
    Désactiver : la clim est éteinte immédiatement.
    """

    _attr_icon = "mdi:air-conditioner"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: ClimateAutomationCoordinator,
        zone: ZoneConfig,
        clim: str,
    ) -> None:
        super().__init__(coordinator, zone)
        self._clim = clim
        slug = clim.split(".", 1)[-1]
        self._attr_unique_id = f"{coordinator.entry_id}_enable_{slug}"
        self._attr_name = f"Activer {slug}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.coordinator.clim_enabled[self._clim] = last.state == "on"

    @property
    def is_on(self) -> bool:
        return self.coordinator.clim_enabled.get(self._clim, True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_clim_enabled(self._clim, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_clim_enabled(self._clim, False)
        self.async_write_ha_state()
