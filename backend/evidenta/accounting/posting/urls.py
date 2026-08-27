"""Posting routes -- `/api/v1/accounting/entries/`.

One route: the manual note. Every other posting arrives as an accounting event
from the module that produced the economic fact, and has no endpoint of its own
by design (R9).
"""

from django.urls import path

from evidenta.accounting.posting import views

app_name = "posting"

urlpatterns = [
    path("manual", views.ManualEntryView.as_view(), name="manual-entry"),
]
