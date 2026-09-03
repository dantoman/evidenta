# 14 — Planul golurilor: ce lipsește ca o companie să-și țină contabilitatea în Evidenta

- **Scris:** 2026-09-03, la două întrebări ale proprietarului, în aceeași sesiune: *„could this be
  enough to manage the accounting for a company? what is missing? shall I make it more flexible?"*,
  apoi *„make a plan for implementation of the missing part"*.
- **Ce este:** citirea sistemului de la `HEAD` (cu munca necomisă din arborele partajat) din poziția
  contabilului care ar trebui să țină cu el o companie din Republica Moldova, potrivită cu secvența de
  unsprezece pași din `PROGRESS.md` și cu `09-f2-backlog.md`. **Nu redeschide nicio decizie**; unde
  cere una, o numește în §6 cu implicitul ei, după regula din `13-lista-de-deblocare.md`.
- **Metoda:** inventar de **cod**, nu de documente — trei treceri (operațiuni; nucleu contabil, fiscal
  și platformă; ecrane), fiecare gol verificat în cod și citat. Nimic măsurat pe un sistem viu:
  suita e cea raportată verde în PROGRESS la 02.09.
- **Regula de dimensionare:** aceeași ca la F1 și F2 — o sarcină încape într-o sesiune, altfel spune
  câte și în ce ordine. Mărimile de mai jos sunt sesiuni, nu zile.
- **`PROGRESS.md` nu e atins de acest document:** poartă modificări necomise ale altei sesiuni.
  Rândul lui îl scrie sesiunea care adoptă planul.

## 0. Răspunsul, într-un paragraf

**Nu încă.** Nucleul contabil e corect și bine apărat — plan SNC cu subconturi proprii, notă manuală cu
dimensiuni, șabloane, storno cu ambele legături, solduri inițiale, balanță, fișa contului, Cartea Mare,
corespondențe, jurnale, export CSV; documente comerciale de servicii cu TVA pe linie; calcul salarial
lunar; parametri fiscali ca date, cu consolă. Ce lipsește sunt **ieșirile lunare pentru care un contabil
e plătit**: factura tipărită, salariile în registru și plătite, banca și casa ca instrumente, ușa de
închidere a lunii, valuta, declarația TVA și fișierul IPC. Pe flexibilitate: **motorul de postare rămâne
rigid** — `R28` e exact ce face registrele TVA, lanțul de audit și rularea în paralel demne de
încredere. Flexibilitatea care lipsește e îngustă și ieftină: contul pe linie în clasa rolului,
relegarea rolurilor din ecran, instrumentele de trezorerie.

## 1. Potrivirea golurilor cu planul — se verifică, nu se citește

Legenda coloanei „În plan": **secvență** = are pas în cei unsprezece; **backlog** = are sarcină în `09`,
dar niciun pas; **nu** = nicăieri. Ultima coloană e ce spune codul, nu ce spune documentul.

