# ADR-061 — Cumulativele de salarii: vocabularul metodei, semnul pozitiv, fereastra anului fiscal

- **Status:** **Acceptat** — **decizie de domeniu** fiscal, semnată de proprietar în rol de contabil
  practicant ([ADR-010](010-contabilul-practicant.md), sub regimul
  [ADR-002](002-guvernanta-deciziilor.md))
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** `OD-04`
- **Afectează:** `accounting/opening` — `opening_balance_payroll_cumulative`; `F2.B6`, `F2.B0`;
  activarea `payroll` în cursul anului (`R25`)
- **Legate:** [ADR-039](039-valuta-si-perioade.md) §6, [ADR-045](045-sursa-de-adevar-pentru-parametri.md),
  [ADR-060](060-vocabularul-capabilitatilor.md), Spec B §8.1

## 1. Context

Setul `opening_balance_payroll_cumulative` există din F1 ca **formă care refuză conținutul**: `code`
e text neinterpretat, fără CHECK și fără enumerare; `amount` e `numeric(20,4)` fără constrângere de
semn; `from_date` e purtat, nu presupus. Docstring-ul modelului spune de ce: a numi tipurile de venit
și contribuțiile ar fi însemnat să răspundă la `OD-04` din modulul cel mai puțin în măsură să
argumenteze.

`OD-04` e deschisă din Amendamentul 1, cu termenul „înainte de F2".

## 2. Nu e o întrebare, sunt două — cu reversibilitate opusă

Rândul din registru cere „modelul cumulativelor". Sub el stau două decizii care nu au aceeași
greutate, iar tratarea lor ca una singură ar fi amânat-o pe cea care contează:

- **Vocabularul lui `code` — reversibil.** Măsurat: `TextField` fără CHECK, singura constrângere e
  `UNIQUE (batch, employee_id, code)`. Un nume nou nu e migrare. Și, azi, niciun rând nu există:
  modulul `payroll` nu e scris, nimic nu scrie setul.
- **Semnul lui `amount` — ireversibil, în modul tăcut.** Fără constrângere, primul tenant poate
  încărca scutirile pozitiv și al doilea negativ; setul ar purta două convenții și **nimic nu ar
  semnala**. E aceeași familie cu „proprietate presupusă în amonte, neimpusă în schemă, consumator
  în aval care se sparge tăcut" pe care [ADR-059](059-linia-poarta-data-inregistrarii.md) o numără.

## 3. Ce spune actul

Metoda e prescrisă, nu aleasă: **Hotărârea Guvernului nr. 697/2014 pct. 38** — reținerea impozitului
din salariu se calculează prin **metoda cumulativă**, de la începutul anului fiscal **sau de la data
angajării**. *(Parafrază din reproducerea SFS, `../_input/cercetare/od-22-impozitul-pe-venit.md` §3 —
**nu citat verbatim**: textul consolidat al hotărârii n-a fost obținut, `legis.md` refuză preluarea și
nu e arhivat.)* Scutirile se acordă la locul de muncă de bază pe baza documentului prevăzut de
**art. 88** din Codul fiscal.

**Ce intră în acel calcul e deci ce trebuie purtat de la începutul ferestrei.** Nu se inventează un
vocabular: se transcrie ce consumă metoda.

**CAS și CNAM nu au nevoie de cumulative.** Nu au plafon anual: contribuția individuală de asigurări
sociale e istorică — măsurat în parametrii încărcați, `cnas.employee_rate = 0` din 01.01.2021 (Legea
nr. 60/2020), iar CNAM e cotă plată pe venit. Fără plafon anual, nimic nu se acumulează ca să
schimbe rezultatul lunii următoare.

## 4. Opțiuni evaluate pentru vocabular

1. **A — coloanele per angajat ale IALS21**, cu semnul cum le raportează formularul. *Avantaje:*
   vocabularul e al actului; raportul anual și cumulativul se potrivesc prin construcție.
   *Dezavantaje:* **azi IALS21 se cunoaște doar din proiectul din 2020.** Identitatea e confirmată —
   Ordinul Ministerului Finanțelor nr. 95 din 30.07.2020, Monitorul Oficial nr. 199-204 din
   07.08.2020, art. 688, în vigoare 01.01.2021 — dar textul adoptat nu s-a obținut, iar modificarea
   prin Ordinul Ministerului Finanțelor nr. 103 din 17.09.2024 e necitită. Ancorarea ar fi pe un
   proiect. *Cost de schimbare:* mic (vocabularul e reversibil), dar afirmația ar fi necitată.
