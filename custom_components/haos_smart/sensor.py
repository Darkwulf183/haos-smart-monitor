"""Sensoren pro Platte."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import HaosSmartConfigEntry, HaosSmartCoordinator
from .entity import HaosSmartEntity, add_new_disks

DIAG = EntityCategory.DIAGNOSTIC
INC = SensorStateClass.TOTAL_INCREASING
MEAS = SensorStateClass.MEASUREMENT


@dataclass(frozen=True, kw_only=True)
class SmartSensorDescription(SensorEntityDescription):
    """key = Schlüssel in values{} der App."""


SENSORS: tuple[SmartSensorDescription, ...] = (
    SmartSensorDescription(
        key="temperature", translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE, state_class=MEAS,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SmartSensorDescription(
        key="power_on_hours", translation_key="power_on_hours",
        device_class=SensorDeviceClass.DURATION, state_class=INC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_unit_of_measurement=UnitOfTime.HOURS, suggested_display_precision=0,
    ),
    SmartSensorDescription(
        key="wear_used", translation_key="wear_used", state_class=MEAS,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SmartSensorDescription(
        key="data_written_tb", translation_key="data_written",
        device_class=SensorDeviceClass.DATA_SIZE, state_class=INC,
        native_unit_of_measurement=UnitOfInformation.TERABYTES,
        suggested_unit_of_measurement=UnitOfInformation.TERABYTES, suggested_display_precision=2,
    ),
    SmartSensorDescription(
        key="data_read_tb", translation_key="data_read",
        device_class=SensorDeviceClass.DATA_SIZE, state_class=INC,
        native_unit_of_measurement=UnitOfInformation.TERABYTES,
        suggested_unit_of_measurement=UnitOfInformation.TERABYTES, suggested_display_precision=2,
    ),
    # --- Diagnose ---
    SmartSensorDescription(
        key="power_cycles", translation_key="power_cycles", state_class=INC, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="unsafe_shutdowns", translation_key="unsafe_shutdowns", state_class=INC, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="crc_errors", translation_key="crc_errors", state_class=INC, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="error_log_entries", translation_key="error_log_entries", state_class=INC, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="reallocated_sectors", translation_key="reallocated_sectors", state_class=MEAS, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="pending_sectors", translation_key="pending_sectors", state_class=MEAS, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="uncorrectable", translation_key="uncorrectable", state_class=MEAS, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="media_errors", translation_key="media_errors", state_class=MEAS, entity_category=DIAG,
    ),
    SmartSensorDescription(
        key="available_spare", translation_key="available_spare", state_class=MEAS,
        native_unit_of_measurement=PERCENTAGE, entity_category=DIAG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaosSmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def build(disk_id: str, disk: dict[str, Any]) -> list:
        values = disk.get("values") or {}
        ents: list = [SmartSensor(coordinator, disk_id, desc) for desc in SENSORS if desc.key in values]
        ents.append(LastUpdateSensor(coordinator, disk_id))
        return ents

    entry.async_on_unload(add_new_disks(coordinator, async_add_entities, build))


class SmartSensor(HaosSmartEntity, SensorEntity):
    entity_description: SmartSensorDescription

    def __init__(self, coordinator: HaosSmartCoordinator, disk_id: str, desc: SmartSensorDescription) -> None:
        super().__init__(coordinator, disk_id, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> float | int | None:
        return (self.disk.get("values") or {}).get(self.entity_description.key)


class LastUpdateSensor(HaosSmartEntity, SensorEntity):
    """Zeitpunkt der letzten erfolgreichen Abfrage dieser Platte."""

    _attr_translation_key = "last_update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = DIAG

    def __init__(self, coordinator: HaosSmartCoordinator, disk_id: str) -> None:
        super().__init__(coordinator, disk_id, "last_update")

    @property
    def native_value(self) -> datetime | None:
        return dt_util.parse_datetime(self.disk.get("last_update") or "")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.disk
        return {
            "geraet": d.get("device"),
            "typ": d.get("type"),
            "letzter_versuch": d.get("checked"),
            "fehler": d.get("error"),
        }
