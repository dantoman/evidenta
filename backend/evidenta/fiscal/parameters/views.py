"""The VAT regime vocabulary over HTTP -- the one thing a document screen needs
from `fiscal` before it can offer a line.

A screen that listed the regimes itself would be a second copy of a nomenclature
the server holds as data (`R15`), and it would go stale the day the table gains
a row. So the screen asks, for the date of the document, and shows what comes
back.

``on`` is required. There is no "today": which regimes exist and what each rate
is are questions about the date of the economic fact (ADR-044), and a screen
that asked without a date would be asking about the wrong day for every
back-dated document.

**A rate that cannot be resolved is reported, not hidden.** While ``vat.standard``
is `draft` (`OD-22`) the row for the standard regime comes back with ``rate:
null`` and the fiscal code that explains it. The screen can then say *why* a
line cannot be priced, which is the whole difference between "the product does
not do VAT" and "the rate has not been activated from a citable act".
"""

from __future__ import annotations

from datetime import date
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.fiscal.parameters.services.resolution import FiscalResolutionError
from evidenta.fiscal.parameters.services.vat import regime_rate, vat_regimes
from evidenta.platform.api.errors import ApiError


class DateRequiredError(ApiError):
    code = "fiscal.date_required"
    status = 400


class VocabularyUnavailableError(ApiError):
    """The regime table itself cannot be resolved for the date."""

    code = "fiscal.vat_regimes_unavailable"
    status = 409


class VatRegimesView(APIView):
    def get(self, request: Request) -> Response:
        on = _on(request)
        try:
            codes = vat_regimes(on)
        except FiscalResolutionError as exc:
            raise VocabularyUnavailableError(
                f"the VAT regime vocabulary cannot be resolved for {on}: {exc.code}",
                fiscal_code=exc.code,
            ) from exc

        rows: list[dict[str, Any]] = []
        for code in codes:
            try:
                resolved = regime_rate(code, on)
            except FiscalResolutionError as exc:
                rows.append({"code": code, "rate_key": None, "rate": None, "unavailable": exc.code})
            else:
                rows.append(
                    {
                        "code": code,
                        "rate_key": resolved.rate_key,
                        "rate": str(resolved.rate),
                        "unavailable": None,
                    }
                )
        return Response({"on": str(on), "regimes": rows})


def _on(request: Request) -> date:
    raw = request.query_params.get("on")
    if not raw:
        raise DateRequiredError("`on` is required: the regimes are those in force on a date")
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise DateRequiredError(f"`on` is {raw!r}, not a date") from exc
