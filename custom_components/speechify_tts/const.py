"""Constants for the Speechify TTS integration."""

from __future__ import annotations

DOMAIN = "speechify_tts"

API_BASE_URL = "https://api.speechify.ai"

CONF_VOICE = "voice"
CONF_MODEL = "model"
CONF_LANGUAGE = "language"
CONF_LOUDNESS_NORMALIZATION = "loudness_normalization"

MODELS = ["simba-3.5", "simba-3.0"]
DEFAULT_MODEL = "simba-3.5"
DEFAULT_LANGUAGE = "en-US"
DEFAULT_LOUDNESS_NORMALIZATION = False

AUDIO_FORMAT = "mp3"
STREAM_ACCEPT = "audio/mpeg"

# Speechify bills and limits by spoken characters per request.
MAX_CHARS_PER_REQUEST = 2000
MAX_CHARS_PER_STREAM = 20000
