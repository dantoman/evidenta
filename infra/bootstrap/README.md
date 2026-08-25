# Bootstrap — ce nu intră în ciclul de migrare

Autoritate: [ADR-012](../../docs/decisions/012-sql-in-django-migrations.md).

Aici stau obiectele pe care Django nu le poate deține și care trebuie să existe **înainte** de
prima migrare:

| Fișier | Conținut | De ce nu e migrare |
|---|---|---|
| `0000_locale_guard.sql` | verifică providerul și colația bazei | nu modifică nimic; oprește lanțul dacă baza a fost creată greșit, când asta se mai poate corecta ieftin |
| `0001_roles.sql` | cele trei roluri, granturile pe bază, extensia `citext`, privilegiile implicite | `CREATE ROLE` este operațiune de cluster, nu de schemă. Nu este tranzacțional în același sens și nu se derulează înapoi cu migrarea |
| `0002_app_context.sql` | schemele `app` și `rls`, funcțiile de context | Schema `rls` e deținută de un rol pe care Django nu îl gestionează |
| `0003_access_predicates.sql` | predicatele de acces | Fiecare politică din fiecare migrare le referă, deci trebuie să existe înaintea tuturor |

## Înainte de toate: baza

Colația bazei este decizie „la creare" ([ADR-015](../../docs/decisions/015-colatie-icu.md)) — nu se
schimbă fără reconstruirea indecșilor pe text.

- **Prin docker:** `POSTGRES_INITDB_ARGS` din `docker-compose.yml` configurează clusterul, iar baza
  moștenește. Nimic de făcut.
- **Pe un cluster existent:** `make create-db`, sau direct
  `CREATE DATABASE evidenta LOCALE_PROVIDER icu ICU_LOCALE 'ro' TEMPLATE template0;`

`0000_locale_guard.sql` verifică rezultatul și oprește lanțul dacă e greșit. Nu e ceremonie: o bază
cu colația greșită funcționează perfect și sortează greșit pentru totdeauna.

## Regulile care fac setul sigur

1. **Toate fișierele sunt idempotente.** Se aplică integral, în ordine, la fiecare rulare. De aceea
   setul nu are nevoie de o istorie de versiuni proprie — ceea ce ar reintroduce exact problema pe
   care ADR-012 o evită.
2. **Se aplică înainte de `migrate`**, printr-un pas separat, o singură comandă: `make bootstrap`.
   `0000` și `0001` rulează ca **superuser**; `0002` și `0003` ca **`evidenta_owner`**. Owner-ul
   primește `CREATE` pe bază în `0001` — fără el nu poate crea schemele `app` și `rls`.
3. **Nimic din ce e per-tabelă nu intră aici.** `ENABLE` / `FORCE ROW LEVEL SECURITY`, politicile și
   granturile pe tabele stau în `../migrations/`, referite din migrațiile Django, ca să ajungă în
   aceeași tranzacție cu tabela.

## Granița, spusă invers

Dacă cineva adaugă un rol nou într-o migrare Django, va descoperi la primul rollback că nu se
derulează înapoi. De aceea granița este o **locație**, nu o convenție: `schema-reviewer` verifică
mecanic că `CREATE ROLE`, `ALTER ROLE` și `CREATE SCHEMA ... AUTHORIZATION` nu apar în afara acestui
director.
