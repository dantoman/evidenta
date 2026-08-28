"""Every commit says which session made it -- and the check is not the hook.

`ADR-002` and `ADR-010` split decisions in two: accounting ones need the owner's
co-signature, engineering ones belong to the implementation. Three sessions commit
as `dantoman`, author and committer, so without a trailer the boundary is
**unverifiable retroactively** -- a commit that closes an accounting decision looks
exactly like one that fixes a test.

**Why a test and not only the hook.** A hook lives in a local `core.hooksPath`
that every clone has to set for itself. That is the shape this project has already
been bitten by twice today: a guard wired correctly and never started, and a CI
pipeline connected for 43 commits without running once. A hook nobody installed
refuses nothing and says nothing about it. This runs in CI, where the setting
cannot be forgotten.

**What it proves and what it does not.** It proves the trailer is *present*. It
cannot prove it is *true*: a session that writes another session's name passes.
That limit is real and is the reason the mechanism is described as repairing
forgetfulness rather than establishing identity -- forgetfulness is what actually
happened on `ee1b599`, a commit no running session could account for.

The anchor is the commit that introduced the hook, found from the history itself
rather than written down as a hash. A hash would need updating and would rot; a
file that appears once does not.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
HOOK = ".githooks/commit-msg"

#: `Session: <name>`, on its own line. The vocabulary of names is deliberately
#: open: sessions are created and destroyed constantly and a closed list would be
#: wrong within the hour.
TRAILER = "Session:"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def in_a_repository() -> bool:
    try:
        git("rev-parse", "--git-dir")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


pytestmark = pytest.mark.skipif(
    not in_a_repository(), reason="the source tree is not a git checkout"
)


def anchor() -> str:
    """The commit that added the hook. Everything after it must carry a trailer.

    Read from the history rather than pinned: a pinned hash is a second place the
    rule lives, and the two drift the first time somebody rebases.
    """
    found = git("log", "--diff-filter=A", "--format=%H", "--", HOOK)
    return found.splitlines()[-1] if found else ""


def test_the_history_is_deep_enough_to_check() -> None:
    """The control, and it **fails** rather than skips.

    A shallow clone -- which is what `actions/checkout` produces by default -- can
    see neither the anchor nor the commits after it, so the check would pass over
    an empty list and report attribution nobody verified. That is the exact shape
    of the failures this file exists because of, so it is refused out loud.
    """
    assert not (REPO / ".git" / "shallow").exists(), (
        "the checkout is shallow, so commit history cannot be verified. CI must "
        "check out with `fetch-depth: 0`; a check that silently passes over a "
        "truncated history reports a guarantee nobody measured."
    )
    assert anchor(), (
        f"{HOOK} is not in the history yet. Until the commit that introduces it "
        f"exists, this test has nothing to anchor on -- it fails rather than "
        f"passes, so the rule cannot arrive without its check."
    )


def unattributed() -> list[str]:
    """Commits after the anchor whose message carries no `Session:` trailer."""
    start = anchor()
    if not start:
        return []
    listing = git("log", "--format=%H%x1f%s%x1f%b%x1e", f"{start}..HEAD")
    offenders = []
    for record in listing.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        sha, subject, body = [*record.split("\x1f"), "", ""][:3]
        if subject.startswith(("Merge", "fixup!", "squash!")):
            continue
        if not any(line.strip().startswith(TRAILER) for line in body.splitlines()):
            offenders.append(f"{sha[:8]} {subject}")
    return offenders


def test_every_commit_since_the_rule_names_its_session() -> None:
    missing = unattributed()
    assert missing == [], (
        "these commits carry no `Session:` trailer:\n  "
        + "\n  ".join(missing)
        + "\n\nThree sessions commit under one git identity, so without it nobody "
        "can say afterwards which commit closed an accounting decision and which "
        "fixed a test -- which ADR-002 makes a governance rule rather than a "
        "preference. Install the hook with `make hooks`."
    )


def test_the_hook_refuses_a_message_without_the_trailer(tmp_path: Path) -> None:
    """The probe. A guard nobody has seen refuse is a guard nobody knows the shape of.

    Run against the hook itself, with both a message that should pass and one that
    should not -- the second direction is the one that matters, and the one a
    hook that silently exits 0 would fail.
    """
    hook = REPO / HOOK
    assert hook.is_file() and hook.stat().st_mode & 0o111, f"{HOOK} is missing or not executable"

    without = tmp_path / "without.txt"
    without.write_text("A change nobody can attribute\n")
    refused = subprocess.run([str(hook), str(without)], capture_output=True, text=True)
    assert refused.returncode != 0, "the hook accepted a message with no trailer"
    assert "Session:" in refused.stderr

    with_trailer = tmp_path / "with.txt"
    with_trailer.write_text("A change somebody can attribute\n\nSession: evidenta-2a\n")
    accepted = subprocess.run([str(hook), str(with_trailer)], capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stderr
