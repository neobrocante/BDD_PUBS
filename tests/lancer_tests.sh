#!/usr/bin/env bash
# Lance tous les tests sur une base TEMPORAIRE (les vraies données ne sont jamais touchées).
#   bash tests/lancer_tests.sh            -> tests API + tests navigateur
#   bash tests/lancer_tests.sh api        -> tests API seulement (pas besoin de Playwright)
# Prérequis navigateur : Node + Playwright (npm i -g playwright ; Chromium installé).
set -uo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8799}
TMP=$(mktemp -d -t bddpubs_tests_XXXX)
export BDD_PUBS_DATA="$TMP/data" BDD_PUBS_SAUVEGARDES="$TMP/sauvegardes" TEST_TMP="$TMP" BASE="http://127.0.0.1:$PORT"
python3 tests/fixtures.py "$TMP"

python3 appli/app.py --no-browser --demo --port "$PORT" > "$TMP/serveur.log" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; wait $PID 2>/dev/null; echo "(base de test : $TMP)"' EXIT
for _ in $(seq 50); do curl -s -o /dev/null "$BASE/api/ping" && break; sleep 0.2; done

ECHECS=0
echo "=== Tests API"; python3 tests/test_api.py || ECHECS=$((ECHECS+1))
if [ "${1:-}" != "api" ]; then
  PW_MOD=$(node -e "try{console.log(require.resolve('playwright'))}catch(e){}" 2>/dev/null)
  [ -z "$PW_MOD" ] && PW_MOD="$(npm root -g 2>/dev/null)/playwright"
  export PW="$PW_MOD"
  for t in tests/ui/[!_]*.js; do
    echo "=== $t"; node "$t" || ECHECS=$((ECHECS+1))
  done
fi
if grep -qi traceback "$TMP/serveur.log"; then echo "!!! Erreurs côté serveur :"; grep -i -A8 traceback "$TMP/serveur.log" | head -40; ECHECS=$((ECHECS+1)); fi
[ "$ECHECS" -eq 0 ] && echo "TOUS LES TESTS PASSENT" || echo "ÉCHEC : $ECHECS série(s) en erreur"
exit "$ECHECS"
