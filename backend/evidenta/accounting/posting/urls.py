"""Posting routes -- `/api/v1/accounting/entries/`.

Two ways in, and they are the same way: a manual note, and the operation template
that expands into one. Every other posting arrives as an accounting event from
the module that produced the economic fact, and has no endpoint of its own by
design (`R9`).

The templates hang off `entries/` rather than getting a prefix of their own
because that is what they are -- a shortcut to an entry, layer 4 of ADR-036
section 7, not a second kind of posting. A separate prefix would suggest a
separate path into the ledger, and there is not one.
"""

from django.urls import path

from evidenta.accounting.posting import views

app_name = "posting"

urlpatterns = [
    path("manual", views.ManualEntryView.as_view(), name="manual-entry"),
    # The entry is in the path because the correction is *of* it; the reason and
    # the correction's own date are in the body, because they are new facts
    # rather than identifiers.
    path(
        "<uuid:entry_id>/reversal",
        views.ReverseEntryView.as_view(),
        name="reverse-entry",
    ),
    # The company is in the path (`C8`); the template's id identifies it inside.
    path(
        "companies/<uuid:company_id>/templates",
        views.TemplateListView.as_view(),
        name="templates",
    ),
    path(
        "companies/<uuid:company_id>/templates/<uuid:template_id>",
        views.TemplateDetailView.as_view(),
        name="template",
    ),
    path(
        "companies/<uuid:company_id>/templates/<uuid:template_id>/activation",
        views.TemplateActivationView.as_view(),
        name="template-activation",
    ),
    path(
        "companies/<uuid:company_id>/templates/<uuid:template_id>/posting",
        views.TemplatePostingView.as_view(),
        name="template-posting",
    ),
]
