---
name: telegram-edge-tts-remy
description: Configurer, diagnostiquer ou utiliser le text-to-speech Telegram avec Microsoft Edge TTS et la voix française Rémy multilingue France fr-FR-RemyMultilingualNeural. Utiliser quand l’utilisateur parle de TTS, text to speech, Edge TTS, Rémy, Remy, voix Telegram, messages vocaux Telegram sortants, ou du plugin Telegram.
---

# Telegram Edge TTS Rémy

Use this skill whenever Anthony asks about outbound Telegram text-to-speech, Edge TTS, the Rémy multilingual France voice, or Telegram voice replies generated from text.

## Goal

Generate or configure Telegram-compatible voice messages using Microsoft Edge TTS with the preferred default voice:

`fr-FR-RemyMultilingualNeural`

This is Rémy, France, male, multilingual.

## Core rules

- Prefer Microsoft Edge TTS for Telegram outbound voice messages.
- Default voice must be `fr-FR-RemyMultilingualNeural` unless Anthony explicitly chooses another voice.
- Keep Telegram replies readable as text as well as voice when `voice: true` is used.
- Do not promise automatic playback in Telegram. Auto-play depends on the Telegram client and its settings.
- Generate Telegram voice files as `.ogg` with Opus codec.
- Keep generated spoken text short, clean, and easy to understand.
- Strip Markdown and noisy technical formatting before synthesis.

## Plugin context

## WebUI voice mode GEN priority

When Anthony asks about WebUI voice mode, Edge TTS, Kokoro, intermediate steps, `GEN` messages, or step titles being read aloud, inspect both:

- `/a0/webui/index.js`
- `/a0/usr/plugins/edge_tts_voice/webui/edge-tts-store.js`

Expected behavior in voice mode:

1. WebUI voice mode is live-first, not catch-up-first. The goal is to hear current reasoning as it appears, not to replay all old `GEN` thoughts after the fact.
2. On chat switch, immediately stop current audio, clear pending final-response timers, flush Edge TTS and fallback GEN queues, and reset deduplication state.
3. On entry into a chat, baseline all already visible `GEN` / `thoughts` steps as seen so they are not replayed. If the chat is already finished, speak only the final `response`.
4. If the selected chat is still running, keep the newest visible `GEN` unmarked so voice mode can latch onto the first currently live reasoning step, then speak only subsequent new GEN steps.
5. Final assistant `response` messages keep highest priority only when that response is newer than any currently visible `GEN` / `thoughts` step.
6. Because WebUI polling passes the full chat history to `speakMessages(logs)`, never let an older final `response` mask fresh intermediate reasoning from a later turn.
7. Then `GEN` / `thoughts` content must be read in full, but only for the live window after the baseline.
8. Intermediate agent step titles / headlines are fallback only.
9. A step title must not interrupt an active or queued `GEN` audio.
10. The final response must also not interrupt queued live intermediate reasoning. If a `GEN` audio is active or has just been queued, delay the final response until the GEN queue is idle.
11. Track already-enqueued GEN speech keys in `webui/index.js`; because polling passes the whole history repeatedly, enqueue every new live GEN once instead of only looking at the newest GEN on each poll.
12. If Edge TTS plugin is available, enqueue GEN speech through `Alpine.store("edgeTtsVoice").enqueueGenThoughtSpeech(...)` rather than starting a fresh `ttsService.speakStream(...)` that can cut off prior audio. Edge TTS store must expose `clearGenThoughtSpeechQueue()` so chat switches flush pending Edge audio.
13. If Edge TTS is not available, use a FIFO fallback queue in `webui/index.js` for GEN speech. Do not call `ttsService.speakStream(...)` repeatedly with different ids in a loop, because each new stream can terminate the previous one.
14. Keep short text deduplication for DOM observer plus log observer paths, because both may see the same GEN content.

Validation commands after changing this behavior:

```bash
cd /a0
node --check webui/index.js
node --check usr/plugins/edge_tts_voice/webui/edge-tts-store.js
grep -n "enqueueGenThoughtSpeech\|processGenThoughtSpeechQueue\|__edgeTtsGenSpeechActive\|lastGenSpeechAt\|enqueueEdgeGenSpeech" \
  webui/index.js usr/plugins/edge_tts_voice/webui/edge-tts-store.js
```

Restart or refresh the WebUI after changing frontend JS so the browser loads the patched modules.

The Telegram integration normally lives here:

`/a0/plugins/_telegram_integration`

Anthony also has a durable user plugin that must be preserved and preferred for Telegram outbound TTS:

`/a0/usr/plugins/edge_tts_voice`

This plugin keeps the Edge TTS logic outside the core Telegram plugin and re-applies the bridge after Agent Zero or Telegram plugin updates. It contains:

- `helpers/synthesizer.py`: Microsoft Edge TTS synthesis to Telegram-compatible `.ogg`/Opus.
- `hooks.py`: `patch_telegram_handler()` that makes the core Telegram handler delegate `_generate_telegram_voice(...)` to `usr.plugins.edge_tts_voice.helpers.synthesizer.generate_telegram_voice` and repairs the `voice=True` branch when needed.
- `extensions/python/startup_migration/_20_edge_tts_voice_telegram_patch.py`: startup auto-repair so updates that overwrite `plugins/_telegram_integration/helpers/handler.py` are corrected on the next Agent Zero startup.
- `execute.py`: manual reapply command.

