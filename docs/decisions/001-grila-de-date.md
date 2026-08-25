# ADR-001 — Grila de date: TanStack Table, cu două componente interne

- **Status:** Acceptat — 2026-08-24, de proprietarul proiectului, sub regimul `ADR-002` (decizie tehnică, fără conținut contabil)
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** niciuna. Extrage grila din `OD-19`, care rămâne deschisă, restrânsă
- **Afectează:** `frontend/`, F0.10, toate ecranele de raportare din F1, notele contabile manuale

## Context

Grila de date este componenta dominantă a frontend-ului într-un ERP contabil, nu un detaliu de
prezentare. Aceleași cerințe reapar la Cartea Mare, balanța de verificare, jurnalele de vânzări și
cumpărări, registrul TVA, fișa contului, listele de documente și liniile de document.

Alegerea a fost ridicată în afara registrului: `OD-19` formula stack-ul frontend ca „componente,
management de stare, client HTTP, rutare, i18n, formatare", ceea ce nu acoperă grila. Termenul real
este mai devreme decât F0.10 — primul ecran cu tabel din F1 fixează în practică soluția pentru
toate celelalte.

Nu există încă cod de frontend. Modelul de volum de date este necunoscut (`OD-30`), deci pragurile
de virtualizare se stabilesc pe estimări, nu pe măsurători.

## Opțiuni evaluate

1. **TanStack Table (headless)** — bibliotecă de stare și logică: modele de rânduri, sortare,
   filtrare, grupare, dimensionare și ordonare de coloane. Nu randează nimic.
   *Avantaje:* MIT, fără cost per dezvoltator; nu impune nimic vizual, deci se compune cu orice
   strat de randare; nu deține datele, deci totalurile pot rămâne autoritatea serverului.
   *Dezavantaje:* randarea, virtualizarea, editarea inline și navigarea cu tastatura se construiesc
   de noi. Efort real, nu de o zi.
   *Cost de schimbare ulterioară:* mediu — dacă ecranele consumă componentele interne și nu
   biblioteca, înlocuirea atinge două fișiere, nu patruzeci.

2. **AG Grid Enterprise** — grila comercială de referință pentru acest tip de aplicație.
   *Avantaje:* virtualizare, coloane înghețate, grupare, agregare, editare și export Excel
   disponibile imediat; răspunsul matur pentru grile ERP.
   *Dezavantaje:* licență comercială per dezvoltator; deține randarea și propriul model de date,
   ceea ce face mai greu de garantat că subtotalurile afișate sunt cele calculate de server;
   bundle mare; adaptarea vizuală la restul aplicației este muncă împotriva bibliotecii.
   *Cost de schimbare ulterioară:* mare — deține stratul de randare.

3. **Construit intern, fără bibliotecă** — mașina de stare a coloanelor, sortării, filtrării și
   grupării, scrisă de la zero.
   *Avantaje:* control total.
   *Dezavantaje:* rescrie muncă rezolvată, fără să rezolve partea grea (virtualizare, tastatură).
   *Cost de schimbare ulterioară:* irelevant — costul e la construcție.

## Decizie

**TanStack Table**, consumat exclusiv prin două componente interne distincte.

Grila de citire și grila de introducere au cerințe incompatibile și **nu se unifică**. O componentă
care le acoperă pe amândouă este mediocră la amândouă.

**`DataGrid` — citire.** Cartea Mare, jurnale, registre, balanțe, fișe de cont, liste de documente.
Mii până la zeci de mii de rânduri. Virtualizată. Coloane înghețate. Read-only, cu drill-down.
Paginare, sortare și filtrare **pe server**.

**`EntryGrid` — introducere.** Linii de document, note contabile manuale, linii de salarizare.
Zeci de rânduri. Nevirtualizată. Navigare completă cu tastatura, validare pe celulă, adăugare de
rânduri fără mouse.

Reguli care însoțesc decizia:

- **Niciun ecran nu importă `@tanstack/react-table` direct.** Singurele puncte de intrare sunt
  `DataGrid` și `EntryGrid`.
- **Subtotalurile și totalurile vin de la server.** Într-o grilă virtualizată cu paginare, orice
  sumă calculată în browser este calculată pe un subset. Un total greșit într-un raport contabil
  este defect grav, nu inconsecvență cosmetică.
- **Exportul (Excel, CSV, PDF) se generează pe server**, din aceeași sursă ca afișarea, ca să nu
  poată diverge de ce vede utilizatorul.
- **Formatarea numerică este centralizată într-un singur modul**: MDL, separatori de mii, două
  zecimale, negative în notație contabilă, aliniere la dreapta, cifre tabulare. Acesta este strat
  de **afișare**; precizia și rotunjirea de calcul sunt `DNB-08` și rămân pe server.
- **Configurația de coloane se persistă per utilizator și per tenant.** Cere un model de preferințe
  cu context de tenant — deci intră în F0, nu se improvizează în F1.

## Consecințe

- Devine posibil: un comportament unic de grilă pe toate ecranele; înlocuirea bibliotecii fără a
  atinge ecranele; garanția că un total afișat este un total calculat de server.
- Devine scump: o grilă cu cerințe care nu încap în niciuna dintre cele două componente. Se
  extinde componenta existentă sau se ridică decizie, nu se scrie a treia grilă ad-hoc.
- De modificat ca urmare:
  - `OD-19` se restrânge (grila iese din ea) — făcut;
  - backlog-ul F1 primește **`DataGrid` și `EntryGrid` ca sarcini proprii, cu buget de timp**, nu
    ca parte din „implementează raportul X". Altfel prima grilă se naște grăbită în interiorul unui
    raport și devine baza pe care se copiază tot restul;
  - modelul de preferințe de utilizator intră în domeniul F0;
  - `CLAUDE.md` primește regulile de mai sus în secțiunea de convenții frontend, care încă nu
    există.
- Se verifică automat: regulă ESLint `no-restricted-imports` pe `@tanstack/react-table`, cu
  excepție doar pentru fișierele celor două componente. Fără ea, regula „niciun ecran nu importă
  direct" este o intenție, nu un invariant.

## Surse

- Conversație 2026-08-24, în continuarea întrebării despre shadcn/Tailwind.
- `000-open-decisions.md`: `OD-19` (stack frontend), `OD-30` (model de volum), `OD-33`
  (guvernanța ADR-urilor), `DNB-08` (precizie și rotunjire).
- `CLAUDE.md` §2.5 (limbă), §4 (deciziile deschise nu se închid tacit).
