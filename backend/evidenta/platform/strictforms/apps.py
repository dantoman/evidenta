from django.apps import AppConfig


class StrictFormsConfig(AppConfig):
    """The register of state-issued form ranges -- `art. 118²` Cod fiscal.

    Named for what these are called in the law: *formulare cu regim special*,
    strict-accountability forms. The English word is unusual because the concept
    is: a document whose number the entity does not choose.

    Separate from `platform.numbering` on purpose, and the difference is the
    whole module. Numbering (ADR-022) *generates* from a counter, which is right
    for documents the entity numbers itself. A fiscal invoice on paper carries a
    series and a number **issued by the tax service**, for the whole life of the
    business, and the system may only *consume* from that range. Bending the
    counter to do both would produce free numbering wherever somebody forgot
    which kind of document they had.
    """

    name = "evidenta.platform.strictforms"
    label = "strictforms"
    verbose_name = "Strict-accountability forms"
    default_auto_field = "django.db.models.BigAutoField"
