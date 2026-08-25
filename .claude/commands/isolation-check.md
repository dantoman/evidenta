---
description: Run both tenant isolation suites under the application role and report
---

Run the two isolation suites and report the result honestly. This is the check that stands between
the product and a cross-tenant data leak; a green run that was not actually green is worse than a
red one.

## 1. Confirm the role first

Both suites must run under the **application database role**, never as superuser or as the table
owner. A suite running as owner bypasses RLS entirely and passes for the wrong reason.

Before running anything, verify which role the test configuration uses. If you cannot confirm it
from the configuration, stop and say so — do not run the suites and report a result you cannot
trust.

## 2. Run

```
make isolation-check
```

If the target is not implemented yet, run the suites directly:

- `backend/tests/isolation/` — suite 1, penetration
- `backend/tests/schema_guard/` — suite 2, model guard

## 3. Suite 1 — penetration

Authenticated as Tenant A, every resource type of Tenant B must be unreachable: invoices, journal
entries, payroll, attachments, API objects, read models.

Confirm the four cases that are easy to forget are present and passing, and name them individually
in your report:

- engagement expired
- engagement revoked
- engagement with restricted scope
- Celery task with no context set — must fail, not return data

A suite that passes without containing these cases has not been run properly. If any of the four is
missing, report it as a gap in coverage, not as a pass.

## 4. Suite 2 — model guard

It enumerates every table in the schema and fails when one lacks a tenant context column, an active
RLS policy, or `FORCE ROW LEVEL SECURITY`.

If it fails on a table that is legitimately global, the fix is **not** to add the table to the
exception list on your own judgement. The limitative list is fixed in `docs/specs/spec-a-tenancy.md`
and changing it is a decision. Report it and stop.

## 5. Report

```
## Isolation check

Database role: <role> — confirmed | NOT CONFIRMED

Suite 1 — penetration: PASS | FAIL (N failures)
  expired engagement:     covered/pass | covered/fail | not covered
  revoked engagement:     covered/pass | covered/fail | not covered
  restricted scope:       covered/pass | covered/fail | not covered
  Celery without context: covered/pass | covered/fail | not covered

Suite 2 — model guard: PASS | FAIL (N tables)
  <table> — what it lacks

Verdict: isolation holds | isolation is broken by <what> | result not trustworthy because <what>
```

Never adjust a test to make the suite pass. If production code is wrong, the suite is right.
