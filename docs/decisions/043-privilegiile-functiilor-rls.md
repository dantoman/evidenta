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

## 5. Inversele corectate — `OD-64`

Cele opt fișiere nu se repară prin editare: `C31` le face append-only din clipa aplicării. Corecția
sunt **opt fișiere noi**, `0042`–`0049`, iar `run_sql_file` primește un `down_name` care le indică.
Direcția de dus nu se schimbă deloc — același fișier, aceeași amprentă. Se schimbă doar din ce fișier
se citește inversul, iar acel invers **nu rulase niciodată**, deci nu se falsifică niciun istoric.

Patru lucruri sunt parte din contract, nu detalii de stil:

- **Ordinea: triggere, apoi politici, apoi funcții.** Verificată de test, fiindcă la patruzeci de
  linii nu se mai vede la review și se manifestă abia când cineva chiar derulează înapoi.
- **Fără `CASCADE`.** Un `CASCADE` nu se oprește la ce a creat migrarea: poate șterge obiecte
  atașate între timp de altă migrare, tăcut, raportând succes. Dacă un `DROP` cade pe dependență,
  eroarea e informație.
- **Rotația se testează sub rolul care o va rula** — `evidenta_owner`, prin conexiunea de migrare.
  Rulată ca superuser ar trece întotdeauna și ar eșua în producție: verde din motivul greșit.
- **Rotație, nu inversare:** `down`, apoi `up` din nou, cu catalogul comparat înainte și după. „N-a
  aruncat" nu e afirmația; „baza e unde a plecat" este. A doua aplicare prinde funcția rămasă,
  numele de politică ciocnit, triggerul orfan.

Plus proba că reparația era necesară: un test asertează că inversul **original** încă eșuează cu
„must be owner of function". Fără el, nimic n-ar distinge „am reparat un defect" de „am rescris un
fișier care mergea".

### 5.1 De ce `0028` e reversibil, și de ce motivul evident e greșit

`0028_auth_request_path` e singura dintre cele opt care transformă date: adaugă `token_hash` și umple
rândurile existente. Argumentul tentant — *„șterge doar datele pe care el le-a creat"* — e adevărat
azi și **se rupe tăcut**: din clipa în care producția scrie token-uri reale, inversul șterge date pe
care nu le-a creat el. Cine aplică peste un an raționamentul „date auto-create" unei coloane care nu
e efemeră ajunge la concluzia greșită.

Motivul real este **regenerabilitatea**: o amprentă de token e efemeră prin natură. Nu se pierde
informație, se pierd sesiuni. Consecința operațională e scrisă în fișier fiindcă cine derulează
înapoi în producție trebuie s-o știe dinainte: **toată lumea se deloghează.**

### 5.2 Recidiva

Orice migrare care atinge `journal_entry`, `journal_line` sau perioadele declară
`REVERSIBILITY = "reversible-tested"` sau `"irreversible"`. **Niciodată niciuna, niciodată `noop`** —
un `noop` rulează, nu eșuează, și lasă baza într-o stare pe care n-a descris-o nimeni; într-un
registru append-only e mai rău decât o eroare, fiindcă descoperirea vine mult mai târziu.

Gardianul acceptă **ambele** declarații: ireversibilitatea forțată acolo unde ceva e reversibil de
drept e o minciună la fel de dăunătoare ca `noop`-ul pe ceva ireversibil, doar în direcția opusă. Iar
`"reversible-tested"` nu e o etichetă: gardianul cere ca fișierul să fie în lista rotită efectiv.

## 6. Ce rămâne deschis

`OD-64` este **închisă** prin §5. Ce rămâne din ea e doar constatarea generală care a produs-o: o
migrare inversă nu e exercitată de nimic, iar `C30` cerea existența fișierului, nu funcționarea lui.

## 7. De ce nu s-a văzut

Aceeași formă ca restul constatărilor din 25–26 august: **SQL-ul a rulat, nimic n-a strigat, efectul
n-a existat.** Gardianul de model verifică tabele și politici, nu setări de privilegii; harness-ul
construiește baza de la zero, deci reproduce fidel aceeași stare greșită la fiecare rulare; iar
migrările inverse nu sunt exercitate niciodată — o derulare înapoi e lucrul de care ai nevoie în ziua
în care restul a mers deja prost.
