---
name: pichot-agent-zero-rebase
description: Rebase and maintain Anthony/Pichot local Agent Zero customizations on top of upstream origin/main, with safe review, thematic commits, exclusions, and targeted verification.
triggers:
  - "rebase pichot agent zero"
  - "mettre à jour la branche pichot"
  - "review local Agent Zero modifications"
  - "rebase upstream agent zero pichot"
---

# Pichot Agent Zero Rebase

Use this skill when Anthony wants to review, preserve, rebase, or refresh the local Pichot Agent Zero customizations against upstream `origin/main`.

## Safety Rules

- Work in `/a0` unless the user explicitly names another checkout.
- Never push, delete branches, or discard local changes without explicit confirmation.
- Before any branch/rebase operation, create a backup branch from the current `HEAD`.
- Keep untracked runtime noise out of commits: `.bak*`, `venv/`, temporary patch files, `space-agent/`, and accidental shell-output files.
- Prefer thematic commits that can be rebased or dropped independently.
- Use the framework runtime `/opt/venv-a0/bin/python` for Agent Zero tests when available.

## Standard Workflow

1. Inspect current state.

   ```bash
   cd /a0
   git fetch --all --prune
   git status --short --branch
   git remote -v
   git branch -vv --all --no-color | sed -n '1,120p'
   git diff --stat
   git diff --name-status
   ```

2. Compare against upstream.

   ```bash
   BASE=$(git merge-base HEAD origin/main)
   git log --oneline --decorate "$BASE..origin/main"
   git log --oneline --decorate origin/main..HEAD
   git diff --stat origin/main
   git diff --check || true
   ```

   Check whether upstream has touched the same files:

   ```bash
   git diff --name-only > /tmp/a0-pichot-files.txt
   while IFS= read -r f; do
     echo "--- $f"
     git log --oneline --decorate "$BASE..origin/main" -- "$f"
   done < /tmp/a0-pichot-files.txt
   ```

3. Classify local work.

   Typical Pichot groups:

   - restart/runtime stability;
   - editable message queue UI/backend;
   - manual chat rename and safer auto titles;
   - scheduler `uvloop`/`nest_asyncio` guards;
   - Codex/OAuth Responses normalization;
   - Kokoro French voice defaults;
   - Telegram voice/progress bridge;
   - local operational skills.

   Mark uncertain files as review-only instead of committing them immediately.

4. Create a safety branch.

   ```bash
   backup="backup/pre-pichot-main-$(date +%Y%m%d_%H%M%S)"
   git branch "$backup"
   echo "backup_branch=$backup"
   ```

5. Prepare local excludes.

   Add local-only patterns to `.git/info/exclude`, not `.gitignore`, unless the user asks for a repository-wide ignore rule.

   Common excludes:

   ```text
   *.bak
   *.bak-*
   *.bak.*
   *.bak_*
   venv/
   /0
   /3
   /c.stock_corrige
   /tatus tracked ==n'
   /patches/pr_fd_leak_*
   /patches/patch_stream_options_usage.py
   /patches/0001-fix-code_execution-close-PTY-file-descriptors.patch
   /patches/fix-ui-restart-hangs.patch
   /space-agent/
   ```

6. Create or update the integration branch.

   ```bash
   git switch -c pichot/main 2>/dev/null || git switch pichot/main
   ```

   If starting from an existing dirty branch, switch only after confirming the dirty worktree will be carried safely.

7. Commit thematically.

   Use `git reset -q` between groups, then `git add` only the files for that group.

   Recommended commit subjects:

   ```text
   pichot: stabilize restart and runtime init
   pichot: add editable message queue UI
   pichot: improve chat rename controls
   pichot: guard scheduler uvloop patching
   pichot: normalize Codex Responses input
   pichot: set Kokoro French voice defaults
   pichot: bridge Telegram voice and progress updates
   pichot: add local operational skills
   ```

   Before each commit:

   ```bash
   git diff --cached --stat
   git diff --cached --check
   git commit -m "pichot: concise subject"
   ```

8. Rebase on upstream.

   Rebase the Pichot stack onto current `origin/main`. Use the known old base or merge-base of the Pichot stack, not an arbitrary commit.

   ```bash
   git rebase --onto origin/main OLD_BASE pichot/main
   git status --short --branch
   git rev-list --left-right --count origin/main...HEAD
   ```

   If conflicts happen, resolve by feature group, run syntax checks on touched files, then `git rebase --continue`.

9. Verify.

   Use bounded checks. Prefer targeted tests over full-suite runs unless the user asks for exhaustive verification.

   ```bash
   PY=/opt/venv-a0/bin/python
   [ -x "$PY" ] || PY=python3

   $PY -m py_compile \
     api/restart.py api/chat_rename.py \
     extensions/python/monologue_start/_60_rename_chat.py \
     helpers/message_queue.py helpers/process.py helpers/runtime.py helpers/task_scheduler.py \
     plugins/_oauth/helpers/codex.py plugins/_telegram_integration/helpers/handler.py run_ui.py

   node --check webui/components/chat/input/input-store.js
   node --check webui/components/chat/message-queue/message-queue-store.js
   node --check webui/components/sidebar/chats/chats-store.js
   node --check plugins/_kokoro_tts/webui/kokoro-tts-store.js

   $PY -m pytest -q \
     tests/test_oauth_codex.py \
     tests/test_task_scheduler_timezone.py \
     tests/test_task_scheduler_uvloop_import.py \
     tests/test_message_queue.py \
     tests/test_run_ui_background_init.py \
     tests/test_ui_restart.py

   git diff --check
   ```

10. Report clearly.

    Include:

    - branch name;
    - backup branch name;
    - number of commits ahead/behind `origin/main`;
    - commit subjects;
    - tests/checks run and results;
    - files intentionally excluded or left for review;
    - whether anything was pushed.

## Push Policy

Only push after explicit user confirmation:

```bash
git push -u fork pichot/main
```

If the user wants upstream contribution, create smaller PR branches from the thematic commits instead of proposing the whole `pichot/main` customization stack.
