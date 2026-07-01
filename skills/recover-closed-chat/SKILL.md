---
name: recover-closed-chat
description: Retrouver et rouvrir un chat Agent Zero fermé par erreur, récemment fermé, archivé, disparu de l’UI, ou contenant des mots-clés donnés; utiliser pour “retrouve/réouvre mon ancien chat”, “chat fermé”, “chat que je viens de fermer”, “conversation disparue”, “marge min liv” ou recherche dans /a0/usr/chats.
---

# Recover Closed Chat

Use this skill to find a closed, hidden, archived, or accidentally lost Agent Zero chat and reopen it in the WebUI.

## Goal

Identify the correct chat context in `/a0/usr/chats`, then open it in the active Agent Zero browser tab.

## Workflow

1. Clarify only if needed:
   - If the user says it was closed recently, prioritize modification time over keyword score.
   - If the user gives keywords, use them to score candidates.
   - If the user gives an approximate time, filter around that window.

2. Search candidates in `/a0/usr/chats`:
   - Inspect `chat.json`, `messages/*.txt`, and `backups/*`.
   - Score by exact keyword matches and recent file modification time.
   - For “just closed”, list chats modified in the last few minutes first.

3. Identify the best context id:
   - The context id is the folder name under `/a0/usr/chats/<ctxid>`.
   - Confirm the candidate by checking message snippets, chat title/name, or recent user messages.
   - If several candidates are close, choose the most recent and verify with `browser.content` after opening.

4. Reopen in the WebUI:
   - Prefer the existing Agent Zero browser tab if one is open.
   - Navigate to `http://127.0.0.1:5000/?ctxid=<ctxid>`.
   - If the URL normalizes back to `/`, inspect `browser.content`; the frontend may consume the context id and clean the URL.

5. If the WebUI shows `/login`:
   - Check `AUTH_LOGIN` and whether auth is active without exposing secrets.
   - Never print `AUTH_PASSWORD`.
   - Use a temporary local autologin page only if necessary, reading credentials from environment variables inside the container and auto-submitting the form.
   - After login, navigate again to `/?ctxid=<ctxid>`.

6. Verify success:
   - Call `browser.content` and confirm the expected messages/keywords are visible.
   - Respond to the user with the found topic, context id, and confirmation that it is open.

## Useful Commands

Find recently modified chats:

```bash
cd /a0/usr/chats
find . -maxdepth 3 -type f -mmin -10 -printf '%T@ %p\n' | sort -nr | head -80
```

Score chats by keywords:

```bash
cd /a0
python3 - <<'PY'
import os, json, re, glob, time
base='/a0/usr/chats'
keywords=['marge min liv']
patterns=[re.compile(re.escape(k), re.I) for k in keywords]
rows=[]
for d in glob.glob(base+'/*'):
    if not os.path.isdir(d):
        continue
    cid=os.path.basename(d)
    files=glob.glob(d+'/chat.json')+glob.glob(d+'/messages/*.txt')+glob.glob(d+'/backups/*')
    text=''
    mt=0
    for f in files:
        try:
            mt=max(mt, os.path.getmtime(f))
            text += '\n' + open(f,'r',encoding='utf-8',errors='ignore').read()
        except Exception:
            pass
    score=sum(len(p.findall(text)) for p in patterns)
    if score:
        title=''
        try:
            meta=json.load(open(d+'/chat.json','r',encoding='utf-8'))
            title=meta.get('name') or meta.get('title') or meta.get('heading') or ''
        except Exception:
            pass
        rows.append((score, mt, cid, title))
for score, mt, cid, title in sorted(rows, key=lambda x:(x[0],x[1]), reverse=True)[:30]:
    print(score, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)), cid, title)
PY
```

Temporary autologin pattern when required:

```bash
cd /tmp
python3 - <<'PY'
import os, html
from http.server import BaseHTTPRequestHandler, HTTPServer
PORT=50137
USER=os.environ.get('AUTH_LOGIN','')
PWD=os.environ.get('AUTH_PASSWORD','')
TARGET='http://127.0.0.1:5000/?ctxid=CTXID_HERE'
class H(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        body=f'''<!doctype html><form id="f" method="POST" action="http://127.0.0.1:5000/login">
<input name="username" value="{html.escape(USER)}">
<input name="password" type="password" value="{html.escape(PWD)}">
<input name="next" value="{html.escape(TARGET)}">
</form><script>document.getElementById('f').submit();setTimeout(()=>location.href='{html.escape(TARGET)}',1500)</script>'''.encode()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
HTTPServer(('127.0.0.1', PORT), H).serve_forever()
PY
```

Open with browser:

```text
browser navigate/open: http://127.0.0.1:5000/?ctxid=<ctxid>
```

## Safety and Cleanup

- Do not expose passwords, tokens, or auth environment values.
- Kill or reset the temporary autologin terminal session after use if it is still running.
- Do not modify chat files unless explicitly asked.
- Do not archive, delete, or rename chats during recovery.
