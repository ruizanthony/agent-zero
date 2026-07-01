---
name: rename-a0-project-folder
description: Renommer le dossier physique d’un projet Agent Zero dans /a0/usr/projects, mettre à jour .a0proj/project.json, réparer les références chatProject/chats, et vérifier que l’UI ou le plugin Filter Chat pointe vers le nouveau chemin. Utiliser quand l’utilisateur veut renommer un projet comme agent-zero-itself en a0-itself ou pilotage_laboratoires_pichot en direction.
---

# Rename Agent Zero Project Folder

Utiliser ce skill quand il faut renommer le dossier d’un projet Agent Zero sous `/a0/usr/projects` tout en gardant le projet cohérent dans l’UI, Filter Chat, les fichiers `.a0proj`, et les chats associés.

## Principes

- Ne pas renommer aveuglément le projet actif sans prévenir : le chemin courant peut être utilisé par le contexte en cours.
- Toujours sauvegarder ou au minimum vérifier l’état avant déplacement.
- Le nom de dossier, `.a0proj/project.json.name`, `.a0proj/project.json.title`, et les références éventuelles dans les chats peuvent être différents, mais il est préférable de les aligner si l’objectif est la clarté.
- Éviter les espaces dans les noms de dossiers. Préférer `kebab-case`, `snake_case`, ou un nom court comme `direction`.

## Procédure sûre

### 1. Identifier les projets et vérifier les collisions

```bash
cd /a0/usr/projects
ls -la
for p in */.a0proj/project.json; do echo "--- $p"; sed -n '1,80p' "$p"; done
```

Vérifier que la destination n’existe pas déjà :

```bash
test ! -e /a0/usr/projects/NOUVEAU_NOM && echo OK || echo "Destination existe déjà"
```

### 2. Inspecter les métadonnées du projet source

```bash
jq . /a0/usr/projects/ANCIEN_NOM/.a0proj/project.json
find /a0/usr/projects/ANCIEN_NOM/chatProject -maxdepth 1 -type f 2>/dev/null | wc -l
```

Si `jq` n’est pas disponible, utiliser `cat` ou `python -m json.tool`.

### 3. Sauvegarder les métadonnées avant modification

```bash
ts=$(date +%Y%m%d_%H%M%S)
cp -a /a0/usr/projects/ANCIEN_NOM/.a0proj/project.json "/a0/usr/projects/ANCIEN_NOM/.a0proj/project.json.bak-rename-$ts"
```

Pour une opération sensible, sauvegarder tout le dossier :

```bash
tar -C /a0/usr/projects -czf "/a0/usr/projects/ANCIEN_NOM.rename-backup-$ts.tgz" ANCIEN_NOM
```

### 4. Renommer le dossier

```bash
mv /a0/usr/projects/ANCIEN_NOM /a0/usr/projects/NOUVEAU_NOM
```

Exemples :

```bash
mv /a0/usr/projects/pilotage_laboratoires_pichot /a0/usr/projects/direction
mv /a0/usr/projects/agent-zero-itself /a0/usr/projects/a0-itself
```

Attention : éviter de renommer `agent-zero-itself` pendant qu’un chat travaille dans ce projet, sauf si l’utilisateur accepte de réouvrir le projet/chat après l’opération.

### 5. Mettre à jour `.a0proj/project.json`

Lire le fichier :

```bash
cat /a0/usr/projects/NOUVEAU_NOM/.a0proj/project.json
```

Puis mettre à jour au minimum les champs `name` et souvent `title` :

```bash
python - <<'PY'
import json
from pathlib import Path
path = Path('/a0/usr/projects/NOUVEAU_NOM/.a0proj/project.json')
data = json.loads(path.read_text())
data['name'] = 'NOUVEAU_NOM'
data['title'] = 'NOUVEAU_TITRE'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
PY
```

Exemples :

```bash
python - <<'PY'
import json
from pathlib import Path
for folder, title in [('direction', 'direction'), ('a0-itself', 'a0-itself')]:
    path = Path('/a0/usr/projects') / folder / '.a0proj' / 'project.json'
    data = json.loads(path.read_text())
    data['name'] = folder
    data['title'] = title
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
PY
```

