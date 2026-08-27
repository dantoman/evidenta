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
# `node_modules` is linked rather than installed. Dependency completeness is the
# lockfile's question and `npm ci`'s; this asks only whether the source is
# complete.
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

if $self_test; then
    rm "$work/frontend/src/shared/api/client.ts"
    echo "check-committed --self-test: am scos un fișier din copie; typecheck-ul TREBUIE să cadă"
    if (cd "$work/frontend" && npx tsc -b --noEmit >/dev/null 2>&1); then
        echo "check-committed --self-test: NU a căzut. Verificarea nu verifică nimic." >&2
        exit 1
    fi
    echo "check-committed --self-test: a căzut, cum trebuie."
    exit 0
fi

echo "check-committed: typecheck peste arborele comis ($(git -C "$root" rev-parse --short HEAD))"
cd "$work/frontend" && npx tsc -b --noEmit
echo "check-committed: arborele comis se compilează."
