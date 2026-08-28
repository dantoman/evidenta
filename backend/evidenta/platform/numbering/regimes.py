"""The two numbering regimes -- the numbering module's public vocabulary.

Its own module rather than a name inside `models`, and the reason is `D6`: a
service of another module that needs to say "this series numbers documents
itself" would otherwise have to import `numbering.models`, which is the coupling
the rule exists to stop. The vocabulary is not a table; it is a contract, and a
contract belongs where anybody may read it.

The same shape `accounting.events.registry` and `accounting.slots.catalogue`
already have: the value another module needs lives outside the model layer.
"""

from __future__ import annotations

from django.db import models


class NumberingRegime(models.TextChoices):
    """Who produces the identifier -- the two regimes run in parallel, always.

    ``OWN`` is the counter this platform maintains: the company chooses the shape
    of the number, the platform guarantees uniqueness and hands out the next one.

    ``EXTERNAL`` is an identifier that **arrives**. An e-Factura number is
    assigned by the tax service's exchange (`Exx` plus nine digits, Ordinul SFS
    185/2023); a range of strict-accountability forms is issued under `art. 118²`
    and consumed through `platform.strictforms`. Neither is generated here, and
    the practical consequence is a refusal rather than a setting: `allocate`
    raises on an external series instead of quietly producing a number that would
    then collide with the one that arrives.

    The other half of the same fact is on the document: a document under an
    external regime may be validated **without** a number, because the number is
    not ours to have yet. One under our own regime may not.
    """

    OWN = "own"
    EXTERNAL = "external"
