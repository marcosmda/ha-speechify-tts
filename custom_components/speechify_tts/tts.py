"""Speechify text-to-speech entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpeechifyConfigEntry
from .api import SpeechifyError, SpeechifyVoice
from .const import (
    AUDIO_FORMAT,
    CONF_LANGUAGE,
    CONF_LOUDNESS_NORMALIZATION,
    CONF_MODEL,
    CONF_VOICE,
    DEFAULT_LANGUAGE,
    DEFAULT_LOUDNESS_NORMALIZATION,
    DEFAULT_MODEL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeechifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Speechify TTS entity."""
    async_add_entities([SpeechifyTTSEntity(entry)])


def _base(code: str) -> str:
    return code.split("-")[0].split("_")[0].lower()


class SpeechifyTTSEntity(TextToSpeechEntity):
    """Speechify TTS entity."""

    # The TTS manager needs the entity's own name, so don't inherit it from the device.
    _attr_has_entity_name = False
    _attr_name = "Speechify"
    _attr_supported_options = [ATTR_VOICE, CONF_MODEL]

    def __init__(self, entry: SpeechifyConfigEntry) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Speechify",
            model="Text-to-speech API",
            name="Speechify",
            entry_type=DeviceEntryType.SERVICE,
        )

        voices = entry.runtime_data.voices
        self._voices: dict[str, SpeechifyVoice] = {v.voice_id: v for v in voices}

        languages: set[str] = set()
        for voice in voices:
            if voice.locale:
                languages.add(voice.locale)
            languages.update(voice.languages)
        self._attr_supported_languages = sorted(languages) or [DEFAULT_LANGUAGE]

        default_voice = self._default_voice()
        configured = entry.options.get(CONF_LANGUAGE)
        if configured:
            self._attr_default_language = configured
        elif default_voice and default_voice.locale:
            self._attr_default_language = default_voice.locale
        else:
            self._attr_default_language = DEFAULT_LANGUAGE

    def _default_voice(self) -> SpeechifyVoice | None:
        voice_id = self._entry.options.get(CONF_VOICE)
        if voice_id and voice_id in self._voices:
            return self._voices[voice_id]
        return None

    @property
    def default_options(self) -> dict[str, Any]:
        """Default per-request options."""
        voice = self._default_voice()
        options: dict[str, Any] = {
            CONF_MODEL: self._entry.options.get(CONF_MODEL, DEFAULT_MODEL)
        }
        if voice:
            options[ATTR_VOICE] = voice.voice_id
        return options

    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Voices whose own locale matches the language, best picks first."""
        base = _base(language)
        matching = [v for v in self._voices.values() if _base(v.locale) == base]
        if not matching:
            matching = [
                v
                for v in self._voices.values()
                if any(_base(lang) == base for lang in v.languages)
            ]
        matching.sort(
            key=lambda v: (
                v.locale.lower() != language.lower(),
                v.staff_pick_rank if v.staff_pick_rank is not None else 9999,
                v.name.lower(),
            )
        )
        return [Voice(v.voice_id, v.label) for v in matching] or None

    def _pick_voice(self, language: str, requested: str | None) -> str:
        if requested:
            return requested
        default = self._default_voice()
        if default and _base(default.locale) == _base(language):
            return default.voice_id
        voices = self.async_get_supported_voices(language)
        if voices:
            return voices[0].voice_id
        if default:
            return default.voice_id
        raise HomeAssistantError(
            f"No Speechify voice for '{language}'. Pick a voice in the integration options."
        )

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize speech."""
        voice_id = self._pick_voice(language, options.get(ATTR_VOICE))
        model = options.get(CONF_MODEL) or self._entry.options.get(
            CONF_MODEL, DEFAULT_MODEL
        )
        try:
            audio = await self._entry.runtime_data.client.async_synthesize(
                message,
                voice_id=voice_id,
                model=model,
                language=language or None,
                loudness_normalization=self._entry.options.get(
                    CONF_LOUDNESS_NORMALIZATION, DEFAULT_LOUDNESS_NORMALIZATION
                ),
            )
        except SpeechifyError as err:
            raise HomeAssistantError(f"Speechify: {err}") from err
        return AUDIO_FORMAT, audio
