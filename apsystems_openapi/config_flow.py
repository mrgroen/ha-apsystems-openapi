from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, DEFAULT_BASE_URL
from .api import APSClient

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("app_id"): str,
    vol.Required("app_secret"): str,
    vol.Required("sid", description="System ID as shown in EMA"): str,
    vol.Optional("base_url", default=DEFAULT_BASE_URL): str,
    vol.Optional("scan_interval", default=1800): int,  # seconds
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        session = async_get_clientsession(self.hass)
        client = APSClient(
            app_id=user_input["app_id"],
            app_secret=user_input["app_secret"],
            sid=user_input["sid"],
            base_url=user_input["base_url"] or DEFAULT_BASE_URL,
            session=session,
        )
        try:
            summary = await client.get_system_summary()
            if summary.get("code") != 0:
                return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors={"base": "auth"})
        except Exception:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors={"base": "cannot_connect"})

        await self.async_set_unique_id(f"{user_input['sid']}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=f"APsystems {user_input['sid']}", data=user_input)
