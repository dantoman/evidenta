"""`/api/v1/platform/coa-templates/` -- the versions of the chart of accounts, for the
console (ADR-076 §4.3, `P-10`).

Read only. `coa_template` is global and readable by the application role under
any context, so this is the ORM. Loading a version is `P-10` from a CSV the
operator holds (`load_coa_template`), which no screen can do; publishing is part
of the same load. What the console adds is the list: which versions exist, from
when, under which act, how many accounts, and how many companies instantiated
each -- the last a count, not a company.

Here in `accounting.coa` rather than in `platform`, because the dependency graph
runs one way: the console's reference pages are mounted by the module that owns
the data.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.coa.models import CoaTemplate
from evidenta.platform.api.permissions import IsPlatformStaff


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


class CoaTemplatesView(APIView):
    permission_classes = (IsPlatformStaff,)

    def get(self, request: Request) -> Response:
        rows = (
            CoaTemplate.objects.select_related("act")
            .annotate(account_count=Count("coatemplateaccount", distinct=True))
            .order_by("code", "valid_from")
        )
        return Response(
            {
                "templates": [
                    {
                        "id": str(row.id),
                        "code": row.code,
                        "version": row.version,
                        "status": row.status,
                        "valid_from": _iso(row.valid_from),
                        "valid_to": _iso(row.valid_to),
                        "published_at": _iso(row.published_at),
                        "source_act": row.source_act,
                        "source_reference": row.source_reference,
                        "act": (
                            {
                                "act_type": row.act.act_type,
                                "act_number": row.act.act_number,
                                "act_date": _iso(row.act.act_date),
                                "title": row.act.title,
                            }
                            if row.act is not None
                            else None
                        ),
                        "account_count": int(row.account_count),
                    }
                    for row in rows
                ]
            }
        )
