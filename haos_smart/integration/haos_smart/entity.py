"""Gemeinsame Basis: ein Gerät pro Platte."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HaosSmartCoordinator


def _manufacturer(model: str) -> str | None:
    """Erstes Wort des Modellnamens, falls es nach Hersteller aussieht."""
    known = ("Samsung", "WDC", "WD", "Western", "Crucial", "Kingston", "Intel", "Seagate",
             "Toshiba", "SanDisk", "Micron", "SK", "Hynix", "Transcend", "Lexar", "Patriot",
             "Corsair", "PNY", "Verbatim", "Intenso", "HGST", "Hitachi", "ADATA", "Teamgroup")
    first = (model or "").split(" ", 1)[0]
    for name in known:
        if first.lower().startswith(name.lower()):
            return {"WDC": "Western Digital", "WD": "Western Digital",
                    "Western": "Western Digital"}.get(name, name)
    return None


class HaosSmartEntity(CoordinatorEntity[HaosSmartCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HaosSmartCoordinator, disk_id: str, key: str) -> None:
        super().__init__(coordinator)
        self.disk_id = disk_id
        self._attr_unique_id = f"{disk_id}_{key}"
        d = self.disk
        model = d.get("model") or d.get("device")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, disk_id)},
            name=model,
            model=model,
            manufacturer=_manufacturer(model),
            serial_number=d.get("serial"),
            sw_version=d.get("firmware"),
            hw_version=f"{d['capacity_gb']} GB" if d.get("capacity_gb") else None,
        )

    @property
    def disk(self) -> dict[str, Any]:
        return self.coordinator.data["disks"].get(self.disk_id, {})

    @property
    def available(self) -> bool:
        return super().available and self.disk_id in self.coordinator.data["disks"]


def add_new_disks(
    coordinator: HaosSmartCoordinator,
    async_add_entities: Callable[[Iterable[Entity]], None],
    build: Callable[[str, dict[str, Any]], list[Entity]],
) -> Callable[[], None]:
    """Entitäten für vorhandene Platten anlegen und später neu auftauchende ergänzen."""
    known: set[str] = set()

    @callback
    def _check() -> None:
        new = [i for i in coordinator.data["disks"] if i not in known]
        if not new:
            return
        entities: list[Entity] = []
        for disk_id in new:
            known.add(disk_id)
            entities.extend(build(disk_id, coordinator.data["disks"][disk_id]))
        async_add_entities(entities)

    _check()
    return coordinator.async_add_listener(_check)
