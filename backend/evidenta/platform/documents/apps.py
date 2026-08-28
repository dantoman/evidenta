from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    """The document core, and the one type it owns itself.

    Every other type is registered by the module that owns it -- that inversion
    is what lets `platform` hold the vocabulary without importing anything above
    it. The storno is the exception, and deliberately: a storno of a sale and a
    storno of a purchase are the same document with the same rules, so putting it
    in either module would be choosing one of them arbitrarily and giving the
    other a copy.
    """

    name = "evidenta.platform.documents"
    label = "documents"
    verbose_name = "Documents"

    def ready(self) -> None:
        from evidenta.platform.documents.services.reversal import register_reversal_type

        register_reversal_type()
