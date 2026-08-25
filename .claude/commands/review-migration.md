---
description: Full review chain for a database migration, before it is committed
argument-hint: <migration-path> (optional; defaults to migrations in the working tree)
---

Review the migration `$1`. If no argument is given, find every uncommitted migration under
`backend/evidenta/*/migrations/` and every uncommitted SQL file under `infra/migrations/`, and
review all of them together — a Django migration and the RLS policy that protects its tables are
one change, not two.

## 1. Establish what the migration does

Read it. Then read the models it derives from, and the previous migration in the same app. Write a
short factual summary before delegating: which tables are created, which columns are added or
dropped, which constraints and indexes appear, which tables gain or lack an RLS policy.

Do not delegate on the basis of the filename. The agents will read the files, but they need to know
which decision the migration implements and what it is supposed to achieve — they do not see this
conversation.

## 2. Delegate

**schema-reviewer** — always. Give it: the migration paths, the model paths, and one sentence on
what the change is for. Ask it to pay attention to the points that apply here (incoming foreign
keys on append-only tables, partition columns, index leading order, additive-only discipline,
primary key types, RLS coupling).

**tenancy-guard** — always. Give it the same paths plus any queryset, task or endpoint code that
changed alongside.

**accounting-reviewer** — if any table touched holds accounting data: journal entries, journal
lines, accounting events, periods, opening balances, posting rules.

**fiscal-reviewer** — if any table touched holds fiscal parameters, registry entries, declaration
data or payroll results.

## 3. Judge the findings

- Every CRITICAL blocks the commit. Fix it, then re-run the affected agent on the corrected files.
- Every WARNING gets an explicit decision from you: fix now, or record why not.
- Every OPEN DECISION reported by an agent goes into `docs/decisions/000-open-decisions.md` if it
  is not already there. It does not get resolved by picking the plausible option.

## 4. Check the two things agents cannot see

- **Reversibility.** Does the migration drop or rewrite anything holding financial data? If yes, an
  approved archival plan must be referenced in the docstring (C5). No plan means no commit.
- **Ordering.** Will the new table be reachable by application code before its policy is applied?
  If the answer is yes for even one deploy step, the change is unsafe as sequenced.

## 5. Report

```
## Migration review — <paths>

What it does: <2-3 lines>

schema-reviewer:      N critical, N warning
tenancy-guard:        N critical, N warning
accounting-reviewer:  N critical, N warning | not applicable
fiscal-reviewer:      N critical, N warning | not applicable

Resolved: <what you fixed>
Accepted with reason: <warnings you chose not to fix, and why>
New open decisions recorded: <references>

Verdict: safe to commit | blocked by <what>
```
