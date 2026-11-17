"""Config flow for Speechify TTS."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SpeechifyAuthError, SpeechifyClient, SpeechifyError, SpeechifyVoice
from .const import (
    CONF_LANGUAGE,
    CONF_LOUDNESS_NORMALIZATION,
    CONF_MODEL,
    CONF_VOICE,
    DEFAULT_LOUDNESS_NORMALIZATION,
    DEFAULT_MODEL,
    DOMAIN,
    MODELS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


async def _validate_key(hass, api_key: str) -> str | None:
    """Return an error key, or None when the key works."""
    client = SpeechifyClient(async_get_clientsession(hass), api_key)
    try:
        await client.async_validate()
    except SpeechifyAuthError:
        return "invalid_auth"
    except SpeechifyError:
        _LOGGER.exception("Error validating the Speechify API key")
        return "cannot_connect"
    return None


class SpeechifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Speechify TTS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if (error := await _validate_key(self.hass, api_key)) is None:
                self._async_abort_entries_match({CONF_API_KEY: api_key})
                return self.async_create_entry(
                    title="Speechify", data={CONF_API_KEY: api_key}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the stored key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if (error := await _validate_key(self.hass, api_key)) is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SpeechifyOptionsFlow:
        """Return the options flow."""
        return SpeechifyOptionsFlow()


def _voice_sort_key(voice: SpeechifyVoice) -> tuple[str, int, str]:
    rank = voice.staff_pick_rank if voice.staff_pick_rank is not None else 9999
    return (voice.locale.lower(), rank, voice.name.lower())


class SpeechifyOptionsFlow(OptionsFlowWithReload):
    """Default voice, model and language."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if not user_input.get(CONF_LANGUAGE):
                user_input.pop(CONF_LANGUAGE, None)
            return self.async_create_entry(data=user_input)

        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")

        voices: list[SpeechifyVoice] = self.config_entry.runtime_data.voices
        voice_options = [
            SelectOptionDict(value=v.voice_id, label=v.label)
            for v in sorted(voices, key=_voice_sort_key)
        ]
        options = self.config_entry.options
        default_voice = options.get(CONF_VOICE) or (
            voice_options[0]["value"] if voice_options else vol.UNDEFINED
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_VOICE, default=default_voice): SelectSelector(
                    SelectSelectorConfig(
                        options=voice_options, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(
                    CONF_MODEL, default=options.get(CONF_MODEL, DEFAULT_MODEL)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=MODELS, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional(
                    CONF_LANGUAGE,
                    description={"suggested_value": options.get(CONF_LANGUAGE)},
                ): str,
                vol.Required(
                    CONF_LOUDNESS_NORMALIZATION,
                    default=options.get(
                        CONF_LOUDNESS_NORMALIZATION, DEFAULT_LOUDNESS_NORMALIZATION
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
