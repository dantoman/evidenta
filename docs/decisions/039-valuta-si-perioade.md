# ADR-039 — Moneda funcțională, exercițiul fiscal și perioadele

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Fază:** F1 — Accounting Core
- **Închide:** `DN-04` (Spec A §11.4), `DN-05` (Spec A §11.5)
- **Blochează:** schema `journal_line`, modelul de perioade, închiderea
- **Legate:** [ADR-032](032-cheia-de-partitionare.md) (cheia de partiționare),
  [ADR-038](038-vocabularul-de-evenimente.md), [ADR-036](036-forma-postarii.md)

Două decizii grupate: amândouă ating direct schema liniei de jurnal și modelul de perioade.

---

# Partea I — Moneda funcțională (`DN-04`)

## 1. Reformularea întrebării

„Monedă funcțională fixă MDL sau configurabilă?" nu e întrebarea care contează — moneda de raportare
statutară e MDL și nu e negociabilă. Întrebarea reală: **linia de jurnal poartă valută din ziua 1?**

## 2. Decizia

**Moneda funcțională: MDL, fixă.** O monedă funcțională configurabilă dublează complexitatea
fiecărui raport statutar pentru zero beneficiu de piață.

**Linia de jurnal poartă câmpurile de valută de la început**, chiar dacă F1 nu implementează
reevaluarea. Există cerere reală — rezidenți IT Park care facturează în EUR/USD, import, diferențe
de curs — iar costul adăugării azi e aproape zero. Costul adăugării în F3 este rescrierea fiecărei
postări dintr-un registru **imutabil**: o migrare pe care nu vrei s-o faci niciodată.

## 3. Schema — numele din Spec B, nu altele

> **Corectură față de forma inițială a propunerii, și nu una cosmetică.** Propunerea introducea
> `amount`, `original_amount` și `rate`. Primul **colapsa `debit` și `credit` într-o singură coloană
> cu semn**, iar Spec B §1.3 le are separate, ambele `NOT NULL DEFAULT 0`, cu
> `CHECK ((debit = 0) <> (credit = 0))`. `R11` — Σ Debit = Σ Credit, verificat în bază — se sprijină
> pe forma aceea. Un `amount` cu semn o pierde. Iar [ADR-036](036-forma-postarii.md) §4.2
> formulează invariantul tot ca „suma debitelor = suma creditelor", deci cele două propuneri se
> contraziceau între ele.

Linia poartă, cu numele deja scrise în Spec B §1.3 și deja folosite în cod din F0.9:

| Câmp | Tip | Conținut |
|---|---|---|
| `debit` | `numeric(20,4)` | În moneda funcțională. `NOT NULL DEFAULT 0`, `CHECK >= 0` |
| `credit` | `numeric(20,4)` | Idem. `CHECK ((debit = 0) <> (credit = 0))` |
| `currency` | `char(3)` | Moneda tranzacției. `MDL` pentru majoritatea liniilor |
| `amount_currency` | `numeric(20,4)` | Suma în moneda tranzacției |
| `exchange_rate` | `numeric(18,8)` | Cursul aplicat. `1` pentru moneda funcțională |

Toate obligatorii. O linie în MDL are `currency = 'MDL'`, `amount_currency = debit + credit`,
`exchange_rate = 1` — Spec B stochează `1` și nu `NULL` tocmai ca regula de derivare să n-aibă caz
special și `CHECK (exchange_rate > 0)` să n-aibă excepție.

### 3.1 Convenții deja fixate, și una care chiar lipsea

- **Precizia cursului: decisă.** `numeric(18,8)`, Spec B §7.2, implementată în `ExchangeRate` la
  F0.9. Nu e o întrebare deschisă.
- **Rotunjirea nu se decide aici.** Este `DNB-08`, are ADR propriu —
  [ADR-037](037-conventii-de-platforma.md), `Propus`, blocat pe verificare externă — și rămâne
  acolo **logică fiscală versionată**, selectată prin `fiscal_logic_version` după data efectivă a
  perioadei (`R17`). Distincția contează: dacă ar deveni o constantă de platformă, ar ieși din
  registrul fiscal, adică din singurul loc unde `R18` ajunge la ea — iar recalcularea unei perioade
  din 2026 ar folosi regula de azi.
