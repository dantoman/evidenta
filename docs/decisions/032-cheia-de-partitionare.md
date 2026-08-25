# ADR-032 — Cheia de partiționare: desemnată acum, aplicată la un prag măsurat

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `OD-01`. Restrânge `OD-30`
- **Sursa:** `docs/_bootstrap/11-volume-model.md` (F0.11), măsurători în `backend/tests/volume/`

## Context

`R21` desemnează un set de tabele append-only de volum mare și le impune o disciplină — fără chei
străine intrând, coloana naturală de partiționare `NOT NULL` de la început, indecși care încep cu
contextul de tenant. Ce coloană devine cheie de partiționare a rămas deschis ca `OD-01`, cu mențiunea
din Amendamentul 1 că decizia se ia **după benchmark**, nu înainte.

Benchmark-ul există acum. Modelul de volum stă pe agregate publice (BNS, BNM) plus cifrele deja
scrise în Amendament, cu cinci ipoteze declarate și testate la sensibilitate. Măsurătorile rulează
sub `evidenta_app`, cu politicile RLS active.

## Ce s-a măsurat

Un milion de rânduri `audit_event` într-un singur tenant, scrise prin rolul aplicației cu `WITH
CHECK` evaluat pe fiecare rând:

| | Valoare |
|---|---|
| Scriere | 13.000–18.000 rânduri/s |
| Enumerarea Spec A §9.3, `LIMIT 50` | **6.749 ms**, un milion de rânduri citite |
| Aceeași, după `audit_event_recent_idx` | **1,05 ms**, 50 de rânduri citite |
| `count(*)` pe tenant | ≈6 s |

## Decizie

**Cheile se desemnează acum. Partiționarea se aplică la prag, nu la dată.**

| Tabelă | Cheie | Granularitate |
|---|---|---|
| `audit_event`, `document_event`, arhivele de payload | `occurred_at` | lunar sau trimestrial |
| `journal_line`, `inventory_movement` | `accounting_date` | anual |
| oricare | **niciodată `tenant_id`** | — |

**Pragul:** o tabelă se partiționează când trece de ~100 milioane de rânduri **și** interogările ei
se pot elaga după cheie. Ambele condiții, nu una. O tabelă mare ale cărei interogări nu ating cheia
nu câștigă nimic din partiționare, iar una mică nu are ce câștiga oricum.

### De ce nu `tenant_id`, măsurat și nu presupus

Distribuția BNS arată o piață dominată de micro: 68,6% dintre întreprinderile active au 0–4
salariați. La 15.000 de tenanți, raportul de volum între un tenant mijlociu și unul micro este de
ordinul 50:1. Partiționarea pe `tenant_id` ar produce partiții care diferă cu două ordine de mărime,
iar cea mare nu s-ar putea sparge mai departe.

Peste asta, numărul de tenanți crește prin vânzări. `tenant_id` ca cheie ar face din fiecare client
nou o operațiune de schemă.

### De ce timpul, și nu altceva

Retenția și arhivarea sunt deja pe perioadă — planul cere balanță de verificare pe 5 ani. O partiție
veche se detașează și se arhivează într-o operațiune, în loc să fie ștearsă rând cu rând dintr-o
tabelă append-only. Pentru `audit_event`, unde valoarea scade cu vechimea, asta este chiar motivul
pentru care partiționarea plătește.

## Ce a găsit benchmark-ul înainte de a răspunde la întrebare

**Un index greșit ca formă, nu o tabelă prea mare.** Enumerarea „ce s-a întâmplat în tenantul ăsta,
cel mai recent întâi" citea un milion de rânduri ca să întoarcă cincizeci — nu printr-un scan
secvențial, ci printr-un *index scan* peste tot. `audit_event_scope_idx` este `(tenant_id,
company_id, occurred_at)`: în interiorul unui tenant, rândurile sunt ordonate întâi după companie,
deci o ordonare după timp nu se poate servi din el.

Reparat prin `audit_event_recent_idx` — `(tenant_id, occurred_at DESC)`, migrarea `audit/0002`.
6.749 ms → 1,05 ms. Costul, măsurat: un al patrulea index pe tabela cu cel mai mare volum de
scriere, între 8% și 20% din debitul de scriere, cu varianță între rulări de același ordin.

Consecința pentru această decizie: **partiționarea nu era problema, iar dacă am fi partiționat fără
să măsurăm, am fi făcut o operațiune scumpă care nu repara nimic.** Interogarea ar fi citit tot
tenantul în fiecare partiție atinsă.

Verificarea scrisă inițial căuta absența cuvântului „Seq Scan" și trecea mulțumită la 6,7 secunde.
Acum verifică rândurile citite.

## O constatare care depășește partiționarea

**Planificatorul nu poate estima selectivitatea prin `app.current_tenant_id()`.** Funcția este
`STABLE`, dar nu are statistici, deci planificatorul presupune un număr fix de rânduri indiferent de
tabelă — s-a văzut `rows=1` acolo unde realitatea era 1.000.000.

Valabil pentru **fiecare** interogare din sistem, fiindcă toate filtrează prin ea. Două consecințe
practice: forma planului se schimbă cu dimensiunea reală în feluri pe care un fixture mic nu le arată
(la 2.000 de rânduri planificatorul alege corect *bitmap scan* plus sortare top-N, la un milion trece
la *index scan*), iar un plan prost ales din acest motiv nu se repară cu `ANALYZE`.

Nu se închide nimic aici. Se consemnează, fiindcă orice viitoare surpriză de performanță o va
întâlni.

## Consecințe

- `R21` și `R22` rămân neschimbate — disciplina este ce face trecerea la partiționare o operațiune
  în loc de o rescriere, iar decizia de față nu o înlocuiește
- `infra/schema/append_only.toml` conține deja `partition_column` pentru fiecare tabelă; acest ADR
  confirmă alegerile și adaugă pragul. Fișierul rămâne sursa unică
- **`OD-30` se restrânge**, nu se închide: volumul nu mai depinde de o firmă colaboratoare, dar
  structura (`OD-28`, F1.G0) și verificarea la leu (F1.2) încă o cer
- Măsurătorile rămân rulabile: `EVIDENTA_VOLUME_ROWS=1000000` în `backend/tests/volume/`. Un
  benchmark care nu se mai poate rula nu mai este o măsurătoare, ci o afirmație

## Limita, scrisă ca să nu fie presupusă

Măsurat pe mașina de dezvoltare, o instanță PostgreSQL 18 locală, fără concurență. Cifrele sunt
utile ca **raporturi** — 6.749 față de 1,05 — nu ca praguri de producție. Un prag de producție cere
măsurare pe hardware de producție, cu concurență, și acela este un exercițiu de F2, nu o condiție
pentru această decizie.
