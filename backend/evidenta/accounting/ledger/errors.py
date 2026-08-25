"""Refusals from the ledger, each with a stable code -- C10.

Every one of them is a refusal the posting engine will branch on, so the code is
the contract and the message is for the human reading the log.

They are few on purpose. The ledger has almost no opinions: it refuses what R10,
R12 and R14 forbid and accepts everything else, because deciding *what* to post
is the engine's question and deciding *whether it balances* is the database's.
"""

from __future__ import annotations

from evidenta.platform.api.errors import ApiError


class EntryNotFoundError(ApiError):
    """No such entry, or not visible. Deliberately the same answer (IZ-04)."""

    code = "ledger.entry_not_found"
    status = 404


class NotPostedError(ApiError):
    """Only a posted entry is reversed.

    A draft is not a mistake in the books -- nothing was recorded yet, so there
    is nothing to cancel. Reversing one would put two entries in the ledger where
    the correct outcome is none.
    """

    code = "ledger.entry_not_posted"
    status = 409


class AlreadyReversedError(ApiError):
    """One active reversal per entry.

    A second is refused because it is almost always a process error -- the same
    correction requested twice -- and the cost of being wrong is a ledger that
    double-cancels an entry, which no report will show as odd.
    """

    code = "ledger.entry_already_reversed"
    status = 409