- **Direcția cursului: aceasta chiar lipsea, și e decisă aici.** **MDL per unitate de valută
  străină** — forma în care publică BNM. Derivarea este
  `funcțional = amount_currency × exchange_rate`, ceea ce codul din F0.9 face deja; până acum
  convenția trăia doar într-o înmulțire, nescrisă.

### 3.2 Data cursului — trei reguli distincte

| Situație | Curs | Bază legală |
|---|---|---|
| Livrare în baza contractului în valută | Cursul oficial la **data apariției obligației fiscale privind TVA** | art. 97 alin. (6) |
| Valută necotată de BNM | Conversie în doi pași: în valută cotată, apoi în lei, la aceeași dată | art. 97 alin. (7) |
| Livrare pe teritoriul RM, contract în valută, decontare în lei | Cursul din **ziua plății** | art. 98 alin. (2) |

Data obligației fiscale se determină conform art. 108 — de regulă data livrării, cu excepții pentru
factura emisă sau plata primită anterior.

**Consecință de schemă, nededusă în propunere:** cursul se aplică la o dată care nu este nici
`document_date`, nici `accounting_date`. Linia poartă deci și `rate_date` — data la care s-a luat
cursul. Fără ea, art. 97 alin. (6) nu se poate nici aplica, nici verifica ulterior, iar postarea nu
se poate reconstitui.

### 3.3 Art. 98 alin. (2) nu este diferență de curs

Pentru livrări interne cu contract în valută și decontare în lei, diferența dintre valoarea la data
facturii și cea la data plății **constituie valoare impozabilă a livrării** — ajustare a bazei TVA,
nu diferență de curs contabilă. Handler propriu, distinct de cel de diferențe de curs; confuzia lor
produce o declarație TVA greșită, nu o clasificare imprecisă.

**Intră în F2, odată cu TVA**, nu în faza de reevaluare valutară.

## 4. Domeniul F1

F1 **transportă** câmpurile de valută. Nu implementează reevaluarea soldurilor, diferențele de curs
realizate și nerealizate, ori închiderea cu recalculare valutară.

**Constrângere care trebuie respectată totuși în F1:** soldurile de cont se calculează **atât în
MDL, cât și în moneda originală**. Un cont bancar în EUR are sold în MDL pentru balanță și sold în
EUR pentru reconcilierea cu extrasul. Dacă F1 agregă doar MDL, reevaluarea ulterioară devine
imposibilă fără migrare pe o tabelă append-only de volum mare.

---

# Partea II — Exercițiul fiscal și perioadele (`DN-05`)

## 5. Decizia

**Perioada operațională e luna. Exercițiul fiscal e o entitate cu `start_date` și `end_date`
explicite, implicit calendaristic.**

## 6. Exercițiul nu este obligatoriu calendaristic

Legea contabilității și raportării financiare nr. 287/2017, art. 24 alin. (1): perioada de gestiune
este anul calendaristic, **cu patru excepții expres prevăzute**:

| Lit. | Excepție | Implicație |
|---|---|---|
| a) | Reorganizare și lichidare | Exercițiu trunchiat, sfârșit arbitrar |
| b) | Entități care aplică perioada entității-mamă | **Exercițiu complet necalendaristic** |
| c) | Perioadă stabilită de Ministerul Finanțelor | Necalendaristic, prin act administrativ |
| d) | Entități nou-create | De la înregistrarea de stat până la 31 decembrie sau ultima zi a perioadei |

**Excepția (b) decide.** Orice filială a unei companii-mamă străine poate avea exercițiu aprilie–
martie. Nu e caz teoretic — e situația normală pentru subsidiarele cu proprietar străin.

Costul modelului flexibil: două coloane. Costul presupunerii „douăsprezece luni, ianuarie–decembrie":
logica de închidere refăcută, plus un segment întreg de clienți pe care produsul nu-l poate servi.
Presupunerea nu poate apărea nicăieri în închidere, agregare sau raportare.

**Prima perioadă nu poate depăși 12 luni.** Regula din Legea 113/2007 — care o ducea până la 31
decembrie al anului *următor* la înregistrare după 1 octombrie — nu mai există în legea în vigoare.

### 6.1 Exercițiul determină și perioada fiscală la impozitul pe venit

Anul fiscal este anul calendaristic, dar contribuabilii îndreptățiți să aplice altă perioadă de
gestiune au perioada fiscală corespunzătoare acesteia. Modelul leagă cele două, nu le tratează
independent.

