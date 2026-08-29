# 07 — Backlog F1, parțial: grilele de date

- **Data:** 2026-08-24
- **Statut:** **detaliul canonic** pentru `F1.G1` și `F1.G2`. Backlogul F1 există acum
  (`08-f1-backlog.md`) și le **secvențiază**, fără să le copieze: o a doua copie a aceleiași
  sarcini diverge de prima, iar F0 a produs destule exemple. Cine caută poziția lor în fază se uită
  în `08`; cine le implementează, aici.
- **Sursa:** `../decisions/001-grila-de-date.md` (Acceptat), `CLAUDE.md` §2.6 (`C16`–`C22`)
- **Ordinea F1 de referință:** `../_input/evidenta-implementation-spec.md` §6.2

## De ce sarcini proprii

TanStack Table este headless: dă starea și logica — modele de rânduri, sortare, filtrare, grupare,
dimensionare — și nimic altceva. Virtualizarea, coloanele înghețate, comportamentul tastaturii și
editarea se construiesc aici. Bugetul de timp este **mai mare** decât ar fi fost cu o grilă
comercială, nu mai mic. O grilă născută ca efect secundar al primului raport devine baza pe care se
copiază tot restul.

## Secvențiere

```
F1.2 (Ledger)  →  F1.G1 (DataGrid)   →  F1.8 (Rapoarte contabile)
               →  F1.G2 (EntryGrid)  →  F1.7 (Note contabile manuale)
```

Ambele după F1.2, ca să existe date reale pe care să lucreze. `DataGrid` înaintea F1.8, `EntryGrid`
înaintea F1.7.

## Conflict de secvențiere, semnalat

**Cerința de proces:** ambele componente se construiesc pe date reale din 1C, nu pe date fictive.
Performanța virtualizării și nevoile reale de coloane apar doar la volum; o grilă validată pe 50 de
rânduri inventate nu este validată.

**Problema:** F1.9 — importatorul 1C — vine în ordinea de referință **după** F1.7 și F1.8. Cerința
nu poate aștepta modulul.

**Rezolvare propusă:** ceea ce lipsește este *setul de date*, nu *conectorul*. Se produce un extras
unic dintr-o bază 1C reală — plan de conturi, parteneri, un an de rulaje — anonimizat, versionat ca
fixture de dezvoltare. F1.9 rămâne la locul lui și construiește conectorul propriu-zis.

**Blocat de:** — *(2026-08-29, [ADR-054](../decisions/054-importul-e-distributie-corpusul-e-intern.md)
§3.4: **alternativa de mai jos e aleasă explicit**. `OD-28` și `OD-30` au plecat la F3, cu
importatorul; extrasul real, când vine, se folosește pentru a doua jumătate. `OD-32` — contabilul
practicant — s-a închis prin `ADR-010`.)*

**Aceasta este o precondiție, nu un detaliu de implementare.** Alternativa se alege explicit, nu
prin omisiune — și alternativa **nu** este „date inventate" pur și simplu:

> **Date inventate cu volum realist:** zeci de mii de linii, distribuție plauzibilă a conturilor,
> denumiri de lungime realistă.

Ce validează asta: **performanța virtualizării și lățimea coloanelor** — jumătate din ce vrei de la
datele reale.

Ce pierzi: **cealaltă jumătate** — structurile pe care nu le anticipezi, conturile folosite ciudat,
câmpurile pe care nimeni nu le completează. Un generator scris de aceeași persoană care proiectează
grila reproduce exact așteptările pe care grila ar trebui să le înfrunte.

Diferența este numită aici ca decizia să fie luată știind ce se sacrifică.

**F1.G0, cum se construiește (ADR-054):** volumul din modelul F0.11 — scenariul „Mare", 18.000 de
documente pe an, cu distribuția lui pe conturi; structura din corpusul F1.10 și din planul real de
476 de conturi — parteneri cu IDNO-uri fictive, un an de rulaje generat din cazurile corpusului,
denumiri de lungime realistă. Versionat ca fixture de dezvoltare, ca și cum ar fi venit din 1C.

---

## F1.G1 — `DataGrid`

- **Obiectiv:** o componentă de citire, virtualizată, care servește toate rapoartele și listele din
  F1 fără ca vreun ecran să atingă TanStack direct.
- **Conține:**
  - virtualizare;
  - coloane înghețate;
  - redimensionare și reordonare de coloane;
  - configurație de coloane persistată **per utilizator și per tenant**;
  - randarea rândurilor de subtotal (valorile vin de la server — `C19`);
  - cârlig de drill-down către documentul sursă;
  - stări de încărcare, gol și eroare;
  - integrare cu modulul de formatare numerică (`C18`).
- **Fișiere:** `frontend/src/components/grid/DataGrid/`, modulul de formatare,
  regula ESLint `no-restricted-imports` (`C16`), modelul de preferințe de utilizator (backend)
- **Depinde de:** F1.2 (date reale în ledger), F1.G0 *(setul de date 1C — vezi mai sus)*
- **Review:** `tenancy-guard` (preferințele de coloane sunt date per tenant),
  `schema-reviewer` (modelul de preferințe)
