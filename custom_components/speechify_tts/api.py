"""Minimal async client for the Speechify text-to-speech API."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
import logging
import re
from typing import Any

import aiohttp

from .const import API_BASE_URL, AUDIO_FORMAT, MAX_CHARS_PER_REQUEST

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=60)
_MAX_RETRIES = 2
_RETRYABLE_STATUS = {429, 500, 502, 503}


class SpeechifyError(Exception):
    """Base error for the Speechify API."""


class SpeechifyAuthError(SpeechifyError):
    """The API key is missing or invalid."""


class SpeechifyPaymentError(SpeechifyError):
    """The workspace is out of credits or lacks the plan for this request."""


@dataclass(slots=True)
class SpeechifyVoice:
    """A voice from the Speechify catalog."""

    voice_id: str
    name: str
    locale: str
    gender: str
    models: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    staff_pick_rank: int | None = None

    @property
    def label(self) -> str:
        """Human readable label for selectors."""
        return f"{self.name} ({self.locale}, {self.gender})"


class SpeechifyClient:
    """Talks to api.speechify.ai."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        base_url: str = API_BASE_URL,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a request, retrying rate limits and transient server errors."""
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{self._base_url}{path}"

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with self._session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=_TIMEOUT,
                ) as resp:
                    if resp.status < 400:
                        return await resp.json()

                    body: dict[str, Any] = {}
                    try:
                        body = await resp.json()
                    except (aiohttp.ContentTypeError, ValueError):
                        pass
                    error = body.get("error") or {}
                    code = error.get("code", "unknown")
                    message = error.get("message") or resp.reason or "error"

                    if resp.status in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                        delay = _retry_delay(resp.headers.get("Retry-After"), attempt)
                        _LOGGER.debug(
                            "Speechify %s (%s), retrying in %.1fs", resp.status, code, delay
                        )
                        await asyncio.sleep(delay)
                        continue

                    if resp.status == 401:
                        raise SpeechifyAuthError(message)
                    if resp.status == 402:
                        raise SpeechifyPaymentError(message)
                    raise SpeechifyError(f"{resp.status} {code}: {message}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_retry_delay(None, attempt))
                    continue
                raise SpeechifyError(f"Cannot reach Speechify: {err}") from err

        raise SpeechifyError("Speechify request failed after retries")

    async def async_validate(self) -> None:
        """Check the API key with a cheap call."""
        await self._request("GET", "/v1/voices", params={"limit": 1})

    async def async_get_voices(self) -> list[SpeechifyVoice]:
        """Return every voice the workspace can use (shared and personal)."""
        voices: list[SpeechifyVoice] = []
        cursor: str | None = None
        for _ in range(100):  # hard stop against a misbehaving cursor
            params: dict[str, Any] = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = await self._request("GET", "/v1/voices", params=params)
            for raw in data.get("voices", []):
                voices.append(_parse_voice(raw))
            cursor = data.get("next_cursor")
            if not data.get("has_more") or not cursor:
                break
        return voices

    async def async_synthesize(
        self,
        text: str,
        *,
        voice_id: str,
        model: str,
        language: str | None,
        loudness_normalization: bool,
    ) -> bytes:
        """Synthesize text to MP3, splitting text over the per-request limit."""
        audio = bytearray()
        for chunk in split_text(text, MAX_CHARS_PER_REQUEST):
            payload: dict[str, Any] = {
                "input": chunk,
                "voice_id": voice_id,
                "model": model,
                "audio_format": AUDIO_FORMAT,
                "options": {"loudness_normalization": loudness_normalization},
            }
            if language:
                payload["language"] = language
            data = await self._request("POST", "/v1/audio/speech", json=payload)
            try:
                audio.extend(base64.b64decode(data["audio_data"]))
            except (KeyError, ValueError) as err:
                raise SpeechifyError("Speechify returned no audio") from err
        return bytes(audio)


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    """Seconds to wait before the next attempt."""
    if retry_after:
        try:
            return min(float(retry_after), 10.0)
        except ValueError:
            pass
    return float(2**attempt)


def _parse_voice(raw: dict[str, Any]) -> SpeechifyVoice:
    models = raw.get("models") or []
    languages: list[str] = []
    for model in models:
        for lang in model.get("languages") or []:
            locale = lang.get("locale")
            if locale and locale not in languages:
                languages.append(locale)
    return SpeechifyVoice(
        voice_id=raw["id"],
        name=raw.get("display_name") or raw["id"],
        locale=raw.get("locale") or "",
        gender=raw.get("gender") or "not_specified",
        models=[m["name"] for m in models if m.get("name")],
        languages=languages,
        staff_pick_rank=raw.get("staff_pick_rank"),
    )


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_text(text: str, limit: int) -> list[str]:
    """Split text into chunks under limit, preferring sentence boundaries."""
    text = text.strip()
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [c for c in chunks if c]
