# Corpusul de regresie — F1.10

Circa treizeci de cazuri construite intern, fiecare cu documentul, postarea așteptată — conturi și
sume — și **citarea** care o susține. Un caz care nu poate cita nu intră: `case(...)` din
`citations.py` e singura ușă, iar `test_corpus_integrity.py` verifică mecanic că fiecare citare
are un pasaj transcris în
[`docs/_input/cercetare/f1-10-corpus-citari.md`](../../../docs/_input/cercetare/f1-10-corpus-citari.md)
sau o secțiune a unui ADR existent.

**Ce testează corpusul** ([ADR-054](../../../docs/decisions/054-importul-e-distributie-corpusul-e-intern.md)
§3): că implementarea corespunde actelor citate — **nu** că înțelegerea noastră corespunde practicii.
Un caz greșit e un caz cu citare greșită, ceea ce se vede. Divergența dintre înțelegere și practică
se prinde la primul client real (F3).

**Rulează în CI** cu restul suitei (`uv run pytest -q`, `C14`); separat:
`uv run pytest -m fiscal_regression` sau `uv run pytest tests/corpus`. Sub rolul aplicației (`T1`).

## Cum e construit

- **`book.py`** — o companie pe **codurile Planului** (221, 242, 351, 811…), singurul loc din suită
  unde codurile reale apar în fixture-uri, fiindcă aici *sunt* obiectul: cazul citează *Plan 221* și
  afirmă o postare pe 221. Nu încarcă și nu decide planul de conturi al produsului (`OD-23`).
  Convențiile pe care stau handlerele — scara sumelor, direcția de rotunjire, regula de absorbție —
  vin din **fișierele livrate** (`fiscal/parameters/data/*.toml`) prin **calea livrată**:
  `load_fiscal_parameters` (draft) și `activate_fiscal_parameters --approver` (activ), sub rolul
  de date de referință, cu rând în `privileged_access_log` (ADR-049, `P-4`). O modificare a
  fișierului, a încărcătorului sau a porții de activare schimbă ce rulează corpusul.
- **`agree(book)`** — criteriul de ieșire din F1, punctele 1–2: pe aceleași linii, balanța, fișa
  contului, Cartea Mare și șahul dau un singur răspuns. Fiecare caz se termină cu el; gardianul
  verifică prezența apelului.
- **Seturile** — `corpus/<cheie>/<versiune>`, convenția pe care o foloseau deja cele două valori
  `regression_case_set` din fișierele livrate. `<cheie>` e `logic_key` din `fiscal_logic_version`
  când cazul fixează o regulă versionată (`production.overhead_absorption`,
  `accounting.money_rounding`), altfel familia handlerului (`settlement.differences`,
  `period.year_closed`…). Gardianul cere ca fiecare `regression_case_set` numit de un fișier de
  parametri să aibă cel puțin un caz.

## Cazurile, pe module

| Modul | Handler | Actul |
|---|---|---|
| `test_c5_absorption.py` | repartizarea costurilor indirecte (ADR-058) | SNC „Stocuri" pct. 29–31, **Anexa 1** (exemplul numeric al actului), pct. 57; Plan 811, 821, 714, clasa 8 |
| `test_c4_settlement.py` | diferențele la decontare (ADR-057) | SNC „Diferenţe de curs valutar şi de sumă" pct. 8–10, 17, 19–21, 23, **Exemplele 1, 2, 5**; Plan 221, 521, 612, 622, 714, 722, 242; nomenclatorul 6226/7224, 6227/7225, 6127/7147 |
| `test_revaluation.py` | reevaluarea la data raportării (A10, ADR-097) | SNC „Diferenţe de curs valutar şi de sumă" pct. 11, 13–15, **Exemplul 3**; nomenclatorul 2211/2212, 6226/7224 |
| `test_closing.py` | închiderea lunii și a exercițiului (ADR-056) | SNC „Capital propriu şi datorii" pct. 21, 23, **Exemplul 7**; Plan 611, 714, 731, 351, 333, clasa 8; ADR-050 §3.2, ADR-054 §4 |
| `test_manual_note.py` | nota manuală | SNC „Venituri" pct. 17, **Exemplul 8**; Plan 221, 242, 216, 521, 534, 611, 711, 731 |
| `test_opening_balances.py` | soldurile inițiale | Plan 216, 221, 242, 311, 521 („Soldul contului … este debitor/creditor"); cap. I, partida dublă |
| `test_storno.py` | stornoul (ADR-006, ADR-038 §7.2) | SNC „Politici contabile…" pct. 33 (1), (2); SNC „Venituri" pct. 17, Exemplul 8 |

## Abateri cunoscute, motivate

Nu sunt eșecuri tolerate: fiecare are o decizie în spate și un caz care o afirmă.

1. **C5, banul rămas — pe cota cea mai mare.** Coloana 4 a tabelului din Anexa 1 însumează 120 000
   cu banul din împărțire pe „B" (28 235,30); motorul îl pune pe cota cea mai mare („A": 49 411,77)
   și între cote egale pe codul cel mai mic (ADR-058 §2.5). Cele două postări ale actului —
   totalurile — ies exact; două celule diferă cu un ban. Actul nu prescrie regula restului; noi am
   ales **determinismul față de date** (același fapt, altă ordine, aceleași cote). Decizia
   proprietarului (2026-08-30), afirmată în
   `test_anexa_1_in_full_reproduces_the_two_postings_the_act_writes`.