| # | Golul | În plan | Unde | Ce spune codul |
|---|---|---|---|---|
| 1 | Parametrii `draft`: cotele TVA, salariul minim inexistent | secvență | `OD-22`; `13` §C6, §C12; consola din ADR-091 | `vat_rate()` refuză numind cheia; linia CAS iese fără sumă, rularea nu se aprobă |
| 2 | Salariile nu ajung în registru și nu se plătesc | backlog | `F2.B4` — pasul 3 a livrat calculul, nu postarea | niciun `payroll.*` în registrul de evenimente; `approve()` schimbă starea și scrie audit (`payroll/services/runs.py`); cele cinci roluri din ADR-065 §7 lipsesc din `roles_snc_2020.csv` |
| 3 | Factura tipărită, PDF, fluturaș tipărit | backlog | `F2.P1`, `OD-74` | nicio bibliotecă PDF în `uv.lock`; fluturașul e text (`payslip.py`); trei locuri declară absența |
| 4 | e-Factura | secvență | pasul 11, `F2.A7`, `OD-24` | o valoare de enum și comentarii |
| 5 | Declarația TVA | secvență | pasul 6, `F2.A6` (rest); textul — `13` §C5 | `operations/tax`: fără model, serviciu sau rută |
| 6 | Fișierul IPC | secvență | pasul 4 livrat ca entitate; `13` §C4 | `IpcDeclaration` fără ieșire: nici XML, nici formular |
| 7 | Banca și casa ca instrumente; OP, dispoziții, registru de casă, extras | backlog | `F2.A4`, `F2.A5` — pasul 5 e numit „complet" fără ele | `treasury_account` e categorie `cash|bank` (`treasury/models.py`); fără cont bancar, IBAN, valută; `CASA_VALUTA`, `CONT_CURENT_VALUTA` inaccesibile |
| 8 | Ușa de închidere a lunii și a exercițiului | **nu** | — | `close_period`, `reopen_period`, `close_fiscal_year` există (`periods/services/lifecycle.py`), fără rută și fără ecran |
| 9 | Valuta: cursul, decontarea, reevaluarea | parțial | `F2.A9` (BNM), `OD-127` (decontarea); reevaluarea are actul (`F2.X2 (f)`), nu sarcină | alocarea refuză valuta (`allocation.py`); niciun endpoint de curs; handlerul de diferențe fără apelant; reevaluarea declarată absentă |
| 10 | Avansurile de la clienți | backlog | ADR-073 §6 → `F2.A3` (rest) | `nature = advance` refuzat la emitere (`issuing.py`) |
| 11 | Decontul de avans, titularul de avans (2261) | **nu** | — | zero, în orice formă |
| 12 | Mijloacele fixe: registru, amortizare | secvență | pasul 9, `F2.A8`, după `C2` din F1.4.4 — **nelivrat** | doar `opening_balance_asset`, fără rută HTTP |
| 13 | Consumabile, OMVSD | F4 | în afara F2 | achiziția nu poate cumpăra stoc (`purchases/models.py`) |
| 14 | Concedii, medicale | secvență | pasul 7, `F2.B3`; actele **obținute** (`f2-x2-concedii-indemnizatii-fluturas.md`) | nimic |
| 15 | Încetarea contractului, avansul salarial, popririle | **nu** | — | nimic |
| 16 | Impozitul pe venit al entității: regimul, ratele în avans, 731 | parțial | VEN12 amânat (`OD-79`); regimul și ratele — nicăieri | închiderea exercițiului presupune 731 postat de altcineva (`closing.py`) |
| 17 | Nerezidenți: TVA la importul de servicii, reținerea la sursă | **nu** | — | `partner_resident` servește doar diferențelor; `IMPOZIT_VENIT_RETINUT_SURSA` (5343) există fără consumator |
| 18 | Alte rețineri: contracte civile, dividende, chirie | parțial | pasul 8 (`OD-102`, zilieri); dividende și chirie — nicăieri | IPC scrie doar codul `SAL` |
| 19 | Situații financiare, IALS21, BNS | secvență | pasul 10, `F2.C1`–`C3`; anexele SNC **transcrise** (`F2.X2 (e)`) | nimic |
| 20 | Fișa partenerului, actul de verificare, scadențele | parțial | `F2.A3` numește scadențele; restul — nicăieri | rapoartele n-au filtru pe dimensiune; documentul n-are `due_on`; panoul spune „lipsește" |
| 21 | Atașamentele | backlog | `OD-52` | `RefusingStorage` pe fiecare apel |
| 22 | Administrare: legarea rolurilor de cont; utilizatori și roluri | parțial | `OD-37` (membrii); legarea — nicăieri | `slots` fără `urls.py`/`views.py`; panoul spune „cont de casă nelegat" fără ecran |
| 23 | Solduri inițiale HTTP: stocuri, active, cumulative de salarii | **nu** | — | serializatorul acceptă `gl`, `receivables`, `payables`; serviciul le are pe toate șase |
| 24 | Flexibilitate: contul pe linie în clasa rolului | **nu** | ADR-073 §4 fixează „destinația alege rolul" | enum de patru destinații; venitul în trei feluri |

**Bilanț:** 24 de goluri — 8 au pas, 6 au sarcină fără pas, 10 nu sunt nicăieri. Cele zece sunt
toate lucruri pe care contabilul le face **în fiecare lună** (închidere, decont, rețineri, fișa
partenerului) sau de la prima companie (instrumente, relegare, contul pe linie).

## 2. Secvența revizuită

Principiul rămâne al proprietarului: **calendarul clientului**, lunarul înaintea anualului. Ce se
schimbă: între pasul 5 livrat și pasul 6 terminat intră **ce are nevoie prima lună închisă**, iar
pașii 6–10 primesc ce le lipsea. Nimic nu se scoate; nimic nu se reordonează din ce a fost livrat.