- **Terminat:** un raport real din F1.8 randează peste fixture-ul F1.G0 la volum, cu subtotaluri
  primite de la server, drill-down funcțional, și zero import direct de `@tanstack/react-table` în
  ecrane — verificat de ESLint, nu de citire.
- **Blocat de:** `OD-19` (management de stare, client HTTP). *`OD-34` închisă prin `ADR-009`;
  `OD-35` prin `ADR-042`; ținta de performanță (`OD-29`) prin [ADR-053](../decisions/053-tinta-de-performanta.md).*

---

## F1.G2 — `EntryGrid`

- **Obiectiv:** **primitiva generală de introducere cu tastatura** a aplicației. Nu „grila de linii
  de document" — o primitivă care acoperă orice suprafață cu aceeași nevoie: introducere rapidă,
  tastatură, validare pe celulă, volum mic sau mediu.
- **Domeniu, enumerat ca cerință de proiectare, nu ca listă de utilizări viitoare:**
  - note contabile manuale;
  - solduri inițiale (GL, clienți, furnizori, stocuri, active, angajați);
  - **maparea conturilor la import** (1C);
  - **potrivirea extrasului bancar**;
  - linii de document;
  - linii de salarizare.
- **De ce contează acum, nu la F1.9.** Dacă `EntryGrid` e conceput îngust — pentru liniile unei
  facturi — atunci reconcilierea chiar are nevoie de altceva, iar a doua bibliotecă de grilă
  (`OD-41`) devine inevitabilă. Dacă e conceput ca primitivă generală, probabil o face inutilă.
  **Acesta este singurul element din discuția despre grile care are cost dacă întârzie.**
  *`ADR-001` spune „`EntryGrid` — introducere" și enumeră exemple; nu restrânge domeniul. Sarcina
  de față îl specifică — elaborare, nu contrazicere.*
- **Precondiție:** contractul de introducere cu tastatura (`OD-36`) se scrie și se aprobă **înainte**
  de cod. *Scris și aprobat: [ADR-052](../decisions/052-contractul-de-tastatura.md), 2026-08-29.* Ordinea de tab, tastele rapide, deplasarea pe linii și comportamentul tastaturii numerice
  sunt decizie, nu detaliu de implementare.
- **Conține:**
  - editare pe celulă;
  - validare pe celulă;
  - semantica `Tab` și `Enter` (deplasare vs. confirmare vs. linie nouă — se fixează în contract);
  - adăugare și ștergere de rânduri din tastatură;
  - comportamentul câmpurilor numerice;
  - indicator de echilibru debit/credit.
- **Separatorul zecimal — cerință explicită.** Interfața este în română, unde separatorul zecimal
  este **virgula**. Contabilii introduc de la tastatura numerică, care produce **punct**. `EntryGrid`
  acceptă ambele la introducere și afișează consecvent, conform `C18`. *Descoperit la testarea cu
  utilizatori, acest detaliu găsește douăzeci de ecrane deja construite pe comportamentul greșit.*
- **Fișiere:** `frontend/src/components/grid/EntryGrid/`, contractul de tastatură în
  `docs/decisions/`
- **Depinde de:** F1.2, F1.G0, contractul de tastatură
- **Review:** `accounting-reviewer` (indicatorul de echilibru reflectă `R11`, nu îl înlocuiește —
  echilibrul se verifică în bază de date, nu în grilă)
- **Terminat:** trei criterii, al treilea fiind cel care verifică efectiv generalitatea:
  1. o notă contabilă completă, cu minim cinci linii, se introduce de la tastatură fără mouse, pe
     fixture-ul F1.G0;
  2. valorile cu punct și cu virgulă produc același rezultat, iar ecranul nu adaugă niciun handler
     propriu de taste;
  3. **aceeași componentă, fără fork și fără ramuri specifice ecranului, servește o suprafață care
     nu este linii de document** — maparea conturilor la import. Fără acest criteriu,
     „primitivă generală" rămâne intenție, iar `OD-41` se redeschide singură.
- **Blocat de:** `OD-19`. *`OD-34` închisă prin `ADR-009`; `OD-35` prin `ADR-042`; `OD-36` — contractul — prin [ADR-052](../decisions/052-contractul-de-tastatura.md), 2026-08-29.*

---

## Ce nu conțin aceste sarcini

- **Documentele tipărite.** `C22` le scoate din React. Factura, ordinul de plată, balanțele,
  situațiile financiare și declarațiile se generează server-side, ca pipeline separat. Nu este
  sarcină de grilă și nu se strecoară în una.
- **Exporturile.** `C20` le pune pe server. `DataGrid` declanșează exportul; nu îl produce.
- **Panoul de reconciliere.** Ecranul de reconciliere 1C și cel de potrivire a extrasului bancar au
  aceeași formă: două seturi, sugestii de potrivire calculate pe server, confirmare rapidă, cazuri
  rămase. Interacțiunea dominantă **nu este editarea de celule** — este acceptarea sau respingerea
  unei sugestii, plus corectarea manuală a excepțiilor. Forma potrivită este probabil un panou de
  potrivire în două coloane cu tastatură, nu o grilă. Nu este sarcină de grilă și nu se presupune că
  este una; se proiectează la F1.9, uitându-se la interacțiune, nu la aspect. Vezi `OD-41`.
