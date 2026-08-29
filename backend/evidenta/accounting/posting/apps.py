from django.apps import AppConfig


class PostingConfig(AppConfig):
    """The Posting Engine. It writes through the ledger's service, never itself.

    Its own tables are the operation templates of F1.7.3 -- layer 4 of ADR-036,
    the client's shortcuts to a manual note. They hold no ledger data: a template
    is expanded into a manual payload and handed to the same entry point a typed
    note goes through.

    It became an installed app for a different reason: ADR-038 has modules
    **register** their event types at the import of their AppConfig, which is the
    inversion that keeps `D2` intact. Without an app config the registration would
    happen only when something imported the module, so the vocabulary would depend
    on import order -- and `check_registry`, which runs at process start, would see a
    different registry than the one that serves the request.
    """

    name = "evidenta.accounting.posting"
    label = "posting"
    verbose_name = "Posting engine"

    def ready(self) -> None:
        # Importing is the registration: `manual` registers at module level, so
        # this runs once per interpreter however many times it is imported.
        # Deliberately not calling `check_registry()` here -- ADR-038 section 5
        # puts that in the processes that serve, because in `ready()` it would
        # also fail `migrate`, and a deploy could not run the migration that
        # fixes it.
        from evidenta.accounting.posting.services import (
            closing,  # noqa: F401
            manual,  # noqa: F401
            reversal,  # noqa: F401
        )
