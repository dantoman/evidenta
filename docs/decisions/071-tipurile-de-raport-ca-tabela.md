# ADR-071 — Tipurile de raport de muncă sunt tabelă de referință, iar domeniul invariantului e cheie străină spre ea

- **Status:** **Propus** — **decizie de domeniu** fiscal *şi* excepţie `R1`, deci cere confirmarea
  proprietarului înainte de implementare. **Tabela nu se construieşte până la `Acceptat`.** Regimul:
  [ADR-002](002-guvernanta-deciziilor.md) cu [ADR-010](010-contabilul-practicant.md)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** jumătatea `C1(b)` din instrucţiunea de execuţie a `F2.B1`
- **Afectează:** `infra/rls/exceptions.toml` (**modificarea lui e ADR — `R1`**), `fiscal/registry`,
  `F2.B1`, `F2.B2`
- **Legate:** [ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3,
  [ADR-070](070-trei-feluri-nu-o-familie.md) §3–§4,
  [ADR-068](068-anexa-citita-categoria-e-a-raportului.md)

> **REZERVĂ NEATINSĂ (`OD-85`):** acest ADR nu afirmă nicio valoare din anexa nr. 1. Foloseşte din ea
> doar **distincţia de tipuri**, care e text citit, nu cifră.

## 1. Ce se decide

**Tipurile de raport de muncă devin o tabelă de referinţă globală**, iar **domeniul unui invariant de
calcul e cheie străină spre ea** — nu enumerare liberă, nu şir.

Vocabularul e **închis şi are exact două valori**, care sunt exact cele pe care actele le disting
azi:

| Cod | Ce e | Ancora |
|---|---|---|
| `employment_contract` | contract individual de muncă | anexa nr. 1 la Legea nr. 489/1999, **pct. 1.1, prima liniuţă** |
| `civil_contract` | contract civil de executare de lucrări / prestare de servicii | idem, aceeaşi liniuţă; **art. 19 alin. (7) teza a doua** |

Textul integral e în [`anexa-1-la-legea-489-1999.md`](../_input/cercetare/anexa-1-la-legea-489-1999.md)
— **nu se re-derivă**.

## 2. Fără „general", fără „altul", fără „nedeterminat"

**O a treia valoare e drumul prin care „invariant aplicat orb" reintră sub alt nume.**

Invariantul art. 22 alin. (1) se aplică *„pentru fiecare **salariat**"*
([ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3). Un domeniu numit `general` sau `orice` ar
face din aplicarea lui pe contracte civile o **valoare acceptată**, nu o greşeală — iar rezultatul e
cel măsurat acolo: datoria umflată la salariul minim, **perfect echilibrată**, deci `R11` trece şi
niciun test de sold n-o vede.

**E simetricul exact al rezervei din `OD-93`**, unde a treia valoare a lui `MarginBasis` ar fi fost
drumul prin care „margine fără sursă" reintră. Acolo interdicţia e pe *sursă*, aici pe *domeniu*;
forma e aceeaşi.

**Dacă apare nevoia unei a treia valori, e rând nou în registru** — o decizie explicită, nu o
adăugire la o listă.

## 3. De ce cheie străină şi nu enumerare

Cu **şir sau enum deschis**, cineva scrie `orice_bază_CAS` şi defectul e înapoi: **vizibil, dar
înapoi**. Cu **cheie străină**, un domeniu inexistent e **violare de cheie străină** — nu ajunge în
bază deloc.

> **Structura nu ia decizia** ([ADR-070](070-trei-feluri-nu-o-familie.md) §4). Ce face e că **mută
> alegerea greşită din tăcere într-un diff**: un domeniu **greşit** se citeşte, se caută şi apare la
> revizie; unul **inexistent** nu apare nicăieri.

## 4. Ce se atinge din `exceptions.toml`, şi de ce nu se putea evita

Tabela e **globală**: vocabularul e al actelor, acelaşi pentru toţi tenanţii, deci **n-are
`tenant_id`**. `R1` cere ca fiecare tabelă business să aibă unul, iar excepţiile să fie **enumerate
limitativ** în `infra/rls/exceptions.toml` — **modificarea fişierului e ADR**. Acesta e ADR-ul.

Intrarea propusă, pe tiparul lui `permission`, care e precedentul exact — catalog fix, acelaşi pentru
toţi, însămânţat din migrarea care îl defineşte:

```toml
[[table]]
name = "employment_relationship_type"
tenant_column = false
policy_shape = "global_read_only"
writer_role = "evidenta_owner"
```

**De ce nu se putea evita, formulat cu grijă:** un `tenant_id` aici ar însemna că un tenant poate avea
alte tipuri de raport decât altul, ceea ce e fals **în interiorul unei jurisdicţii**. Şi atât spune —
nici mai mult.

> **Tabela e globală fiindcă produsul deserveşte o singură jurisdicţie. A doua jurisdicţie redeschide
> decizia.** Tipurile nu sunt universale: sunt cele pe care le distinge dreptul Republicii Moldova azi.
>
> **Şi dimensiunea care apare atunci nu e tenantul, e jurisdicţia.** Merită spus acum, fiindcă o
> formulare de tipul *„distincţia e a legii"* pare să excludă subiectul, iar cine îl deschide peste doi
> ani ar găsi o afirmaţie care îi spune că nu e nimic de discutat. **Amânare cu condiţia de siguranţă
> numită** — altfel e indistinctă de neglijenţă.

Iar fără tabelă, domeniul redevine şir, adică §3.

### 4.1 Rândul din `exceptions.toml` îşi poartă justificarea, mărginit

`OD-95` numeşte tocmai riscul unei excepţii nemărginite. Deci intrarea nu se adaugă tăcut: câmpul
`reason` spune **ce anume** e exceptat şi **până unde** — *vocabular de două valori impus de lege,
acelaşi pentru toţi tenanţii unei jurisdicţii, însămânţat din migrare ca `permission`; nu se extinde la
alte tabele ale modulului*. Iar `source` trimite la acest ADR, ca excepţia să nu poată fi citită fără
decizia care a sancţionat-o.

## 4bis. Cheia străină e `NOT NULL` — altfel exerciţiul se pierde

**Decizie, nu detaliu de schemă.** Dacă domeniul unui invariant e nullable, *„fără domeniu"* redevine
exprimabil — iar `NULL` s-ar citi, inevitabil, ca *„se aplică oriunde"*. Adică exact `orice_bază_CAS`,
sub alt nume, obţinut prin omisiune în loc de alegere.

Un invariant fără domeniu nu e o stare validă: **art. 22 se aplică raporturilor de muncă, şi asta e o
proprietate a lui, nu o configurare.** Deci coloana e `NOT NULL`, **fără implicit** — pe acelaşi tipar
ca `source_confidence`: *un implicit ar lăsa rândul să ajungă fără ca nimeni să fi decis*.

## 4ter. Tabela **nu** poartă margini, şi iată de ce

`OD-89` face din starea datată implicitul, deci absenţa marginilor e o **excepţie care se
argumentează**, nu una care se tace.

Tipurile sunt derivate din lege, iar legea se schimbă — pct. 1.8 a fost abrogat, deci un tip *poate*
dispărea. Şi totuşi:

> **Nimic nu rezolvă un tip după dată.** Ce se rezolvă după dată e **ce referă un tip** — domeniul unui
> invariant, care e versionat în registrul de logică, cu `valid_from`-ul lui. Întrebarea *„ce spunea
> domeniul invariantului în martie"* e a invariantului; întrebarea *„ce tipuri existau în martie"* nu e
> pusă de nimic.

Consecinţele, ca decizia să fie completă:

- **rândurile nu se şterg niciodată** — un tip abrogat rămâne, cu cheia străină `PROTECT`, ca
  referinţele istorice să rezolve;
- **apariţia unui al treilea tip e un rând nou**, plus decizia din §2, nu o modificare de margine.

**Ce ar infirma decizia, scris ca să fie recunoscut:** primul consumator care are nevoie de *„ce tipuri
existau la data D"*. Dacă apare, tabela primeşte margini şi acest paragraf se retrage.

**`writer_role = "evidenta_owner"`, nu `evidenta_refdata`:** vocabularul e **cod**, nu date de
referinţă încărcabile — se însămânţează din migrarea care creează tabela şi ajunge în bază odată cu
deploy-ul, exact ca `permission`. Datele de referinţă se încarcă prin `P-4`; un vocabular de două
valori impuse de lege nu se încarcă, se defineşte.

## 5. Unde stă tabela, şi de ce nu în `payroll`

În **`fiscal`**. Motivul e `D1`: `fiscal` nu importă din niciun modul business, deci dacă domeniul
unui invariant fiscal ar arăta spre o tabelă din `operations/payroll`, dependenţa ar fi interzisă.
Invers e permis — `operations` depinde de `fiscal` —, deci `payroll` va referi tabela fără să încalce
nimic.

Şi e coerent pe fond: **distincţia e făcută de acte fiscale**, nu de dreptul muncii. Art. 22 spune
„salariat"; art. 19 alin. (7) spune „contracte civile". Amândouă sunt din Legea nr. 489/1999.

## 6. Limitarea, declarată acum ca să nu fie descoperită ca surpriză

> **Reziduul rămâne „a ales greşit dintre două tipuri reale", nu „n-a ales".**

Cineva poate lega invariantul art. 22 de `civil_contract` şi defectul e înapoi. Cheia străină nu
împiedică asta — **îngustează de la „orice şir" la „un tip care există"**, şi atât poate face
structura.

Ce se câştigă totuşi e verificabilitatea: o legare greşită e **un rând care se citeşte** şi apare
într-un diff, pe când un domeniu inexistent — sau absent — nu apare nicăieri. `ADR-070` §4 numeşte
diferenţa: *„a ales greşit"* se prinde citind; *„n-a ales"* nu are ce fi citit.

## 7. Ce **nu** decide acest ADR

- **Forma declarării domeniului pe versiunea de logică.** Nu toată logica fiscală are domeniu de
  raport — rotunjirea monetară n-are. Dacă domeniul stă pe `fiscal_logic_version`, pe o tabelă de
  legătură, sau pe entitatea invariantului, **se decide la `F2.B2`**, unde invariantul are consumator
  real. Proiectat aici, ar fi o schemă validată de nimic — chiar defectul pe care instrucţiunea `C2` îl
  numeşte.
- **Dacă tipurile primesc atribute** (coloana (d) a anexei — prestaţiile asigurate diferă pe puncte).
  Azi tabela e vocabular; dacă devine purtătoare de drepturi, e altă decizie.

## 8. Consecinţe

- **Devine posibil, după `Acceptat`:** `C1(b)`, apoi `C2`, apoi restul `F2.B1`.
- **Devine imposibil:** un domeniu de invariant care nu corespunde niciunui tip real.
- **De modificat ca urmare:** `infra/rls/exceptions.toml` (o intrare), `fiscal` (tabela şi
  însămânţarea ei), `F2.B1` (legarea), `F2.B2` (invariantul art. 22 cu domeniul lui).
- **Nu se implementează nimic până la `Acceptat`** — `R1` face din asta o condiţie, nu o preferinţă.

## 9. Surse

- Anexa nr. 1 la Legea nr. 489/1999, **pct. 1.1 prima liniuţă**, şi **art. 19 alin. (7) teza a doua** —
  text integral în [`anexa-1-la-legea-489-1999.md`](../_input/cercetare/anexa-1-la-legea-489-1999.md),
  obţinut de proprietar 2026-08-30.
- **Art. 22 alin. (1)** — *„pentru fiecare salariat"*, prin
  [ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3.
- `CLAUDE.md` `R1`, `D1`, `C2`, `C6`; `infra/rls/exceptions.toml`, intrarea `permission` ca precedent.
- [ADR-070](070-trei-feluri-nu-o-familie.md) §3–§4 (coloană în loc de gardian; plafonul structurii),
  `OD-93` (simetricul, pe sursă).