2. **Golul 2014–2017** (ADR-058 §6). Regula de absorbție e în vigoare din 01.01.2014, direcția de
   rotunjire din 28.10.2017; un fapt datat între ele găsește regula și nu găsește direcția, iar
   registrul refuză numind cheia și data — rămâne refuz, cum a decis proprietarul. Cazul din corpus
   e datat 30.06.2016 și stă pe datele din fișierele livrate: cine ar închide golul mutând
   `valid_from` înapoi ar vedea aici.

## Explicate, nu divergențe

3. **C4, Exemplul 2, termenul avansului — redacție abrogată.** Actul recunoaște creanța integral la
   cursul livrării și, la trecerea în cont a avansului primit la alt curs, înregistrează pe partea
   avansată **783 lei** diferență de curs (primul termen din cei 2 910). **Datare verificată
   (2026-08-30):** Exemplul 2 e textul din 2013, fără notă de modificare; pct. 11 și 12 au fost
   rescrise prin OMF 48/2019 (în vigoare 01.01.2020) și mută avansurile acordate/primite pe partea
   nemonetară — nu se recalculează, se înregistrează la cursul recunoașterii inițiale. Handlerul, cu
   `settles_advance = True`, nu postează nimic: e redacția în vigoare, nu o lacună. Primul termen
   ilustrează redacția abrogată și **nu e de implementat**; corpusul reproduce al doilea (2 127 lei).

## Raportate — acum decizii deschise

4. **C5, nivelul la care se aplică cota din pct. 30 — `OD-77`.** Anexa 1 aplică raportul
   *efectiv / normal* **pe fiecare produs**, cu capacitatea normală a produsului, și abia apoi
   însumează: 103 764,71 în cost, 16 235,29 la cheltuieli. Handlerul primește **o** capacitate
   normală și **un** volum efectiv pe fapt; cu cele trei produse într-un singur fapt (17 000 din
   20 000) ar da 102 000 / 18 000. Corpusul reproduce actul postând un fapt per produs. Propunerea
   din `OD-77`: `AllocationFact` poartă capacitatea per produs — de închis prin ADR peste ADR-058,
   nu în corpus.
5. **Storno parțial fără legătură navigabilă — `OD-78`.** Cazurile pct. 33 (2) și Exemplul 8
   (returul) corectează *o parte* dintr-o înregistrare, deci trec prin nota manuală cu corespondența
   inversă, nu prin `post_reversal` — și nota nu poartă nicio legătură spre înregistrarea corectată.
   Cele două legături `R14` există numai la stornoul integral. De închis înainte de F2: vânzările vor
   produce retururi parțiale în volum.

## Ce nu e aici

- **Reformarea bilanțului** (334, 333 → 332) — `OD-73`, în afara lanțului livrat.
- **Impozitul pe venit ca sumă calculată** — cazurile îl *înregistrează* (Plan 731), nu îl
  calculează; cota e parametru (`R15`, `OD-22`). La fel TVA-ul: suma e a documentului.
- **Perioada de gestiune = anul** — citată prin ADR-054 §4 (Legea 287/2017 art. 24 alin. (1)), al
  cărei text nu a fost citit aici; Planul spune „la finele perioadei de gestiune" și SNC
  „Prezentarea situaţiilor financiare" pct. 18 pune închiderea conturilor de gestiune între lucrările
  premergătoare situațiilor financiare.
