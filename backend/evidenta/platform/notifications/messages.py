"""The message catalogue -- the resource file C32 asks for, on the backend.

C32 puts interface strings in resource files from the first screen, and the
reason it gives is the one that applies here too: it is what makes "we are adding
Russian" cost a translation instead of a walk through two hundred call sites.
Backend notifications are interface, so they obey the same rule -- the text lives
here and nowhere else.

Romanian, per C15. This is interface, not a register, so C33 and ADR-016 do not
bind it -- but nothing in this file ever reaches an accounting register either,
and the split matters: `docs/decisions/016-limba-contabilitatii.md` makes a
generated document in another language a non-compliant artefact.

**No message names the other party, and that is not a wording choice.** The
accountant's name belongs to the accountant's tenant. F0.6.5 requires that no
notification carry another tenant's data, and a notice that named the firm would
be doing exactly that -- worse, it would be smuggling across a boundary the
policies enforce, because a client user cannot read the `firm` row at all today.

That last part is a measured fact rather than a design intent: the policy on
`firm` is `rls.has_tenant_access(tenant_id)` over the **firm's own** tenant, and
a client administrator is neither a member of it nor acting for it. The comment
above that policy says the client should see who keeps their books, and the
predicate does not implement it. Recorded as `OD-51`. When it is closed, the
names come back by editing this file and nothing else -- which is the whole point
of a resource file.

Until then a client with two accountants cannot tell from the notice which one
left, and that cost is visible here rather than hidden behind a name pulled from
a row the recipient may not read.

**Model vocabulary does not appear in these strings** (C37): no `tenant`, no
`firm`, no `engagement`, no `assignment`. The mapping to interface words is fixed
in ADR-017. `test_notifications.py` greps this file for those terms, which is the
check C37 describes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    """One notification type.

    `subject` and `body` are format strings filled from the notification's
    `params`. `required_params` is checked at dispatch rather than at render: a
    notification missing a substitution would otherwise be stored successfully
    and fail in the recipient's inbox, where nobody can fix it.
    """

    subject: str
    body: str
    required_params: tuple[str, ...] = ()


CATALOGUE: dict[str, Message] = {
    # ADR-077 §5-§6. The consent sentence from ADR-017, verbatim, with the real
    # ticket number -- a request without one cannot be written, by constraint.
    "support.requested": Message(
        subject="Solicitare de acces pentru suport",
        body=(
            "Echipa Evidenta solicită acces temporar la datele companiei pentru rezolvarea "
            "solicitării #{request_ref}. Aprobarea se dă din spațiul de lucru, este doar-citire "
            "și expiră automat."
        ),
        required_params=("request_ref",),
    ),
    "support.approved": Message(
        subject="Acces pentru suport aprobat",
        body=(
            "Accesul echipei Evidenta pentru solicitarea #{request_ref} a fost aprobat și expiră "
            "la {expires_at}. Poate fi retras oricând din spațiul de lucru."
        ),
        required_params=("request_ref", "expires_at"),
    ),
    "support.revoked": Message(
        subject="Acces pentru suport retras",
        body="Accesul echipei Evidenta pentru solicitarea #{request_ref} a fost retras.",
        required_params=("request_ref",),
    ),
    "engagement.revoked": Message(
        subject="Accesul contabilului a fost retras",
        body=(
            "Accesul companiei de contabilitate la datele dumneavoastră a fost "
            "retras. Datele rămân neatinse și vă aparțin."
        ),
    ),
    "engagement.suspended": Message(
        subject="Accesul contabilului a fost suspendat",
        body=(
            "Accesul companiei de contabilitate a fost suspendat. Puteți alege "
            "să continuați pe cont propriu sau să transferați evidența altcuiva."
        ),
    ),
    "accountant.closed": Message(
        subject="Compania de contabilitate și-a încetat activitatea",
        body=(
            "Compania de contabilitate care vă ținea evidența și-a încetat "
            "activitatea. Accesul ei a fost suspendat, nu retras: alegerea a ce "
            "urmează vă aparține. Datele nu au fost atinse."
        ),
    ),
    "engagement.invited": Message(
        subject="Invitație de colaborare",
        body=(
            "Ați primit o invitație de colaborare de la o companie de "
            "contabilitate. Invitația nu produce niciun acces până când nu o "
            "acceptați."
        ),
    ),
    "engagement.accepted": Message(
        subject="Colaborarea a fost acceptată",
        body="Colaborarea a fost acceptată și este activă.",
    ),
}


class UnknownMessageError(KeyError):
    """A dispatch named a message that is not in the catalogue."""


def render(type_key: str, params: dict[str, object]) -> tuple[str, str]:
    """Subject and body for one notification.

    Rendering happens at read time, not at write time -- see the module docstring
    on `Notification`. A missing substitution raises here rather than producing a
    sentence with a hole in it.
    """
    try:
        message = CATALOGUE[type_key]
    except KeyError:
        raise UnknownMessageError(type_key) from None
    return message.subject.format(**params), message.body.format(**params)
