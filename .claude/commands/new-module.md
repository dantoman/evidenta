---
description: Scaffold a new module according to project conventions, with RLS policy, tests and review chain
argument-hint: <module-path> (e.g. platform/audit, masterdata/partners)
---

Scaffold the module `$1` in `backend/evidenta/`, following the conventions in `CLAUDE.md`.

## 1. Refuse early if it should not exist yet

Read `docs/PROGRESS.md` and `docs/_bootstrap/06-f0-backlog.md`.

- If `$1` belongs to a later phase than the current one, stop and say so. "Modelled in F0" does not
  mean "create the app now" — it means the current phase's schema must not make the future module
  impossible.
- If a task in the backlog names `$1` and lists blocking open decisions, read
  `docs/decisions/000-open-decisions.md`. If any of them is still open, stop and report which
  decision blocks what. Do not pick a reasonable-looking option and continue.

## 2. Reconnaissance

Delegate to **repo-explorer**: "Map an existing module of comparable shape in
`backend/evidenta/`, report its file layout, its service entry points, and its dependencies in and
out." Use the result to match the existing structure rather than inventing a new one.

Then read the relevant specification: `docs/specs/spec-a-tenancy.md` for platform, masterdata,
identity and engagement concerns; `docs/specs/spec-b-accounting.md` for ledger, posting, periods,
currency and fiscal logic concerns.

## 3. Create the structure

One Django app per module. No `utils` or `common` catch-alls.

```
backend/evidenta/$1/
├── __init__.py
├── apps.py
├── models.py            structure and constraints only, no business logic
├── services/            the logic lives here
│   └── __init__.py
├── migrations/
└── tests/
```

Rules that apply while writing it, from `CLAUDE.md`:

- every business model carries `tenant_id` (R1) — if `$1` is one of the enumerated exceptions, say
  so explicitly in the model docstring and cite the exception
- the default manager does not filter by tenant (C3)
- no signals for financial logic (C4)
- `UUID` primary keys for externally exposed entities, `bigint` for append-only high-volume tables (C6)
- if `$1` writes anything with a financial effect, it emits an accounting event — it does not touch
  the ledger (R9)

## 4. RLS policy

In the same change, add to `infra/migrations/`:

- `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` on every new table
- the policy for both access paths — member of the tenant, and active engagement of the firm over
  the tenant — in the form fixed by `docs/specs/spec-a-tenancy.md`
- grants for the application role

A table that exists in one commit and gains its policy in the next is unprotected in between. Both
land together.

## 5. Register the dependencies

Add `$1` to the module dependency contracts so D1–D6 are enforced mechanically, not by convention.
If the tooling for that is not in place yet, say so instead of skipping silently.

## 6. Review chain

Delegate in this order, giving each agent the concrete file paths you created and the decision
context — the agents do not see this conversation:

1. **tenancy-guard** — always
2. **schema-reviewer** — if there are migrations
3. **accounting-reviewer** — if the module produces, modifies or consumes a financial effect
4. **fiscal-reviewer** — if it touches rates, contributions, thresholds, declarations or the registry

Resolve every CRITICAL before continuing. Report WARNINGs with your judgement on each.

## 7. Tests

Delegate to **test-author** with the module path and a note of which financial effects exist.
Then run the full suites: `make isolation-check`.

## 8. Close the loop

Update `docs/PROGRESS.md`: what was done, what remains, any new open question. If a decision came
up and was taken, write the ADR in `docs/decisions/`. If one came up and was not taken, add it to
`docs/decisions/000-open-decisions.md` and say so in your final report.