```
livrat: 1 2 3 4 5 · 6 început (ADR-089, ADR-090)

5a  salariile în registru și plata lor            F2.B4 (rest)                    2 sesiuni  ← LIVRAT 03.09 (postarea, plata, lista de plată)
5b  tipărirea: pipeline, factura, fluturașul       F2.P1 + OD-74 (ADR)             3          ← LIVRAT 03.09 (ADR-095, ReportLab; OP-ul rămâne)
5c  banca și casa ca instrumente                   F2.A4 + F2.A5 + decizia §6.4    3
5d  ușa de închidere                               NOU G1                          1          ← LIVRAT 03.09
5e  valuta: cursul, decontarea, reevaluarea        F2.A9 + OD-127 + NOU A10        3          ← LIVRAT 03.09 (ADR-097; BNM și consola rămân)
6   TVA: declarația, proratarea, radierea          F2.A6 (rest)                    2
6a  avansurile de la clienți                       F2.A3 (rest)                    1
6b  decontul de avans                              NOU A11                         2 + ADR
6c  nerezidenții                                   NOU A12                         2 + cercetare
7   concedii, medicale + încetare, avans, popriri  F2.B3 + NOU B7                  2 + 2
8   celelalte regimuri + reținerile la sursă       pasul 8 + NOU B8                2 + 2
8a  regimul de impozit pe venit al entității       NOU C6                          1 + cercetare
9   mijloacele fixe                                C2 (F1.4.4) → F2.A8             1 + 2
10  anualul: situațiile, IALS21, BNS               F2.C1, F2.C2, F2.C3             2 + 2 + 1
11  import 1C, e-Factura                           F3 (OD-28), F2.A7 (OD-24)       —

transversal, oricând după 5b:
    fișa partenerului, scadențele, filtrele        NOU P4+                         2
    legarea rolurilor din ecran; echipa            NOU G2 (+ OD-37)                1          ← LIVRAT 03.09 (legarea; echipa așteaptă OD-37)
    soldurile inițiale: rutele lipsă               NOU G3                          1          ← LIVRAT 03.09
    contul pe linie în clasa rolului               NOU A13 (ADR peste ADR-073 §4)  1 + ADR
    atașamentele: providerul                       OD-52                           1
```

**De ce 5a–5e înaintea sfârșitului pasului 6.** O declarație TVA pe o lună care nu se poate închide e
o declarație pe nisip: fără ușa de închidere, orice document validat după depunere schimbă registrul;
fără salariile în registru, fișa lui 5311 e goală și balanța nu e a companiei; fără factura tipărită,
clientul n-are ce livra clientului lui. Toate patru sunt în backlog de la 30.08 (`F2.A4`, `F2.A5`,
`F2.B4`, `F2.P1`) și au fost lăsate în afara secvenței; **5d** e singurul care n-avea nici sarcină.

**Punctele de sincronizare, moștenite din `09`:** `F2.P1` se construiește o dată, înaintea primului
document tipărit „terminat" (factura, fluturașul, OP-ul, actul de verificare, situațiile); instrumentele
de trezorerie (5c) preced valuta (5e), decontul (6b) și reținerile la plată (B8, A12); ușa de închidere
(5d) precede regimul de impozit (8a) și anualul (10).

## 3. Sarcinile noi

Aceeași formă ca la F0–F2: `Obiectiv`, `Depinde de`, `Review`, `Terminat`, `Blocat de`, plus mărimea.
Definition of Done din spec §7 se aplică peste fiecare.

### G1 — Ușa de închidere

- **Obiectiv:** rutele `POST …/periods/<id>/closing`, `POST …/periods/<id>/reopening` (motiv
  obligatoriu), `POST …/fiscal-years/<id>/closing`, peste serviciile care există; ecranul
  „Închidere" per companie: lunile cu starea lor, **verificările dinaintea închiderii calculate pe
  server** — documente validate și neposte (numărătoarea există în registrul TVA), rulare de salarii
  aprobată și nepostată (după 5a), roluri nelegate, extras nepotrivit (după 5c), clasa 8 nenulă (cea
  din `close_period`) — butonul de închidere, redeschiderea cu motiv, închiderea exercițiului cu lanțul
  din ADR-056 (6/7 → 351 → 333). Refuzurile există în motor (`R12`); ușa doar le expune. Nu decide
  nimic despre perioada stornoului: ADR-007 rămâne `Propus`, fără implicit pe API (`13` §A4).
