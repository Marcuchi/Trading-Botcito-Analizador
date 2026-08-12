#!/usr/bin/env bash
# Persiste last_state.json (deteccion de transiciones) entre ejecuciones del
# workflow, porque cada corrida de GitHub Actions arranca desde cero.
# Ademas escribe un heartbeat cada ~25 dias para que GitHub no desactive el
# schedule por inactividad (limite: 60 dias sin commits).
set -euo pipefail
cd "$(dirname "$0")/.."

git config user.email "ml-rsi-bot@users.noreply.github.com"
git config user.name "ml-rsi-bot"

git add last_state.json
if ! git diff --cached --quiet; then
    git commit -m "chore: actualizar estado del bot" -q
    echo "[PERSIST] Estado actualizado."
fi

HB=".github/state/heartbeat"
mkdir -p "$(dirname "$HB")"
LAST_HB="$(git log -1 --format=%ct -- "$HB" 2>/dev/null || echo 0)"
NOW="$(date -u +%s)"
if [ $(( NOW - LAST_HB )) -gt 2160000 ]; then
    echo "$NOW" > "$HB"
    git add "$HB"
    git commit -m "chore: heartbeat del bot" -q
    echo "[PERSIST] Heartbeat escrito."
fi

git push -q
echo "[PERSIST] Repositorio sincronizado."
