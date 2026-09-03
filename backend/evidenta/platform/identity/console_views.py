"""The console's staff pages -- who is an employee of the platform (ADR-092).

Reading the list is metadata about the platform and any employee may see it;
writing is the `admin`'s, through `P-12` on the reference-data connection, with
the acting admin stamped on the log row. The list comes from
`rls.console_staff()`, which refuses under a tenant context and refuses a
caller with no live row before it reads a thing -- so these views cannot be
reached usefully from anywhere but the console, whatever a client sends.

A person holds one role at a time (the primary key is the person). Changing a
role is a revocation followed by a grant, so that both dates exist; an admin
cannot revoke themselves, so the console can never end up with nobody able to
reopen it.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.permissions import IsPlatformAdmin, IsPlatformStaff
from evidenta.platform.audit.services.privileged import (
    REFDATA_ALIAS,
    PrivilegedPath,
    privileged_run,
)
from evidenta.platform.identity.models import StaffRole
from evidenta.platform.identity.services.staff import (
    StaffGrantError,
    StaffRow,
    grant_staff_by_id,
    list_staff,
    revoke_staff_by_id,
    user_id_by_email,
)


class StaffUserNotFoundError(ApiError):
    code = "staff.user_not_found"
    status = 404


class StaffRefusedError(ApiError):
    """A refusal from the service, carrying its code and status."""

    def __init__(self, error: StaffGrantError) -> None:
        self.code = error.code
        self.status = error.status
        super().__init__(str(error))


class GrantInput(serializers.Serializer[dict[str, Any]]):
    email = serializers.CharField()
    staff_role = serializers.ChoiceField(choices=StaffRole.values)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({name: "câmp necunoscut" for name in sorted(unknown)})
        return attrs


def serialize(row: StaffRow) -> dict[str, Any]:
    return {
        "user_id": str(row.user_id),
        "email": row.email,
        "full_name": row.full_name,
        "staff_role": row.staff_role,
        "granted_by_email": row.granted_by_email,
        "granted_at": row.granted_at.isoformat(),
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


class StaffView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "POST":
            return [IsPlatformAdmin()]
        return [IsPlatformStaff()]

    def get(self, request: Request) -> Response:
        return Response({"staff": [serialize(row) for row in list_staff()]})

    def post(self, request: Request) -> Response:
        data = GrantInput(data=request.data)
        data.is_valid(raise_exception=True)
        email = str(data.validated_data["email"]).strip().lower()
        role = str(data.validated_data["staff_role"])
        target = user_id_by_email(email)
        if target is None:
            raise StaffUserNotFoundError(f"no active account behind {email!r}")
        admin = request.platform_staff  # type: ignore[attr-defined]
        try:
            with privileged_run(
                PrivilegedPath.P12_PLATFORM_STAFF,
                actor=f"console:{admin.staff_role}",
                actor_user_id=admin.user_id,
                request_id=str(getattr(request, "request_id", "console")),
                payload={"operation": "grant", "user_id": str(target), "staff_role": role},
                using=REFDATA_ALIAS,
            ):
                grant_staff_by_id(
                    user_id=target,
                    staff_role=role,
                    granted_by_user_id=admin.user_id,
                    using=REFDATA_ALIAS,
                )
        except StaffGrantError as error:
            raise StaffRefusedError(error) from error
        return Response({"user_id": str(target), "staff_role": role}, status=201)


class RevokeStaffView(APIView):
    permission_classes = (IsPlatformAdmin,)

    def post(self, request: Request, user_id: uuid.UUID) -> Response:
        admin = request.platform_staff  # type: ignore[attr-defined]
        try:
            with privileged_run(
                PrivilegedPath.P12_PLATFORM_STAFF,
                actor=f"console:{admin.staff_role}",
                actor_user_id=admin.user_id,
                request_id=str(getattr(request, "request_id", "console")),
                payload={"operation": "revoke", "user_id": str(user_id)},
                using=REFDATA_ALIAS,
            ):
                revoke_staff_by_id(
                    user_id=user_id, revoked_by_user_id=admin.user_id, using=REFDATA_ALIAS
                )
        except StaffGrantError as error:
            raise StaffRefusedError(error) from error
        return Response({"user_id": str(user_id), "revoked": True})
