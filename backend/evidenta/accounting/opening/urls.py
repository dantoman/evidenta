"""Routes for the opening balances.

The company is a path segment on creation because a batch belongs to a company;
after that the batch's own id is enough, and RLS decides whether this context can
see it. The tenant is never in the path (`C8`) -- it is the host the browser is
already on.

``validation`` and ``posting`` are nouns, not verbs: they are the states being
created, and a POST that creates one reads the same as every other POST here.
"""

from django.urls import path

from evidenta.accounting.opening import views

app_name = "opening"

urlpatterns = [
    path(
        "companies/<uuid:company_id>",
        views.BatchListView.as_view(),
        name="batches",
    ),
    path("<uuid:batch_id>", views.BatchDetailView.as_view(), name="batch"),
    path("<uuid:batch_id>/rows", views.BatchRowsView.as_view(), name="batch-rows"),
    path(
        "<uuid:batch_id>/validation",
        views.BatchValidationView.as_view(),
        name="batch-validation",
    ),
    path(
        "<uuid:batch_id>/posting",
        views.BatchPostingView.as_view(),
        name="batch-posting",
    ),
]