## 7. Perioada TVA este luna, pentru toți — și nu este perioada contabilă

Codul fiscal art. 114 alin. (1): perioada fiscală privind TVA este luna calendaristică. **Nu există
variantă trimestrială** — nici pe prag, nici pe categorie.

Art. 114 alin. (2): la anularea înregistrării, ultima perioadă fiscală începe în prima zi a lunii în
care a avut loc anularea și se termină în ultima zi a lunii în care actul de anulare a intrat în
vigoare. Dacă lunile diferă, **perioada fiscală TVA depășește o lună calendaristică**.

| Concept | Regulă |
|---|---|
| Perioadă contabilă | Strict lunară, mereu, pentru toți |
| Perioadă fiscală TVA | Normal egală cu luna; **neregulată la anularea înregistrării** |

Declarația se construiește pe perioada fiscală. În 99% din cazuri coincid — iar dacă modelul le
confundă, cazul de anulare devine imposibil de raportat corect.

### 7.1 Termenele sunt date versionate, nu constante

Art. 115: declarația se depune și TVA se plătește până la data de **25** a lunii următoare. O
versiune anterioară a aceluiași articol prevedea „ultima zi a lunii care urmează".

Termenul s-a schimbat în timp — deci **calendarul de raportare intră în `fiscal_parameter`**, cu
`valid_from`/`valid_to` și sursă, exact ca orice alt parametru fiscal (`R15`). Structura există din
F0.8 și e goală. Un raport reconstituit pentru o perioadă din trecut trebuie să afișeze termenul de
atunci.

## 8. Stările perioadei

| Stare | Se poate posta | Cum se ajunge |
|---|---|---|
| `open` | Da | Implicit la creare |
| `closed` | Nu | Închidere explicită de contabil |
| `locked` | Nu, ireversibil | Închiderea exercițiului care o conține |

Redeschiderea unei perioade `closed` e posibilă cât exercițiul e deschis, cu motivare și
înregistrare în audit. După `locked`, niciodată. Refuzul aparține motorului, nu interfeței (`R12`).

## 9. Documentul întârziat, și cele trei date ale liniei

Un document cu data de 28 martie sosește pe 5 aprilie, iar martie e închisă. **Postarea cade în
perioada deschisă în care se face înregistrarea, nu în cea a documentului.**

> **Corectură față de propunere.** Aceasta introducea `posting_date`, care intra în coliziune cu
> [ADR-032](032-cheia-de-partitionare.md) — acceptat — unde `accounting_date` este cheia de
> partiționare a lui `journal_line`, anual, `NOT NULL` de la început prin `R22`. Nu se introduce un
> nume nou: `accounting_date` **este** data postării.

Linia poartă trei date, fiecare cu rolul ei:

| Coloană | Ce este | De ce |
|---|---|---|
| `accounting_date` | Data postării | Cheia de partiționare (ADR-032); decide perioada |
| `document_date` | Data documentului sursă | Rapoartele fiscale o cer; fără ea se pierde data reală |
| `rate_date` | Data cursului aplicat | Art. 97 alin. (6); nu coincide cu celelalte două |

`accounting_date` și `document_date` se indexează amândouă: rapoartele se construiesc pe una sau pe
alta, după cerința fiecăruia.

### 9.1 Tiparul, fiindcă a treia apariție nu mai e coincidență

Distincția de mai sus s-a redescoperit de trei ori, independent, în module diferite, fără ca vreuna
dintre dăți să pornească de la celelalte:

| Unde | Data economică | Data tehnică |
|---|---|---|
| Linia de registru (§9) | `document_date` — când s-a produs faptul | `accounting_date` — unde intră în registru |
| Rezoluția regulii ([ADR-044](044-data-de-rezolutie.md)) | data perioadei calculate | data calculului, păstrată ca metadată de audit |
| Linia de salariu (F2) | perioada de muncă — declarația nominală, drepturile | data de angajament — rezoluția tarifului |

Al treilea rând nu e presupunere: tarifele stau în anexa nr. 1 la **Legea nr. 489/1999**, iar legea
se ancorează în momentul acumulării — art. 20 alin. (5), „contribuțiile aferente salariilor
**calculate**", pe contabilitate de angajamente. Un salariu calculat în iunie pentru muncă din martie
se acumulează în iunie: **fapt economic nou, nu recalculare a lui martie.** Așa s-a dizolvat `OD-66`,
care presupunea contrariul și era gata să scrie o excepție la `R18` pentru un conflict inexistent.

