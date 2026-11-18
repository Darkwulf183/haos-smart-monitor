"""Holt die Plattendaten von der App."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, INTEGRATION_VERSION, REFRESH_TIMEOUT, REQUEST_TIMEOUT, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type HaosSmartConfigEntry = ConfigEntry[HaosSmartCoordinator]


class CannotConnect(Exception):
    """App nicht erreichbar oder Antwort unbrauchbar."""


class HaosSmartApi:
    """Kleiner Client für die JSON-API der App."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self._session = async_get_clientsession(hass)
        self._base = f"http://{host}:{port}"

    async def _request(self, method: str, path: str, timeout: int) -> dict[str, Any]:
        try:
            async with self._session.request(
                method, self._base + path, timeout=aiohttp.ClientTimeout(total=timeout),
                # Damit die App erkennt, welche Integrationsversion gerade läuft
                headers={"X-HAOS-SMART-Integration": INTEGRATION_VERSION},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise CannotConnect(f"{method} {path}: {err!r}") from err
        if not isinstance(data, dict) or not isinstance(data.get("disks"), list):
            raise CannotConnect(f"{method} {path}: unerwartete Antwort")
        return data

    async def get_disks(self) -> dict[str, Any]:
        return await self._request("GET", "/api/disks", REQUEST_TIMEOUT)

    async def refresh(self) -> dict[str, Any]:
        return await self._request("POST", "/api/refresh", REFRESH_TIMEOUT)


def _index(payload: dict[str, Any]) -> dict[str, Any]:
    """API-Antwort -> {"app": ..., "disks": {id: platte}}.

    Platten ohne Werte (noch nie gelesen, z. B. erster Lauf im Standby) werden
    übersprungen – ihre ID wäre noch nicht die Seriennummer.
    """
    disks = {
        d["id"]: d
        for d in payload.get("disks", [])
        if isinstance(d, dict) and d.get("id") and d.get("values")
    }
    app = {k: payload.get(k) for k in ("version", "last_scan", "scanning", "interval_min")}
    return {"app": app, "disks": disks}


class HaosSmartCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fragt /api/disks regelmäßig ab."""

    config_entry: HaosSmartConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HaosSmartConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = HaosSmartApi(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
        self._last_app_version: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = _index(await self.api.get_disks())
        except CannotConnect as err:
            raise UpdateFailed(f"App nicht erreichbar: {err}") from err
        self._check_version(data["app"].get("version"))
        return data

    def _check_version(self, app_version: str | None) -> None:
        """Hinweis unter Einstellungen > Reparaturen, wenn App und Integration auseinanderlaufen."""
        if app_version == self._last_app_version:
            return
        self._last_app_version = app_version
        if app_version and app_version != INTEGRATION_VERSION:
            ir.async_create_issue(
                self.hass, DOMAIN, "version_mismatch",
                is_fixable=False, severity=ir.IssueSeverity.WARNING,
                translation_key="version_mismatch",
                translation_placeholders={"app": app_version, "integration": INTEGRATION_VERSION},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, "version_mismatch")

    async def async_refresh_disks(self) -> None:
        """Platten sofort neu auslesen lassen (dauert, bis die App fertig ist)."""
        try:
            payload = await self.api.refresh()
        except CannotConnect as err:
            raise UpdateFailed(f"Auslesen fehlgeschlagen: {err}") from err
        data = _index(payload)
        self._check_version(data["app"].get("version"))
        self.async_set_updated_data(data)
