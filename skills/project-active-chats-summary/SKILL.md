---
name: project-active-chats-summary
description: Résumer les chats actifs d’un projet Agent Zero, faire le tour des derniers points à traiter, dernières questions, décisions, sujets ouverts et pistes d’amélioration. Utiliser quand l’utilisateur demande un récapitulatif des chats actifs, une synthèse projet, un tour des projets, ou cite un projet comme MES.
---

# Project Active Chats Summary

Use this skill to summarize active or recent Agent Zero chats for a named project, such as MES, a0-itself, or any project under `/a0/usr/projects`.

## Goal

Return a concise operational summary covering:

- active or recent chats found for the project;
- latest points to treat;
- latest open questions;
- decisions or confirmations already made;
- risks, blockers, and follow-up actions;
- improvement ideas or next priorities.

## Workflow

1. Identify the project name from the user request.
2. Locate project exports under `/a0/usr/projects/<project>/chatProject` when available.
3. Cross-check live chat folders under `/a0/usr/chats` because recent Telegram or active contexts may not yet be exported into the project folder.
4. Inspect `chat.json`, `messages/*.txt`, and optionally `backups/*`.
5. Prefer recently modified chats, chats whose title/project/metadata match the project, and chats whose messages contain the project keywords.
6. Extract only useful operational facts. Do not include noise, secrets, or irrelevant tool logs.
7. Produce a mobile-friendly synthesis in French for Anthony unless asked otherwise.

## Useful commands

List candidate project folders:

```bash
find /a0/usr/projects -maxdepth 3 -type d -name chatProject -print | sort
```

List recent chat folders:

```bash
find /a0/usr/chats -maxdepth 1 -mindepth 1 -type d -printf '%T@ %TY-%Tm-%Td %TH:%TM %p\n' | sort -nr | head -80
```

Score candidates by project keywords:

```bash
timeout 60s python3 - <<'PY'
import json, os, re, time
from pathlib import Path

keywords = ['MES']  # replace with project keywords, lowercase matching is applied
roots = [Path('/a0/usr/chats')]
project_exports = Path('/a0/usr/projects')

terms = [k.lower() for k in keywords]
rows = []

for root in roots:
    if not root.exists():
        continue
    for chat in root.iterdir():
        if not chat.is_dir():
            continue
        score = 0
        snippets = []
        meta = {}
        cj = chat / 'chat.json'
        if cj.exists():
            try:
                meta = json.loads(cj.read_text(errors='ignore'))
            except Exception:
                meta = {}
            hay = json.dumps(meta, ensure_ascii=False).lower()
            score += sum(hay.count(t) * 3 for t in terms)
        for msg in sorted((chat / 'messages').glob('*.txt'))[-80:]:
            try:
                txt = msg.read_text(errors='ignore')
            except Exception:
                continue
            low = txt.lower()
            hits = sum(low.count(t) for t in terms)
            if hits:
                score += hits
                snippets.append(re.sub(r'\s+', ' ', txt[:500])[:500])
        if score:
            mtime = max((p.stat().st_mtime for p in chat.rglob('*') if p.is_file()), default=chat.stat().st_mtime)
            rows.append((score, mtime, chat.name, meta.get('name') or meta.get('title') or '', snippets[:3]))

for score, mtime, ctxid, title, snippets in sorted(rows, key=lambda r: (r[0], r[1]), reverse=True)[:30]:
    print(f'\n=== score={score} date={time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))} ctxid={ctxid} title={title}')
    for s in snippets:
        print(' -', s)
PY
```

## Summary structure

Keep the final answer concise and readable by voice/TTS:

- Start with a one-sentence global status.
- Then list the main active subjects.
- Then list priorities or next actions.
- Mention uncertainty when a chat could not be confidently linked to the project.

For Telegram, avoid Markdown tables. Prefer short paragraphs and simple bullets.

## Quality checks

- Verify that every included topic is backed by a found chat/export/message.
- Do not invent active chats from memory alone.
- If the search coverage is partial, say what was inspected and what may be missing.
- If the user asks for a specific project and no chats are found, report that and propose broader keywords.
