# ADR-048 — Formula este unitatea de postare; dimensiunile sunt sloturi tipizate

- **Status:** Acceptat — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md); cerută
  explicit de proprietar prin instrucțiunea scrisă „construirea bazei motorului", etapa 1+2.
  **Nu decide nimic contabil**: niciun cont, nicio corespondență, nicio declarație de dimensiuni —
  toate se livrează goale (§6)
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** — *(deschide `OD-69`, §7)*
- **Afectează:** `journal_entry` (trei coloane), `journal_formula` (tabelă nouă, append-only),
  `coa_template_account` și `company_account` (patru coloane), `accounting/posting/formula.py`,
  `accounting/posting/services/formulas.py`, `ledger/services/writing.py`,
  `ledger/services/reversal.py`, `infra/schema/append_only.toml`
- **Legate:** [ADR-036](036-forma-postarii.md) §5 (handlerul), [ADR-029](029-dimensiuni-analitice.md)
  (cele 15 coloane), [ADR-039](039-valuta-si-perioade.md) §3 (valuta pe linie),
  [ADR-047](047-stampila-parametrului-la-postare.md) (ștampila parametrului),
  [ADR-044](044-data-de-rezolutie.md) (data efectivă)

---

## 1. Ce cere instrucțiunea, în termenii ei

> Motorul emite **n formule per linie de document**, nu un număr fixat. Antetul înregistrării poartă
> versiunea regulii aplicate, versiunea planului de conturi și versiunea setului fiscal. Formula
> poartă: cont debitor, cont creditor, sumă în lei, sumă în valută, curs, cotă TVA ca atribut,
> sloturile de dimensiuni. Planul de conturi declară, per cont și per versiune, ce tipuri de
> dimensiuni poartă contul și care sunt obligatorii. Trei sloturi tipizate pe formulă, al patrulea
> opțional. Fără JSONB, fără EAV.

Și testul aplicat peste tot: *dacă un lucru poate fi exprimat ca dată peste structura existentă,
nu se construiește acum; dacă cere altă structură, se construiește acum, gol.*

Ce exista deja, măsurat: `journal_line` are 15 coloane de dimensiuni (ADR-029), tripla de valută și
cele trei date (ADR-039); `company_account.required_dimensions` spune ce e **obligatoriu**, nu ce e
**purtat**; motorul are cei șase invarianți peste `ProposedLine` (F1.4.3) și un scriitor de linii;
antetul nu poartă nicio versiune. Formula nu exista nicăieri: nici ca structură, nici ca contract.

## 2. Opțiuni evaluate

### 2.1 Unde trăiește formula

