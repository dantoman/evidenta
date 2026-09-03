"""The revaluation tables and `settlement` lose UPDATE and DELETE for the application role.

REVERSIBILITY = "reversible-tested"

0079 said "INSERT and SELECT only" and granted exactly that -- over default
privileges that had already granted everything, so the sentence was true of the
file and false of the database (schema reviewer, 2026-09-03). `settlement`
(0074) had the same gap. A REVOKE in a new file, per C31; the reverse grants
them back. `settlement.currency` also gets the code collation of C34.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("currency", "0002_revaluation"),
        ("settlements", "0002_settlement_currency"),
    ]

    operations = [
        run_sql_file(
            "0080_currency_privileges",
            up_sha256="5622f9d146f39be757f9431c408b536bac878fb72acaee73fcf22e87437301a8",
            down_sha256="024a4a6a174875d37c9cae32a1f6fbc92dc29b9449bfe393f7889f87f61b80aa",
        ),
    ]
