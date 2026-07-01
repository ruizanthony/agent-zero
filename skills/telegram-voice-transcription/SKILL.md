---
name: telegram-voice-transcription
description: Transcrire et interpréter les messages vocaux Telegram, notes vidéo Telegram, fichiers audio ou demandes de transcription vocale. Utiliser dès qu’un message contient un vocal, une note vidéo, un fichier audio, ou que l’utilisateur demande de transcrire un vocal. Priorité à Faster Whisper ou Whisper local, en français par défaut pour Anthony, sans API externe sauf confirmation explicite.
---

# Telegram Voice Transcription

Use this skill whenever the user sends a Telegram voice message, Telegram video note, audio attachment, or asks to transcribe a voice/audio message.

## Core rules

- Prefer local transcription with `faster_whisper`.
- If `faster_whisper` is unavailable, try local `whisper`.
- Do not use the OpenAI API or any external transcription API unless Anthony explicitly confirms it.
- For Telegram voice/video-note messages from Anthony, assume French by default.
- If the transcription is ambiguous or incoherent, propose the most likely French interpretation before acting.
- For replies intended for Telegram, keep the answer concise and mobile-friendly.
- When useful and possible, reply with `voice: true`, while keeping the text short and readable.

## Workflow

1. Identify the audio/video attachment path from the user message.
2. Check the file exists and inspect duration/streams when needed with `ffprobe`.
3. Transcribe locally with Faster Whisper in French.
4. If the transcript is empty or suspicious, retry without VAD and/or extract mono WAV audio with `ffmpeg`.
5. Treat generic hallucinations such as “Sous-titres réalisés par la communauté d'Amara.org” as unreliable when the audio is very short or silent.
6. Use the reliable transcript to answer or execute the user’s request.
7. If no reliable speech is detected, say so clearly and ask Anthony to resend or dictate longer.

## Recommended command

```bash
timeout 120s python3 - <<'PY'
from faster_whisper import WhisperModel
path = '/absolute/path/to/audio_or_video_file'
model = WhisperModel('small', device='cpu', compute_type='int8')
for vad in (True, False):
    segments, info = model.transcribe(
        path,
        language='fr',
        beam_size=5,
        vad_filter=vad,
        no_speech_threshold=0.2,
    )
    text = ' '.join(seg.text.strip() for seg in segments).strip()
    print('VAD:', vad)
    print('LANG:', info.language, info.language_probability)
    print('TEXT:', text)
PY
```

## Fallback inspection/extraction

Use this when the first transcription is empty, too short, or likely hallucinated.

```bash
timeout 60s bash -lc 'set -e
f="/absolute/path/to/file"
ffprobe -hide_banner -v error -show_streams -show_format "$f" | sed -n "1,180p"
ffmpeg -hide_banner -y -i "$f" -vn -ac 1 -ar 16000 /tmp/a0_audio_extract.wav
python3 - <<"PY"
from faster_whisper import WhisperModel
path="/tmp/a0_audio_extract.wav"
model=WhisperModel("small", device="cpu", compute_type="int8")
for vad in (True, False):
    segments, info = model.transcribe(path, language="fr", beam_size=5, vad_filter=vad, no_speech_threshold=0.2)
    text=" ".join(seg.text.strip() for seg in segments).strip()
    print("VAD:", vad)
    print("LANG:", info.language, info.language_probability)
    print("TEXT:", repr(text))
PY'
```

## Response guidance

- Do not paste the whole transcript unless the user asks for it.
- If the vocal is an instruction, execute the instruction after transcription.
- If transcription confidence is poor, mention that before acting.