### 6. Chercher et corriger les références à l’ancien nom

Chercher dans les métadonnées projet et chats :

```bash
old='ANCIEN_NOM'
grep -RIn --exclude-dir=node_modules --exclude-dir=.git --exclude='*.faiss' --exclude='*.pkl' "$old" \
  /a0/usr/projects/NOUVEAU_NOM/.a0proj \
  /a0/usr/projects/NOUVEAU_NOM/chatProject \
  /a0/usr/chats 2>/dev/null | head -100
```

Si les chats stockent un champ `project`, `project_name`, `project_path`, `telegram_bot_cfg.default_project`, ou similaire, corriger uniquement les fichiers JSON sûrs après inspection.

Important après un renommage déjà effectué : les chats peuvent être invisibles dans le nouveau projet même si le dossier projet est correct. Vérifier et réparer alors les champs structurés suivants, sans remplacer globalement l'historique conversationnel :

- `/a0/usr/chats/*/chat.json` : `data.project`
- `/a0/usr/chats/*/chat.json` : `data.telegram_bot_cfg.default_project`
- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `project_name`
- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `context_data.data.project`
- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `context_data.data.telegram_bot_cfg.default_project`

Approche prudente pour JSON :

```bash
python - <<'PY'
import json
from pathlib import Path
old = 'ANCIEN_NOM'
new = 'NOUVEAU_NOM'
roots = [Path('/a0/usr/projects/NOUVEAU_NOM/chatProject'), Path('/a0/usr/chats')]
keys = {'project', 'project_name', 'projectName', 'project_path', 'projectPath'}
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob('*.json'):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        changed = False
        def walk(x):
            global changed
            if isinstance(x, dict):
                for k, v in list(x.items()):
                    if k in keys and isinstance(v, str) and old in v:
                        x[k] = v.replace(old, new)
                        changed = True
                    else:
                        walk(v)
            elif isinstance(x, list):
                for item in x:
                    walk(item)
        walk(data)
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            print(path)
PY
```

Ne pas remplacer globalement dans tous les messages sans besoin : l’ancien nom peut faire partie de l’historique conversationnel.

### 7. Valider

```bash
python -m json.tool /a0/usr/projects/NOUVEAU_NOM/.a0proj/project.json >/dev/null && echo 'project.json OK'
test -d /a0/usr/projects/NOUVEAU_NOM/.a0proj && echo 'dossier projet OK'
test ! -e /a0/usr/projects/ANCIEN_NOM && echo 'ancien dossier absent OK'
```

Lister les projets vus par Agent Zero :

```bash
find /a0/usr/projects -maxdepth 2 -path '*/.a0proj/project.json' -print -exec sh -c 'echo --- $1; python -m json.tool "$1" | sed -n "1,40p"' sh {} \;
```

### 8. Rafraîchir l’UI / Filter Chat

- Recharger l’interface Agent Zero.
- Si le plugin Filter Chat cache la liste des projets, redémarrer Agent Zero ou le plugin selon son mécanisme.
- Vérifier que le nouveau projet apparaît et que les anciens noms ne sont plus proposés comme projets actifs.
- Si un chat était ouvert sur l’ancien projet, le rouvrir depuis le nouveau projet ou vérifier son `ctxid`.

## Piège UI avec le plugin `chat_project_filter`

Après avoir réparé les champs JSON, si les chats actifs existent dans `/a0/usr/chats/*/chat.json` avec `data.project = NOUVEAU_NOM` mais que la barre latérale n'en affiche qu'une partie, vérifier le filtre frontend du plugin :

