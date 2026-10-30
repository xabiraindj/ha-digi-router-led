"""Configuración de la integración DIGI."""
import ipaddress

import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD


class DigiLedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                ipaddress.ip_address(host)
                user_input[CONF_HOST] = host
                return self.async_create_entry(
                    title=f"DIGI Router ({host})",
                    data=user_input,
                )
            except ValueError:
                errors["base"] = "invalid_host"

        schema = vol.Schema({
            vol.Required(CONF_HOST, default="192.168.1.1"): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
