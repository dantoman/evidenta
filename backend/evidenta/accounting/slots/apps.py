from django.apps import AppConfig


class SlotsConfig(AppConfig):
    """Which account a semantic role means, for one company, on one date.

    ADR-036 section 5.1 calls them *roluri de cont — sloturi semantice*: two words
    for one thing, and both are used here because both are in the sources. A
    handler asks for `TVA_COLECTATA`; it never writes `5344`. That is the whole
    point -- an account code in a handler is a fiscal parameter compiled into
    code, and `R15` calls that a critical defect.

    This is the module the event registry was waiting for. `ACCOUNT_ROLES` sat
    empty with a comment saying it would be "registered by the module that owns
    the binding of roles to accounts"; that module is this one, and the boot check
    now validates handler declarations against a real catalogue instead of
    against nothing.
    """

    name = "evidenta.accounting.slots"
    label = "slots"
    verbose_name = "Account roles"

    def ready(self) -> None:
        from evidenta.accounting.events.registry import ACCOUNT_ROLES
        from evidenta.accounting.slots.catalogue import ROLES

        ACCOUNT_ROLES.update(ROLES)
