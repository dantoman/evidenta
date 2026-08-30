from django.apps import AppConfig


class TaxConfig(AppConfig):
    """Statutory returns to the tax service.

    Separate from `payroll` because `D4` runs one way: payroll must not import
    tax, and a declaration that lived inside payroll would make every future
    return -- VAT, the annual ones, the ones that carry no salary at all -- either
    live there too or be split later.
    """

    name = "evidenta.operations.tax"
    label = "tax"
    verbose_name = "Statutory returns"
