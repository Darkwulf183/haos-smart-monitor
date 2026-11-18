"""Einrichtung über die Oberfläche."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from .coordinator import CannotConnect, HaosSmartApi


def _detect_host(hass: HomeAssistant) -> str:
    """Hostname der installierten App ermitteln.

    Lokal heißt sie local-haos-smart, aus einem GitHub-Repository <hash>-haos-smart.
    """
    try:
        from homeassistant.components import hassio
        get_info = getattr(hassio, "get_apps_info", None) or getattr(hassio, "get_addons_info")
        infos = get_info(hass) or {}
    except Exception:  # kein Supervisor oder ältere/neuere HA-Version
        return DEFAULT_HOST
    for slug in infos:
        if slug == "haos_smart" or slug.endswith("_haos_smart"):
            return slug.replace("_", "-")
    return DEFAULT_HOST


class HaosSmartConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            try:
                data = await HaosSmartApi(self.hass, host, port).get_disks()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
                return self.async_create_entry(
                    title="HAOS SMART Monitor",
                    data={CONF_HOST: host, CONF_PORT: port},
                    description_placeholders={"disks": str(len(data["disks"]))},
                )

        defaults = user_input or {CONF_HOST: _detect_host(self.hass), CONF_PORT: DEFAULT_PORT}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=defaults[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Host/Port nachträglich ändern."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            try:
                await HaosSmartApi(self.hass, host, port).get_disks()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host, CONF_PORT: port}
                )
        current = user_input or entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=current[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)
