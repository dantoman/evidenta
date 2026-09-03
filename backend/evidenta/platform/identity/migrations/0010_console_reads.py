"""The console's read functions -- ADR-076 §4.3, ADR-092.

No model changes: the paired SQL creates the narrow, staff-gated functions in
schema `rls` through which the console reads metadata about every space, the
staff list, the privileged log, capability activations, release rings and flag
overrides -- the cross-tenant reads R7 permits only through enumerated paths
(Spec A §14). Each function refuses under a tenant context and refuses a caller
with no live `platform_staff` row before it reads anything.

Depends on every table the functions read, so that the GRANTs at the end have
something to grant on.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0009_platform_staff"),
        ("audit", "0003_privileged_access_log"),
        ("capabilities", "0001_initial"),
        ("flags", "0002_readonly_grants"),
        ("tenancy", "0011_provision_company_role"),
    ]

    operations = [
        run_sql_file(
            "0076_console_reads",
            up_sha256="d51c9d9e70f1ca8721c6f89aa4c4e250b9e63e1df027a018283be5cbd097f02e",
            down_sha256="ff034776fc39f1a236197d9a7b698090ebd3967ae8d158431acedc1c15bbd9b9",
        ),
    ]
