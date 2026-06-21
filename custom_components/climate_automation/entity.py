"""Bases d'entités pour Climate Automation."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ClimateAutomationCoordinator
from .models import ZoneConfig


class ClimateAutomationEntity(CoordinatorEntity[ClimateAutomationCoordinator]):
    """Entité de base reliée au coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ClimateAutomationCoordinator) -> None:
        """Initialise l'entité de base."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry_id)},
            name="Climate Automation",
            manufacturer="Climate Automation",
            model="Chauffage multi-zones",
        )


class ZoneEntity(ClimateAutomationEntity):
    """Entité rattachée à une zone (sous-appareil dédié)."""

    def __init__(
        self, coordinator: ClimateAutomationCoordinator, zone: ZoneConfig
    ) -> None:
        """Initialise une entité de zone."""
        super().__init__(coordinator)
        self.zone = zone
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.entry_id}_{zone.key}")},
            name=f"Climate Automation — {zone.name}",
            manufacturer="Climate Automation",
            model="Zone de chauffage",
            via_device=(DOMAIN, coordinator.entry_id),
        )
