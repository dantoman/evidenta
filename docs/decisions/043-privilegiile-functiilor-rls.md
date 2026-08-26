# ADR-043 — Operațiile pe obiectele lui `evidenta_rls` se fac sub rolul lui

- **Status:** Acceptat — decizie tehnică, sub regimul [ADR-002](002-guvernanta-deciziilor.md);
  proprietarul a cerut implementarea după ce defectul a fost măsurat
- **Data:** 2026-08-26
- **Închide:** defectul de privilegii; deschide `OD-64` pentru partea care nu se poate repara
- **Afectează:** `infra/bootstrap/0001_roles.sql` (`NOINHERIT`), fiecare migrare care creează o
  funcție în schema `rls`, `C30`, `C31`
- **Legate:** [ADR-003](003-rls-tenancy-tables.md) (rolul `evidenta_rls`),
  [ADR-012](012-sql-in-django-migrations.md), [ADR-026](026-autentificare-inainte-de-context.md)

## 1. Problema, care are o singură cauză și două fețe

`evidenta_owner` este `NOINHERIT`. Apartenența la `evidenta_rls` **nu îi dă privilegiile** decât
după un `SET ROLE` explicit — și asta e corect: exact de aceea rolul cu `BYPASSRLS` e separat.

Migrările care creează funcții în schema `rls` fac însă așa:

```sql
SET LOCAL ROLE evidenta_rls;
CREATE FUNCTION rls.x() ... SECURITY DEFINER ...;
RESET ROLE;
REVOKE ALL ON FUNCTION rls.x() FROM PUBLIC;   -- emis de OWNER
```

Ultima linie **nu face nimic**. Un `REVOKE` emis de cine nu deține obiectul produce un `WARNING`,
nu o eroare. SQL-ul rulează, migrarea trece, privilegiul rămâne.

Aceeași cauză, a doua față: fișierele `.down.sql` șterg funcțiile ca owner și cad cu
**„must be owner of function"**. `C30` spune că `reverse_sql` nu e opțional — reversul există și nu
rulează.

## 2. Ce s-a măsurat

Pe o bază migrată de la zero, citind `pg_proc.proacl`:

| | |
|---|---|
| funcții în schema `rls` | 25 |
| cu `EXECUTE` pentru PUBLIC | **22** |
| acordate explicit lui `evidenta_app` | 3 |

Printre cele 22: toate cele patru `auth_*` de dinaintea contextului (ADR-026), `resolve_session`,
`resolve_tenant_by_subdomain`, și **ambele căi privilegiate de acces**,
`provision_engagement_company_access` și `revoke_engagement_company_access`.

Demonstrat prin apel, sub rolul aplicației, nu doar din catalog:

- `rls.auth_lookup_user('…')` — **execută**;
- `rls.provision_engagement_company_access('…')` — ajunge la linia 9 din corpul funcției și e oprită
  de garda ei internă, **nu de privilegiu**.

Apărarea era scrisă în migrare, se credea în vigoare, și nu era.

Pentru fețele reversului: `migrate ledger zero` cade. Opt fișiere comise au defectul — `0014`,
`0015`, `0016`, `0023`, `0028`, `0030`, `0032`, `0036`.

## 3. Decizia

**Orice operație asupra unui obiect deținut de `evidenta_rls` — `CREATE`, `DROP`, `GRANT`,
`REVOKE` — se face sub `SET LOCAL ROLE evidenta_rls`.** Nu doar crearea, cum se făcea până acum.

`0041_rls_function_privileges` retrage `EXECUTE` de la PUBLIC pe toate cele 25, de data asta cu
efect, și îl acordă lui `evidenta_app` pe **mulțimea măsurată**: funcțiile apelate din Python
(`grep -r 'rls\.' backend/evidenta/`) reunite cu cele care apar în expresiile politicilor
(`pg_policy`) — o politică se evaluează ca utilizatorul care interoghează. Paisprezece funcții.

Cele unsprezece rămase sunt funcții de trigger sau ajutoare interne. PostgreSQL verifică `EXECUTE`
pe funcția de trigger la `CREATE TRIGGER`, nu la declanșare, deci retragerea nu costă nimic — și
scoate din raza aplicației opt funcții `SECURITY DEFINER` pe care n-avea de ce să le poată apela.

## 4. Prevenirea stă în gardian, nu în schemă — și asta s-a măsurat

`ALTER DEFAULT PRIVILEGES … REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` pare mecanismul evident. **Nu
funcționează aici.** Încercat în ambele forme — cu `REVOKE` singur și cu `GRANT` explicit către
`evidenta_rls` —, în aceeași tranzacție și într-una nouă după commit: o funcție creată ulterior iese
cu ACL implicit, deci din nou cu `EXECUTE` pentru PUBLIC.

Prevenirea o poartă deci `backend/tests/schema_guard/test_function_privileges.py`, care interoghează
catalogul pe o bază construită de la zero la fiecare rulare. Prima migrare care adaugă o funcție fără
să-i retragă PUBLIC-ul face suita roșie. E idiomul proiectului oricum: un gardian, nu o convenție.

Al doilea gardian, `tests/architecture/test_reverse_migrations.py`, refuză orice fișier `.down.sql`
**nou** care șterge o funcție `rls.` fără `SET LOCAL ROLE`. Cele opt existente sunt enumerate ca
excepție care **poate doar să scadă**.

## 5. Ce rămâne deschis

Cele opt fișiere nu se repară prin editare: `C31` le face append-only din clipa în care au fost
aplicate. Corecția e un fișier nou și o migrare nouă, peste șase module — `OD-64`.

## 6. De ce nu s-a văzut

Aceeași formă ca restul constatărilor din 25–26 august: **SQL-ul a rulat, nimic n-a strigat, efectul
n-a existat.** Gardianul de model verifică tabele și politici, nu setări de privilegii; harness-ul
construiește baza de la zero, deci reproduce fidel aceeași stare greșită la fiecare rulare; iar
migrările inverse nu sunt exercitate niciodată — o derulare înapoi e lucrul de care ai nevoie în ziua
în care restul a mers deja prost.
