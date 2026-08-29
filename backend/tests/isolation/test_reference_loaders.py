"""The two loaders, end to end, under the reference-data role -- ADR-049.

What `OD-67` recorded as "complete and inert" -- a chart loader that could only
run as the owner, a confidence service whose caller had to supply a connection --
runs here on the connection the role owns, twice, and is asked three things of
each run: that it is idempotent, that it links the act it cites, and that it
leaves exactly one row in `privileged_access_log`.

The chart is loaded from the shipped file, which is the real one: 476 accounts.
The fiscal parameters are loaded from a fictitious file written by the test,
because `OD-22` is open and no rate may appear in a test.
"""

from __future__ import annotations

import io
import uuid
from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import ProgrammingError

from evidenta.accounting.coa.models import CoaTemplate, CoaTemplateAccount
from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    FiscalParameterSource,
    ParameterStatus,
    SourceConfidence,
)
from evidenta.platform.audit.models import PrivilegedAccessLog
from evidenta.platform.audit.services.privileged import REFDATA_ALIAS
from evidenta.platform.legislation.models import NormativeAct, NormativeActPublication

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

CODE = "TEST-SNC"


def log_rows(path_code: str) -> list[PrivilegedAccessLog]:
    return list(
        PrivilegedAccessLog.objects.using(REFDATA_ALIAS)
        .filter(path_code=path_code, actor="test:loader")
        .order_by("id")
    )


# --- the chart of accounts (P-10) ----------------------------------------------


def load_chart() -> str:
    out = io.StringIO()
    call_command("load_coa_template", code=CODE, actor="test:loader", stdout=out)
    return out.getvalue()


def test_the_chart_loads_under_the_role_and_links_its_act() -> None:
    before = len(log_rows("P-10"))
    output = load_chart()

    template = CoaTemplate.objects.using(REFDATA_ALIAS).get(code=CODE, version="2020")
    assert CoaTemplateAccount.objects.using(REFDATA_ALIAS).filter(template=template).count() == 476
    assert "476 conturi noi" in output

    act = template.act
    assert act is not None
    assert (act.act_type, act.act_number, act.act_date) == ("ordin_mf", "119", date(2013, 8, 6))
    positions = {
        (link.publication.gazette_year, link.publication.gazette_number, link.publication.article)
        for link in NormativeActPublication.objects.using(REFDATA_ALIAS)
        .filter(act=act)
        .select_related("publication")
    }
    assert positions == {(2013, "177-181", "1225"), (2013, "233-237", "1534")}

    rows = log_rows("P-10")
    assert len(rows) == before + 1
    payload = rows[-1].payload
    assert payload is not None and payload["accounts_created"] == 476


def test_the_second_load_writes_nothing_and_still_logs_a_run() -> None:
    load_chart()
    before = len(log_rows("P-10"))
    output = load_chart()
    assert "0 conturi noi, 0 actualizate, 476 neschimbate" in output
    assert len(log_rows("P-10")) == before + 1
    assert NormativeAct.objects.using(REFDATA_ALIAS).filter(act_number="119").count() == 1


def test_the_owner_connection_is_refused_now() -> None:
    """0060 retracted 0044's owner policy: one door, not two."""
    with pytest.raises(ProgrammingError):
        call_command("load_coa_template", code=CODE, database="migration", stdout=io.StringIO())


# --- fiscal parameters (P-4) -----------------------------------------------------


def write_file(tmp_path: Path, *, value: int = 1, effective: bool = True) -> Path:
    effective_line = "effective_from = 2000-01-01" if effective else ""
    path = tmp_path / "fictitious.toml"
    path.write_text(
        f"""
schema_version = 1

[[act]]
ref = "test-act"
act_type = "test"
act_number = "TEST-L/0000"
act_date = 2000-01-01
title = "Act de test pentru încărcător"
{effective_line}

[[act.publications]]
gazette_year = 2000
gazette_number = "TEST 0"
article = "art. 0"

[[parameter]]
key = "test.loader.alpha"
act = "test-act"
value_type = "integer"
value = {value}
valid_from = 2000-01-01
confidence = "provisional"
provisional_reason = "test: fictitious"
""",
        encoding="utf-8",
    )
    return path


def load_parameters(path: Path) -> str:
    out = io.StringIO()
    call_command("load_fiscal_parameters", str(path), actor="test:loader", stdout=out)
    return out.getvalue()


def test_parameters_load_as_draft_with_their_act(tmp_path: Path) -> None:
    before = len(log_rows("P-4"))
    output = load_parameters(write_file(tmp_path))
    assert "1 parametri noi" in output

    row = FiscalParameter.objects.using(REFDATA_ALIAS).get(parameter_key="test.loader.alpha")
    assert row.status == ParameterStatus.DRAFT, "a file cannot carry an approval (D.1)"
    assert row.source_confidence == SourceConfidence.PROVISIONAL
    source = FiscalParameterSource.objects.using(REFDATA_ALIAS).get(pk=row.source_id)
    assert source.act is not None and source.act.act_number == "TEST-L/0000"
    assert len(log_rows("P-4")) == before + 1


def test_the_second_load_is_a_no_op(tmp_path: Path) -> None:
    path = write_file(tmp_path)
    load_parameters(path)
    output = load_parameters(path)
    assert "0 parametri noi, 0 actualizați, 1 neschimbați" in output
    assert (
        FiscalParameter.objects.using(REFDATA_ALIAS)
        .filter(parameter_key="test.loader.alpha")
        .count()
        == 1
    )


def test_a_draft_value_may_be_corrected_but_an_active_one_may_not(tmp_path: Path) -> None:
    load_parameters(write_file(tmp_path, value=1))
    output = load_parameters(write_file(tmp_path, value=2))
    assert "1 actualizați" in output

    row = FiscalParameter.objects.using(REFDATA_ALIAS).get(parameter_key="test.loader.alpha")
    row.status = ParameterStatus.ACTIVE
    row.approved_by_user_id = uuid.uuid4()
    row.save(using=REFDATA_ALIAS, update_fields=["status", "approved_by_user_id"])

    with pytest.raises(CommandError, match="not edited"):
        load_parameters(write_file(tmp_path, value=3))
    row.refresh_from_db(using=REFDATA_ALIAS)
    assert row.value == 2


def test_an_act_without_its_effective_date_cannot_carry_a_parameter(tmp_path: Path) -> None:
    with pytest.raises(CommandError, match="effective_from"):
        load_parameters(write_file(tmp_path, effective=False))
    assert (
        not FiscalParameter.objects.using(REFDATA_ALIAS)
        .filter(parameter_key="test.loader.alpha")
        .exists()
    )


def test_the_shipped_conventions_file_loads_its_act_and_no_value(tmp_path: Path) -> None:
    """What the repository ships today: the act, cited; the values, awaiting V1."""
    output = load_parameters(Path("platform_conventions.toml"))
    assert "1 acte, 0 parametri noi" in output
    act = NormativeAct.objects.using(REFDATA_ALIAS).get(
        act_number="118", act_date=date(2017, 8, 28)
    )
    assert act.effective_from is None
    assert {
        (p.publication.gazette_year, p.publication.gazette_number, p.publication.article)
        for p in act.publications.select_related("publication")
    } == {(2017, "340-351", "1750")}
