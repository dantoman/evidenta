"""Recording an act and where it was published -- the write side of OD-65.

Called by the loaders, under the reference-data connection they already hold.
Idempotent on the act's identity (type, number, date) and on the publication's
position (issue, date, article): running a loader twice records nothing twice,
and two acts naming the same position share one row -- which is the fact the
tables exist for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from evidenta.platform.legislation.models import (
    NormativeAct,
    NormativeActPublication,
    OfficialPublication,
)


@dataclass(frozen=True, slots=True)
class Publication:
    gazette_year: int
    gazette_number: str
    article: str
    published_at: date | None = None
    role: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Act:
    act_type: str
    act_number: str
    act_date: date
    title: str
    effective_from: date | None = None
    url: str | None = None
    notes: str | None = None
    publications: tuple[Publication, ...] = ()


def register_act(act: Act, *, using: str) -> NormativeAct:
    """The act's row, created or brought up to date, with its publications linked.

    Title, dates and notes are updated in place: they describe the act, and a
    correction to a description is not a new act. The identity never changes --
    a different number or date is a different act, so it gets a different row.
    Publications are only ever added; a citation that was true stays true.
    """
    row, _ = NormativeAct.objects.using(using).update_or_create(
        act_type=act.act_type,
        act_number=act.act_number,
        act_date=act.act_date,
        defaults={
            "title": act.title,
            "effective_from": act.effective_from,
            "url": act.url,
            "notes": act.notes,
        },
    )
    for publication in act.publications:
        position, created = OfficialPublication.objects.using(using).get_or_create(
            gazette_year=publication.gazette_year,
            gazette_number=publication.gazette_number,
            article=publication.article,
            defaults={"published_at": publication.published_at, "url": publication.url},
        )
        # The day is knowledge that arrives later than the citation; a run that
        # knows it fills it in, and no run blanks it.
        if not created and publication.published_at and position.published_at is None:
            position.published_at = publication.published_at
            position.save(using=using, update_fields=["published_at"])
        NormativeActPublication.objects.using(using).get_or_create(
            act=row, publication=position, defaults={"role": publication.role}
        )
    return row
