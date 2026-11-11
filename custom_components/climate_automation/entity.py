"""Bases d'entités pour Climate Automation."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ClimateAutomationCoordinator
from .models import ZoneConfig

MANUFACTURER = "Climate Automation"


def main_device_info(entry_id: str) -> DeviceInfo:
    """Décrit l'appareil principal (réglages communs aux zones)."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Climate Automation",
        manufacturer=MANUFACTURER,
        model="Chauffage multi-zones",
    )


def zone_device_info(entry_id: str, zone: ZoneConfig) -> DeviceInfo:
    """Décrit le sous-appareil d'une zone.

    Volontairement sans ``via_device`` : Home Assistant 2026.11 refuse ce
    réglage obsolète et n'ajoute alors pas l'entité. Le rattachement à
    l'appareil principal est fait directement dans le registre des appareils,
    au démarrage de l'intégration (voir ``_async_register_devices``).
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{zone.key}")},
        name=f"Climate Automation — {zone.name}",
        manufacturer=MANUFACTURER,
        model="Zone de chauffage",
    )


class ClimateAutomationEntity(CoordinatorEntity[ClimateAutomationCoordinator]):
    """Entité de base reliée au coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ClimateAutomationCoordinator) -> None:
        """Initialise l'entité de base."""
        super().__init__(coordinator)
        self._attr_device_info = main_device_info(coordinator.entry_id)


class ZoneEntity(ClimateAutomationEntity):
    """Entité rattachée à une zone (sous-appareil dédié)."""

    def __init__(
        self, coordinator: ClimateAutomationCoordinator, zone: ZoneConfig
    ) -> None:
        """Initialise une entité de zone."""
        super().__init__(coordinator)
        self.zone = zone
        self._attr_device_info = zone_device_info(coordinator.entry_id, zone)
