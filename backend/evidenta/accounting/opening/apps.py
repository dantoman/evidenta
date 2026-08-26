from django.apps import AppConfig


class OpeningConfig(AppConfig):
    """Opening balances -- F1.7.2, Spec B section 8.

    A module of its own rather than part of ``posting``. The engine is generic:
    it judges a proposal and writes it, whatever produced it. This holds seven
    tables of staging data, the checks that make them consistent, and one event
    type -- none of which the engine should know about, and all of which would
    have to be excluded from it by hand if they lived there.
    """

    name = "evidenta.accounting.opening"
    label = "opening"
    verbose_name = "Opening balances"

    def ready(self) -> None:
        # Importing is the registration: `posting` registers `opening.balance.posted`
        # at module level, so this runs once per interpreter however many times it
        # is imported. ADR-038 has modules register their own types, which is the
        # inversion that keeps `D2` intact.
        #
        # Deliberately not calling `check_registry()` here -- ADR-038 section 5
        # puts that in the processes that serve, because in `ready()` it would
        # also fail `migrate`, and a deploy could not run the migration that
        # fixes it.
        from evidenta.accounting.opening.services import posting  # noqa: F401
