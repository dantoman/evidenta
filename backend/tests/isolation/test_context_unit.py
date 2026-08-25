"""Context checks that need no database.

Split out deliberately. The check below is about a condition that is evaluated
before any connection exists, and forcing it into a database test made it need
``transaction=True`` -- which in turn made pytest truncate tables at teardown,
which the application role cannot do because it does not own them. Correctly so:
granting TRUNCATE to satisfy a test would widen a production role for a test's
convenience.

The check is a unit test. Treating it as one removes the whole chain.
"""

from __future__ import annotations

import uuid

import pytest

from evidenta.platform.rls.context import (
    OutsideTransactionError,
    TenantContext,
    _apply,
)


def test_setting_context_outside_a_transaction_is_refused() -> None:
    """SET LOCAL outside a transaction is not weaker -- it is inert.

    ``in_atomic_block`` is False on an unconnected connection, so the refusal
    happens before anything touches the database. That is the point: the failure
    is structural, not a database error.
    """
    context = TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), request_id="unit")
    with pytest.raises(OutsideTransactionError):
        _apply(context, "default")
