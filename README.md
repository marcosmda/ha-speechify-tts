# Speechify TTS for Home Assistant

[![GitHub Release][release-shield]][releases]
[![HACS][hacs-shield]][hacs]
[![Validate][validate-shield]][validate]
[![License][license-shield]](LICENSE)

Natural-sounding [Speechify](https://speechify.ai) voices for Home Assistant. Adds a `tts` entity you can use in **Assist voice pipelines**, with `tts.speak`, and anywhere Home Assistant accepts a text-to-speech engine.

> [!NOTE]
> Community project. Not made or endorsed by Speechify.

## Features

- ⚡ **Streaming**: with an LLM conversation agent (Gemini, OpenAI, Claude…), Assist starts speaking the first sentence while the rest of the reply is still being written
- 🗣️ **Simba 3.5 voices in 48 languages**, Simba 3.0 also selectable
- 🎙️ **Every voice in your workspace**, including your cloned voices
- 🌍 **Voices filtered by language** in the Assist pipeline editor, Speechify's top picks first
- 📜 **Long text** over Speechify's 2,000-character limit is split at sentence boundaries
- 🔁 **Retries** rate limits and transient errors, and asks for a new key if yours is revoked
- 🖥️ **UI setup**, no YAML

## Installation

### Marketplace / HACS (recommended)

[![Open your Home Assistant instance and open this repository in the Marketplace.][my-hacs-badge]][my-hacs]

Or manually:

1. Open **Settings → Marketplace** (HACS on Home Assistant 2026.10 and older).
2. Open the menu → **Custom repositories**, add `https://github.com/marcosmda/ha-speechify-tts` with type **Integration**.
3. Install **Speechify TTS** and restart Home Assistant.

### Manual

1. Download the [latest release][releases].
2. Copy `custom_components/speechify_tts` into your `config/custom_components/` folder.
3. Restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up Speechify TTS.][my-config-badge]][my-config]

1. Create an API key at [platform.speechify.ai](https://platform.speechify.ai).
2. Go to **Settings → Devices & services → Add integration → Speechify TTS** and paste the key.
3. Optional: open **Configure** on the integration to set:

| Option | Description |
|---|---|
| Default voice | Used when a request names no voice and the voice speaks the requested language |
| Model | `simba-3.5` (default, 48 languages) or `simba-3.0` (English, de-DE, es-ES, es-MX, fr-FR, it-IT, pt-BR) |
| Default language | e.g. `pt-BR`. Empty uses the default voice's language |
| Loudness normalization | Evens out volume between voices. Adds a little latency |

## Usage

### Assist

**Settings → Voice assistants →** your assistant **→ Text-to-speech → Speechify**, then pick the language and voice.

### Action

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
| `voice` | Any `voice_id` your workspace can use (listed in the integration options) |
| `model` | `simba-3.5`, `simba-3.0` |

## Notes

- Audio is MP3. Streaming uses Speechify's `/v1/audio/stream` endpoint (up to 20,000 characters per request); one-off `tts.speak` calls use `/v1/audio/speech`.
- Speechify's free plan allows 1 request per second and 3 at once. Long messages are sent as several requests in a row.
- Your API key is stored in Home Assistant's config entry and never leaves your instance except to call Speechify.

## Troubleshooting

Turn on debug logs for the integration:

```yaml
logger:
  logs:
    custom_components.speechify_tts: debug
```

Then reproduce the issue and [open an issue][issues] with the log.

## Contributing

Issues and pull requests are welcome.

## License

[MIT](LICENSE)

[release-shield]: https://img.shields.io/github/v/release/marcosmda/ha-speechify-tts?style=for-the-badge
[releases]: https://github.com/marcosmda/ha-speechify-tts/releases
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge
[hacs]: https://hacs.xyz
[validate-shield]: https://img.shields.io/github/actions/workflow/status/marcosmda/ha-speechify-tts/validate.yml?branch=main&label=validate&style=for-the-badge
[validate]: https://github.com/marcosmda/ha-speechify-tts/actions/workflows/validate.yml
[license-shield]: https://img.shields.io/github/license/marcosmda/ha-speechify-tts?style=for-the-badge
[issues]: https://github.com/marcosmda/ha-speechify-tts/issues
[my-hacs-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[my-hacs]: https://my.home-assistant.io/redirect/hacs_repository/?owner=marcosmda&repository=ha-speechify-tts&category=integration
[my-config-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[my-config]: https://my.home-assistant.io/redirect/config_flow_start/?domain=speechify_tts
