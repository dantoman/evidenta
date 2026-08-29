# ADR-054 — Importatorul 1C e instrument de distribuție (F3), nu fundație; F1 se validează pe un corpus intern

- **Status:** Acceptat — decizie de scop, luată de proprietar prin instrucțiune scrisă, 2026-08-29
  (a doua); §4 este o **decizie de domeniu** contabil, răspunsă de sesiune peste actul citat, la
  cererea explicită a proprietarului
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** — *(mută importatorul și `OD-28`/`OD-30` de pe drumul critic al F1 la F3; reclasifică
  F1.10; alege explicit alternativa sintetică pentru F1.G0)*
- **Afectează:** `08-f1-backlog.md` (criteriul de ieșire, F1.9, F1.10, F1.6), `07-f1-grile.md`
  (F1.G0), `000-open-decisions.md` (`OD-28`, `OD-30`), `docs/PROGRESS.md`, F3 (Migration Center)
- **Legate:** [ADR-010](010-contabilul-practicant.md) (măsura riscului e corpusul),
  [ADR-050](050-lantul-de-inchidere-ca-roluri.md) (lanțul), [ADR-039](039-valuta-si-perioade.md) §6
  (perioada de gestiune), [ADR-049](049-rolul-de-date-de-referinta.md) §7 (`OD-28` reformulată)

---

## 1. Context

Criteriul de ieșire din F1 avea cinci puncte, dintre care trei numeau extrasul 1C: *balanță
corectă pe date reale importate din 1C*, *diferență zero la reconciliere*, *corpusul de regresie
în CI* — ultimul blocat pe „contabilul practicant", cu cazuri reale. `OD-28` a fost reformulată
în aceeași zi (ADR-049 §7): baza reală blochează cititorul formatului și validarea la leu, nu
construcția. Proprietarul a tras concluzia până la capăt: **dacă importatorul e opțional, nu are ce
căuta în criteriul de ieșire.** Cele trei criterii validează de fapt altceva — că **registrul e
corect** — iar *„balanță corectă pe date importate din 1C"* testează două lucruri deodată: motorul
și cititorul de format. Despărțite, motorul se validează azi.

Spec-ul de implementare pune deja `migration/mapping` la F2 și `migration/reconciliation` la F3, iar
master planul V2 numește *1C Migration Center productizat* la F3. Doar `migration/onec` stătea în
F1, ca „fundament".

Pe corpus: ADR-010 a colapsat rolurile — a doua semnătură nu mai e verificare independentă, iar
măsura riscului contabil devine acoperirea corpusului de regresie. Backlogul îl bloca totuși pe
„cazurile cu rezultat verificat nu se pot fabrica", adică pe un contabil din afară.

## 2. Opțiuni evaluate

1. **Extrasul 1C rămâne pe drumul critic al F1.** *Avantaj:* validare contra practicii reale.
   *Dezavantaje:* F1 nu se poate închide fără un act extern cu termen necontrolat; criteriul
   amestecă motorul cu cititorul; F0 s-a încheiat cu aceeași dependență deschisă. *Cost:* fiecare
   săptămână de așteptare e o săptămână în care fundația nu e declarată validă, deși e.
2. **Extrasul iese din criteriu; corpusul e intern, construit de cine construiește motorul** —
   *aleasă*. Douăzeci de cazuri cu rezultat considerat corect, cu SNC și planul de conturi citate,
   ca regresie: prind modificările care schimbă comportamentul. **Ce nu prind** e divergența dintre
   înțelegerea noastră și practică — dar aia se prinde la primul client real, care vine oricum
   înainte de v3. *Cost:* onest, numit: corpusul nu e o probă de conformitate, e o probă de
   stabilitate.
3. **Corpus intern, dar importatorul rămâne F1 ca „fundament".** *Dezavantaj:* păstrează în F1 un
   modul pe care nimic din F1 nu-l consumă; „fundament" era numele, nu funcția.

## 3. Decizia

1. **Importatorul 1C (`migration/onec`) trece la F3**, alături de Migration Center — instrument de
   distribuție, nu fundație. `OD-28` și partea de structură din `OD-30` blochează F3, nu F1.
   Cererea de extras (`_input/cereri/od-28-extras-1c.md`) rămâne trimisă; răspunsul ei nu mai
   condiționează nimic din F1.
2. **Criteriul de ieșire din F1 se rescrie:**
   - balanța de verificare corectă — **pe corpusul intern**, nu pe date importate;
   - diferență zero la reconciliere — **între balanță, Cartea Mare și fișa contului, pe același
     corpus** (aceleași linii, trei agregări, un singur răspuns);
   - storno cu lineage coerent — **bifat**: demonstrat de `tests/integration/test_vertical_slice.py`
     (ambele legături `R14`, al doilea storno refuzat, balanța la zero);
   - postarea într-o perioadă închisă refuzată — **bifat**: `test_posting_invariants.py`
     (`test_a_closed_period_refuses_the_posting`, `test_a_locked_period_refuses_with_its_own_code`)
     și `test_periods.py::test_posting_into_a_closed_period_is_refused`;
   - corpusul de regresie rulează în CI — **rămâne**, cu F1.10 reclasificată.