- **Depinde de:** — (`periods/services/lifecycle.py`, `posting/services/closing.py`).
- **Review:** `accounting-reviewer`, `tenancy-guard`.
- **Terminat:** test HTTP sub rolul aplicației: lună închisă → postare refuzată `periods.period_closed`;
  redeschidere cu motiv → `reopened_count` crește; exercițiu închis → lunile `locked`, redeschiderea
  refuzată; ecranul cu test de fum peste `fetch`.
- **Blocat de:** —.
- **Mărime:** o sesiune.

### A10 — Reevaluarea elementelor monetare în valută la data raportării

- **Obiectiv:** handlerul `accounting.revaluation_calculated` (Spec B §7.3) pentru creanțe, datorii,
  casă și bancă în valută, la ultima zi a lunii, la cursul oficial al zilei; Anexa 1 din SNC
  „Diferențe de curs valutar și de sumă" e obținută integral (`F2.X2 (f)`, §9 din cercetare) — forma
  postării se scrie în ADR-ul familiei, cu actul citat; rolurile 6226/7224 există; idempotent pe
  (companie, lună); a doua rulare → nimic; stornabil (`R14`). Emis de închiderea lunii (5d) ca pas
  opțional, nu tăcut: contabilul îl vede pe lista de verificări.
- **Depinde de:** 5c (instrumente în valută), 5e (cursul).
- **Review:** `accounting-reviewer`, `fiscal-reviewer`.
- **Terminat:** `C12` pe o creanță în EUR peste două luni cu curs diferit, apoi decontată — diferența
  realizată la decontare e față de cursul reevaluat, nu față de cel inițial; corpus.
- **Blocat de:** —.
- **Mărime:** o sesiune plus ADR.

### A11 — Decontul de avans (titularul de avans, 2261)

- **Obiectiv:** modul propriu (`operations/expenses` — numele îl fixează ADR-ul familiei; harta din
  spec §4.1 nu-l are): eliberarea numerarului sau transferul către angajat, din casă sau bancă, pe
  2261 cu dimensiunea `employee_id`; decontul ca tip de document din `platform/documents`, cu linii
  (data, documentul justificativ, furnizorul, suma, regimul TVA din `vat.regimes` — deductibilă doar
  cu factură fiscală); aprobarea → postare pe cheltuială după destinație (sau contul din A13), TVA,
  2261; restituirea diferenței sau plata în plus, prin trezorerie; soldul per titular; eliberarea
  spre decontare și plafoanele din Legea 34/2024 (§3.4 din cercetare) sunt **parametri**, nu cod.
- **Depinde de:** 5c; `F2.P1` pentru formularul tipărit, dacă e prescris.
- **Review:** `accounting-reviewer`, `fiscal-reviewer`, `tenancy-guard`.
- **Terminat:** `C12` pe avans → decont cu TVA → restituire; fișa 2261 filtrată pe angajat egală cu
  soldul titularului; același decont de două ori → o înregistrare.
- **Blocat de:** forma tipizată a decontului — act necitit, rând nou în `F2.X2`; construcția nu așteaptă.
- **Mărime:** două sesiuni plus ADR.

### A12 — Nerezidenții: importul de servicii și reținerea la sursă

- **Obiectiv:** (1) achiziția de servicii de la nerezident — TVA la importul de servicii: obligația,
  momentul și baza se **citesc** din Codul fiscal (art. 94, 109 și cele conexe), nu se deduc; handler
  propriu cu eveniment propriu, deductibilitatea în același regim; (2) reținerea la sursă din plățile
  către nerezidenți (art. 91 — de citit), la **plată**, nu la factură, pe `IMPOZIT_VENIT_RETINUT_SURSA`
  (5343, există); (3) exportul de servicii — regimul `exempt_with_deduction` există; de verificat că
  ajunge în rândul potrivit al registrului. Cotele: parametri `draft` până la citire.
- **Depinde de:** `F2.A6` (declarația, ca rândurile să aibă unde merge), 5c.
- **Review:** `fiscal-reviewer`, `accounting-reviewer`.
- **Terminat:** `C12` pe o factură de servicii de la nerezident: cheltuială, TVA la import, reținere la
  plată; registrul de procurări o arată la regimul ei; corpus.
