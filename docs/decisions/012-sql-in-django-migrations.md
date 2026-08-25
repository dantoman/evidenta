# ADR-012 — SQL-ul de politici trăiește în migrațiile Django

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `OD-18`
- **Afectează:** F0.1.6, F0.2.2, fiecare sarcină din F0.3–F0.7 care creează o tabelă

## Context

Două surse de schemă trebuie să ajungă în aceeași bază, în ordine deterministă: migrațiile Django
(tabele, coloane, indici, constrângeri) și SQL-ul pe care Django nu îl poate exprima (roluri,
`ENABLE` / `FORCE ROW LEVEL SECURITY`, politici, granturi).

## Opțiuni evaluate

1. **SQL în interiorul migrațiilor Django**, prin `RunSQL` care aplică fișiere din
   `infra/migrations/`. O comandă, o ordine, o tranzacție.
2. **Runner separat, după `migrate`.** Fișierele rămân artefactul principal, lizibile cap-coadă.
3. **Unealtă de migrare SQL independentă**, cu tabelă de versiuni proprie.

## Decizie

**Opțiunea 1.**

### Argumentul decisiv: atomicitatea la eșec parțial

Dacă `migrate` reușește și un runner de politici eșuează la al treilea fișier, baza rămâne
într-o stare pe care nimeni nu a proiectat-o: tabele noi, politici pe jumătate. Cu opțiunea 1,
tranzacția se derulează înapoi și starea rămâne coerentă.

**Acesta este câștigul care nu se poate obține prin disciplină.** Un proces poate fi respectat
perfect și tot să lase baza inconsistentă, pentru că eșecul nu e o chestiune de rigoare, ci de
moment.

### Al doilea argument: o singură istorie de migrare

Cu opțiunile 2 sau 3, întrebarea „la ce versiune e baza asta" are două răspunsuri, care pot diverge.
Într-un sistem contabil unde se restaurează medii, se clonează producția în staging și se depanează
clienți, un singur număr de versiune valorează mult.

### Un argument pe care NU ne sprijinim

Formularea inițială punea pe primul loc *fereastra de nesecuritate la deploy* — intervalul în care
tabela există fără politică. Argumentul este mai slab decât pare: într-un deploy corect, tabela nouă
nu are date, iar codul care o folosește nu e încă în producție. **Fereastra e reală, dar goală.**

Se consemnează pentru ca nimeni să nu reconstruiască decizia pe el și să tragă concluzii greșite
când contextul se schimbă.

## Prețul real: imutabilitatea migrațiilor

O migrare Django este o **înregistrare a ce s-a aplicat**. Un `RunSQL` care citește un fișier de pe
disc rupe această proprietate: dacă cineva editează fișierul SQL după ce migrarea a rulat undeva,
migrarea aplicată și fișierul curent nu mai corespund — iar `migrate` nu observă, pentru că el ține
minte doar *că* migrarea a rulat.

Trei corectări, toate ieftine:

**1. Hash-ul fișierului în migrare.** Migrarea conține suma de control SHA-256 a SQL-ului pe care
l-a aplicat și eșuează dacă fișierul s-a schimbat. Transformă o eroare tăcută într-una zgomotoasă.

Verificarea se face la **încărcarea modulului de migrare** — adică oriunde Django construiește
graful de migrări. **Măsurat pe Django 5.2.17:**

| Comandă | Declanșează garda |
|---|---|
| `migrate`, `migrate --plan`, `makemigrations`, `showmigrations`, `sqlmigrate` | **da** |
| `check`, `shell`, `runserver` | **nu** — nu încarcă migrările |
| suita de teste | **da** — harness-ul rulează `migrate` |

*(Formularea inițială a acestei secțiuni spunea „orice `manage.py` o declanșează". Este greșită și
s-a corectat aici după măsurare: `check` nu încarcă graful de migrări.)*

Consecința practică nu se schimbă: fișierul editat este prins la prima operațiune de migrare și în
CI. Consecința care se schimbă: **nu** te poți baza pe `check` ca poartă rapidă.

