"""Create the first tenant of an installation, with a user who can log in.

**Why a command and not an endpoint.** Who may create a tenant *through the
product* is `DN-26`, left open by ADR-040 -- self-service, invitation, and
creation by a firm on a client's behalf are three different products. An HTTP
route would answer that by existing. An operator with database credentials
creating the first tenant answers nothing: it is the same act as running the
migrations.

**What it closes.** Every other part of the vertical slice assumes somebody is
signed in, and nothing could produce that somebody. A fresh checkout could
bootstrap roles, migrate, load the chart of accounts -- and then reach a login
screen with no account behind it. The development database had a tenant because
a person once made one by hand, which is the state a command exists to remove.

**It runs as the installation role, and that is measured rather than chosen for
convenience.** Every policy on `tenant`, `user`, `membership` and `role` is
written `TO evidenta_app`; under `FORCE ROW LEVEL SECURITY` the owner therefore
has no applicable policy at all and is refused every one of these inserts --
tried, and refused, before this was written. The alternatives were widening those
policies to the owner, which removes a property that is currently true, or
writing `rls.provision_tenant`, which ADR-040 describes but which would have to
create a user -- and the same ADR says P-9 does not create users. Creating the
first tenant is a DBA act, like `make bootstrap`, so it is spelled that way.

**The second factor is enrolled here, and that is not optional.** ADR-021 makes
it mandatory and `authenticate()` refuses a user without a confirmed one, so a
command that created a user and stopped would produce an account that cannot sign
in -- the failure looking like a wrong password. `OD-48` is why enrolment cannot
happen later through the product: it runs post-authentication, which the new user
cannot reach. The secret is printed once, here, and is never retrievable again.

Nothing else may use the `admin` connection. No privileged path is added, nothing
new is granted to the application role, and the product surface is unchanged.
"""

from __future__ import annotations

import getpass
import uuid
from datetime import UTC, datetime
from typing import Any

import pyotp
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from evidenta.platform.identity.services.authentication import confirm_totp, enrol_totp
from evidenta.platform.identity.services.provisioning import (
    create_membership,
    create_user,
    user_by_email,
)
from evidenta.platform.identity.services.roles import create_system_roles
from evidenta.platform.rls.context import TenantContext, tenant_context, unguarded
from evidenta.platform.rls.installation import (
    InstallationRoleError,
    bind_default_to_installation_role,
)
from evidenta.platform.tenancy.models import Tenant

MINIMUM_PASSWORD = 12


class Command(BaseCommand):
    help = "Create a tenant with its owner, ready to sign in. Operator command."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", required=True)
        parser.add_argument("--legal-name", required=True)
        # The holder's own fiscal identity (ADR-075). Optional, because a tenant
        # without it is the state every existing one is in -- and because the
        # subscription can be signed before the IDNO is at hand. What it costs to
        # leave empty is named on the workspace screen, not hidden.
        parser.add_argument("--idno", default=None)
        parser.add_argument("--legal-form", default=None)
        parser.add_argument("--email", required=True)
        parser.add_argument("--full-name", default="")
        # Not the default path: a password on the command line lands in shell
        # history and in the process list. Accepted anyway for scripted installs,
        # where the operator has already weighed that.
        parser.add_argument("--password", default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        subdomain = options["subdomain"].strip().lower()
        email = options["email"].strip().lower()
        password = options["password"] or getpass.getpass("Parolă: ")
        if len(password) < MINIMUM_PASSWORD:
            raise CommandError(f"parola are cel puțin {MINIMUM_PASSWORD} caractere")

        # The installation role, not the owner and not the application: the
        # reason is in `platform.rls.installation`, which the repair command
        # shares. A CommandError here rather than the RuntimeError, so an
        # operator gets a message instead of a traceback.
        try:
            bind_default_to_installation_role()
        except InstallationRoleError as unavailable:
            raise CommandError(str(unavailable)) from unavailable
        now = datetime.now(UTC)
        tenant_id = uuid.uuid4()

        # The first tenant precedes every context by definition, so the guard has
        # to be told that in as many words. `unguarded` requires a reason for
        # exactly this: a list of suspensions with no stated reason is how the
        # guarantee erodes.
        with unguarded("create_tenant: the first tenant precedes every context"):
            if Tenant.objects.filter(subdomain=subdomain).exists():
                raise CommandError(f"subdomeniul {subdomain!r} este deja folosit")

            with transaction.atomic():
                Tenant.objects.create(
                    id=tenant_id,
                    subdomain=subdomain,
                    legal_name=options["legal_name"],
                    idno=options["idno"],
                    legal_form=options["legal_form"],
                    status="active",
                    default_locale="ro",
                    created_at=now,
                    updated_at=now,
                )

                # An existing address keeps its password. This command creates a
                # tenant; silently resetting someone's credentials because their
                # address was typed again is not part of that.
                #
                # Asked of `identity` through its services, never through its
                # models (D6) -- what an active membership must carry to be valid
                # is that module's knowledge, and assembling the row here would
                # mean re-deriving it.
                user = user_by_email(email)
                reused = user is not None
                if user is None:
                    user = create_user(
                        email=email,
                        full_name=options["full_name"],
                        password=password,
                    )

                roles = create_system_roles(tenant_id)
                create_membership(tenant_id=tenant_id, user_id=user.id, role=roles["owner"])

            secret: str | None = None
            if not reused:
                # Enrolled through the product's own services, inside a context
                # like every post-login operation. Bypassing them would enrol
                # differently than the product does, and the difference would
                # only show up at the first sign-in.
                context = TenantContext(
                    tenant_id=tenant_id, user_id=user.id, request_id="create_tenant"
                )
                with tenant_context(context):
                    enrolment = enrol_totp(user.id, label="bootstrap")
                    # `parse_uri` is typed as returning the base class, whose
                    # `secret` mypy cannot see -- but the narrow `type: ignore`
                    # that used to sit here was itself reported as unused under
                    # `mypy .`, which is what CI runs. `getattr` says the same
                    # thing without claiming to suppress an error that the
                    # checker does not raise.
                    parsed = pyotp.parse_uri(enrolment.provisioning_uri)
                    secret = str(getattr(parsed, "secret", ""))
                    if not secret:  # pragma: no cover -- pyotp always sets it
                        raise CommandError("pyotp nu a întors un secret de înrolare")
                    confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())

        self.stdout.write(f"tenant {subdomain}: {tenant_id}")
        self.stdout.write(f"utilizator {email}: {'existent' if reused else 'nou'}")
        if secret is not None:
            self.stdout.write(f"secret TOTP (o singură dată): {secret}")
        self.stdout.write(f"http://{subdomain}.evidenta.localhost:5173")
