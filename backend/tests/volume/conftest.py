"""Borrowing the isolation harness rather than growing a second one.

``world`` and ``seed`` live in ``tests/isolation/conftest.py`` and are scoped to
that directory. The volume measurements need exactly the same starting position --
two tenants, two users, a membership each, seeded through the privileged path --
and re-deriving it here would mean two harnesses drifting apart, with the
measurements eventually running against a world that no longer matches what the
isolation suite proves.

The alternative is moving those fixtures up to ``tests/conftest.py``. That is
probably right eventually; it is also a change to a file every suite depends on,
which is not worth making as a side effect of adding a benchmark.
"""

from __future__ import annotations

from tests.isolation.conftest import seed, world  # noqa: F401
