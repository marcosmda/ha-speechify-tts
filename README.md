# Speechify TTS for Home Assistant

A custom integration that adds [Speechify](https://speechify.ai) text-to-speech to Home Assistant as a `tts` entity. Use it in Assist voice pipelines, with `tts.speak`, or anywhere Home Assistant accepts a TTS engine.

- Simba 3.5 voices in 48 languages (Simba 3.0 also selectable)
- Every voice your Speechify workspace can use, including cloned voices
- Voices filtered by language in the Assist pipeline editor
- Text over Speechify's 2,000-character request limit is split at sentence boundaries
- Retries on rate limits and transient errors, and asks for a new key when yours is revoked

> This is a community project. It is not made or endorsed by Speechify.

## Installation

### Marketplace / HACS (recommended)

1. In Home Assistant, open **Settings → Marketplace** (HACS on 2026.10 and older).
2. Add this repository as a custom repository with type **Integration**:
   `https://github.com/marcosmda/ha-speechify-tts`
3. Install **Speechify TTS** and restart Home Assistant.

### Manual

Copy `custom_components/speechify_tts` into your Home Assistant `config/custom_components/` folder and restart.

## Setup

1. Create an API key at [platform.speechify.ai](https://platform.speechify.ai).
2. In Home Assistant go to **Settings → Devices & services → Add integration → Speechify TTS** and paste the key.
3. Open the integration's **Configure** dialog to pick a default voice, model, optional default language and loudness normalization.

## Use it

**Assist:** **Settings → Voice assistants →** your assistant **→ Text-to-speech →** *Speechify*, then pick a language and voice.

**Actions:**

```yaml
action: tts.speak
target:
  entity_id: tts.speechify
data:
  media_player_entity_id: media_player.living_room
  message: "Olá! O jantar está pronto."
  language: pt-BR
  options:
    voice: leticia-agent
    model: simba-3.5
```

| Option | Values |
|---|---|
| `voice` | Any `voice_id` from your workspace (see the voice list in the integration options) |
| `model` | `simba-3.5` (default), `simba-3.0` |

## Notes

- Audio is returned as MP3.
- Speechify's free plan allows 1 request per second and 3 at once. Long messages are sent as several requests in a row.
- The API key is stored in Home Assistant's config entry, never in this repository.

## License

MIT
