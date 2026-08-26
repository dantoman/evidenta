"""An act is cited by number *and* date, and a gazette issue by its article.

`R15` requires every fiscal parameter to carry its normative source. The columns
written in `0001_initial` could not actually hold a Moldovan citation:

- `act_number` alone does not identify an act. The chart of accounts is amended
  by orders 188/2014, 100/2019 and 111/2021 -- the ministry restarts its number
  sequence each year, so "Ordinul nr. 100" means nothing without "din
  28.06.2019". `act_date` is therefore NOT NULL: a source that cannot name its
  act is not a source.
- A gazette issue number without the article is not a pinpoint. Real citations
  read "MO nr. 177-181 art. 1225 din 16.08.2013". `official_gazette_article` is
  nullable, because acts exist that were never published in the Monitorul.

The index moves to (act_number, act_date) for the same reason: lookup by number
alone returns the wrong act in a different year.

**Safe as NOT NULL because the tables are empty, and that was measured rather
than assumed** -- `select count(*)` on `fiscal_parameter_source` and
`fiscal_parameter` returned 0 in the only existing database on 2026-08-26. The
module holds no values by design: filling them is OD-22, still open, because a
rate needs a citable act and the practising accountant. The one-off default below
is consumed by `preserve_default=False` and reaches no row.

Additive under `C5`: two columns added, none dropped.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fiscal_parameters", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="fiscalparametersource",
            name="act_date",
            field=models.DateField(default="1900-01-01"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="fiscalparametersource",
            name="official_gazette_article",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RemoveIndex(
            model_name="fiscalparametersource",
            name="fiscal_source_act_idx",
        ),
        migrations.AddIndex(
            model_name="fiscalparametersource",
            index=models.Index(
                fields=["act_number", "act_date"], name="fiscal_source_act_idx"
            ),
        ),
    ]