- **Blocat de:** `F2.X2` — articolele, rând nou în cercetare.
- **Mărime:** cercetare plus două sesiuni.

### A13 — Contul pe linie, în clasa rolului

- **Obiectiv:** linia de achiziție primește opțional `account_id`, validat contra clasei pe care
  destinația o alege — 713x/712x pentru cheltuieli, 261 pentru cheltuieli anticipate, 12x pentru
  intrarea unui activ (după `F2.A8`), 21x după F4; implicitul rămâne rolul din destinație. La fel
  linia de vânzare (venitul dincolo de servicii/mărfuri/produse) și mișcarea de trezorerie. **Nu e
  DSL:** forma postării — câte linii, ce semne, din ce câmp suma — nu se schimbă; se schimbă contul
  rezolvat, în interiorul clasei, exact cum subconturile o fac deja. **Amendează ADR-073 §4** —
  ADR nou care îl înlocuiește pe punctul acela, nu editare.
- **Depinde de:** —.
- **Review:** `accounting-reviewer`.
- **Terminat:** cont din altă clasă → refuz cu cod stabil; contul explicit ajunge pe linia de jurnal;
  fără cont → rolul, ca azi.
- **Blocat de:** decizia proprietarului, §6.3.
- **Mărime:** o sesiune plus ADR.

### B7 — Încetarea contractului, avansul salarial, popririle

- **Obiectiv:** peste `F2.B3`: compensația pentru concediul nefolosit la încetare (Codul muncii —
  articolul din `f2-x2-concedii-indemnizatii-fluturas.md` §1.2, salariul mediu după HG 426/2004, §2);
  avansul salarial ca mișcare de trezorerie legată de rulare și stinsă la plata finală; reținerile pe
  titlu executoriu (poprirea) ca linie `employee_withholding` cu beneficiar partener și plafonul legal
  ca parametru `draft`.
- **Depinde de:** 5a, pasul 7.
- **Review:** `fiscal-reviewer`, `accounting-reviewer`.
- **Terminat:** `C12` pe fiecare; fluturașul le arată; IPC neschimbat de poprire.
- **Blocat de:** `F2.X2` — articolele popririi.
- **Mărime:** două sesiuni.

### B8 — Reținerile la sursă din plățile către persoane fizice rezidente

- **Obiectiv:** la pasul 8, alături de zilieri și contractele civile (`OD-102`): dividendele cu
  reținerea finală, chiria de la persoane fizice, celelalte plăți din art. 90 — **la plată**, pe 5343,
  cu cotele ca parametri din act; codurile de sursă IPC dincolo de `SAL` — Anexa 3 la Ordinul MF
  94/2020 e neobținută (`13` §C4): rândul există, codul rămâne gol, nu ghicit.
- **Depinde de:** 5c, pasul 8.
- **Review:** `fiscal-reviewer`.
- **Terminat:** `C12`; totalul IPC pe cod de sursă egal cu plățile lunii.
- **Blocat de:** `F2.X2`; `13` §C4.
- **Mărime:** două sesiuni.

### C6 — Regimul de impozit pe venit al entității, ratele în avans, 731

- **Obiectiv:** regimul (general / regimul ÎMM — art. 54¹–54⁴, de citit) ca atribut **datat** al
  companiei, după tiparul ADR-088; ratele în avans trimestriale (art. 84 — de citit) ca obligații
  calculate din parametru și postate 731/5341; provizionul anual pe 731 înainte de închidere, ca
  `close_result_accounts` să nu presupună un 731 postat de altcineva. **Calculul VEN12 rămâne
  `OD-79`**, cu declanșatorul lui; aici e statutul și mecanica plăților, fără ajustările fiscale.
- **Depinde de:** G1, `F2.A6`.
- **Review:** `fiscal-reviewer`, `accounting-reviewer`.
- **Terminat:** `C12` pe o rată în avans; la închiderea exercițiului 731 e nenul; corpus.
- **Blocat de:** `F2.X2` — articolele; `OD-79` pentru calcul.
- **Mărime:** cercetare plus o sesiune.

### G2 — Administrarea: legarea rolurilor de cont; echipa

- **Obiectiv:** (1) ecranul „Conturi de sistem" per companie: rolurile cu contul legat, relegarea cu
  `valid_from` — istoric, nu suprascriere; `AccountRoleBinding` le are —, refuzul unui cont din altă
  clasă; rutele care lipsesc din `slots`. (2) Utilizatorii și rolurile tenantului — blocat de `OD-37`;
  se face când se decide.
