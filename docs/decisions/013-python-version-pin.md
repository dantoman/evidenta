# ADR-013 — Versiunea de Python: motivul actual al pinului și condiția de revizuire

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Completează** [ADR-005](005-stack-versions.md). **Nu îl înlocuiește:** decizia rămâne 3.13; se
  corectează motivul consemnat și se adaugă condiția de ieșire
- **Afectează:** `backend/pyproject.toml`, `backend/.python-version`, CI

## Context

`ADR-005` a fixat Python 3.13 cu motivul: „Django 5.2 suportă 3.10–3.14, dar 3.14 doar de la
patch-ul 5.2.8; 3.13 este suportată de toată linia 5.2".

Motivul acela **s-a învechit deja**, la o zi după ce a fost scris. Verificat la 2026-08-24:

| Componentă | Suport Python 3.14 |
|---|---|
| Django 5.2 | da, de la 5.2.8 — iar `uv.lock` pinuiește oricum un patch exact, deci „plancherul de patch" nu mai e un argument |
| psycopg 3 | da, din 3.3; 3.14 e chiar versiunea care aduce template strings pentru interogări |
| Celery | da, suport inițial din 5.6.0 |

Un motiv consemnat care nu mai e adevărat este mai rău decât niciun motiv: cineva îl contestă peste
șase luni, constată că a căzut, și trage concluzia că pinul e arbitrar.

## Motivul actual, care rezistă

**1. Versiunea trebuie fixată explicit — indiferent care e cifra.** Mașina de dezvoltare, CI-ul și
producția rulează aceeași versiune, altfel „merge local" devine o categorie de defect. `uv`
descarcă singur interpretorul, deci asta nu depinde de ce are instalat sistemul. Acesta este
argumentul **pentru pin**, și el nu favorizează 3.13 față de 3.14.

**2. Un sistem contabil face aritmetică zecimală permanent.** Schimbările de comportament în
`decimal`, în rotunjire sau în formatare între versiuni de Python sunt mici, dar într-un ledger o
diferență de un ban este defect, nu zgomot. Versiunea de Python nu are voie să fie o variabilă
necontrolată. Din nou: argument pentru pin, nu pentru 3.13 anume.

**3. Ce favorizează efectiv 3.13:** stiva nu se termină la Django, psycopg și Celery. F1 și F2 aduc
generare de XML pentru declarații, export Excel și PDF — biblioteci cu extensii C, care întârzie
sistematic după o versiune majoră de Python. Alegerea conservatoare costă nimic acum și evită
descoperirea unei incompatibilități în mijlocul lui F2, când e cea mai scumpă.

Acesta este singurul motiv care mai susține 3.13 în loc de 3.14, și el este despre **dependențele
care nu există încă**, nu despre cele care există.

## Condiția de revizuire

Se trece pe 3.14 (sau pe versiunea curentă de atunci) când **toate** sunt adevărate:

1. Toate dependențele din `uv.lock` declară suport pentru versiunea țintă — inclusiv cele adăugate
   în F1 și F2 pentru raportare statutară, XML, Excel și PDF.
2. Corpusul de regresie fiscală (`C14`, F1.10) rulează verde pe versiunea nouă. **Aceasta este
   condiția care contează:** ea, nu citirea unui changelog, demonstrează că aritmetica zecimală și
   formatarea nu s-au mișcat sub noi.
3. Upgrade-ul se face ca sarcină proprie, între faze, niciodată în timpul uneia (`ADR-005`, regula 6).

Până când condiția 2 poate fi evaluată — adică până există corpusul de regresie — upgrade-ul de
Python este prematur indiferent ce spun changelog-urile.

## Consecințe

- `backend/pyproject.toml` primește comentariul cu motivul real și trimiterea aici, ca următorul
  cititor să nu redescopere discuția.
- **De reevaluat la finalul F1**, când corpusul de regresie există și condiția 2 devine verificabilă.
- Nu se schimbă nimic în cod acum.

## Surse

- [Django 5.2 release notes](https://docs.djangoproject.com/en/5.2/releases/5.2/) — compatibilitate Python
- [psycopg 3.3 released](https://www.psycopg.org/articles/2025/12/01/psycopg-33-released/)
- [Celery changelog](https://docs.celeryq.dev/en/stable/changelog.html)
- [ADR-005](005-stack-versions.md), [ADR-011](011-tooling-python.md)
