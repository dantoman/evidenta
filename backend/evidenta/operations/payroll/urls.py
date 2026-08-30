"""Payroll routes -- `/api/v1/payroll/`.

The company is a path segment wherever a collection belongs to a company: the
legal employer is the company, so a list of people or of contracts is *of* one
(ADR-065 section 4). Once an entity exists its own id is the whole address, and
RLS decides whether this context may see it -- the same shape as the opening
batches.

The tenant never appears (`C8`): it is the host the browser is already on.
"""

from django.urls import path

from evidenta.operations.payroll import views

app_name = "payroll"

urlpatterns = [
    path(
        "companies/<uuid:company_id>/employees",
        views.EmployeeListView.as_view(),
        name="employees",
    ),
    path("employees/<uuid:employee_id>", views.EmployeeDetailView.as_view(), name="employee"),
    path(
        "companies/<uuid:company_id>/contracts",
        views.ContractListView.as_view(),
        name="contracts",
    ),
    path("contracts/<uuid:contract_id>", views.ContractDetailView.as_view(), name="contract"),
    path(
        "contracts/<uuid:contract_id>/amendments",
        views.AmendmentListView.as_view(),
        name="amendments",
    ),
    path(
        "contracts/<uuid:contract_id>/termination",
        views.ContractTerminationView.as_view(),
        name="contract-termination",
    ),
    # "What was in force on date D" is a read of the series, and the date is a
    # query because it is a question the reader asks each time, not a property of
    # the contract.
    path(
        "contracts/<uuid:contract_id>/clauses",
        views.ContractClausesView.as_view(),
        name="contract-clauses",
    ),
    path(
        "companies/<uuid:company_id>/timesheets",
        views.TimesheetListView.as_view(),
        name="timesheets",
    ),
    path("timesheets/<uuid:timesheet_id>", views.TimesheetDetailView.as_view(), name="timesheet"),
    path(
        "timesheets/<uuid:timesheet_id>/contracts/<uuid:contract_id>/days",
        views.TimesheetDaysView.as_view(),
        name="timesheet-days",
    ),
    path(
        "timesheets/<uuid:timesheet_id>/closing",
        views.TimesheetClosingView.as_view(),
        name="timesheet-closing",
    ),
    # Exemptions hang off the person, not off a company: the application is
    # theirs, and point 18 dates it. `on` is a query because "what was in force
    # in March" is a question asked each time, not a property of the row.
    path(
        "employees/<uuid:employee_id>/dependents",
        views.DependentListView.as_view(),
        name="dependents",
    ),
    path(
        "employees/<uuid:employee_id>/exemptions",
        views.ExemptionListView.as_view(),
        name="exemptions",
    ),
    path(
        "employees/<uuid:employee_id>/exemptions/withdrawal",
        views.ExemptionWithdrawalView.as_view(),
        name="exemption-withdrawal",
    ),
    # Point 18 computed on the server. A client that derived it would be a second
    # implementation of the rule, drifting the first time only one is edited.
    path(
        "exemption-effective-date",
        views.ExemptionEffectiveDateView.as_view(),
        name="exemption-effective-date",
    ),
    # The vocabulary the contract form needs. Read-only, and it is the fiscal
    # table rather than a copy: a second list in the interface is a second list
    # that drifts.
    path("relationship-types", views.RelationshipTypeListView.as_view(), name="relationship-types"),
]
