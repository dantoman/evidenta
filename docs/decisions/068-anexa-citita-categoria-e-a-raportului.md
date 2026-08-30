# ADR-068 — Amendament la ADR-065: anexa citită mută categoria CAS de pe companie pe raportul de muncă

- **Status:** **Acceptat** — **decizie de domeniu** fiscal, semnată de proprietar în rol de contabil
  practicant ([ADR-010](010-contabilul-practicant.md), sub [ADR-002](002-guvernanta-deciziilor.md))
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Amendează:** [ADR-065](065-schema-salarizarii.md) §2.1, §3, §3.1, §3.2 — restul rămâne neschimbat.
  **ADR-065 nu se reactivează ca `Propus`:** sunt corecţii cu sursă la un ADR acceptat
- **Restrânge:** `OD-85` (de la structură la valori), `OD-81` (refuzul nu e pe companie)
- **Afectează:** `operations/payroll`, `F2.B1`, `F2.B2`, `F2.X1`
- **Legate:** [ADR-065](065-schema-salarizarii.md), [ADR-066](066-rezerva-e-decizie-deschisa.md),
  [ADR-044](044-data-de-rezolutie.md), [ADR-045](045-sursa-de-adevar-pentru-parametri.md)

> **REZERVĂ (`OD-85`):** anexa e citită în **versiunea 2020**, ataşată la LP257/2020. Structura şi
> vocabularul de puncte sunt utilizabile; **valorile curente pentru pct. 1.5, 1.8 şi 1.9 nu sunt** —
> §7. Redacţia curentă a anexei rămâne neobţinută.

## 1. Ce s-a schimbat în temei

**Anexa nr. 1 la Legea nr. 489/1999 a fost obţinută de proprietar** — versiunea 2020, ataşată la
LP257/2020. Până acum toate cotele CAS veneau din **Ordinul CNAS nr. 31-A**, act care *aplică* anexa,
iar rezerva era purtată ca atare din [ADR-044](044-data-de-rezolutie.md) §6 în ADR-065 §3.

Tot ce urmează sunt **corecţii cu sursă**, nu redeschideri.

## 2. Maparea punctelor — confirmată la sursă

**Pct. 1.1 conţine ambele tarife**: **29%** pentru angajatorii autorităţilor şi instituţiilor bugetare
şi publice la autogestiune, **24%** pentru sectorul privat, instituţiile de învăţământ superior şi
cele medico-sanitare. **Distincţia e prin sector, nu prin număr de punct.**

**Pct. 1.2 e exclusiv aviaţia**, condiţii speciale conform anexei nr. 2: **39%** bugetar, **32%**
privat.

Corecţia aplicată la 2026-08-30 (ADR-065 §3, după `fiscal-reviewer`) **era corectă**. Ce se schimbă e
temeiul: nu mai stă doar pe actul de aplicare.

**Pct. 1.4 — rezidenţii parcurilor pentru tehnologia informaţiei — sunt în anexă**, cu trimitere la
Legea nr. 77/2016 atât pentru tarif, cât şi pentru venitul asigurat. Cercetarea internă avea dreptate;
**rezerva adăugată la `OD-81` se retrage.**

## 3. Constatarea decisivă: categoria e a raportului, nu a companiei

**Pct. 1.1, a doua liniuţă, include explicit contractele civile de executare de lucrări sau prestare
de servicii în cazul rezidenţilor parcurilor pentru tehnologia informaţiei** — coroborat cu art. 19
alin. (7) teza a doua.

> **Deci un rezident de parc IT este simultan pct. 1.4 şi pct. 1.1**: 1.4 pentru salariaţi, 1.1 pentru
> contractele civile.

**Şi nu e caz marginal, cum sunt aviaţia sau zilierii. E regimul normal al fiecărui rezident care
contractează un prestator.**

ADR-065 §3.1 spunea că *„categoria rămâne atribut al companiei pentru domeniul declarat al F2"*, cu
aviaţia şi zilierii ca limitări de domeniu improbabile. **Afirmaţia nu se susţine nici pentru
profilul-ţintă.** Forma extinderii era deja scrisă acolo — *„categoria devine atribut pe raportul de
muncă, nu pe companie, iar cea de pe companie rămâne implicitul"* — şi **se aplică acum**, nu pentru
zilieri, ci pentru cazul obişnuit.

**Amendament la §3 şi §3.1:** categoria de plătitor CAS e **a raportului**, cu cea de pe companie ca
**implicit**. `company_cas_payer_category` rămâne, dar nu mai e răspunsul final.