**Tiparul, ca regulă pentru data următoare:** când o entitate poartă un fapt economic și o
înregistrare a lui, **cele două date sunt separate de la început, chiar dacă în cazul obișnuit
coincid.** Data economică conduce ce regulă se aplică; data tehnică conduce unde aterizează
înregistrarea. O singură coloană le confundă exact în cazurile care contează — documentul întârziat,
salariul plătit retroactiv, perioada recalculată — adică precis acolo unde greșeala e vizibilă la un
control și invizibilă în teste scrise pe cazul obișnuit.

**De ce e scris aici și nu descoperit iar în F2:** a patra oară ar fi în modulul de salarii, unde
coloana lipsă nu se adaugă retroactiv — o linie de salariu deja postată n-are de unde să-și afle data
de angajament ulterior.

## 10. Închiderea

**Două `event_type`, nu trei.**

| Tip | Ce face |
|---|---|
| `period.month.closed` | Blocare + **validarea invariantului clasei 8** |
| `period.year.closed` | Închiderea conturilor de rezultate |

Închiderea produce postări normale, prin motor, nu scriere directă în registru (`R9`).

### 10.1 Conturile de gestiune sunt un invariant, nu o închidere

Norma prevede că la data raportării conturile de gestiune se închid cu conturile de bilanț și/sau de
rezultate, **fără să fixeze o frecvență periodică**. Din corespondențe reiese că decontarea e parte
din fluxul continuu al costului, nu un eveniment periodic.

> **Conturile clasei 8 au sold zero la data raportării.**

Repartizarea se face pe parcurs, prin postările normale ale documentelor. Verificarea la închidere
este o **validare**, nu o postare — deci nu are nevoie de `event_type` propriu.

### 10.2 Conturile concrete sunt parametri fiscali, nu constante

Lanțul de închidere a conturilor de rezultate (clasele de venituri și cheltuieli → contul de
rezultat financiar total → contul de profit net) are o formă fixă, dar **numerele de cont nu se
scriu într-un handler**.

`R15` enumeră explicit **mapările de conturi** printre parametrii fiscali: versionate cu
`valid_from`/`valid_to` și cu sursă — act normativ, număr de Monitorul Oficial, dată de publicare.
Se încarcă din `fiscal_parameter`, iar `OD-22` rămâne deschisă: **niciun număr de cont nu intră în
repository fără trimitere la Planul general de conturi și la ordinul care îl aprobă.**

Motivul nu e formalism. Handlerul de închidere este codul care produce rezultatul anului; un număr
de cont scris acolo din memorie este un rezultat pe care nimeni nu-l poate apăra la un control.

## 11. Soldurile inițiale

Intră ca postare într-o perioadă de deschidere, prin `event_type` propriu
(`opening.balance.posted`).

**Perioada de start a unui tenant este ireversibilă.** Odată postate soldurile și închisă prima
perioadă, nu se mai schimbă — se alege conștient, cu avertisment explicit, nu ca un dropdown printre
altele.

Precondiție care azi lipsește: **nu există cale de producție care creează un tenant sau o
companie** (`OD-53`). Wizardul de onboarding e locul unde această alegere trăiește, iar el nu e
scris încă.

## 12. Urmărire legislativă

O modificare a Legii 287/2017 cu intrare în vigoare la 1 ianuarie 2027 transpune Directiva delegată
(UE) 2023/2775. Vizează criteriile de categorisire a entităților, nu perioadele de gestiune — dar
este prima schimbare legislativă majoră care va cădea peste produs, deci este și primul test real al
mecanismului din `R15`–`R18`.

## 13. Modificări de schemă rezultate

1. Exercițiul fiscal cu `start_date` / `end_date` explicite, implicit calendaristic (§6).
2. Perioada contabilă și perioada fiscală TVA ca entități distincte (§7).
3. Calendarul de raportare în `fiscal_parameter`, nu constante (§7.1).
4. Linia poartă trei date: `accounting_date`, `document_date`, `rate_date` (§9).
5. Închiderea: **două** `event_type`, cu clasa 8 ca invariant validat (§10).
