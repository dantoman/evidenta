"""What a person may change about themselves.

**One field today, and the list is short for reasons, not for lack of time.**

``full_name`` is a label: it appears on screen beside the reader's own session and
nowhere else. Nothing depends on it, so correcting it is a correction and nothing
more.

The rest of the row is **not** profile editing, and each has its own path or its
own reason:

* ``email`` is the credential the account authenticates with. Changing it without
  proving control of the new address is either a lockout or a takeover, so it is a
  verification flow -- an address is proposed, confirmed, and only then adopted.
* the password has its own path, which needs the current one.
* ``mfa_enabled`` is enrolment state, not a preference: ADR-021 makes the second
  factor mandatory, and a field that could clear it would be an opt-out written as
  a checkbox.
* ``locale`` has no consumer yet: the interface is Romanian and ADR-014 defers
  Russian as a product decision. A control that changes nothing is worse than a
  missing one.
* ``is_active`` cuts access to every tenant. It is not the subject's to set.

The policy on ``user`` is self-row (`id = app.current_user_id()`), so this cannot
touch anybody else's row even if it tried -- the guard is the database, and the
signature simply has nowhere to put another id.
"""

from __future__ import annotations

import uuid
from typing import Any

from evidenta.platform.api.errors import ApiError
from evidenta.platform.identity.models import User

#: Long enough for any real name, short enough to refuse a pasted document.
NAME_LIMIT = 200


class ProfileMalformedError(ApiError):
    """The change cannot be applied as sent."""

    code = "identity.profile_malformed"
    status = 422


def update_profile(user_id: uuid.UUID, *, full_name: str) -> dict[str, Any]:
    """Correct the reader's own display name."""
    name = (full_name or "").strip()
    if not name:
        raise ProfileMalformedError(
            "a name cannot be blank: it is what the application calls you on every "
            "screen, and an empty one leaves the address in its place"
        )
    if len(name) > NAME_LIMIT:
        raise ProfileMalformedError(f"a name is at most {NAME_LIMIT} characters")

    updated = User.objects.filter(id=user_id).update(full_name=name)
    if not updated:  # pragma: no cover -- the session cannot outlive its user
        raise ProfileMalformedError("the signed-in user is not visible in this context")

    return {"user_id": str(user_id), "full_name": name}
