#!/usr/bin/env bash
# Does the repository build from what is COMMITTED, not from what is on disk?
#
# The failure this exists for succeeds and says nothing: a commit that omits a
# new source file passes `tsc`, `eslint`, `vitest` and `vite build` -- all four
# read the working tree, where the file is present. Only a fresh clone fails, and
# by then it is somebody else's afternoon. Measured on this repository: the
# partner API client was left out of a commit and every local check stayed green,
# because `git commit -- <paths>` does not pick up an untracked file.
#
# So this one reads `git archive HEAD`. It is deliberately the *same* checker on
# a different tree -- the point is not a stricter check, it is a check that
# cannot see the file the commit forgot.
#
# The backend has the same exposure and one twist of its own: `manage.py check`
# does **not** load migrations, so a forgotten SQL file passes it. That is why
# `makemigrations --check` runs too -- it builds the migration graph, which is
# where `run_sql_file` verifies the file exists and matches its checksum. Both
# halves measured on this tree: removing `partners/services/directory.py` fails
# `check` with ModuleNotFoundError, and removing an applied `.up.sql` fails
# `makemigrations` with SqlFileMissingError.
#
# `node_modules` and `.venv` are linked rather than installed. Dependency
# completeness is the lockfile's question -- `npm ci`'s and `uv sync`'s; this
# asks only whether the *source* is complete.
#
# `--self-test` proves the check can fail. A guard nobody has seen fail is a
# guard nobody knows is wired: it deletes one file the tree cannot compile
# without, and expects a non-zero exit. It deletes a file rather than the one a
# real defect involved, because what is being demonstrated is the mechanism.
set -euo pipefail

self_test=false
[ "${1:-}" = "--self-test" ] && self_test=true

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

git -C "$root" archive HEAD | tar -x -C "$work"

if [ ! -d "$root/frontend/node_modules" ]; then
    echo "check-committed: frontend/node_modules lipsește — rulați 'make web-install'" >&2
    exit 1
fi
ln -s "$root/frontend/node_modules" "$work/frontend/node_modules"

if [ ! -d "$root/backend/.venv" ]; then
    echo "check-committed: backend/.venv lipsește — rulați 'make sync'" >&2
    exit 1
fi
ln -s "$root/backend/.venv" "$work/backend/.venv"

if $self_test; then
    rm "$work/frontend/src/shared/api/client.ts"
    echo "check-committed --self-test: am scos un fișier din copie; typecheck-ul TREBUIE să cadă"
    if (cd "$work/frontend" && npx tsc -b --noEmit >/dev/null 2>&1); then
        echo "check-committed --self-test: NU a căzut. Verificarea nu verifică nimic." >&2
        exit 1
    fi
    echo "check-committed --self-test: frontendul a căzut, cum trebuie."

    # Fiecare jumătate își dovedește separat că poate cădea. O probă care
    # acoperă doar frontendul lasă backendul indistinct de un script care
    # tipărește o linie liniștitoare.
    rm "$work/backend/evidenta/masterdata/partners/services/directory.py"
    if (cd "$work/backend" && ./.venv/bin/python manage.py check >/dev/null 2>&1); then
        echo "check-committed --self-test: backendul NU a căzut la un modul lipsă." >&2
        exit 1
    fi
    echo "check-committed --self-test: backendul a căzut la modulul lipsă, cum trebuie."

    rm "$work"/infra/migrations/*.up.sql
    if (cd "$work/backend" && ./.venv/bin/python manage.py makemigrations --check --dry-run \
            >/dev/null 2>&1); then
        echo "check-committed --self-test: migrațiile NU au căzut la SQL lipsă." >&2
        exit 1
    fi
    echo "check-committed --self-test: migrațiile au căzut la SQL lipsă, cum trebuie."
    exit 0
fi

echo "check-committed: peste arborele comis ($(git -C "$root" rev-parse --short HEAD))"

(cd "$work/frontend" && npx tsc -b --noEmit)
echo "check-committed: frontendul comis se compilează."

# Ieșirea se strânge într-un fișier și se tipărește **doar la eșec**. Nu e
# cosmetică: `makemigrations` încearcă să verifice istoricul migrațiilor pe bază,
# copia n-are `.env`, iar avertismentul conține „FATAL: password authentication
# failed". Un gardian care tipărește `FATAL` și trece îi învață pe oameni să-l
# citească pe diagonală, iar următorul `FATAL` adevărat va arăta la fel.
#
# Baza chiar nu e necesară pentru ce se cere aici, și nu e presupunere: proba din
# `--self-test` scoate un `.up.sql` și `makemigrations` cade cu
# `SqlFileMissingError` fără nicio bază la dispoziție.
#
# Fără conductă: codul de ieșire citit printr-o conductă este al ultimei comenzi
# din ea, deci un verificator căzut raportat prin `head` iese cu zero. S-a
# întâmplat exact așa în această sesiune, de două ori.
run_quietly() {
    local label="$1"
    shift
    if ! (cd "$work/backend" && "$@") >"$work/check.log" 2>&1; then
        cat "$work/check.log" >&2
        echo "check-committed: $label — a eșuat." >&2
        exit 1
    fi
    echo "check-committed: $label"
}

run_quietly "backendul comis se încarcă." ./.venv/bin/python manage.py check
run_quietly "graful de migrații comis e complet." \
    ./.venv/bin/python manage.py makemigrations --check --dry-run
