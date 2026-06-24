"""Capteurs de diagnostic de Climate Automation."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COMPUTED_CONFORT,
    COMPUTED_DISABLED,
    COMPUTED_ECO,
    COMPUTED_HORS_GEL,
    COMPUTED_MANUAL,
    COMPUTED_NON_GERE,
    COMPUTED_OFF,
    COMPUTED_PRECHAUFFE_ROUGE,
    DOMAIN,
)
from .coordinator import ClimateAutomationCoordinator
from .entity import ZoneEntity
from .models import ZoneConfig

_COMPUTED_OPTIONS = [
    COMPUTED_OFF,
    COMPUTED_ECO,
    COMPUTED_CONFORT,
    COMPUTED_HORS_GEL,
    COMPUTED_PRECHAUFFE_ROUGE,
    COMPUTED_DISABLED,
    COMPUTED_MANUAL,
    COMPUTED_NON_GERE,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les capteurs de diagnostic (état calculé par clim)."""
    coordinator: ClimateAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for zone in coordinator.zones.values():
        for clim in zone.climates:
            entities.append(ClimComputedSensor(coordinator, zone, clim))

    async_add_entities(entities)


class ClimComputedSensor(ZoneEntity, SensorEntity):
    """État calculé par le moteur pour une clim (diagnostic)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = _COMPUTED_OPTIONS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:state-machine"

    def __init__(
        self,
        coordinator: ClimateAutomationCoordinator,
        zone: ZoneConfig,
        clim: str,
    ) -> None:
        super().__init__(coordinator, zone)
        self._clim = clim
        slug = clim.split(".", 1)[-1]
        self._attr_unique_id = f"{coordinator.entry_id}_computed_{slug}"
        self._attr_name = f"État calculé {slug}"

    @property
    def native_value(self) -> str | None:
        desired = self.coordinator.data.get(self._clim) if self.coordinator.data else None
        return desired.computed if desired else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        desired = self.coordinator.data.get(self._clim) if self.coordinator.data else None
        if desired is None:
            return {}
        return {
            "hvac_mode": desired.hvac_mode,
            "temperature": desired.temperature,
            "fan_mode": desired.fan_mode,
        }
