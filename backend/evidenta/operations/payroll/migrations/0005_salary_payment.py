"""The salary payment document, its lines, and the employee's bank account.

Additive (`C5`): one nullable column on `employee` -- the IBAN the bank's payment
list reads, a code and therefore `COLLATE "C"` in the SQL (`C34`) -- and two
company-scoped tables on the pattern of `0003_payroll_run`: the document that
pays what an approved run left on the salary payable, one line per person.

Three things land in SQL (`0078_salary_payment`): the collation, the freeze
trigger that makes a posted payment's lines unchangeable, and the privileges,
which withdraw DELETE on the document explicitly (`OD-105`).
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0004_contract_cost_destination"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="bank_iban",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="SalaryPayment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("paid_on", models.DateField()),
                (
                    "treasury_account",
                    models.TextField(choices=[("cash", "Cash"), ("bank", "Bank")]),
                ),
                (
                    "status",
                    models.TextField(
                        choices=[("draft", "Draft"), ("posted", "Posted")], default="draft"
                    ),
                ),
                ("posted_by_user_id", models.UUIDField(blank=True, null=True)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        db_column="company_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.company",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        db_column="run_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="payroll.payrollrun",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "salary_payment",
            },
        ),
        migrations.CreateModel(
            name="SalaryPaymentLine",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                (
                    "company",
                    models.ForeignKey(
                        db_column="company_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.company",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        db_column="employee_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="salary_payment_lines",
                        to="payroll.employee",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        db_column="payment_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="payroll.salarypayment",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "salary_payment_line",
            },
        ),
        migrations.AddIndex(
            model_name="salarypayment",
            index=models.Index(fields=["tenant", "company", "paid_on"], name="salary_payment_idx"),
        ),
        migrations.AddIndex(
            model_name="salarypayment",
            index=models.Index(fields=["run", "status"], name="salary_payment_run_idx"),
        ),
        migrations.AddConstraint(
            model_name="salarypayment",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["draft", "posted"])),
                name="salary_payment_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="salarypayment",
            constraint=models.CheckConstraint(
                condition=models.Q(("treasury_account__in", ["cash", "bank"])),
                name="salary_payment_account_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="salarypayment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("status", "posted"), _negated=True),
                    ("posted_by_user_id__isnull", False),
                    _connector="OR",
                ),
                name="salary_payment_posted_has_a_poster",
            ),
        ),
        migrations.AddIndex(
            model_name="salarypaymentline",
            index=models.Index(
                fields=["tenant", "company", "employee"], name="salary_payment_line_emp_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="salarypaymentline",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)), name="salary_payment_line_amount_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="salarypaymentline",
            constraint=models.UniqueConstraint(
                fields=("payment", "employee"), name="salary_payment_line_unique"
            ),
        ),
        run_sql_file(
            "0078_salary_payment",
            up_sha256="77044959a37d6bb2dce975732460a54d8d26d947e13fd4683d30ecd33ff6022e",
            down_sha256="779ca3d3e8221fde7a92a617f0799fc20a57ce486c5aa8cbe0cdac9adff03db1",
        ),
    ]
