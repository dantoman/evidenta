# ADR-072 — `R1` cere confirmarea proprietarului doar pentru excepțiile care lărgesc accesul la date

- **Status:** **Acceptat** — **decizie de proces**, luată de proprietar în instrucțiunea de
  continuare din 2026-08-30: *„`R1` se îngustează: aprobarea proprietarului doar pentru excepțiile
  care LĂRGESC ACCESUL LA DATE. Un catalog global doar-citire, însămânțat din migrare, e commit
  obișnuit — `permission` e precedentul din propriul fișier. Decis de proprietar; scrie-o și mergi."*
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** blocajul repetat al lui `C1(b)`; rândul **B1** din
  [`13-lista-de-deblocare.md`](../_bootstrap/13-lista-de-deblocare.md)
- **Afectează:** `CLAUDE.md` `R1`, antetul lui `infra/rls/exceptions.toml`,
  [ADR-003](003-rls-tenancy-tables.md)
- **Legate:** [ADR-003](003-rls-tenancy-tables.md), [ADR-020](020-roluri-ca-date.md),
  [ADR-049](049-rolul-de-date-de-referinta.md), [ADR-071](071-tipurile-de-raport-ca-tabela.md)

## 1. Ce se schimbă, exact

`R1` spunea: **modificarea `infra/rls/exceptions.toml` este ADR.** Fără distincție.

De acum, fișierul are **două feluri de modificări**, și numai unul cere decizia proprietarului:

| | Modificare | Regim |
|---|---|---|
| **(a)** | **Lărgește accesul la date** | ADR, confirmarea proprietarului, ca până acum |
| **(b)** | **Nu lărgește** | **commit obișnuit**, cu `reason` și `source` scrise |

## 2. Linia dintre ele, scrisă ca să fie aplicabilă fără judecată de caz

**(a) — lărgește, deci ADR.** Orice intrare sau modificare care:

- dă rolului de aplicație vizibilitate peste rânduri **care aparțin altui tenant** — adică orice formă
  de politică în afară de `global_read_only`, pentru o tabelă care poartă date de business;
- numește un `writer_role` **care scrie la runtime** (`evidenta_refdata`, sau oricare altul care nu e
  rolul de migrare) — aceea e o cale privilegiată, și fiecare are ADR-ul ei (`P-3` … `P-10`);
- **scoate sau slăbește** o intrare existentă — inclusiv trecerea unei tabele de la `tenant_column =
  true` la `false`, care nu e adăugare, e retragerea unei protecții de pe date care există deja;
- **schimbă forma unei politici** deja aplicate pe o tabelă cu date.

**(b) — nu lărgește, deci commit obișnuit.** O intrare **nouă**, pentru o tabelă **nouă**, care are
toate cele trei proprietăți deodată:

```toml
tenant_column = false
policy_shape  = "global_read_only"
writer_role   = "evidenta_owner"
```

adică: **vocabular sau catalog global, doar-citire pentru aplicație, însămânțat din migrarea care îl
definește**. Plus, nenegociabil: `reason` care spune **ce** e exceptat și **până unde**, și `source`
care trimite la decizia sau la actul din care vine vocabularul.

> **De ce cele trei împreună și nu una câte una:** `tenant_column = false` singur descrie și o tabelă
> globală **scriibilă**, care e cu totul altceva. `global_read_only` singur nu spune cine scrie.
> `writer_role = "evidenta_owner"` singur nu spune că tabela n-are proprietar. **Conjuncția e ce face
> categoria inofensivă**, și de aceea se cere întreagă.

## 3. De ce e corectă, și de ce n-a fost de la început

**Precedentul e în propriul fișier.** `permission` e exact această formă: catalog fix, același pentru
toți, fără coloană de tenant, însămânțat din `identity/0003`, cu politica din `0019`. Intrarea lui
spune singură de ce: *„catalogul e cod (ADR-020) și se însămânțează din migrarea care îl definește …
deci ajunge în bază odată cu deploy-ul, nu printr-o încărcare."*

