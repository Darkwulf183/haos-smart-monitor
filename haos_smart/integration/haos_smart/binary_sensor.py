"""Problem-Sensor pro Platte."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HaosSmartConfigEntry, HaosSmartCoordinator
from .entity import HaosSmartEntity, add_new_disks


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaosSmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entry.async_on_unload(
        add_new_disks(coordinator, async_add_entities,
                      lambda disk_id, _disk: [HealthSensor(coordinator, disk_id)])
    )


class HealthSensor(HaosSmartEntity, BinarySensorEntity):
    """An = Problem. Gründe stehen im Attribut 'gruende'."""

    _attr_translation_key = "health"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: HaosSmartCoordinator, disk_id: str) -> None:
        super().__init__(coordinator, disk_id, "health")

    @property
    def is_on(self) -> bool:
        return bool(self.disk.get("problem"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.disk
        return {
            "gruende": d.get("reasons") or [],
            "smart_passed": d.get("smart_passed"),
            "fehler": d.get("error"),
        }