### 3.1 Consecinţă pentru `OD-81`: refuzul se reformulează, nu se inversează

Decizia rămâne: **forma substitutivă nu intră în F2.** Ce se schimbă e unde se prinde refuzul.

- **Nu pe companie.** Un refuz pe companie ar bloca şi ce e **obişnuit** la un rezident de parc IT:
  contractele lui civile, care stau la pct. 1.1 cu tarif normal.
- **Pe raport.** Se refuză **rularea de salarii care conţine salariaţi ai unui rezident de parc IT** —
  regimul substitutiv, nemodelat. Restul nu se atinge.

> **Şi iese la iveală un caz fără casă, consemnat ca atare:** CAS-ul datorat pe **contractele civile**
> ale rezidentului e o obligaţie pe o plată care **nu e salariu**, deci salarizarea nu o produce, iar
> achiziţiile de la persoane fizice n-au azi nicio noţiune de CAS. Nu se rezolvă aici. → `OD-91`.

## 4. Pct. 1.5 — un tarif, doi plătitori. `EmployerCharge` nu îl poate exprima

Anexa: **24% total, din care 18% din mijloacele angajatorului şi 6% de la bugetul de stat** — confirmă
art. 17 alin. (3²).

**Nu e cotă diferită, e cotă împărţită.** Măsurat, ADR-065 §2.1 defineşte `EmployerCharge` ca *„cotă
peste brut, în sarcina angajatorului"*, cu **o singură** postare — debit cheltuială, credit datorie.
Asta exprimă un tarif, nu o împărţire.

Ce cere structura:

- **obligaţia evaluată** — 24% pe bază; e cifra pe care IPC21 o raportează, fiindcă formularul
  raportează contribuţiile **calculate**;
- **partea suportată de entitate** — 18%; **doar ea se postează** ca datorie şi cheltuială;
- restul nu trece prin conturile entităţii: angajatorul virează 18% din mijloace proprii.

**Amendament la §2.1:** `EmployerCharge` poartă **două sume — evaluată şi suportată** —, egale în
cazul obişnuit. A le confunda înseamnă ori o declaraţie sub obligaţie, ori o cheltuială umflată cu o
sumă pe care entitatea n-a plătit-o.

## 5. Art. 22 alin. (1) — invariant de calcul, nu parametru

**Baza lunară pentru fiecare salariat nu poate fi mai mică decât salariul minim lunar pe ţară,
proporţional timpului lucrat**; la timp parţial, contribuţia nu poate fi sub **25%** din cea calculată
la salariul minim.

> **Un handler care înmulţeşte baza cu cota îl ratează, iar declaraţia iese sub minim.**

Distincţia contează pentru unde stă: e **logică fiscală** (`R16`), versionată în registru şi cu caz de
corpus, **nu parametru** (`R15`). Parametru e doar salariul minim pe ţară, care se încarcă prin
`F2.X1`.

