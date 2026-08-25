# ADR-011 — Tooling Python: uv, ruff, pytest, mypy strict selectiv

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `OD-15`
- **Afectează:** F0.0.1, F0.0.2, F0.0.4, F0.1.4, F0.1.5, F0.2 — și, prin ele, tot codul Python

## Context

`OD-15` era ultimul blocaj al lanțului Python. F0.1.1–F0.1.3 s-au livrat fiind SQL, dar F0.1.4
(middleware) și F0.1.5 (decorator Celery) nu pot începe fără un mediu.

Este genul de decizie unde ezitarea costă mai mult decât alegerea greșită: fiecare variantă
rezonabilă e reversibilă cu efort mic, iar amânarea blochează o fază întreagă.

## Decizie

| Rol | Unealtă |
|---|---|
| Mediu și dependențe | **uv** |
| Lint și formatare | **ruff** — ambele, o singură unealtă |
| Teste | **pytest** + **pytest-django** |
| Verificare de tipuri | **mypy**, în mod strict, **doar** pe `platform` și `accounting` |

Reguli care însoțesc decizia:

- **Lock file comis.** `uv.lock` este pinul exact (`ADR-005`, regula 5). `pyproject.toml` declară
  constrângerile *decise* — linia Django și versiunea Python; restul dependențelor nu primesc
  planșeu de versiune acolo, pentru că lock-ul este cel care fixează. Adăugarea unui planșeu în
  `pyproject.toml` este un act deliberat, nu o obișnuință.
- **mypy strict nu se aplică pe tot codul.** Pe module unde tipurile nu adaugă nimic — migrații,
  fixture, cod de prezentare — strictețea produce zgomot care se ignoră, iar un verificator care se
  ignoră nu verifică nimic. Se aplică unde greșeala costă: izolarea și ledgerul.
- **Flagurile de strictețe se enumeră explicit**, în loc de `strict = true`. Documentația mypy
  avertizează că lista acoperită de `strict` se schimbă între versiuni; enumerarea face ca un
  upgrade să nu modifice tăcut ce se impune, și face vizibil în fișier ce anume se cere.

## Ce rămâne în afara deciziei

`fiscal` **nu** este în lista mypy strict. Nu pentru că nu ar merita — argumentul „unde greșeala
costă" i s-ar aplica direct — ci pentru că decizia a numit platforma și contabilitatea. Este
candidatul evident la extindere, la F0.8; extinderea este o linie în `pyproject.toml`, deci se face
când se ajunge acolo, nu acum și nu tacit.

## Consecințe

- **Devine posibil:** F0.0.1, apoi F0.1.4 și F0.1.5 — deci restul lui F0.1.
- **uv aduce și interpretorul.** Sistemul de față are Python 3.14; proiectul cere 3.13
  (`ADR-005`). `uv` îl descarcă singur, deci nu apare presiunea de a folosi ce e instalat.
- **De modificat ca urmare:** `backend/pyproject.toml`, `backend/.python-version`, țintele `lint`,
  `format`, `typecheck` și `test` din `Makefile`, jobul de CI (`OD-16`, încă deschis).
- **Se verifică automat:** CI rulează `ruff check`, `ruff format --check`, `mypy` și `pytest`. Un
  `uv.lock` modificat fără ADR de upgrade se semnalează la review (`ADR-005`).

## Surse

- `000-open-decisions.md`: `OD-15`, `OD-16`
- [ADR-005](005-stack-versions.md) — versiuni și regula de pinuire
- `_input/evidenta-implementation-spec.md` §2.2, §2.4
