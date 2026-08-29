"""Normative acts and where they were published -- OD-65, ADR-049.

`R15` wants every fiscal parameter to name its act *and* the Monitorul Oficial
position that published it. The first model of that provenance put one
publication on the act row, and that shape was measured wrong on 2026-08-28 from
the Ministry of Finance's own consolidated texts: the order approving the
standards (OMF 118/2013) and the order approving the chart of accounts (OMF
119/2013) each print two citations, and the second one -- MO nr. 233-237 art.
1534 of 22.10.2013 -- is the same on both. So a position in the Monitor is not a
property of an act; it is a thing two acts can share. A second pair of columns
cannot express that, and a table can.

Three tables, all global (the same law for everyone) and all written only under
the reference-data role. `fiscal_parameter_source` and `coa_template` point at
`NormativeAct`; their older free-text or single-publication columns stay, because
migrations are additive (C5), and the loaders fill both.

**Lives in `platform`, not in `fiscal`**, and the placement is the point of
`OD-65`'s last sentence: "it decides what a citation looks like everywhere
downstream". The chart of accounts is an accounting act, not a fiscal parameter
(`OD-56`); putting the act registry under `fiscal` would have repeated the
definition error that made `OD-22` look bigger than it is.
"""

from __future__ import annotations

import uuid

from django.db import models


class NormativeAct(models.Model):
    """One act, identified by type, number and date -- all three.

    The number alone repeats across years (the ministry restarts its sequence
    annually) and across issuers (OMF 118 of 06.08.2013 approves the standards;
    OMF 118 of 28.08.2017 approves the invoice form). The date is part of the
    identity, not decoration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    #: `lege`, `ordin_mf`, `hg`, `ordin_sfs` ... -- a code, byte-ordered (C34).
    act_type = models.TextField()
    act_number = models.TextField()
    act_date = models.DateField()

    #: The title as the act carries it, in Romanian -- a name, linguistic order.
    title = models.TextField()

    #: When the act, as a whole, entered into force. A parameter's own
    #: `valid_from` may differ (an amending order can set several dates).
    effective_from = models.DateField(null=True, blank=True)

    url = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "normative_act"
        constraints = [
            models.UniqueConstraint(
                fields=["act_type", "act_number", "act_date"],
                name="normative_act_identity_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.act_type} {self.act_number} din {self.act_date:%d.%m.%Y}"


class OfficialPublication(models.Model):
    """One position in Monitorul Oficial: issue, date, article.

    An issue number without the article is a magazine, not a reference; the
    three together are what a citation prints and what two acts can share.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    #: The identity is the citation's own: *Monitorul Oficial, 2017, nr. 340-351,
    #: art. 1750*. Issue numbers and article numbers restart every year, so the
    #: year is part of it; the day of publication is not -- a citation is
    #: complete without it, and ADR-037 section 0 quotes one exactly so.
    gazette_year = models.IntegerField()
    #: `177-181`, `233-237` -- the issue range as printed.
    gazette_number = models.TextField()
    #: `1225`, `1534` -- the article number within the issue.
    article = models.TextField()
    #: Known for some positions and not others; filled when read, never invented.
    published_at = models.DateField(null=True, blank=True)

    url = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "official_publication"
        constraints = [
            models.UniqueConstraint(
                fields=["gazette_year", "gazette_number", "article"],
                name="official_publication_position_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"MO {self.gazette_year} nr. {self.gazette_number} art. {self.article}"


class NormativeActPublication(models.Model):
    """An act appeared at a position. Many-to-many, because both directions are
    real: an act has several publications, and one publication covers several
    acts.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    act = models.ForeignKey(
        NormativeAct, on_delete=models.PROTECT, related_name="publications", db_column="act_id"
    )
    publication = models.ForeignKey(
        OfficialPublication,
        on_delete=models.PROTECT,
        related_name="acts",
        db_column="publication_id",
    )

    #: What this publication is for this act, in the act's own terms:
    #: `initial` (the act itself), `consolidated` (a republication), `annex`
    #: (an annex published apart from its act). Free text on purpose: the
    #: vocabulary is the Monitor's, not ours, and it is not closed.
    role = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "normative_act_publication"
        constraints = [
            models.UniqueConstraint(
                fields=["act", "publication"], name="normative_act_publication_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.act_id} @ {self.publication_id}"
