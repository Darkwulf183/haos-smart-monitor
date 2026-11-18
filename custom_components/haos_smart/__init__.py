"""HAOS SMART Monitor – Sensoren für die Platten am Home-Assistant-Rechner.

Die Daten liefert die gleichnamige App; diese Integration fragt nur deren
API ab und legt pro Platte ein Gerät mit Sensoren an.
"""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import HaosSmartConfigEntry, HaosSmartCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: HaosSmartConfigEntry) -> bool:
    coordinator = HaosSmartCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HaosSmartConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