2. **B — vocabularul metodei cumulative însăși**, cel din §3. *Avantaje:* trei nume, fiecare consumat
   efectiv de calcul, fiecare sprijinit pe pct. 38; decidabil azi fără să se inventeze nimic.
   *Dezavantaje:* dacă IALS21 adoptat cere o a patra coloană per angajat, lista crește — creștere
   aditivă, nu rescriere.

## 5. Decizie

**Opțiunea B, extinsă la A când actul adoptat e obținut.** Trei chei, toate în teritoriul impozitului
pe venit — ceea ce e consecința §3, nu o restrângere aleasă:

| `code` | Ce poartă |
|---|---|
| `income_tax.taxable_income` | venitul impozabil cumulat de la `from_date` |
| `income_tax.exemptions_granted` | scutirile acordate cumulat (art. 88) |
| `income_tax.withheld` | impozitul reținut cumulat |

**Nu se ancorează pe proiectul din 2020.** Extinderea la coloanele IALS21 are declanșator:
*obținerea ordinului adoptat* (`F2.X2 (c)`). Până atunci lista rămâne cea a metodei.

**Semnul: toate valorile pozitive, semnificația purtată de `code`, nu de semn.** Motivul, al
proprietarului: *un cumulativ e o mărime, nu o mișcare.* „Scutiri acordate cumulat" e o sumă de
scutiri, nu o diminuare a ceva. Semnul ar fi o a doua dimensiune care spune ce spune deja numele, iar
când două lucruri codifică aceeași informație, ele diverg.

→ **`CHECK amount >= 0`**, cu nume, adăugat de prima migrare care atinge tabela (`F2.B6`). Tabela e
goală, deci constrângerea nu are ce respinge retroactiv.

**Fereastra: anul fiscal, nu exercițiul companiei.** `from_date` rămâne coloană purtată, iar pct. 38
e motivul pentru care nu putea fi presupusă: pentru un angajat încadrat în cursul anului fereastra
începe **la data angajării**, nu la 1 ianuarie. Un exercițiu nu e obligat să înceapă în ianuarie
(ADR-039 §6), iar fereastra anului de salarizare nu e oricum aceeași întrebare.

## 6. Consecințe

- **Devine posibil:** `F2.B6` — activarea `payroll` la mijloc de an cu impozit corect din prima lună;
  `initialisation_state = complete` capătă un criteriu verificabil (cele trei chei încărcate per
  angajat activ).
- **Devine imposibil:** două convenții de semn coexistând tăcut; și încărcarea unui `code` care nu
  spune ce poartă.
- **Rămâne deschis, cu declanșator:** dacă IALS21 adoptat cere coloane per angajat pe care metoda nu
  le consumă. Declanșator: `F2.X2 (c)`. Nu e `OD` nou — e extinderea acestui ADR, aditivă.
- **De modificat ca urmare:** `OD-04` trece în „Închise"; `09-f2-backlog.md` — `F2.B6` și tabelul de
  blocaje; Spec B §8.1 primește vocabularul.
- **Se verifică:** un caz de corpus (`F2.C5`) — un angajat cu cumulative de la alt sistem primește,
  în luna activării, același impozit ca și cum tot anul ar fi fost calculat aici.

## 7. Surse

- Hotărârea Guvernului nr. 697/2014 pct. 38 și Codul fiscal art. 88, prin
  `../_input/cercetare/od-22-impozitul-pe-venit.md` §3 — **parafrază, nu citat verbatim**; textul
  consolidat n-a fost obținut.
- Legea nr. 60/2020 (contribuția individuală de asigurări sociale = 0 din 01.01.2021), cu publicarea
  în `../_input/cercetare/f2-x1-identitatile-actelor.md`.
- Ordinul Ministerului Finanțelor nr. 95 din 30.07.2020 (IALS21), Monitorul Oficial nr. 199-204 din
  07.08.2020, art. 688 — identitate confirmată, text adoptat neobținut;
  `../_input/cercetare/f2-x2-formularele-sfs.md`.
- Spec B §8.1; `CLAUDE.md` `R15`, `R18`, `R25`.
- Măsurat în cod la 2026-08-30: `accounting/opening/models.py`
  (`OpeningBalancePayrollCumulative` — `code` fără CHECK, `amount` fără constrângere de semn,
  `from_date` purtat, `UNIQUE (batch, employee_id, code)`).
- Instrucțiunea proprietarului, 2026-08-30.