After an update, if Telegram voice output stops, run:

```bash
cd /a0 && /a0/venv/bin/python3.12 /a0/usr/plugins/edge_tts_voice/execute.py
systemctl restart agent-zero.service
```

Then verify:

```bash
cd /a0 && /a0/venv/bin/python3.12 - <<'PY'
import inspect
from plugins._telegram_integration.helpers import handler
print('delegate marker', 'usr.plugins.edge_tts_voice.helpers.synthesizer' in inspect.getsource(handler._generate_telegram_voice))
print('voice branch uses helper', '_generate_telegram_voice' in inspect.getsource(handler.send_telegram_reply))
PY
```

Important files may include:

- `helpers/handler.py`
- `helpers/telegram_client.py`
- response hook files that pass `voice` through to `send_telegram_reply(...)`

The expected Telegram sending flow is:

1. Send the normal text reply.
2. If `voice: true`, synthesize a voice file.
3. Send the `.ogg` voice message through Telegram.
4. Use short deduplication to avoid duplicate text-plus-voice pairs from multiple hooks.

## Environment overrides

These variables may control Edge TTS behavior:

- `TELEGRAM_EDGE_TTS_VOICE`
- `TELEGRAM_EDGE_TTS_RATE`
- `TELEGRAM_EDGE_TTS_VOLUME`
- `TELEGRAM_EDGE_TTS_PITCH`
- `TELEGRAM_REPLY_DEDUPE_TTL`

Recommended default:

```bash
TELEGRAM_EDGE_TTS_VOICE=fr-FR-RemyMultilingualNeural
```

## Diagnostics

Check whether `edge_tts` is installed:

```bash
python3 - <<'PY'
import edge_tts
print(edge_tts.__version__ if hasattr(edge_tts, '__version__') else 'edge_tts installed')
PY
```

List French voices:

```bash
python3 - <<'PY'
import asyncio, edge_tts

async def main():
    voices = await edge_tts.list_voices()
    for v in voices:
        name = v.get('ShortName', '')
        locale = v.get('Locale', '')
        if locale.startswith('fr') or 'French' in str(v):
            print(name, '-', locale, '-', v.get('Gender', ''))

asyncio.run(main())
PY
```

Verify the preferred voice exists:

```bash
python3 - <<'PY'
import asyncio, edge_tts

TARGET = 'fr-FR-RemyMultilingualNeural'

async def main():
    voices = await edge_tts.list_voices()
    matches = [v for v in voices if v.get('ShortName') == TARGET]
    print('FOUND' if matches else 'MISSING', TARGET)

asyncio.run(main())
PY
```

## Generate a Telegram-compatible sample

```bash
timeout 120s bash -lc 'set -euo pipefail
text="Bonjour Anthony. Ceci est un test de la voix Rémy multilingue France pour Telegram."
mp3=/tmp/telegram_edge_tts_remy.mp3
ogg=/tmp/telegram_edge_tts_remy.ogg
python3 - <<PY
import asyncio, edge_tts
text = """$text"""
voice = "fr-FR-RemyMultilingualNeural"
rate = "+0%"
volume = "+0%"
pitch = "+0Hz"
async def main():
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume, pitch=pitch)
    await communicate.save("$mp3")
asyncio.run(main())
PY
ffmpeg -hide_banner -y -i "$mp3" -c:a libopus -b:a 48k -vbr on "$ogg"
ls -lh "$mp3" "$ogg"'
```

## Implementation checklist for Telegram plugin

When modifying the Telegram plugin:

1. Locate the outbound reply function, usually `send_telegram_reply(...)`.
2. Confirm it accepts or receives `voice: bool`.
3. Confirm text is sent even when a voice message is generated.
4. Confirm `_generate_telegram_voice(text)` or equivalent uses Edge TTS.
5. Confirm the default voice is `fr-FR-RemyMultilingualNeural`.
6. Confirm the generated file is converted to `.ogg` Opus before `send_voice(...)`.
7. Confirm deduplication prevents duplicate text-plus-voice pairs, but does not suppress the normal text message.
8. Compile touched Python files with `python3 -m py_compile`.

## Suggested Python synthesis helper

```python
async def _generate_edge_tts_voice(text: str, output_ogg: str) -> str:
    import os
    import tempfile
    import edge_tts
    import asyncio
    import subprocess

    voice = os.getenv('TELEGRAM_EDGE_TTS_VOICE', 'fr-FR-RemyMultilingualNeural')
    rate = os.getenv('TELEGRAM_EDGE_TTS_RATE', '+0%')
    volume = os.getenv('TELEGRAM_EDGE_TTS_VOLUME', '+0%')
    pitch = os.getenv('TELEGRAM_EDGE_TTS_PITCH', '+0Hz')

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        mp3_path = tmp.name

    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume, pitch=pitch)
    await communicate.save(mp3_path)

    subprocess.run(
        ['ffmpeg', '-hide_banner', '-y', '-i', mp3_path, '-c:a', 'libopus', '-b:a', '48k', '-vbr', 'on', output_ogg],
        check=True,
    )
    return output_ogg
```

## Response guidance

For Anthony on Telegram:

- Keep replies concise.
- If `voice: true` is used, also include text so the message remains readable.
- Mention only when necessary that automatic playback depends on Telegram, not Agent Zero.
