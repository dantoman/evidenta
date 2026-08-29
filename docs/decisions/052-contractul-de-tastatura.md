# ADR-052 — Contractul de introducere cu tastatura: nicio operațiune frecventă nu cere mouse-ul

- **Status:** Acceptat — decizie de produs, luată de proprietar prin instrucțiune scrisă,
  2026-08-29 (punctul 6); sub regimul [ADR-002](002-guvernanta-deciziilor.md), fără conținut contabil
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** `OD-36`
- **Afectează:** `EntryGrid` (F1.G2), toate ecranele de introducere — note manuale, solduri
  inițiale, linii de document, maparea conturilor la import, potrivirea extrasului bancar; `CLAUDE.md`
  §2.8 (regula nenumerotată devine `C40`)
- **Legate:** [ADR-001](001-grila-de-date.md) (cele două componente), `_bootstrap/07-f1-grile.md`
  F1.G2 (cerințele de proiectare), [ADR-042](042-scara-de-densitate.md)

---

## 1. Context

`OD-36` cerea, înainte de orice cod de `EntryGrid`, un contract: ordinea de tab, tastele rapide,
deplasarea pe linii, tastatura numerică. Contabilul venit de la 1C introduce documente fără mouse
și nicio bibliotecă nu oferă asta. `07-f1-grile.md` F1.G2 spune de ce contează *acum*: dacă
`EntryGrid` e concepută îngust, reconcilierea are nevoie de altceva și a doua grilă (`OD-41`) devine
inevitabilă. `CLAUDE.md` §2.8 ține, până la contract, o singură constrângere: ecranele nu adaugă
handlere proprii de taste peste `EntryGrid`.

## 2. Opțiuni evaluate

1. **Semantica implicită a browserului.** `Tab` mută focusul, `Enter` trimite formularul.
   *Dezavantaj:* `Enter` care trimite un document cu patruzeci de linii la a treia linie e exact
   accidentul pe care contabilul îl știe din formularele web; `Tab` printr-o grilă cu opt coloane
   e de două ori mai lent decât în 1C.
2. **Semantica de foaie de calcul.** `Enter` coboară pe verticală, `Tab` merge pe orizontală.
   *Dezavantaj:* introducerea contabilă e pe rând, câmp cu câmp — o linie de document se
   completează de la stânga la dreapta și abia apoi urmează alta; coborârea pe verticală e
   reflexul greșit pentru fluxul real.
3. **Semantica 1C: `Enter` avansează câmp cu câmp, iar la capătul rândului deschide rândul
   următor** — *aleasă*. E reflexul pe care îl aduce fiecare utilizator țintă, și nu contravine
   nimănui.

## 3. Decizia — contractul

Regula de fond, din care decurg toate cele de mai jos:

> **Nicio operațiune frecventă nu cere mouse-ul.**

| Tastă | Comportament |
|---|---|
| `Enter` | avansează la câmpul următor; **pe ultimul câmp al rândului deschide o linie nouă** |
| `Escape` | anulează editarea **celulei**; a doua apăsare anulează **rândul** (în lucru) |
| tastare peste o celulă selectată | **înlocuiește** conținutul — nu îl completează |
| tastă `F` din celulă | deschide **nomenclatorul** câmpului (cont, partener, articol) |
| `Ctrl+Enter` | **validează documentul** — tranziția `draft → validated` a stratului documentar, nu postarea |
| săgeți | **navighează** între celule fără a intra în editare |

Cerințele deja fixate în `07-f1-grile.md` F1.G2 rămân parte a contractului: separatorul zecimal
acceptă **și punct, și virgulă** la introducere (tastatura numerică produce punct, interfața
românească afișează virgulă — `C18`); adăugarea și ștergerea de rânduri se fac din tastatură;
indicatorul de echilibru debit/credit reflectă `R11`, nu îl înlocuiește.

### 3.1 Ce rămâne de fixat, și nu se fixează tacit

Trei detalii nu sunt în instrucțiune; se implementează cu implicitul de mai jos și **se confirmă**,
nu se presupun închise:

- **`Tab`** — aceeași ordine de avans ca `Enter`, dar **fără** să deschidă linie nouă pe ultimul
  câmp (`Shift+Tab` înapoi). Implicit propus: `Tab` e navigare, `Enter` e introducere.
- **Care tastă `F`** — implicit propus `F4`, cum e în 1C; cu `F2` pentru intrarea în editare a
  celulei selectate.
- **Ștergerea rândului** — implicit propus `Ctrl+Delete` pe rândul selectat, cu confirmare doar
  dacă rândul are conținut.

## 4. Consecințe

- **Devine posibil:** F1.G2 se deblochează — `EntryGrid` are contractul înaintea codului, cum cerea
  `07-f1-grile.md`; nota manuală de azi (tabel simplu, fără `EntryGrid`) capătă componenta pe care o
  aștepta.
- **Devine imposibil sau scump, asumat:** un ecran nu poate decide că la el `Enter` face altceva;
  un utilizator venit din alt sistem nu primește setare de „mod tastatură" — o singură semantică,
  pentru toți (`R23`, aceeași logică ca la rotunjire în ADR-037 §6.2).
- **Ce se modifică:** `CLAUDE.md` §2.8 — nota nenumerotată devine regula `C40`: *comportamentul de
  tastatură aparține `EntryGrid`, conform contractului din ADR-052; ecranele nu adaugă handlere
  proprii de taste*; `07-f1-grile.md` F1.G2 („Blocat de: `OD-36`" se taie); `000-open-decisions.md`.
- **Ce se verifică automat:** criteriile de terminare din F1.G2 rămân cele trei de acolo — o notă
  cu minimum cinci linii introdusă fără mouse; punct și virgulă produc același rezultat și ecranul
  nu adaugă niciun handler propriu; aceeași componentă servește maparea conturilor la import. Plus
  un test Vitest per rând din tabelul §3, peste `EntryGrid`, nu peste un ecran.

## 5. Surse

- Instrucțiunea proprietarului, 2026-08-29, punctul 6 — tabelul §3 e transcrierea ei.
- `docs/_bootstrap/07-f1-grile.md` F1.G2; [ADR-001](001-grila-de-date.md); `CLAUDE.md` §2.8, `C16`,
  `C18`; `000-open-decisions.md` rândul `OD-36`.
- Benchmark 1C: `Enter` avansează și deschide linie nouă, `F4` deschide selecția, `Escape`
  anulează — practica pe care o aduc utilizatorii, nu temei.
