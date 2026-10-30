"""Integración para el control de los LED del router DIGI."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, ["switch"])
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    return await hass.config_entries.async_unload_platforms(
        entry, ["switch"]
    )
