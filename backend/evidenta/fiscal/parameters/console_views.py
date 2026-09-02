"""Fiscal parameters over HTTP, for the platform's console -- ADR-076 §4.3.

The owner's question, verbatim: *"I expect this part to be set in the settings of
the system. If VAT gets changed?"* Until now the answer was a TOML file and two
shell commands. This is the screen's server side: list what is loaded, write a
new dated version of a parameter, and activate a draft as the signed-in approver.

**Where it runs, and why that is a decision (ADR-091).** These views write the
global reference tables from the request-serving process, on the reference-data
connection, inside `privileged_run` (`P-4`) -- the same door the commands use,
with the same log row, and with the caller stamped as `actor_user_id`. What they
check first is *who*: a live `operator` in `platform_staff`, through the
permission class, inside the request's own context. There is no tenant in that
context -- the console host has none -- so nothing here can mix a client's data
into a write that applies to everyone.

**What is not here.** Logic versions (`[[logic]]` in the files) stay with the
loader: a version names code that has to be deployed, which no screen can do.
Company-scoped parameters are not offered either: the console administers the
platform, not a client's status (ADR-076 §2).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    MarginBasis,
    SourceConfidence,
    ValueType,
)
from evidenta.fiscal.parameters.services.authoring import (
    ActiveNotEditedError,
    AuthoringError,
    MarginMissingError,
    NotADraftError,
    ParameterDraft,
    ParameterInvalidError,
    ParameterNotFoundError,
    activate_parameter,
    write_parameter,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.permissions import IsPlatformOperator, IsPlatformStaff
from evidenta.platform.audit.services.privileged import (
    REFDATA_ALIAS,
    PrivilegedPath,
    privileged_run,
)
from evidenta.platform.legislation.services.registry import Act, Publication


class FiscalParameterInvalidError(ApiError):
    code = ParameterInvalidError.code
    status = ParameterInvalidError.status


class FiscalActiveNotEditedError(ApiError):
    code = ActiveNotEditedError.code
    status = ActiveNotEditedError.status


class FiscalParameterNotFoundError(ApiError):
    code = ParameterNotFoundError.code
    status = ParameterNotFoundError.status


class FiscalMarginMissingError(ApiError):
    code = MarginMissingError.code
    status = MarginMissingError.status


class FiscalNotADraftError(ApiError):
    code = NotADraftError.code
    status = NotADraftError.status


#: The service's refusals, each given its HTTP shape. Enumerated rather than
#: derived so that a new refusal in the service is a compile-time question here,
#: not a 500 at the first click.
_API_ERRORS: dict[type[AuthoringError], type[ApiError]] = {
    ParameterInvalidError: FiscalParameterInvalidError,
    ActiveNotEditedError: FiscalActiveNotEditedError,
    ParameterNotFoundError: FiscalParameterNotFoundError,
    MarginMissingError: FiscalMarginMissingError,
    NotADraftError: FiscalNotADraftError,
}


def _raise_api(error: AuthoringError) -> ApiError:
    kind = _API_ERRORS.get(type(error), FiscalParameterInvalidError)
    return kind(str(error))


class _ClosedSerializer(serializers.Serializer[Any]):
    """A serializer that refuses fields it does not declare.

    DRF drops unknown keys silently, and on a write that is the wrong default:
    a client that sends `status: active` believing it did something must be
    told it did nothing. Same rule as the partner editor.
    """

    def to_internal_value(self, data: Any) -> Any:
        # On the incoming mapping rather than on `initial_data`, which only the
        # root serializer has: the act and its publication are nested, and a
        # stray key inside them deserves the same refusal.
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {name: "câmp necunoscut" for name in sorted(unknown)}
                )
        return super().to_internal_value(data)


class PublicationInput(_ClosedSerializer):
    gazette_year = serializers.IntegerField()
    gazette_number = serializers.CharField()
    article = serializers.CharField()
    published_at = serializers.DateField(required=False, allow_null=True)


class ActInput(_ClosedSerializer):
    """An act cited in full: type, number, date, title, and when it took effect."""

    act_type = serializers.CharField()
    act_number = serializers.CharField()
    act_date = serializers.DateField()
    title = serializers.CharField()
    effective_from = serializers.DateField(required=False, allow_null=True)
    url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    publication = PublicationInput(required=False, allow_null=True)


class DraftInput(_ClosedSerializer):
    parameter_key = serializers.CharField()
    value_type = serializers.ChoiceField(choices=ValueType.values)
    value = serializers.JSONField()
    unit = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    valid_from = serializers.DateField(required=False, allow_null=True)
    valid_to = serializers.DateField(required=False, allow_null=True)
    margin_basis = serializers.ChoiceField(
        choices=MarginBasis.values, required=False, allow_null=True
    )
    margin_reference = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    observed_in = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    confidence = serializers.ChoiceField(
        choices=SourceConfidence.values, default=SourceConfidence.PROVISIONAL
    )
    provisional_reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    act = ActInput()
    margin_act = ActInput(required=False, allow_null=True)


def _act(data: dict[str, Any]) -> Act:
    publication = data.get("publication")
    publications: tuple[Publication, ...] = ()
    if publication:
        publications = (
            Publication(
                gazette_year=int(publication["gazette_year"]),
                gazette_number=str(publication["gazette_number"]),
                article=str(publication["article"]),
                published_at=publication.get("published_at"),
            ),
        )
    return Act(
        act_type=str(data["act_type"]).strip(),
        act_number=str(data["act_number"]).strip(),
        act_date=data["act_date"],
        title=str(data["title"]).strip(),
        effective_from=data.get("effective_from"),
        url=(data.get("url") or "").strip() or None,
        notes=(data.get("notes") or "").strip() or None,
        publications=publications,
    )


def _iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _act_out(source: Any) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "act_type": source.act_type,
        "act_number": source.act_number,
        "act_date": _iso(source.act_date),
        "title": getattr(source, "title", None),
        "effective_from": _iso(getattr(source, "effective_from", None)),
    }


def serialize(row: FiscalParameter) -> dict[str, Any]:
    """The row as the screen shows it: value, margin, act, status, approval."""
    source = row.source
    act = source.act
    return {
        "id": str(row.id),
        "parameter_key": row.parameter_key,
        "scope": row.scope,
        "scope_ref": str(row.scope_ref) if row.scope_ref else None,
        "value_type": row.value_type,
        "value": row.value,
        "unit": row.unit,
        "valid_from": _iso(row.valid_from),
        "valid_to": _iso(row.valid_to),
        "margin_basis": row.margin_basis,
        "margin_reference": row.margin_reference,
        "margin_act": _act_out(row.margin_act),
        "observed_in": row.observed_in,
        "act": {
            "act_type": source.act_type,
            "act_number": source.act_number,
            "act_date": _iso(source.act_date),
            "title": act.title if act is not None else None,
            "effective_from": _iso(source.effective_from),
        },
        "status": row.status,
        "confidence": row.source_confidence,
        "provisional_reason": row.provisional_reason,
        "approved_by_user_id": str(row.approved_by_user_id) if row.approved_by_user_id else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "updated_at": row.updated_at.isoformat(),
    }


def _rows(using: str | None = None) -> Any:
    manager = FiscalParameter.objects if using is None else FiscalParameter.objects.using(using)
    return manager.select_related("source__act", "margin_act").order_by(
        "parameter_key", "valid_from", "created_at"
    )


class FiscalParametersView(APIView):
    """List every loaded version; write a new one."""

    def get_permissions(self) -> list[BasePermission]:
        # Reading is metadata about the platform and any employee may see it;
        # writing is `P-4`, the operator's path (ADR-076 §4.1).
        if self.request.method == "POST":
            return [IsPlatformOperator()]
        return [IsPlatformStaff()]

    def get(self, request: Request) -> Response:
        rows = _rows()
        key = request.query_params.get("key")
        if key:
            rows = rows.filter(parameter_key=key)
        return Response({"parameters": [serialize(row) for row in rows]})

    def post(self, request: Request) -> Response:
        data = DraftInput(data=request.data)
        data.is_valid(raise_exception=True)
        valid = dict(data.validated_data)
        margin_act = valid.get("margin_act")
        draft = ParameterDraft(
            key=str(valid["parameter_key"]),
            value_type=str(valid["value_type"]),
            value=valid["value"],
            act=_act(valid["act"]),
            unit=valid.get("unit"),
            valid_from=valid.get("valid_from"),
            valid_to=valid.get("valid_to"),
            margin_basis=valid.get("margin_basis"),
            margin_reference=valid.get("margin_reference"),
            margin_act=_act(margin_act) if margin_act else None,
            observed_in=valid.get("observed_in"),
            confidence=str(valid.get("confidence") or SourceConfidence.PROVISIONAL),
            provisional_reason=valid.get("provisional_reason"),
        )
        staff = request.platform_staff  # type: ignore[attr-defined]
        try:
            with privileged_run(
                PrivilegedPath.P4_FISCAL_RULES,
                actor=f"console:{staff.staff_role}",
                actor_user_id=staff.user_id,
                request_id=str(getattr(request, "request_id", "console")),
                payload={
                    "operation": "draft",
                    "key": draft.key,
                    "valid_from": _iso(draft.valid_from),
                },
                using=REFDATA_ALIAS,
            ) as run:
                written = write_parameter(draft, using=REFDATA_ALIAS)
                run.payload["outcome"] = written.outcome
        except AuthoringError as error:
            raise _raise_api(error) from error
        # Read back on the reference connection: the row as written, with its
        # act joined. (Not the request's own connection -- under the test
        # harness the reference transaction is not yet committed there, and a
        # view that read what it had not yet committed would be the bug.)
        row = _rows(REFDATA_ALIAS).get(pk=written.row.pk)
        status = 201 if written.outcome == "created" else 200
        return Response({"outcome": written.outcome, "parameter": serialize(row)}, status=status)


class ActivateFiscalParameterView(APIView):
    """Turn a draft live, as the signed-in operator -- amendment D.1's approval.

    Idempotent by state: an already active row answers 200 with `already_active`
    and changes nothing, so a repeated click is not a second approval.
    """

    permission_classes = (IsPlatformOperator,)

    def post(self, request: Request, parameter_id: uuid.UUID) -> Response:
        staff = request.platform_staff  # type: ignore[attr-defined]
        try:
            with privileged_run(
                PrivilegedPath.P4_FISCAL_RULES,
                actor=f"console:{staff.staff_role}",
                actor_user_id=staff.user_id,
                request_id=str(getattr(request, "request_id", "console")),
                payload={"operation": "activate", "parameter_id": str(parameter_id)},
                using=REFDATA_ALIAS,
            ) as run:
                activated = activate_parameter(
                    parameter_id, approver=staff.user_id, using=REFDATA_ALIAS
                )
                run.payload["outcome"] = activated.outcome
                run.payload["key"] = activated.row.parameter_key
        except AuthoringError as error:
            raise _raise_api(error) from error
        row = _rows(REFDATA_ALIAS).get(pk=parameter_id)
        return Response({"outcome": activated.outcome, "parameter": serialize(row)})