> **Domeniul, adăugat prin [ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3:** articolul spune
> *„pentru fiecare **salariat**"*, iar acest paragraf a purtat cuvântul fără să spună unde se opreşte.
> **Invariantul e al raportului de muncă, nu al oricărei baze CAS** — aplicat pe contracte civile
> umflă datoria tăcut şi perfect echilibrat.

## 6. Anexa nr. 3 — nomenclator închis, încărcabil ca date

Drepturi şi venituri aferent cărora **nu se calculează CAS**, cu text complet şi cu trimiteri la
actele care le stabilesc. E `R15` curat: listă închisă, versionabilă, cu act pe fiecare poziţie.
→ `F2.X1`.

> ## ⚠ CORECTAT 2026-08-30: „43 de poziţii" era greşit ca descriere
>
> Identificatorii reali sunt **1, 2, 2¹, 3, 4, …, 38, 40, 41, 42, 43, plus 10¹** — **poziţia 39
> lipseşte**, iar două poziţii poartă exponent.
>
> **Cine încarcă „1–43" fabrică un 39 inexistent şi pierde doi exponenţi.** Coloana de identificator
> e **TEXT, nu întreg**.
>
> **Cifra 43 era un număr de rânduri produs de o numărare, prezentat ca proprietate a documentului** —
> exact forma pe care o vânăm de o zi, produsă de mine în timp ce o descriam.

## 7. Ce **nu** e utilizabil din versiunea 2020, şi de ce

| Punct | Versiunea 2020 | Redacţia curentă |
|---|---|---|
| **1.5** | pragul **95%** | **70%**, prin LP187/2025, în vigoare **18.07.2025** |
| **1.8** (taxi) | **există** | **abrogat** de la 01.07.2026, prin LP318/2025 |
| **1.9** (zilieri) | taxă fixă conform legii bugetului asigurărilor sociale anuale | **text intermediar necunoscut** — §8 |

**Tabelul e utilizabil ca structură şi vocabular de puncte. Nu e utilizabil ca sursă a valorilor
curente pentru 1.5, 1.8 şi 1.9.** Deci `OD-85` **se restrânge la valori**, nu se închide.

### 7.1 Zilierii nu sunt o contradicţie, sunt o versionare

`od-22-cnas-cnam.md` dă **6%, datorat de beneficiarul de lucrărilor**; anexa 2020 dă taxă fixă. **Nu e
o eroare de citire.** Fişierul de cercetare listează, la „Ce nu s-a putut verifica" pct. 1, chiar
cifra 6% printre cele citite din **Ordinul CNAS nr. 31-A/2026**, nu din anexă. Iar §8 arată că pct.
1.9 s-a modificat între 2020 şi acum.

**Deci ambele pot fi corecte pentru data lor, şi niciuna nu e „cota".** Nimic nu s-a încărcat în
`fiscal_parameter` pentru zilieri — verificat pe baza vie —, deci nicio valoare greşită n-a ajuns în
date. Ce e demonstrabil greşit e coloana de valabilitate a rândului din cercetare, care spune
*„permanent"*; corectată acolo, cu data.

## 8. Fapt de metodă, cu dovadă directă

> ## ⚠ RETRAS 2026-08-30, în aceeaşi zi. Demonstraţia era falsă.
>
> Acest paragraf afirma: *„LP318/2025 modifică la pct. 1.9 «pct. 1.1–1.8» în «pct. 1.1–1.7», iar în
> versiunea 2020 pct. 1.9 nu conţine nicio clauză de excludere — deci există o redacţie intermediară
> pe care n-o avem."*
>
> **Clauza există.** Anexa deschisă integral o dă verbatim, şi citeşte exact *„pct. 1.1–1.8"*. LP318
> art. II pct. 3 o confirmă independent: ca să substitui text **în interiorul** poziţiei 1.9, poziţia
> trebuie să aibă text. Nu exista nicio redacţie intermediară de dedus.
>
> **Regula per-redacţie rămâne în picioare** — stă pe verificările din §8.1 şi §8.2, confirmate
> empiric de două ori (nota de mai jos). **Ce cade e demonstraţia**, iar o regulă cu exemplul retras
> nu se lasă cu exemplul retras tăcut.

**Mecanismul probabil, şi e formă nouă pentru taxonomia „nimic nu strigă": conţinut citit printr-un
convertor cu pierderi, tratat ca documentul.** Clauza stă la coada unei celule de tabel — exact ce
taie un extractor de text. **Aceeaşi familie cu `git commit -- <căi> ia din arborele de lucru, nu din
index**: o proprietate a **uneltei**, atribuită **sursei**. Şi e mai perfidă decât aceea, fiindcă
unealta a returnat un document plauzibil şi complet la citire.

Consecinţa practică: *„am obţinut anexa"* nu înseamnă *„ştim ce spune azi"*.

### 8.1 Precondiţia, fără de care nimic din §2–§6 n-ar fi legitim

**Textul unei redacţii e consolidat; doar chenarele sunt necumulative.** Adică ce se citeşte în corpul
unei redacţii e forma în vigoare la acea redacţie, iar ce nu se poate cumula sunt notele editoriale
care spun *ce act a schimbat ce*. Fără această precondiţie, citirea pragului de 70% din corpul legii
n-ar fi fost legitimă — ar fi fost o presupunere că textul e la zi.

**Confirmată empiric, de două ori independent** (2026-08-30, proprietarul):

1. **Anexa nr. 3 la Legea nr. 489/1999, în redacţia LP318, conţine pct. 10¹** — introdus de
   LP187/2025 — **deşi chenarele marchează doar LP318**. Textul cumulează; chenarul nu.
2. **Ordinul Ministerului Finanţelor nr. 103/2024 a dispărut din antetul redacţiei 154297**, deşi
   efectele lui sunt în text.

Deci chenarul e o **notă despre ultima modificare**, nu un istoric — iar cine îl citeşte ca istoric
conchide că o modificare anterioară nu s-a aplicat.

### 8.2 A doua dovadă, mai tare decât prima

Prima dovadă (pct. 1.9) arată că **există** redacţii intermediare pe care nu le avem — dedus dintr-o
trimitere care nu se potriveşte.

A doua o **arată**: cele două redacţii ale Ordinului MF nr. 95/2020 — OMF nr. 103/17.09.2024 şi OMF
nr. 59/04.05.2026 — sunt **acelaşi act, şi le deţinem pe amândouă**. Diferenţa dintre ele nu se
deduce, se citeşte. **Două redacţii ale aceluiaşi `doc_id` spun lucruri diferite despre aceeaşi
obligaţie** — nu ipotetic, ci verificabil, cu ambele texte pe masă.

### 8.3 Pasul care a mers de două ori din două

**Când o anexă e neobţinută, verifică dacă articolele corpului o referenţiază cu valoare explicită.**
Aici a funcţionat de două ori: pragul de 70% e în **art. 17 alin. (3¹)**, iar porţiunea de 6% de la
bugetul de stat în **art. 17 alin. (3²)** — amândouă observate în corpul redacţiei în vigoare, fără
anexă. Ce a rămas neobţinut e doar totalul de 24% şi împărţirea 18/6.

> **Deci `OD-85` se restrânge mai mult decât „la valori": ce lipseşte sunt MARGINILE, nu valorile.**
> Ştim ce spune, nu ştim din când.

### 8.4 Corecţia care schimbă forma rândului de metodă

Formularea propusă de sesiune la 2026-08-30 — *„fiecare valoare poartă data redacţiei"* — e **greşită
în felul în care greşesc lucrurile plauzibile**. O redacţie dă un **punct interior**, nu o margine:

> din *„V apare în redacţia R"* se deduce doar `valid_from ≤ data(R) ≤ valid_to`.

**Un `valid_from` scris din data redacţiei e o margine fabricată** — corectă ca valoare, inventată ca
interval, şi nimic n-o compară vreodată cu ceva.

**Exemplul, pe pragul de 70%** (art. 17 alin. (3¹)): ştim că e adevărat în redacţia LP318; **nu** ştim
că e valabil din 18.07.2025 — asta stă în articolul final al LP187/2025, necitit; iar
`valid_from = 2026-07-01` ar fi **fals**, fiindcă valoarea precedă redacţia.

**Regula corectă cere două câmpuri, nu unul** — observaţia şi marginea. Decizia asupra formei lor e
`OD-92`.

## 9. Consecinţe

- **Devine posibil:** cotele CAS au sursă în lege, nu doar în actul de aplicare; anexa nr. 3 se
  încarcă; art. 22 intră ca invariant în `F2.B2`.
- **Devine imposibil:** un refuz de parc IT pe companie; un `EmployerCharge` cu o singură sumă la
  pct. 1.5; o categorie de plătitor citită doar de pe companie.
- **De modificat ca urmare:** ADR-065 §2.1, §3, §3.1, §3.2 se citesc prin acest amendament; `OD-85`
  restrânsă la valori; `OD-81` reformulată; `OD-91` nouă (CAS pe contractele civile); `F2.X1` primeşte
  anexa nr. 3 şi salariul minim; `F2.B2` primeşte invariantul art. 22.
- **Rămân neobţinute**, toate trei fiind **fişiere ataşate, nu text**, şi niciuna blocând structura:
  anexa la HG nr. 941/2020 (Catalogul duratelor), anexa nr. 1 la Ordinul MF nr. 95/2020 (formularul
  IALS21), şi **redacţia curentă a anexei nr. 1 la Legea nr. 489/1999**.

## 10. Surse

- **Anexa nr. 1 la Legea nr. 489/1999, versiunea 2020**, ataşată la LP257/2020 — pct. 1.1, 1.2, 1.4,
  1.5, 1.8, 1.9; **anexa nr. 3** (43 de poziţii); **art. 17 alin. (3²)**, **art. 19 alin. (7)**,
  **art. 22 alin. (1)**. Obţinută şi citită de proprietar, 2026-08-30.
- LP187/2025 (pragul agricol 70%, în vigoare 18.07.2025); LP318/2025 (abrogarea pct. 1.8 de la
  01.07.2026, şi modificarea trimiterii din pct. 1.9).
- Legea nr. 77/2016 — regimul parcurilor pentru tehnologia informaţiei, citată de anexă.
- `../_input/cercetare/od-22-cnas-cnam.md`, „Ce nu s-a putut verifica" pct. 1 — pentru §7.1.
- [ADR-065](065-schema-salarizarii.md) §2.1, §3, §3.1, §3.2.
