# Salariul minim pe țară pentru 2026 — HG 771/2025

- **Scris:** 2026-09-03, la delegarea proprietarului („if needed my decision… just do it on my behalf"),
  pentru parametrul `labour.minimum_wage_monthly` (`13-lista-de-deblocare.md` §C12: parametru
  inexistent, iar art. 22 alin. (1) din Legea 489/1999 cere baza CAS cel puțin la salariul minim,
  proporțional timpului lucrat — `payroll/services/runs.py`, `_minimum_base`).
- **Fișierul de date:** `backend/evidenta/fiscal/parameters/data/salariu_minim.toml`.

## 1. Identitatea actului

| Ce | Valoare | Sursa | Text citit? |
|---|---|---|---|
| Actul | **Hotărârea Guvernului nr. 771 din 17.12.2025** privind stabilirea cuantumului salariului minim pe țară pentru anul 2026 | indexul `legis.md` (titlul „HG771/2025", `doc_id=152064`); `monitorul.fisc.md` („Hotărârea Guvernului nr. 771 din 17 decembrie 2025") | **nu** — `legis.md` răspunde 403 |
| Publicarea | Monitorul Oficial, **18.12.2025** | `monitorul.fisc.md` | numărul ediției și poziția: **neobținute** |
| Temeiul | art. 3 din Legea nr. 1432/2000 privind modul de stabilire și reexaminare a salariului minim (MO 2001, nr. 21-24, art. 79) | proiectul redactat (mai jos) | da, în proiect |
| Ședința | Guvern, 17.12.2025 — punctele NU-915-MMPS-2025 (salariul minim) și NU-916-MMPS-2025 (salariul mediu prognozat, HG 773/2025) | comunicatul `gov.md` | da |

## 2. Ce prescrie — din proiectul redactat (NU-915-MMPS-2025, gov.md), verbatim

> **1.** Se stabilește, începând cu 1 ianuarie 2026, salariul minim pe țară în cuantum de **6300 de lei
> lunar** pentru un program complet de lucru de **169 de ore** (în medie pe lună), ceea ce reprezintă
> **37,28 lei pe oră**.
> În cazul în care programul de muncă este, potrivit legii, mai mic de 40 de ore pe săptămână, salariul
> minim orar se calculează prin raportarea salariului minim lunar, prevăzut în prezentul punct, la
> numărul mediu de ore lunar, potrivit programului legal de lucru aprobat.
>
> **2.** Prezenta hotărâre intră în vigoare la data de 1 ianuarie 2026.

Comunicatul `gov.md` din 17.12.2025 confirmă cifra și predecesorul: „salariul minim pe țară va crește
de la 5500 la 6300 de lei lunar"; `sindicate.md` reproduce 6300 / 169 ore / 37,27 lei pe oră (a doua
zecimală diferă de proiect — 37,28 —; parametrul încărcat e cel lunar, ora nu e parametru).

## 3. Ce s-a încărcat, și cu ce încredere

- `labour.minimum_wage_monthly = 6300 MDL`, `valid_from = 2026-01-01`, `margin_basis = act`,
  `margin_reference` = pct. 1 și pct. 2 ale proiectului; `confidence = provisional`, fiindcă textul
  **adoptat** nu s-a citit, iar numărul și poziția din MO nu sunt afirmate.
- Activat pe baza de dezvoltare la 2026-09-03, aprobator `dev@example.md`, pe delegarea proprietarului.

## 4. Ce nu s-a putut verifica

- Textul adoptat al HG 771/2025 (legis.md 403; PDF-ul de pe gov.md e proiectul, nu actul).
- Numărul ediției MO și poziția.
- Cuantumul pentru 2025 (5500 lei, afirmat de comunicat) și actul lui — **neîncărcat**: fereastra
  parametrului începe la 2026-01-01, iar o rulare din 2025 refuză numind cheia, nu presupune.