**2. Fișierele SQL sunt append-only.** Odată referite de o migrare aplicată, nu se editează.
Corecția este un fișier nou și o migrare nouă. **Aceeași regulă ca pentru ledger, din același
motiv:** ce s-a aplicat s-a aplicat, iar corectarea istoriei ascunde ce s-a întâmplat.

**3. `reverse_sql` obligatoriu.** Nicio migrare care creează o politică nu se comite fără
instrucțiunea care o retrage. Structural: helperul cere pereche `.up.sql` / `.down.sql` și refuză
migrarea dacă a doua lipsește. Verificabil de `schema-reviewer`.

## Granița: ce NU intră în ciclul de migrare

PostgreSQL are DDL tranzacțional, dar nu peste tot. Rolurile sunt operațiuni de cluster, nu de
schemă; `CREATE INDEX CONCURRENTLY` nu rulează în tranzacție (în Django: `AddIndexConcurrently` cu
`atomic = False`).

Granița este o **locație**, nu o convenție:

| Director | Conținut | Aplicat de |
|---|---|---|
| `infra/bootstrap/` | roluri, schemele `app` și `rls`, funcțiile de context, predicatele de acces | pas separat, înainte de `migrate`; fișiere idempotente, reaplicate integral |
| `infra/migrations/` | per tabelă: `ENABLE` + `FORCE ROW LEVEL SECURITY`, politici, granturi | `RunSQL` din migrațiile Django |

Setul de bootstrap nu are istorie de versiuni proprie pentru că **toate fișierele lui sunt
idempotente** și se reaplică în întregime. Fără asta, ar reapărea exact cele două istorii pe care
decizia le evită.

Predicatele stau în bootstrap pentru că fiecare politică din fiecare migrare le referă: trebuie să
existe înaintea tuturor.

## Ordinea în interiorul unei migrări

Obligatorie, în aceeași migrare:

```
CREATE TABLE
  → ALTER TABLE ... ENABLE ROW LEVEL SECURITY
  → ALTER TABLE ... FORCE ROW LEVEL SECURITY
  → CREATE POLICY ...
  → GRANT ...
```

Scrisă aici, `schema-reviewer` o poate verifica mecanic. Nescrisă, ar fi rămas convenție.

## Consecințe

**Devine posibil:** F0.1.6, și prin el fiecare sarcină din F0.3–F0.7 care creează o tabelă.

**Efect secundar care merită numit:** gardianul de model (suita 2) devine **plasă de siguranță, nu
singura garanție**. Structura asigură că tabela și politica apar împreună; gardianul rămâne pentru
cazul în care cineva ocolește tiparul. Cele două se întăresc reciproc — și este prima dată în acest
proiect când o garanție de securitate nu depinde de disciplină.

**Ce trebuie modificat:**

- `backend/evidenta/platform/rls/sql.py` — helperul cu verificare de hash și pereche up/down
- `infra/migrations/README.md`, `infra/bootstrap/README.md`
- `.claude/agents/schema-reviewer.md` — patru verificări noi
- `CLAUDE.md` — `C30`, `C31`
- backlog F0.1.6

**Ce se verifică automat:**

| Verificare | Unde |
|---|---|
| hash-ul fișierului corespunde cu cel din migrare | la încărcarea migrării, la fiecare `manage.py` |
| fiecare `RunSQL` are `reverse_sql` | `schema-reviewer` + helperul, structural |
| `CREATE ROLE` / `ALTER ROLE` / `CREATE SCHEMA` nu apar în afara `infra/bootstrap/` | `schema-reviewer` |
| ordinea tabelă → RLS → politici → granturi în aceeași migrare | `schema-reviewer` |
| fișier SQL referit de o migrare aplicată, modificat ulterior | hash, la încărcare |

## Surse

- `000-open-decisions.md`: `OD-18`
- [ADR-003](003-rls-tenancy-tables.md) — de ce predicatele stau în bootstrap
- `CLAUDE.md` R2, R10 *(imutabilitatea, aceeași regulă ca pentru ledger)*
