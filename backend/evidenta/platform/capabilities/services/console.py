"""Capability activations across every space, for the console -- ADR-076 §4.3, R25.

Through `rls.console_capabilities()` (0076): staff-gated, refused under a tenant
context, and returning the activation as a fact about the platform -- which
space, which company, which capability, from when, in what initialisation state.
Read only: activating a capability is the client's act inside their own space,
and the console lists it rather than doing it for them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from django.db import connection


@dataclass(frozen=True, slots=True)
class ActivationRow:
    id: uuid.UUID
    subdomain: str
    legal_name: str
    company_id: uuid.UUID | None
    company_legal_name: str | None
    company_idno: str | None
    capability_key: str
    effective_from: date
    effective_to: date | None
    initialisation_state: str
    source: str
    activated_at: datetime


def list_activations() -> list[ActivationRow]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, subdomain, legal_name, company_id, company_legal_name, company_idno, "
            "capability_key, effective_from, effective_to, initialisation_state, source, "
            "activated_at FROM rls.console_capabilities()"
        )
        rows = cursor.fetchall()
    return [ActivationRow(*row) for row in rows]