- fichier : `/a0/usr/plugins/chat_project_filter/webui/project-filter-store.js`
- symptôme : le code filtre seulement avec `ctx.project?.name`, alors que certains contextes chargés depuis les chats actifs portent le projet dans `ctx.data.project`
- correction : centraliser la lecture du projet dans un helper du type `getChatProjectName(ctx)` qui lit au minimum :
  - `ctx.project.name`
  - `ctx.project.title`
  - `ctx.project_name`
  - `ctx.projectName`
  - `ctx.data.project`
  - `ctx.data.project_name`
  - `ctx.data.projectName`
  - `ctx.output_data.project.name`
  - `ctx.output_data.project.title`

Après modification, valider avec :

```bash
node --check /a0/usr/plugins/chat_project_filter/webui/project-filter-store.js
```

Attention : le frontend ne peut filtrer que les champs présents dans le snapshot envoyé à la sidebar. `AgentContext.output()` expose naturellement `output_data`, mais pas tout `data`. Donc, pour une correction durable qui survit aux mises à jour d'Agent Zero, ne pas patcher le cœur si possible : mettre à jour les JSON persistés pour aligner à la fois `data` et `output_data`.

Champs à corriger pour les chats actifs :

- `/a0/usr/chats/*/chat.json` : `data.project = NOUVEAU_NOM`
- `/a0/usr/chats/*/chat.json` : `data.telegram_bot_cfg.default_project = NOUVEAU_NOM` si présent
- `/a0/usr/chats/*/chat.json` : `output_data.project = {'name': NOUVEAU_NOM, 'title': NOUVEAU_NOM, 'color': '#adb5bd'}`
- `/a0/usr/chats/*/chat.json` : `output_data.project_name = NOUVEAU_NOM`

Champs à corriger pour les archives :

- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `project_name = NOUVEAU_NOM`
- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `context_data.data.project = NOUVEAU_NOM`
- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `context_data.data.telegram_bot_cfg.default_project = NOUVEAU_NOM` si présent
- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `context_data.output_data.project = {'name': NOUVEAU_NOM, 'title': NOUVEAU_NOM, 'color': '#adb5bd'}`
- `/a0/usr/projects/NOUVEAU_NOM/chatProject/*.json` : `context_data.output_data.project_name = NOUVEAU_NOM`

Valider ensuite avec :

```bash
python3 -m py_compile /a0/helpers/state_snapshot.py
node --check /a0/usr/plugins/chat_project_filter/webui/project-filter-store.js
```

Après modification des JSON persistés, redémarrer Agent Zero pour recharger les contextes actifs depuis `/a0/usr/chats`, puis faire un hard refresh PWA pour reprendre le JavaScript et le cache-buster du plugin.

## Commande groupée pour un renommage simple

Adapter `old`, `new`, et `title`, puis exécuter :

```bash
set -euo pipefail
old='ANCIEN_NOM'
new='NOUVEAU_NOM'
title='NOUVEAU_TITRE'
base='/a0/usr/projects'

test -d "$base/$old/.a0proj" || { echo "Projet source introuvable: $base/$old"; exit 1; }
test ! -e "$base/$new" || { echo "Destination existe déjà: $base/$new"; exit 1; }

ts=$(date +%Y%m%d_%H%M%S)
cp -a "$base/$old/.a0proj/project.json" "$base/$old/.a0proj/project.json.bak-rename-$ts"
mv "$base/$old" "$base/$new"

OLD="$old" NEW="$new" TITLE="$title" python - <<'PY'
import json, os
from pathlib import Path
base = Path('/a0/usr/projects')
new = os.environ['NEW']
title = os.environ['TITLE']
path = base / new / '.a0proj' / 'project.json'
data = json.loads(path.read_text())
data['name'] = new
data['title'] = title
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(path)
PY

python -m json.tool "$base/$new/.a0proj/project.json" >/dev/null
echo "Renommage terminé: $old -> $new"
```

## Exemple exact pour la demande d’Anthony

```bash
# pilotage_laboratoires_pichot -> direction
old='pilotage_laboratoires_pichot' new='direction' title='direction'

# agent-zero-itself -> a0-itself
old='agent-zero-itself' new='a0-itself' title='a0-itself'
```

Exécuter la commande groupée une fois par projet, pas les deux en même temps, puis valider l’UI après chaque renommage.