3. **F1.10 nu mai e blocată pe un contabil extern.** E o sarcină de construit cazuri — circa
   douăzeci, fiecare cu documentul, postarea așteptată, contul și suma, și **citarea** (SNC,
   Planul general de conturi, ADR-036 §11) — făcută de sesiunea de implementare, cu review
   `fiscal-reviewer` / `accounting-reviewer`. Cazul care nu poate cita nu intră.
   *Precizarea proprietarului, aceeași zi:* cerința de citare **schimbă natura riscului** — corpusul
   nu mai testează dacă înțelegerea corespunde practicii, ci dacă **implementarea corespunde actelor
   citate**. O proprietate mai slabă, dar onestă și verificabilă intern: un caz greșit e un caz cu
   citare greșită, ceea ce se vede.
4. **F1.G0 se construiește sintetic**, alegând explicit alternativa pe care `07-f1-grile.md` o
   numea: volum realist din modelul F0.11, structură din corpus (plan real de 476 de conturi,
   parteneri, un an de rulaje generat). Ce se sacrifică e scris acolo și rămâne scris: structurile
   neanticipate. Se recuperează la primul extras real, la F3.

## 4. Întrebarea de treizeci de secunde — închiderea lunii nu postează lanțul 351

Proprietarul a numit ce îl preocupă cel mai mult dintre validările „mutate": *închiderea lunii care
nu postează lanțul 351, fiindcă dacă e greșită, e structurală*. Răspunsul, peste actul din repo:

**Proiectarea e corectă. Lanțul 351 e anual, nu lunar.**

- Planul general de conturi, cap. III, clasa 6: *„…iar în debit – decontarea **la finele perioadei
  de gestiune** a veniturilor acumulate la rezultatul financiar total"*; simetric pentru clasa 7;
  *„Contul 351 «Rezultat financiar total» la sfîrşitul perioadei de gestiune nu are sold"*
  ([`od-22-planul-de-conturi.md`](../_input/cercetare/od-22-planul-de-conturi.md) §2, transcris din
  PDF-ul Ministerului Finanțelor).
- Legea contabilității și raportării financiare nr. 287/2017, art. 24 alin. (1): **perioada de
  gestiune este anul calendaristic**, cu cele patru excepții enumerate în
  [ADR-039](039-valuta-si-perioade.md) §6 — niciuna nu e luna.
- Deci „finele perioadei de gestiune" e sfârșitul exercițiului. Lunar, conturile claselor 6 și 7
  **rămân deschise și acumulează**; rezultatul intermediar al unei luni sau al unui semestru se
  **citește** din rulajele lor, nu se **postează**. Închiderea lunii e blocare (`R12`) plus
  invariantul clasei 8 — conturile de gestiune se închid în interiorul perioadei, fiindcă costul
  producției se decontează pe măsură ce se fabrică, nu la an.
- Consecința structurală, spusă invers: dacă lanțul s-ar posta lunar, 333 ar primi douăsprezece
  profituri parțiale în cursul anului, iar reformarea bilanțului (334 → 333, 333 → 332) ar avea
  douăsprezece momente în loc de unul — ceea ce actul nu prevede nicăieri.

Ce rămâne **inferență**, marcată ca atare: situațiile financiare intermediare (art. 22 din aceeași
lege, pentru entitățile de interes public) se derivă din rulaje — actul nu prescrie o postare
intermediară, iar absența unei prescripții nu e o prescripție. Dacă o entitate le vrea postate, e o
politică (strat 3) pe care nimeni n-a cerut-o; nu se construiește.

## 5. Consecințe

- **Devine posibil:** F1 nu mai are niciun blocaj extern. Rămâne `V1` — Ordinul MF 118/2017,
  Anexele 1 și 1a, document public, o oră — și atât. F1.5.4 (închiderea) și F1.10 (corpusul) pot
  începe; criteriul de ieșire se poate bifa din cod și din corpus.
- **Devine imposibil sau scump, asumat:** conformitatea cu practica reală nu e demonstrată de F1 —
  e demonstrată de primul client, la F3, cu Migration Center; grilele se validează pe structuri
  anticipate până atunci.
- **Ce se modifică:** `08-f1-backlog.md` — criteriul de ieșire (două bifate, trei rescrise), F1.9
  mutat la F3, F1.10 reclasificată, F1.6 blocată doar pe `V1` (valorile `OD-22` sunt ale F2);
  `07-f1-grile.md` F1.G0; `000-open-decisions.md` — `OD-28` și `OD-30` blochează F3; `PROGRESS.md`.
- **Ce se verifică automat:** corpusul (`C14`), în CI, la fiecare modificare de parametru sau
  algoritm; la F1.5.4, testul că `period.month.closed` nu produce nicio linie pe 351/333 și că
  `period.year.closed` produce lanțul din ADR-050 §3.2 în ordinea de acolo.

## 6. Surse

- Instrucțiunea proprietarului, 2026-08-29 (a doua).
- Planul general de conturi contabile, Ordinul MF nr. 119 din 06.08.2013, cap. III — clasa 6, clasa
  7, contul 351 ([`od-22-planul-de-conturi.md`](../_input/cercetare/od-22-planul-de-conturi.md) §2).
- Legea nr. 287/2017, art. 24 alin. (1) — perioada de gestiune ([ADR-039](039-valuta-si-perioade.md) §6).
- `docs/_input/evidenta-implementation-spec.md` — `migration/` (onec F1, mapping F2, reconciliation
  F3); `docs/_input/evidenta-master-plan-v2.md` — F3, „1C Migration Center productizat".
- [ADR-010](010-contabilul-practicant.md); `07-f1-grile.md` — „Conflict de secvențiere, semnalat".
- `backend/tests/integration/test_vertical_slice.py`, `tests/isolation/test_posting_invariants.py`,
  `tests/isolation/test_periods.py` — cele două criterii deja demonstrate, citite, nu presupuse.
