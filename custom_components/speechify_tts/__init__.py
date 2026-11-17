"""The Speechify TTS integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SpeechifyAuthError, SpeechifyClient, SpeechifyError, SpeechifyVoice

PLATFORMS: list[Platform] = [Platform.TTS]


@dataclass(slots=True)
class SpeechifyData:
    """Runtime data for a config entry."""

    client: SpeechifyClient
    voices: list[SpeechifyVoice]


type SpeechifyConfigEntry = ConfigEntry[SpeechifyData]


async def async_setup_entry(hass: HomeAssistant, entry: SpeechifyConfigEntry) -> bool:
    """Set up Speechify from a config entry."""
    client = SpeechifyClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    try:
        voices = await client.async_get_voices()
    except SpeechifyAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SpeechifyError as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = SpeechifyData(client=client, voices=voices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpeechifyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
