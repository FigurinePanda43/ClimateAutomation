"""Entités number de Climate Automation (températures, seuils, délais)."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DECALAGE_COUCHER_STEP,
    DEFAULT_ANTI_COURT_CYCLE_MINUTES,
    DOMAIN,
    MAX_ANTI_COURT_CYCLE,
    MAX_DECALAGE_COUCHER,
    MAX_HORS_GEL_THRESHOLD,
    MAX_SEUIL,
    MAX_TEMP,
    MIN_ANTI_COURT_CYCLE,
    MIN_DECALAGE_COUCHER,
    MIN_HORS_GEL_THRESHOLD,
    MIN_SEUIL,
    MIN_TEMP,
    SETTING_ANTI_COURT_CYCLE,
    SETTING_DECALAGE_COUCHER,
    SETTING_HORS_GEL,
    SETTING_SEUIL_BASSE,
    SETTING_SEUIL_HAUTE,
    SETTING_TEMP_CONFORT,
    SETTING_TEMP_ECO,
    SEUIL_STEP,
    TEMP_STEP,
)
from .coordinator import ClimateAutomationCoordinator
from .entity import ClimateAutomationEntity, ZoneEntity
from .models import ZoneConfig


@dataclass(frozen=True, kw_only=True)
class ZoneNumberDescription:
    """Décrit une entité number de zone."""

    key: str
    name: str
    icon: str
    min_value: float
    max_value: float
    step: float
    unit: str
    on_main_device: bool = False


ZONE_NUMBERS: tuple[ZoneNumberDescription, ...] = (
    ZoneNumberDescription(
        key=SETTING_TEMP_CONFORT,
        name="Température confort",
        icon="mdi:thermometer-high",
        min_value=MIN_TEMP,
        max_value=MAX_TEMP,
        step=TEMP_STEP,
        unit=UnitOfTemperature.CELSIUS,
    ),
    ZoneNumberDescription(
        key=SETTING_TEMP_ECO,
        name="Température éco",
        icon="mdi:thermometer-low",
        min_value=MIN_TEMP,
        max_value=MAX_TEMP,
        step=TEMP_STEP,
        unit=UnitOfTemperature.CELSIUS,
    ),
    ZoneNumberDescription(
        key=SETTING_HORS_GEL,
        name="Seuil hors-gel (température pièce)",
        icon="mdi:snowflake-thermometer",
        min_value=MIN_HORS_GEL_THRESHOLD,
        max_value=MAX_HORS_GEL_THRESHOLD,
        step=TEMP_STEP,
        unit=UnitOfTemperature.CELSIUS,
        on_main_device=True,
    ),
    ZoneNumberDescription(
        key=SETTING_SEUIL_HAUTE,
        name="Seuil production haute",
        icon="mdi:solar-power",
        min_value=MIN_SEUIL,
        max_value=MAX_SEUIL,
        step=SEUIL_STEP,
        unit=UnitOfPower.KILO_WATT,
    ),
    ZoneNumberDescription(
        key=SETTING_SEUIL_BASSE,
        name="Seuil production basse",
        icon="mdi:solar-power-variant",
        min_value=MIN_SEUIL,
        max_value=MAX_SEUIL,
        step=SEUIL_STEP,
        unit=UnitOfPower.KILO_WATT,
    ),
    ZoneNumberDescription(
        key=SETTING_DECALAGE_COUCHER,
        name="Décalage coucher du soleil (négatif = avant, positif = après)",
        icon="mdi:weather-sunset-down",
        min_value=MIN_DECALAGE_COUCHER,
        max_value=MAX_DECALAGE_COUCHER,
        step=DECALAGE_COUCHER_STEP,
        unit=UnitOfTime.MINUTES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les entités number."""
    coordinator: ClimateAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = [AntiCourtCycleNumber(coordinator)]
    for zone in coordinator.zones.values():
        for desc in ZONE_NUMBERS:
            entities.append(ZoneNumber(coordinator, zone, desc))

    async_add_entities(entities)


class ZoneNumber(ZoneEntity, NumberEntity, RestoreEntity):
    """Réglage numérique d'une zone."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: ClimateAutomationCoordinator,
        zone: ZoneConfig,
        desc: ZoneNumberDescription,
    ) -> None:
        super().__init__(coordinator, zone, on_main_device=desc.on_main_device)
        self._desc = desc
        self._attr_unique_id = f"{coordinator.entry_id}_{zone.key}_{desc.key}"
        self._attr_name = (
            f"{zone.name} {desc.name}" if desc.on_main_device else desc.name
        )
        self._attr_icon = desc.icon
        self._attr_native_min_value = desc.min_value
        self._attr_native_max_value = desc.max_value
        self._attr_native_step = desc.step
        self._attr_native_unit_of_measurement = desc.unit

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            try:
                value = float(last.state)
            except (ValueError, TypeError):
                return
            setattr(self.coordinator.settings[self.zone.key], self._desc.key, value)

    @property
    def native_value(self) -> float:
        return getattr(self.coordinator.settings[self.zone.key], self._desc.key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_zone_setting(
            self.zone.key, self._desc.key, value
        )
        self.async_write_ha_state()


class AntiCourtCycleNumber(ClimateAutomationEntity, NumberEntity, RestoreEntity):
    """Délai global anti-court-cycle (minutes)."""

    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-cog"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = MIN_ANTI_COURT_CYCLE
    _attr_native_max_value = MAX_ANTI_COURT_CYCLE
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: ClimateAutomationCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{SETTING_ANTI_COURT_CYCLE}"
        self._attr_name = "Délai anti-court-cycle"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            try:
                self.coordinator.anti_court_cycle_minutes = float(last.state)
            except (ValueError, TypeError):
                pass

    @property
    def native_value(self) -> float:
        return self.coordinator.anti_court_cycle_minutes

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_anti_court_cycle(value)
        self.async_write_ha_state()
