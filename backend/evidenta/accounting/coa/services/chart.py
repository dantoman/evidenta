"""Which chart version a company's postings stand on -- ADR-048.

A journal entry stamps the chart version in force when it was posted, beside the
rule version and the fiscal effective date. Of the three, this is the one that
**cannot be re-derived later**: `company_chart.template` is the company's
current template, and the day propagation (`OD-03`) moves a company to a newer
version, every entry posted before that would be read against a chart it never
used. The stamp is what keeps a 2026 entry readable against the 2026 chart in
2030 (`R18`).

A public service rather than a model read, so the ledger and the engine can ask
without importing `coa.models` (`D6`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from evidenta.accounting.coa.models import CoaTemplate, CompanyChart


@dataclass(frozen=True, slots=True)
class ChartVersion:
    template_id: uuid.UUID
    code: str
    version: str


def chart_version_of(company_id: uuid.UUID) -> ChartVersion | None:
    """The template version this company's chart was built on, or None.

    None is a real answer, not a lookup failure: a company whose accounts were
    written directly -- a fixture, a migration of data -- has no template row to
    name, and stamping a made-up one would be worse than stamping nothing. RLS
    also makes another tenant's chart read as absent (IZ-04).
    """
    chart = (
        CompanyChart.objects.filter(company_id=company_id)
        .select_related("template")
        .only("template__id", "template__code", "template__version")
        .first()
    )
    if chart is None:
        return None
    return ChartVersion(
        template_id=chart.template.id, code=chart.template.code, version=chart.template.version
    )


def template_version(template_id: uuid.UUID) -> ChartVersion | None:
    """The version a stamped `chart_template_id` names, for a reader of the entry.

    Distinct from `chart_version_of`, and the distinction is the reason the stamp
    exists: that one answers what the company uses *now*, this one what an entry
    was posted *against*. After propagation (`OD-03`) the two differ, and a
    drill-down that labelled an old entry with the current version would be
    stating something the entry never said.
    """
    template = CoaTemplate.objects.filter(id=template_id).only("id", "code", "version").first()
    if template is None:
        return None
    return ChartVersion(template_id=template.id, code=template.code, version=template.version)
