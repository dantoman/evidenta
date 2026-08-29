# ADR-055 — Precizia cantității este a unității de măsură: coloană obligatorie, fără implicit, înghețată la prima cantitate

- **Status:** Acceptat — **decizie de domeniu** (produs și contabilitate), luată de proprietar prin
  instrucțiune scrisă, 2026-08-29, după lectura `V1`; alegerea de inginerie dintre „coloană pe
  `unit_of_measure`" și „`scope` nou pe `fiscal_parameter`" lăsată sesiunii, cu observația
  proprietarului că a doua ar fi recipientul greșit chiar cu scope-ul potrivit
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** `OD-70`
- **Afectează:** `masterdata/uom` (`decimal_places` fără implicit; `services/precision`; trigger
  `0061`), `accounting/currency/services/amounts.line_amounts` (primește precizia, nu o rezolvă),
  `fiscal/parameters/services/scales` (fără `quantity_scale`), [ADR-037](037-conventii-de-platforma.md) §3.2
- **Legate:** [`v1-factura-fiscala-omf-118-2017.md`](../_input/cercetare/v1-factura-fiscala-omf-118-2017.md),
  [ADR-049](049-rolul-de-date-de-referinta.md), [ADR-054](054-importul-e-distributie-corpusul-e-intern.md) §4

---

## 1. Context

`V1` a fost citită: Ordinul MF nr. 118 din 28.08.2017 — formularul (anexa nr. 1) și Instrucțiunea
(anexa nr. 2) — **tace** asupra zecimalelor cantității, nici pe categorii, nici per unitate; pct. 13
spune doar *„se indică […] cantitatea mărfurilor"*, iar pct. 12 cere unitatea de măsură lângă ea.
Tăcerea e consemnată. Ce rămâne nu e „câte zecimale", ci **cine** le alege (`OD-70`).

**Măsurat înainte de a decide forma:** `unit_of_measure.decimal_places smallint NOT NULL`, cu
`CHECK 0..6`, există din F0.7 — cu un `default=0` în model, adică „bucăți dacă nu spune nimeni".
Nicio unitate nu e încărcată în baza de dezvoltare. Cele patru tabele care poartă o cantitate cu
unitatea ei: `document_line.unit_id`, `journal_line.uom_id`, `journal_formula.uom_id`,
`opening_balance_inventory.uom_id`; catalogul (`item.base_unit_id`, `item_unit`, `item_barcode`)
referă unitatea fără să poarte cantități.

## 2. Opțiuni evaluate

1. **Platforma** — un `accounting.quantity_scale` global, ca precizia sumelor. *Dezavantaj:* o valoare
   ar fi greșită pentru majoritatea unităților — bucățile n-au zecimale, kilogramele au trei, litrii
   trei, orele două. Pentru câteva ore în 2026-08-29 a existat exact această cheie, în rezolvatorul
   fiscal; e scoasă de aici.
2. **Tenantul** — politică (strat 3, ADR-036). *Dezavantaj:* pune o proprietate a lucrului măsurat pe
   compania care îl măsoară; nimic din SNC n-o cere; și e **singurul loc unde răspunsul nu depinde
   de tenant** — a-l face per tenant ar inventa o divergență.
3. **Unitatea de măsură** — *aleasă*. Precizia e atribut al nomenclatorului de unități, ca și
   coeficientul de conversie. **Nu e parametru fiscal**: nu vine dintr-un act, nu se schimbă prin
   lege, n-are `valid_from`. `fiscal_parameter` ar fi recipientul greșit chiar dacă ar avea `scope`
   per unitate — motiv pentru care alegerea de inginerie n-a mai fost o alegere: coloana există, ce
   lipsea era să fie **obligatorie, fără implicit**, și **înghețată** odată folosită.

**Întrebarea pusă explicit de proprietar — există vreun motiv ca precizia cantității să fie totuși
parametru fiscal?** Verificat pe cod, nu: `R18` (recalcularea unei perioade cu parametrii de atunci)
nu e atins, fiindcă sumele postate sunt autoritative (ADR-037 §4) și cantitatea liniei stă pe linie
cum a fost scrisă; ce cere `R18` aici nu e istoric de valori, ci **ca valoarea să nu se schimbe sub
liniile care o poartă** — de unde triggerul, nu `valid_from`. Singura constrângere externă
plauzibilă — schema XML e-Factura (`V2`) ar putea plafona zecimalele — e un plafon global, deja
exprimat de `CHECK (decimal_places <= 6)`, nu o valoare per unitate.

## 3. Decizia

1. **`unit_of_measure.decimal_places` e obligatorie și fără implicit.** Cine creează unitatea spune
   câte zecimale poartă. `NOT NULL` era deja în bază; migrarea `uom/0002` scoate implicitul din model.
2. **Precizia îngheață la prima cantitate purtată** (`0061`): un `UPDATE` al lui `decimal_places` pe
   o unitate referită de o linie de document, de jurnal, de formulă sau de solduri inițiale e refuzat
   de trigger, sub orice rol; corecția e o unitate nouă. Catalogul (articole, coduri de bare) nu
   îngheață nimic: nu poartă cantități.
3. **Calculul liniei primește precizia, nu o rezolvă.** `line_amounts(quantity_scale=…)` — argument
   obligatoriu; stratul documentar îl citește prin `masterdata.uom.services.precision.quantity_scale_of`
   (D6). O cantitate mai fină decât unitatea e **refuzată, nu rotunjită**: la preț, rotunjirea produce
   o eroare de bani; la cantitate, produce un document care descrie altceva decât s-a întâmplat.
4. **`accounting.quantity_scale` nu există** în rezolvatorul fiscal și nu intră în
   `platform_conventions.toml`; comentariul de acolo spune de ce.

## 4. Consecințe

- **Devine posibil:** `line_amounts` nu mai așteaptă un parametru care n-ar fi venit niciodată;
  unitățile se definesc cu precizia lor și o păstrează; F1.6 rămâne cu o singură alegere a
  proprietarului (§5 din ADR-037 — direcția la echidistanță).
- **Devine imposibil sau scump, asumat:** o unitate cu precizia greșită, odată folosită, nu se
  corectează — se înlocuiește; migrarea de unități între precizii e o operațiune de nomenclator, nu
  o editare.
- **Ce se modifică:** `test_masterdata.py` (unitățile își spun precizia), `test_documents.py` (fără
  implicit; înghețarea), `test_line_rounding.py` (`line()` trece precizia unității),
  `test_reverse_sql.py` (`0061` în lista de rotații), registrul (`OD-70` în E), ADR-037 §3.2.
- **Ce se verifică automat:** `IntegrityError` la o unitate fără precizie; `restrict_violation` la
  schimbarea preciziei unei unități cu linie de document; schimbarea liberă pe una nefolosită;
  refuzul unei cantități mai fine decât unitatea; rotația `0061` în gardianul de schemă.

## 5. Surse

- Instrucțiunea proprietarului, 2026-08-29 (a treia și a patra).
- Ordinul MF nr. 118 din 28.08.2017, anexa nr. 2, pct. 12–13 — tăcerea asupra zecimalelor
  ([cercetare](../_input/cercetare/v1-factura-fiscala-omf-118-2017.md) §4).
- `backend/evidenta/masterdata/uom/models.py` (F0.7) — coloana existentă; `information_schema` pe
  baza de dezvoltare — cele nouă coloane care referă o unitate.
- `CLAUDE.md` — `R10`, `R15`, `R18`, `D6`; [ADR-037](037-conventii-de-platforma.md) §3.2, §4.