**Ce apăra `R1` în forma largă:** ca nimeni să nu scoată `tenant_id` de pe o tabelă de business
adăugând un rând într-un fișier de configurare. Apărarea aia rămâne **întreagă** — e clasa (a).

**Ce a costat forma largă, măsurat:** `C1(b)` — un catalog de trei valori, doar-citire, impuse de
lege — s-a oprit **trei sesiuni la rând** pe o confirmare. Trei sesiuni au raportat *„singura oprire
legitimă"* despre aceeași tabelă. **O regulă care oprește de trei ori același commit inofensiv nu
apără nimic acolo; mută doar costul pe proprietar.**

**Și de ce nu s-a văzut mai devreme:** primele trei excepții au fost toate din clasa (a) — căi
privilegiate cu `evidenta_refdata`, unde confirmarea era exact la locul ei. Regula a fost scrisă din
cazurile pe care le avea. Clasa (b) a apărut a doua oară abia acum.

## 4. Ce **nu** se schimbă

- **Fișierul rămâne singurul loc unde trăiește lista.** Nu se duplică în documentație (`R1`, teza
  întâi), și nimeni nu adaugă o tabelă acolo ca să facă suita să treacă.
- **Gardianul de model nu sare peste nimic.** Verifică forma declarată — o tabelă listată cu politică
  lipsă cade la fel de tare ca una nelistată (`R2`).
- **`reason` și `source` sunt obligatorii pe orice intrare**, din ambele clase. `OD-95` numește riscul
  unei excepții nemărginite; îngustarea de aici **nu** îl atinge, fiindcă motivul mărginit e cerut
  independent de cine aprobă.
- **`R21` (`append_only.toml`) nu e atins de acest ADR.** Are aceeași formă și probabil aceeași
  concluzie — rândul **B2** din lista de deblocare o propune —, dar e alt fișier, alt invariant, și nu
  se închide în treacăt.

## 5. Ce ar infirma decizia, scris ca să fie recunoscut

**Un catalog global doar-citire care ajunge totuși să lărgească accesul.** Forma ar fi: o tabelă
declarată `global_read_only` care ține, în rândurile ei, **date derivate din rândurile unui tenant** —
un catalog de coduri care în practică enumeră clienții cuiva. Atunci lipsa lui `tenant_id` nu mai e
o proprietate a vocabularului, e o scurgere.

Dacă apare una, linia din §2 se mută: nu e de ajuns ca tabela să fie doar-citire, trebuie ca
**conținutul** ei să nu provină din date de tenant. Până atunci, criteriul din §2 se aplică așa cum e
scris — un criteriu care anticipează un caz pe care nimeni nu l-a văzut e o regulă validată de nimic.

## 6. Consecințe

- **Devine posibil, azi:** `ADR-071` se acceptă și tabela lui se construiește fără o a patra oprire;
  orice vocabular global viitor (tipuri de document fiscal, coduri de suspendare IRM19, clasificatorul
  funcțiilor) intră ca commit obișnuit.
- **Rămâne imposibil:** o tabelă de business fără `tenant_id`, o cale de scriere la runtime, sau
  retragerea unei protecții existente — toate trei rămân clasa (a).
- **De modificat ca urmare:** `CLAUDE.md` `R1` (textul regulii), antetul lui
  `infra/rls/exceptions.toml` (unde regula e repetată pentru cine deschide fișierul).

## 7. Surse

- Instrucțiunea de continuare a proprietarului, 2026-08-30, citată verbatim în antet.
- `infra/rls/exceptions.toml`, intrarea `permission` — precedentul, cu motivul scris în ea.
- [ADR-020](020-roluri-ca-date.md) (catalogul e cod), [ADR-049](049-rolul-de-date-de-referinta.md)
  (rolul de date de referință și căile privilegiate), [ADR-003](003-rls-tenancy-tables.md) (tabelele
  fără proprietar).
