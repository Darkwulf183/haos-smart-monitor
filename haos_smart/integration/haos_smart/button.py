"""Button „Jetzt auslesen“."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

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
                      lambda disk_id, _disk: [RefreshButton(coordinator, disk_id)])
    )


class RefreshButton(HaosSmartEntity, ButtonEntity):
    """Lässt die App alle Platten sofort neu auslesen."""

    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HaosSmartCoordinator, disk_id: str) -> None:
        super().__init__(coordinator, disk_id, "refresh")

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_refresh_disks()
        except UpdateFailed as err:
            raise HomeAssistantError(str(err)) from err
