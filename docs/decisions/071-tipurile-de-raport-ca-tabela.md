# ADR-071 — Tipurile de raport de muncă sunt tabelă de referință, iar domeniul invariantului e cheie străină spre ea

- **Status:** **Acceptat** — **decizie de domeniu** fiscal, confirmată de proprietar în
  instrucţiunea de continuare din 2026-08-30, cu **trei corecţii cerute odată cu acceptarea**: a
  treia valoare (`service_relationship`, §1), `reason`/`source` lipsă din fragmentul TOML (§4), şi
  nota despre rolul de însămânţare (§4quater). Regimul:
  [ADR-002](002-guvernanta-deciziilor.md) cu [ADR-010](010-contabilul-practicant.md).
  **Nu mai e excepţie care cere confirmare separată:** intrarea din `exceptions.toml` e din clasa
  care nu lărgeşte accesul ([ADR-072](072-exceptia-care-nu-largeste.md) §2)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** jumătatea `C1(b)` din instrucţiunea de execuţie a `F2.B1`
- **Afectează:** `infra/rls/exceptions.toml` (o intrare, clasa (b) din
  [ADR-072](072-exceptia-care-nu-largeste.md)), `fiscal/registry`, `F2.B1`, `F2.B2`
- **Legate:** [ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3,
  [ADR-070](070-trei-feluri-nu-o-familie.md) §3–§4,
  [ADR-068](068-anexa-citita-categoria-e-a-raportului.md),
  [ADR-072](072-exceptia-care-nu-largeste.md)

> **REZERVĂ NEATINSĂ (`OD-85`):** acest ADR nu afirmă nicio valoare din anexa nr. 1. Foloseşte din ea
> doar **distincţia de tipuri**, care e text citit, nu cifră.

## 1. Ce se decide

**Tipurile de raport de muncă devin o tabelă de referinţă globală**, iar **domeniul unui invariant de
calcul e cheie străină spre ea** — nu enumerare liberă, nu şir.

Vocabularul e **închis şi are exact trei valori**, care sunt exact cele pe care actele le disting
azi:

| Cod | Ce e | Ancora |
|---|---|---|
| `employment_contract` | contract individual de muncă | anexa nr. 1 la Legea nr. 489/1999, **pct. 1.1, prima liniuţă** |
| `service_relationship` | raporturi de serviciu în baza actului administrativ | idem, aceeaşi liniuţă |
| `civil_contract` | contract civil de executare de lucrări / prestare de servicii | idem, aceeaşi liniuţă; **art. 19 alin. (7) teza a doua** |

Textul integral e în [`anexa-1-la-legea-489-1999.md`](../_input/cercetare/anexa-1-la-legea-489-1999.md)
— **nu se re-derivă**.

### 1.1 A treia formă a fost ratată la prima citire, şi merită spus de ce

Prima redacţie a acestui ADR spunea **două** valori. Prima liniuţă de la pct. 1.1 numeşte **trei**,
verbatim: *„persoane cu **contract individual de muncă**, **raporturi de serviciu în baza actului
administrativ**, **ori prin alte tipuri de contracte civile** în vederea executării de lucrări sau
prestării de servicii"*. Corecţia e a proprietarului, la acceptare.

**Cum s-a pierdut:** ADR-ul a fost scris din **întrebarea** care îl produsese — *unde se opreşte
invariantul art. 22* —, iar acea întrebare opune „salariat" lui „prestator pe contract civil".
Raportul de serviciu nu apare în opoziţia aia, deci n-a apărut nici în tabel. **Textul fusese citit;
distincţia care se căuta era alta.** Nu e operand lipsă (`ADR-070` §1): operandul era în repo, în
fişierul de cercetare, în aceeaşi propoziţie.

**Şi de ce contează, nu doar de ce e corect:** funcţionarul public numit prin act administrativ nu e
angajat prin contract, dar **este** salariat în sensul art. 22 — deci invariantul bazei minime îl
prinde, iar un model cu două valori l-ar fi împins în `civil_contract`, unde art. 22 **nu** se aplică.
Rezultatul ar fi fost tăcut şi echilibrat: contribuţie sub minim, `R11` trecut, niciun test de sold
declanşat. **Exact defectul pe care ADR-069 îl măsurase în cealaltă direcţie.**

## 2. Fără „general", fără „altul", fără „nedeterminat"

**O valoare-coş e drumul prin care „invariant aplicat orb" reintră sub alt nume.**

Invariantul art. 22 alin. (1) se aplică *„pentru fiecare **salariat**"*
([ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3). Un domeniu numit `general` sau `orice` ar
face din aplicarea lui pe contracte civile o **valoare acceptată**, nu o greşeală — iar rezultatul e
cel măsurat acolo: datoria umflată la salariul minim, **perfect echilibrată**, deci `R11` trece şi
niciun test de sold n-o vede.

**E simetricul exact al rezervei din `OD-93`**, unde a treia valoare a lui `MarginBasis` ar fi fost
drumul prin care „margine fără sursă" reintră. Acolo interdicţia e pe *sursă*, aici pe *domeniu*;
forma e aceeaşi.

**Dacă apare nevoia unei a patra valori, e rând nou în registru** — o decizie explicită, nu o
adăugire la o listă. **Şi a treia a intrat exact aşa** (§1.1): prin decizia proprietarului la
acceptare, cu ancora ei în text, nu prin lărgirea tăcută a unei liste.

> **Distincţia care contează, fiindcă altfel §1.1 pare să contrazică acest paragraf:** o valoare
> **care numeşte o formă reală din act** e o corecţie a vocabularului — se adaugă cu ancora ei. O
> valoare **care nu numeşte nimic** (`general`, `altul`, `orice`) nu e o a patra formă, e absenţa
> alegerii scrisă ca alegere. Prima se adaugă când actul o cere; a doua nu se adaugă niciodată.

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
limitativ** în `infra/rls/exceptions.toml`.

**Ce s-a schimbat între redacţia `Propus` şi cea acceptată:** `R1` s-a îngustat
([ADR-072](072-exceptia-care-nu-largeste.md)). Intrarea de mai jos e din clasa **(b)** — nu lărgeşte
accesul la date —, deci nu mai cere o confirmare separată. Paragraful rămâne fiindcă **motivul** e
neschimbat şi trebuie citit odată cu rândul; ce cade e blocajul, nu argumentul.

Intrarea, pe tiparul lui `permission`, care e precedentul exact — catalog fix, acelaşi pentru toţi,
însămânţat din migrarea care îl defineşte:

```toml
[[table]]
name = "employment_relationship_type"
tenant_column = false
policy_shape = "global_read_only"
writer_role = "evidenta_owner"
reason = "Vocabular de trei valori impus de lege — contract individual de munca, raporturi de serviciu in baza actului administrativ, contract civil (anexa nr. 1 la Legea nr. 489/1999, pct. 1.1 prima liniuta). Acelasi pentru toti tenantii unei jurisdictii, insamantat din migrarea care il defineste, ca `permission`. Exceptia se opreste aici: nu se extinde la alte tabele ale modulului, si nicio tabela care poarta date de raport de munca nu o mosteneste."
source = "ADR-071; regimul intrarii — ADR-072 §2, clasa (b)"
```

**Fragmentul din redacţia `Propus` n-avea `reason` şi `source`** — corectat la acceptare, la
observaţia proprietarului. Merită notat de ce contează: §4.1 de mai jos **cerea** motivul mărginit, în
proză, iar fragmentul care urma să fie copiat în fişier nu-l purta. Un exemplu care contrazice regula
de deasupra lui se copiază, nu se citeşte.
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
`reason` spune **ce anume** e exceptat şi **până unde** — *vocabular de trei valori impus de lege,
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
- **apariţia unui al patrulea tip e un rând nou**, plus decizia din §2, nu o modificare de margine.

**Ce ar infirma decizia, scris ca să fie recunoscut:** primul consumator care are nevoie de *„ce tipuri
existau la data D"*. Dacă apare, tabela primeşte margini şi acest paragraf se retrage.

## 4quater. Rolul de însămânţare, şi cum trece prin uşa unică

**`writer_role = "evidenta_owner"`, nu `evidenta_refdata`:** vocabularul e **cod**, nu date de
referinţă încărcabile — se însămânţează din migrarea care creează tabela şi ajunge în bază odată cu
deploy-ul, exact ca `permission`. Datele de referinţă se încarcă prin `P-4`; un vocabular de trei
valori impuse de lege nu se încarcă, se defineşte.

**Nota cerută la acceptare, şi e despre un lucru care nu era evident:** rolul de însămânţare e
owner-ul, dar sub `FORCE ROW LEVEL SECURITY` **owner-ul nu vede rândurile unei tabele ale cărei
politici numesc alte roluri** — exact eşecul tăcut care a produs `platform/rls/backfill.py`. Deci
însămânţarea **nu** se scrie ca `RunSQL("INSERT …")`: trece prin `backfill()`, care declară
cardinalitatea *înainte* de scriere şi **măsoară** ce vede rolul, în loc s-o declare.

Consecinţele practice, ca migrarea să nu fie rescrisă de trei ori:

- **`expected = 0`** — tabela e nouă, iar „n-a atins nimic" şi „n-avea ce atinge" trebuie să rămână
  distincte (`OD-94`);
- **constrângerea intră în aceeaşi migrare, după scriere** — regula (c) din `OD-94`, impusă mecanic:
  un `CHECK` peste mulţimea de coduri, ca o însămânţare greşită să cadă **atunci**, nu la primul
  consumator;
- **`ENABLE` + `FORCE` + `CREATE POLICY` + `GRANT` în acelaşi fişier SQL cu `CREATE TABLE`** (`C30`),
  cu perechea `.down.sql` (`C31`).

**Şi o corecţie măsurată la construcţie, consemnată aici fiindcă paragraful de mai sus o cerea
greşit.** Prima redacţie a fişierului SQL **n-avea politică permanentă de scriere pentru owner** —
argumentul fiind că însămânţarea trece prin uşă, iar uşa suspendă `FORCE` în tranzacţia migrării,
deci o politică permanentă ar fi excepţia care cere motiv propriu (`OD-95`). **Gardianul
`test_reference_load_policy` a contrazis-o cu un fapt, nu cu o preferinţă:** sub `FORCE`, un
privilegiu **fără politică** nu vede nimic, deci `writer_role = "evidenta_owner"` ar fi declarat o
cale de scriere **care nu există**. `permission` poartă exact aceeaşi politică, din exact acelaşi
motiv. Tabela o are acum; declaraţia şi baza spun acelaşi lucru.

## 5. Unde stă tabela, şi de ce nu în `payroll`

În **`fiscal`**. Motivul e `D1`: `fiscal` nu importă din niciun modul business, deci dacă domeniul
unui invariant fiscal ar arăta spre o tabelă din `operations/payroll`, dependenţa ar fi interzisă.
Invers e permis — `operations` depinde de `fiscal` —, deci `payroll` va referi tabela fără să încalce
nimic.

Şi e coerent pe fond: **distincţia e făcută de acte fiscale**, nu de dreptul muncii. Art. 22 spune
„salariat"; art. 19 alin. (7) spune „contracte civile". Amândouă sunt din Legea nr. 489/1999.

## 6. Limitarea, declarată acum ca să nu fie descoperită ca surpriză

> **Reziduul rămâne „a ales greşit dintre trei tipuri reale", nu „n-a ales".**

Cineva poate lega invariantul art. 22 de `civil_contract` şi defectul e înapoi. Cheia străină nu
împiedică asta — **îngustează de la „orice şir" la „un tip care există"**, şi atât poate face
structura. **§1.1 e chiar demonstraţia:** vocabularul a fost greşit o redacţie întreagă, iar ce l-a
corectat a fost o citire, nu o constrângere.

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

### 7.1 Dar cardinalitatea domeniului **se decide aici**, şi e opusul a ce sugera §4bis

> **REZERVĂ ÎNCHISĂ (`OD-106`):** ridicată aici, închisă în aceeaşi zi de `F2.B2`, prin **prima**
> dintre cele două forme sancţionate mai jos: `calculation_invariant_domain`, un rând per tip
> aplicabil. Invariantul art. 22 are două rânduri — `employment_contract` şi `service_relationship` —
> iar calculul citeşte o **mulţime** şi face test de apartenenţă, nu egalitate. Testul care le
> desparte există: cu brutul sub minim, primele două se încarcă pe minim, al treilea pe brut.

**Constatarea proprietarului, 2026-08-30, imediat după ce a treia valoare a intrat.** §1.1 stabileşte
că funcţionarul numit prin act administrativ **este salariat în sensul art. 22**. Deci invariantul
bazei minime se aplică la **două** dintre cele trei tipuri — `employment_contract` **şi**
`service_relationship` — şi nu se aplică la `civil_contract`.

**O singură coloană `FK` poate spune „acest invariant se aplică tipului X". Nu poate spune „tipurilor
X şi Y".** Iar §4bis, citit repede, sugerează exact forma greşită: vorbeşte despre *„domeniul unui
invariant"* ca despre o coloană `NOT NULL`, fiindcă la redactare vocabularul avea două valori şi
invariantul părea să prindă exact una.

**Ce s-ar întâmpla dacă F2.B2 leagă printr-o singură cheie**, scris ca să fie recunoscut:

- art. 22 se leagă de `employment_contract`;
- `service_relationship` **nu-l primeşte**;
- contribuţia funcţionarului iese **sub minim**, perfect echilibrată — `R11` trece, niciun test de
  sold n-o vede.

**Adică exact defectul pe care ADR-071 există ca să-l facă imposibil**, reintrat prin cardinalitate în
loc de prin vocabular. Al treilea drum de întoarcere al aceleiaşi familii, după „a treia valoare-coş"
(§2) şi „domeniu nullable" (§4bis).

**Ce se fixează, deci:**

> **Domeniul unui invariant este o MULŢIME de tipuri, nu un tip.** Formele care exprimă asta: **un rând
> per tip aplicabil** (invariantul apare de două ori, o dată per tip), sau o **tabelă de legătură**
> `invariant × tip`. Formele care NU o exprimă, şi sunt de aceea excluse: o coloană `FK` unică, şi
> orice codificare a mulţimii într-un şir.

**Şi consecinţa asupra lui §4bis, ca să nu se citească contradictoriu:** cerinţa *„fără implicit,
`NOT NULL`"* rămâne — se mută doar de pe coloană pe **legătură**: un invariant fără **niciun** rând de
domeniu e la fel de inexprimabil pe cât era un `NULL`. Ce se schimbă e că „exact unul" devine „cel
puţin unul".

**De ce se scrie acum şi nu la `F2.B2`:** motivul e proaspăt şi verificabil azi — anexa e citită, cele
trei tipuri există în bază, iar propoziţia din §1.1 care îl produce e la două paragrafe distanţă.
Peste trei sarcini, acelaşi raţionament s-ar reface **din defect**, care e forma cea mai scumpă de a-l
afla.
## 8. Consecinţe

- **Devine posibil, acum:** `C1(b)`, apoi `C2`, apoi restul `F2.B1`.
- **Devine imposibil:** un domeniu de invariant care nu corespunde niciunui tip real.
- **Rămâne de decis, cu cardinalitatea fixată:** forma legării (§7.1, `OD-106`).
- **De modificat ca urmare:** `infra/rls/exceptions.toml` (o intrare), `fiscal` (tabela şi
  însămânţarea ei), `F2.B1` (legarea), `F2.B2` (invariantul art. 22 cu domeniul lui).
- **Se implementează acum.** Condiţia era `Acceptat`, iar acceptarea a venit cu cele trei corecţii
  din antet; `R1` nu mai adaugă una separată ([ADR-072](072-exceptia-care-nu-largeste.md)).

## 9. Surse

- Anexa nr. 1 la Legea nr. 489/1999, **pct. 1.1 prima liniuţă**, şi **art. 19 alin. (7) teza a doua** —
  text integral în [`anexa-1-la-legea-489-1999.md`](../_input/cercetare/anexa-1-la-legea-489-1999.md),
  obţinut de proprietar 2026-08-30.
- **Art. 22 alin. (1)** — *„pentru fiecare salariat"*, prin
  [ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3.
- `CLAUDE.md` `R1`, `D1`, `C2`, `C6`; `infra/rls/exceptions.toml`, intrarea `permission` ca precedent.
- [ADR-070](070-trei-feluri-nu-o-familie.md) §3–§4 (coloană în loc de gardian; plafonul structurii),
  `OD-93` (simetricul, pe sursă).