1. **Formula doar ca contract al handlerului**, expandată în linii și uitată. *Avantaj:* zero
   schemă. *Dezavantaj:* o înregistrare cu trei linii nu mai poate spune care debit corespunde
   cărui credit — iar fișa contului se citește prin corespondență („în corespondență cu contul"),
   nu prin linii. Cheia de contopire n-ar avea unde să fie constrângere. *Cost de schimbare
   ulterioară:* maxim — istoria postată n-are corespondențe și nu le poate primi.
2. **Formula înlocuiește linia**: registrul devine cu două conturi pe rând. *Avantaj:* un singur
   rând per corespondență. *Dezavantaj:* contrazice Spec B §1.3, ADR-039 §3 (corectura care a
   respins `amount` cu semn) și tot ce s-a construit pe `journal_line` — echilibrul în bază, stornoul,
   balanța, cele 15 coloane. Rescrie F1.2 din temelii. *Cost:* rescrierea unui registru livrat.
3. **Formula ca tabelă proprie, lângă linii, cu linia derivată din ea** — *aleasă*. O formulă se
   expandează în exact două linii; `journal_line` rămâne ce era, iar `journal_formula` ține
   corespondența, cheia de contopire și sloturile tipizate. *Dezavantaj:* suma stă în două locuri.
   *Cum se ține:* un singur writer, o singură tranzacție, și un constraint trigger amânat care refuză
   la COMMIT o înregistrare ale cărei formule nu însumează totalul debitor al liniilor — a doua
   barieră, pentru importul și migrările care nu trec prin writer.

### 2.2 Cum se tipizează un slot

1. **Poziție goală, tipul dedus din declarația contului la citire.** Patru `uuid` pe formulă,
   sensul poziției dat de `company_account` la data postării. *Dezavantaj:* o declarație schimbată
   după postare face istoria neinterpretabilă — sau interpretabilă doar cu declarația de atunci,
   care nu e versionată pe zi. Exact clasa de defect pe care ADR-047 o numește: referința se
   rezolvă la ce spune lumea *acum*.
2. **Perechi tip + valoare pe rând** — *aleasă*. `slot_n_dimension` (nume din vocabularul ADR-029)
   și `slot_n_value_id`. Rândul e autodescriptiv; o declarație schimbată azi lasă anul trecut
   exact la fel de lizibil. Costul: patru coloane text în plus pe o tabelă mare, cu `COLLATE "C"`.
3. **`jsonb` sau tabelă atribut-valoare.** Respinse de instrucțiune și de ADR-029 pentru același
   motiv: nici cheia de contopire, nici cheia agregatelor nu pot fi constrângeri reale peste ele.

### 2.3 Sloturi comune sau per parte

Instrucțiunea spune „trei sloturi tipizate pe formulă, al patrulea opțional" — **pe formulă**, nu
pe fiecare parte. 1C ține subconto separat pe Dt și pe Ct. S-a urmat instrucțiunea literal, cu
consecința scrisă în §5: formula poartă **reuniunea** a ce declară cele două conturi, fiecare linie
primește partea ei, iar un transfer între două valori ale aceluiași cont (Dt 221/A — Ct 221/B) nu
se exprimă într-o singură formulă. Dacă la Etapa 8 asta se dovedește insuficient, trecerea la
sloturi per parte e un ADR care înlocuiește secțiunea aceasta — nu opt coloane adăugate în treacăt.

## 3. Decizia

**Formula este unitatea pe care o emite motorul și pe care o citește contabilul; linia rămâne
unitatea pe care o însumează balanța.** Concret:

### 3.1 Contul declară ce poartă

`coa_template_account` și `company_account` primesc `slot_1_dimension … slot_4_dimension` — nume din
`DIMENSION_KEYS`, `COLLATE "C"`, cu trei reguli în bază: cunoscut (în vocabular), contiguu (slotul
*n+1* nu e umplut înaintea lui *n*), distinct (o dimensiune, o poziție). `required_dimensions` rămâne
singurul loc care spune ce e **obligatoriu**; sloturile spun ce e **purtat**; o constrângere le
leagă — `*_required_within_slots`: un cont nu poate cere ce nu poartă.

Declarația se copiază din șablon la instanțiere, intră prin încărcătorul de plan ca **date** (două
coloane opționale în CSV: `dimension_slots`, `required_dimensions`), și se poate extinde per
companie prin `declare_dimension_slots` — un cont de sistem se **extinde**, nu se **îngustează**
(ADR-036 §6.3, stratul 2: compania adaugă analitica ei peste a planului).

### 3.2 Formula, ca rând

`journal_formula`: `debit_account_id`, `credit_account_id`, `amount` (MDL), `currency`,
`amount_currency`, `exchange_rate`, `rate_date`, `document_date`, `vat_rate` + `vat_rate_key` (atribut,
nu dimensiune — o cotă parametrizează calculul pe care formula îl consemnează; nu e o axă de analiză
și n-are fișă proprie de indexat), `quantity`/`uom_id`, patru perechi `slot_n_dimension` /
`slot_n_value_id`. Append-only, în `append_only.toml`, `bigint`, `accounting_date NOT NULL`, fără
nicio cheie intrând; singura ieșitoare e spre `journal_entry`, din motivul pentru care `journal_line`
o are.

**Cheia de contopire e o constrângere de unicitate reală** — `journal_formula_merge_key` peste
(înregistrare, cele două conturi, valută, curs, data cursului, data documentului, cotă TVA și cheia
ei, unitate, cele patru perechi de sloturi), cu `NULLS NOT DISTINCT`, fiindcă majoritatea coloanelor
sunt NULL pe majoritatea rândurilor și fără asta constrângerea n-ar constrânge nimic.

### 3.3 Antetul poartă trei versiuni

Pe `journal_entry`: `rule_ref` (referința implementării selectate din registru — `sales.delivery.v1`;
poartă versiunea în nume), `chart_template_id` (versiunea planului de conturi din care s-au citit
conturile; **singura dintre cele trei care nu se poate re-deriva**: `company_chart.template` e
versiunea *curentă*, iar propagarea `OD-03` o va muta), `fiscal_effective_date` (data pentru care
s-a rezolvat setul fiscal — vezi §7 pentru de ce e o dată și nu un id). Se scriu de writer, în
aceeași tranzacție cu liniile; sunt imutabile după postare prin trigger propriu, fiindcă lista din
`0036` e append-only (C31). Stornoul **copiază** planul și data fiscală ale originalului și pune
propria `rule_ref` — nu recalculează nimic (R18).

### 3.4 Ce face motorul, în ordine

`accounting/posting/formula.py` și `services/formulas.py`:

1. **`bind_roles`** — rolurile handlerului devin conturi prin `slots.resolve_role`, la data postării;
   un rol nelegat refuză (ADR-036 §5.1).
2. **`place`** — planul decide ce păstrează fiecare parte: linia de debit primește valorile pe care
   contul debitor le declară, linia de credit pe ale ei; formula stochează **reuniunea**, în ordinea
   declarației debitorului, apoi ce adaugă creditorul. O dimensiune pe care n-o declară niciuna
   dintre părți **nu e purtată** — handlerul descrie faptul complet, planul spune ce reține entitatea
   (stratul 2). Peste patru în reuniune: refuz cu cod.
3. **`merge`** — formulele cu aceeași cheie se contopesc; doar suma adună.
4. **`verify`** — cei șase invarianți, peste expansiunea în `ProposedLine`; **o singură
   implementare**, nu una pentru formule.
5. **`assert_dimensions_present`** — obligativitatea, per parte, cu partea ei.
6. ștampila planului, numărul (ultimul, ADR-022), `post_entry` cu linii **și** formule.

Nimic din acest lanț nu calculează o sumă (Etapa 3) și nu rotunjește (`DNB-08`).

## 4. Ce rămâne legitim fără formule

Nota manuală și soldurile inițiale scriu doar linii. Nu e o excepție ce va fi închisă: o notă în
care o persoană a scris trei debite și un credit nu are o descompunere unică în corespondențe, și
a inventa una ar însemna a consemna în registru ceva ce omul n-a spus. Triggerul de la COMMIT lasă
să treacă o înregistrare **fără** formule și refuză una ale cărei formule nu spun ce spun liniile.

## 5. Consecințe

**Devine posibil:** un handler care emite un număr variabil de corespondențe per linie de document;
fișa contului citită prin corespondență, din `journal_formula`, fără să reconstruiască perechi din
linii; contopirea deterministă, garantată de bază; declarația de analitică per cont, ca date, cu
cerințele ei ținute în interiorul ei de o constrângere; recalcularea unei perioade cu planul de
atunci, nu cu cel de azi.

**Devine imposibil sau scump, asumat:** un al cincilea slot pe formulă e migrare pe două tabele
append-only; sloturile sunt comune celor două părți (§2.3) — o formulă ale cărei conturi declară
împreună peste patru axe distincte se refuză, nu se trunchiază; `journal_formula` adaugă un rând la
fiecare două linii și un index unic cu 18 coloane pe o tabelă de volum mare — prețul cerut explicit
pentru „constrângere reală, nu cheie calculată în aplicație".

**Ce se verifică automat:** `tests/isolation/test_dimension_slots.py` (declarația, cele patru
constrângeri în bază, extinderea fără îngustare, copierea la instanțiere, CSV-ul livrat fără nicio
declarație); `tests/isolation/test_formulas.py` (n formule → 2n linii, plasarea per parte,
contopirea și cheia ei ca `IntegrityError`, cele zece forme refuzate, formule ≠ linii refuzat la
COMMIT, imutabilitatea pe rânduri semănate, stornoul oglindit cu ștampilele copiate, legarea
rolurilor, ștampilele pe nota manuală, izolarea); gardianul de model peste `journal_formula` ca
append-only; rotația `0056`/`0057` în `test_reverse_sql`.

## 6. Ce NU decide

Niciun cont nu poartă nicio dimensiune — CSV-ul planului n-are nicio declarație și un test o
asertează. Nicio corespondență nu există. Nicio metodă de evaluare, niciun proces periodic, nicio
cotă. Cele nouă decizii deschise rămân deschise; ADR-036 §11 nu e atins.

## 7. Ce se raportează, nu se decide

- **`OD-69` — „versiunea setului fiscal" nu are identitate în acest sistem.** Instrucțiunea cere ca
  antetul să poarte „versiunea setului fiscal, valabilă la data contabilă". Nu există o entitate
  „set fiscal": parametrii (R15) și logica (R17) sunt versionate rând cu rând pe `valid_from` /
  `valid_to`, iar rândurile pe care le-a folosit efectiv o postare sunt ștampilele din ADR-047. Ce
  identifică unic setul, în modelul de aici, este **data pentru care s-a rezolvat** — de aceea antetul
  poartă `fiscal_effective_date`, nu un id. Dacă proprietarul vrea un set fiscal ca entitate numită
  și versionată (un „pachet" de versiuni, cu act), aceea e structură în modulul `fiscal`, cu calea
  de scriere `P-4` — teritoriul `OD-67` — și nu s-a construit aici. Golul măsurat pe drum: versiunile
  de **logică** fiscală (`fiscal_logic_version`) nu se ștampilează per înregistrare, doar parametrii.
- **O referință din instrucțiune nu se rezolvă.** „Cheia de contopire din ADR-018 §3 și cheia
  agregatelor din §7" — ADR-018 din acest repository e despre engagementuri multiple și n-are nici
  contopire, nici agregate; niciun document din `docs/` nu conține termenul. S-a construit după
  intenția enunțată (tuplul de dimensiuni ca și coloane reale, indexat compus, cu unicitate reală).
  **Tabela de agregate** (sold per cont × tuplu de dimensiuni × perioadă) nu s-a construit: e
  derivabilă din `journal_formula` fără migrare pe registru, iar balanța de azi agregă liniile la
  cerere (A5).
- **Sloturi comune, nu per parte** (§2.3) — consecință a literei instrucțiunii, cu limita numită.

## 8. Surse

- Instrucțiunea proprietarului „construirea bazei motorului", 2026-08-29, etapa 1+2.
- Spec B §1.3, §1.7, §3.1, §4.3; [ADR-029](029-dimensiuni-analitice.md); [ADR-036](036-forma-postarii.md)
  §5–§6; [ADR-039](039-valuta-si-perioade.md) §3, §9; [ADR-047](047-stampila-parametrului-la-postare.md).
- `CLAUDE.md` — R10, R11, R13, R15, R18, R21, R22, C5, C31, C34, D6.
- Benchmark 1C: три субконто per cont, separate pe Dt/Ct; „свернуть проводки" ca alegere de
  configurație — practică, nu temei.