- **Depinde de:** —.
- **Review:** `tenancy-guard`, `accounting-reviewer`.
- **Terminat:** relegarea schimbă contul pe postările de după `valid_from`, nu pe cele dinainte
  (`C12`); `IZ` nou pentru rutele de legare.
- **Blocat de:** `OD-37`, doar pentru (2).
- **Mărime:** o sesiune pentru (1).

### G3 — Soldurile inițiale: rutele lipsă

- **Obiectiv:** serializatoare și ecran pentru seturile `inventory`, `asset`, `payroll_cumulative`;
  serviciul le are pe toate șase. Fără ele, o companie pusă în funcțiune la mijloc de an calculează
  greșit scutirile (`13` §D10) și nu poate porni activele la pasul 9.
- **Depinde de:** —.
- **Review:** `tenancy-guard`, `accounting-reviewer`.
- **Terminat:** cele șase seturi prin HTTP sub rolul aplicației; setul de salarii cu constrângerea de
  semn respectată.
- **Blocat de:** —.
- **Mărime:** o sesiune.

### P4+ — Fișa partenerului, actul de verificare, scadențele, filtrele pe dimensiune

- **Obiectiv:** `due_on` pe document, din `payment_terms_days`, editabil; filtrul pe partener și pe
  angajat pe fișa contului, Cartea Mare și registru; soldurile deschise pe scadențe; **actul de
  verificare** cu partenerul, document generat server-side prin `F2.P1`, în română (`C38`, `C39`);
  panoul încetează să spună „lipsește" la restanțe.
- **Depinde de:** `F2.P1`.
- **Review:** `accounting-reviewer`, `tenancy-guard` — `OD-84`: dimensiunea `employee` pe rapoarte
  cere drept separat; se decide la primul filtru pe angajat, nu se ocolește.
- **Terminat:** totalul actului de verificare egal cu fișa 2211 filtrată pe partener; export.
- **Blocat de:** —.
- **Mărime:** două sesiuni.

## 4. Sarcinile existente — ce le-a rămas, citit din cod

| Sarcina | Ce a rămas | Ce e deblocat între timp |
|---|---|---|
| `F2.B4` (5a) | cele cinci roluri din ADR-065 §7 în catalog; `payroll.run_approved` cu handlerul pe granularitatea ADR-065 §8; plata salariilor prin trezorerie cu dimensiunea `employee_id`; lista de plată ca CSV — adaptor (`OD-27`); fluturașul tipărit după 5b | — |
| `F2.P1` (5b) | ADR-ul pentru `OD-74` (biblioteca, pinuită); factura fiscală după OMF 118/2017 (`V1` citită); fluturașul; ordinul de plată după Regulamentul BNM 108/2023 (**citit**, `F2.X2 (g)` §5); dispozițiile de casă și registrul de casă **așteaptă** forma (`13` §C8); determinism byte-cu-byte | OP-ul: actul e citit |
| `F2.A4`, `F2.A5` (5c) | contul bancar per companie (IBAN, valută, bancă) și casieria per valută ca **instrumente**; documentul de trezorerie referă instrumentul; extrasul în model intern, panoul de potrivire (`OD-41`); cititorii ca adaptoare (`OD-27`); plafoanele Legii 34/2024 ca parametri | plafoanele: citite din comunicatul MF (§3.3 din cercetare) |
| `F2.A9` + `OD-127` (5e) | endpoint de introducere manuală a cursului — pe consolă, calea `P-3`, **primul pas**; conectorul BNM după `OD-76`; trezoreria în valută; denominarea pe `Document` (migrare aditivă); alocarea în valută emite evenimentul — handlerul există | reevaluarea: actul e obținut (A10) |
| `F2.A6` (6) | declarația cu structura **reconstituită din fragmente** (`f2-x2-formularele-sfs.md` §1.3), marcată provizorie, generată ca fișier; proratarea cu formula reprodusă de SFS (§3 din cercetarea `(d)`); radierea cu ușă; versiunile de logică în registru cu corpus | — |
| `F2.A3` (6a) | avansul: încasarea creditează 523, factura finală îl stinge contra creanței (ADR-073 §6); tratamentul ca **legătură**, în decontare | — |
| `F2.B3` (7) | concediul de odihnă, salariul mediu (HG 426/2004), indemnizația medicală (Legea 289/2004, HG 108/2005) — ca versiuni de logică cu corpus | **toate actele obținute** (`F2.X2 (b)`) |
| `F2.A8` (9) | `C2` întâi (amortizarea, `c2-amortizarea.md`); apoi registrul, punerea în funcțiune, amortizarea lunară ca eveniment per obiect, casarea, vânzarea; dimensiunea fiscală de la primul obiect | HG 704/2019 obținută; Catalogul HG 941/2020 nu |
| `F2.C1` (10) | situațiile pentru **o singură categorie** (`13` §C9), din anexele transcrise; maparea cont → rând ca date; `OD-73` la prima închidere reală | anexele 1–6 transcrise (`F2.X2 (e)` §6) |
| `F2.C2` (10) | IALS21/INR14 după redacțiile obținute (regula zilierului e scrisă în `09`); IPC ca fișier când Anexa 1 e citită | — |
| `F2.C3` (10) | `OD-25` — formatele; intern, seturile există odată ce 5a postează | — |
| `F2.A7` (11) | payload-ul intern, sub context românesc, arhivat ca atașament (`OD-52`); transportul — `OD-24` | — |
| `OD-52` | providerul S3, layout-ul, semnarea, limitele reale | — |

