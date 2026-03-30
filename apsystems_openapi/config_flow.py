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
    vol.Optional("scan_interval", default=1800): vol.All(int, vol.Range(min=1800, max=7200)),  # 30 min to 2 hours
    vol.Optional("sunrise_offset", default=30): vol.All(int, vol.Range(min=0, max=120)),  # minutes after sunrise
    vol.Optional("sunset_offset", default=30): vol.All(int, vol.Range(min=0, max=120)),  # minutes after sunset
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user", 
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "scan_interval_help": "Seconds between API calls during solar hours (default 3600 = 60 min)",
                    "sunrise_offset_help": "Minutes to wait after sunrise before starting API calls (default 30)",
                    "sunset_offset_help": "Minutes to wait after sunset before stopping API calls (default 30)",
                }
            )
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

    @staticmethod
    def async_get_options_flow(config_entry):
        return APSOptionsFlow(config_entry)


class APSOptionsFlow(config_entries.OptionsFlow):
    """Options flow to adjust scan intervals and focus inverter."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Merge options into the config entry data so __init__.py reads them
            new_data = {**self._entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.data
        schema = vol.Schema({
            vol.Optional("scan_interval", default=current.get("scan_interval", 1800)): vol.All(
                int, vol.Range(min=1800, max=7200)
            ),

        })
        return self.async_show_form(step_id="init", data_schema=schema)
