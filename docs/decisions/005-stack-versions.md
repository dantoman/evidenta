# ADR-005 — Versiunile stack-ului: regula, apoi valorile

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `OD-14`. **Nu** închide `OD-15` (tooling Python), care rămâne deschis
- **Afectează:** F0.0.1, F0.0.2, F0.0.3, `docker-compose.yml`

## Context

`OD-14` bloca prima sarcină din backlog și, prin ea, toată faza F0. Documentele de intrare fixează
stack-ul (Django, DRF, PostgreSQL cu RLS, Redis, Celery, React + TypeScript + Vite) și o singură
constrângere de versiune: PostgreSQL 16+.

Aceasta nu este o decizie de arhitectură. Este o alegere care se reface periodic. Ce merită
consemnat este **regula după care se alege**, nu numerele — numerele expiră.

## Opțiuni evaluate

1. **Ultima versiune stabilă a fiecărei componente.** Cel mai mult timp până la următorul upgrade
   forțat. Dar Django non-LTS are 8 luni de suport, ceea ce înseamnă un upgrade obligatoriu în
   mijlocul unei faze.
2. **LTS peste tot unde există, stabil recent unde nu.** Ferestrele de suport se aliniază cu durata
   fazelor. Prețul: se rulează cu funcționalități cu un ciclu în urmă, ceea ce aici nu costă nimic —
   RLS este matur de ani, iar nimic din F0–F2 nu depinde de noutăți.
3. **Versiuni conservatoare, cu un ciclu în urmă de LTS.** Suport pe termen scurt, upgrade mai
   devreme, fără câștig.

## Decizie

**Opțiunea 2.** Regula, în ordinea priorității:

1. **Django pe LTS.** Niciodată pe o versiune non-LTS.
2. **PostgreSQL pe stabil recent** — nu beta, nu ultima lună după lansarea majoră.
3. **Node pe Active LTS.**
4. **Python pe cea mai recentă versiune oficial suportată de linia Django aleasă**, fără a depinde
   de o versiune de patch anume pentru acel suport.
5. **Totul pinuit exact**, în lockfile. Nicio dependență cu interval deschis.
6. **Upgrade deliberat, niciodată în timpul unei faze.** Un upgrade este o sarcină proprie, cu
   suitele rulate înainte și după.

### Valorile, verificate la 2026-08-24

| Componentă | Versiune | De ce |
|---|---|---|
| **Django** | **5.2 LTS** | Singurul LTS lansat. Suport de securitate până în aprilie 2028. Următorul LTS, 6.2, apare în aprilie 2027 |
| **Python** | **3.13** | Django 5.2 suportă 3.10–3.14, dar 3.14 doar de la patch-ul 5.2.8. 3.13 este suportată de toată linia 5.2 și nu leagă proiectul de un plancher de patch |
| **PostgreSQL** | **18** | Ultima majoră stabilă (18.6 la data deciziei), cu aproape un an de patch-uri. 19 este în beta. Depășește cu mult cerința „16+" |
| **Node** | **24 „Krypton"** | Active LTS, din noiembrie 2025 până în mai 2028 — acoperă F0–F3 fără upgrade forțat |

Componentele care **nu** se fixează aici, ci la F0.0.1, la ultima versiune compatibilă cu cele de
mai sus, pinuite în lockfile: Django REST Framework, Celery, Redis, React, TypeScript, Vite.
Motivul separării: cele patru de mai sus au ferestre de suport care determină planificarea; restul
sunt dependențe obișnuite, care se aleg o dată și se actualizează în bloc.

## Consecințe

- **Devine posibil:** F0.0.1, deci întregul lanț F0.0 → F0.1.
- **Fereastra de upgrade:** Django 6.2 LTS (aprilie 2027) și PostgreSQL 19 devin candidate în
  timpul F2. Upgrade-ul se planifică între faze, ca sarcină proprie.
- **De modificat ca urmare:** `docker-compose.yml` — imaginea `postgres:16-alpine`, marcată SCHELET,
  devine `postgres:18-alpine`; `CLAUDE.md` §2.1 — se înlocuiește nota „versiunile exacte nu sunt
  încă fixate".
- **Ce rămâne deschis:** `OD-15` — manager de pachete, linter, formatter, type checker, pre-commit.
  Este ultima piesă care blochează F0.0.1. **Nu blochează F0.1**, care este SQL.
- **Se verifică automat:** CI rulează pe versiunile pinuite; un lockfile modificat fără ADR de
  upgrade este semnalat la review.

## Surse

- [Django is moving to an annual release cycle](https://www.djangoproject.com/weblog/2026/aug/10/annual-release-cycle/) — confirmă că 5.2 LTS și 6.2 LTS își păstrează angajamentele de suport
- [Django 5.2 release notes](https://docs.djangoproject.com/en/5.2/releases/5.2/) — compatibilitatea Python
- [PostgreSQL 18.6, 17.11, 16.15, 15.19, 14.24 and 19 Beta 3 Released](https://www.postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365/) — versiunile suportate în august 2026
- [Node.js Releases](https://nodejs.org/en/about/previous-releases) — calendarul LTS
- `_input/evidenta-implementation-spec.md` §2.1