## 5. Ce rămâne în afara F2, cu declanșator

- **Stocuri și OMVSD** (F4). Declanșator: primul client cu marfă sau cu obiecte de inventar ținute pe
  213. Până atunci consumabilele merg pe cheltuială la achiziție, iar nota scrisă pe ecranul de
  achiziții o spune.
- **VEN12 și amortizarea fiscală** (`OD-79`). Declanșatorul e scris: pilotul traversează 31 decembrie.
  C6 pregătește statutul și plățile, nu calculul.
- **Importul 1C** (F3, familia `OD-28`).
- **Canalele instituționale** (`OD-24`, `OD-25`, `OD-26`, `OD-27`, `OD-75`): fișierul întâi, ca în
  `13` §C7; depunerea automată e strat peste.

## 6. Deciziile proprietarului, cu implicitul

Aceeași regulă ca în `13`: fiecare rând poartă ce fac dacă nu primesc răspuns.

| # | Decizia | Unde lovește | **Implicit dacă tace** |
|---|---|---|---|
| 6.1 | ~~**Activarea parametrilor** `draft`~~ **făcută 03.09 prin delegare**, cu marginea la data observației; salariul minim încărcat (HG 771/2025) — cotele TVA, salariul minim (parametru inexistent, `13` §C12) — din consolă | tot ce e mai jos: fără ele o companie înregistrată nu emite cu TVA, iar o rulare nu se aprobă | Nimic; e actul proprietarului. Construcția merge pe `draft` activat în baza de test, ca până acum |
| 6.2 | **Ordinea:** 5a–5e intră înaintea sfârșitului pasului 6? | secvența din `PROGRESS.md` | **Da**, în ordinea scrisă în §2 |
| 6.3 | **A13 — contul pe linie** în clasa rolului, sau destinații noi în enum? | ADR-073 §4; fiecare linie de achiziție de acum înainte | **Contul explicit în clasa rolului**, implicitul rămâne rolul. Reversibil: o coloană opțională |
| 6.4 | **Modelul instrumentelor de trezorerie:** cont bancar per companie cu valută și casierie per valută; documentul de trezorerie referă instrumentul | 5c; 5e; decontul; salariile plătite | **Așa.** Schimbarea după e migrare pe fiecare document de trezorerie |
| 6.5 | **Decontul de avans** e tip de document din `platform/documents`, cu ciclul lui de viață | A11 | **Da**; modulul se numește în ADR |

## 7. Criteriul intern, pe sarcini

Cele trei luni sintetice din `09` §„Criteriul de ieșire", punct cu punct, cu sarcina care le face
posibile: facturi — livrate, **tipărite** după 5b; decontări — livrate, **în valută** după 5e; extras —
5c; casă — 5c; trei rulări — livrate, **postate și plătite** după 5a; trei închideri — 5d; trei
declarații TVA — 6; trei IPC — fișierul după `13` §C4; situațiile la trimestru — 10. **Niciun punct al
criteriului nu e atins fără 5a–5d.**
