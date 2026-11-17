"""Speechify text-to-speech entity."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import contextlib
import logging
import re
from typing import Any

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    TtsAudioType,
    Voice,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpeechifyConfigEntry
from .api import SpeechifyError, SpeechifyVoice, split_text
from .const import (
    AUDIO_FORMAT,
    MAX_CHARS_PER_STREAM,
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

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Speak streamed text (e.g. an LLM reply) sentence by sentence."""
        return TTSAudioResponse(AUDIO_FORMAT, self._stream_audio(request))

    async def _stream_audio(self, request: TTSAudioRequest) -> AsyncGenerator[bytes]:
        language = request.language
        options = request.options or {}
        voice_id = self._pick_voice(language, options.get(ATTR_VOICE))
        model = options.get(CONF_MODEL) or self._entry.options.get(
            CONF_MODEL, DEFAULT_MODEL
        )
        loudness = self._entry.options.get(
            CONF_LOUDNESS_NORMALIZATION, DEFAULT_LOUDNESS_NORMALIZATION
        )
        client = self._entry.runtime_data.client

        # Sentences flow from the text stream into this queue; None ends it.
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def _collect_sentences() -> None:
            buffer = ""
            try:
                async for chunk in request.message_gen:
                    buffer += chunk
                    sentences, buffer = pop_sentences(buffer)
                    for sentence in sentences:
                        await queue.put(sentence)
                if buffer.strip():
                    await queue.put(buffer.strip())
            finally:
                await queue.put(None)

        collector = self.hass.async_create_background_task(
            _collect_sentences(), name="speechify_tts_collect_sentences"
        )
        try:
            finished = False
            while not finished:
                sentence = await queue.get()
                if sentence is None:
                    break
                # The first sentence is spoken alone so audio starts early; after
                # that, everything that arrived while speaking is sent together.
                batch = [sentence]
                while not queue.empty():
                    more = queue.get_nowait()
                    if more is None:
                        finished = True
                        break
                    batch.append(more)

                for text in split_text(" ".join(batch), MAX_CHARS_PER_STREAM):
                    _LOGGER.debug("Streaming %d characters", len(text))
                    async for audio in client.async_stream(
                        text,
                        voice_id=voice_id,
                        model=model,
                        language=language or None,
                        loudness_normalization=loudness,
                    ):
                        yield audio
        except SpeechifyError as err:
            raise HomeAssistantError(f"Speechify: {err}") from err
        finally:
            if not collector.done():
                collector.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await collector


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…。！？])\s+|\n+")


def pop_sentences(buffer: str) -> tuple[list[str], str]:
    """Split complete sentences off the front of a growing text buffer.

    Returns the complete sentences and the unfinished remainder. A sentence
    counts as complete once whitespace follows its end punctuation, so
    "3.5" or a sentence still being typed is left in the buffer.
    """
    parts = _SENTENCE_BOUNDARY.split(buffer)
    if len(parts) == 1:
        return [], buffer
    *complete, rest = parts
    return [s.strip() for s in complete if s.strip()], rest
