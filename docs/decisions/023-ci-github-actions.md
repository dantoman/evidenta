# ADR-023 — CI pe GitHub Actions, cu Postgres ca serviciu

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `OD-16`
- **Afectează:** F0.0.4, F0.2.6, și fiecare commit de acum înainte

## Context

Suitele de izolare rulează astăzi doar când le rulez manual, pe un cluster temporar. Funcționează —
dar `CLAUDE.md` C13 cere rulare la fiecare commit, iar Amendamentul §D.3 spune că suita a doua
„prinde tabela pe care cineva o adaugă peste trei ani fără să știe regula".

**O suită care nu rulează automat nu prinde nimic peste trei ani.** Prinde doar ce își amintește
cineva să ruleze azi. Acesta este întregul motiv pentru care decizia contează.

## Decizie

**GitHub Actions**, pentru că repo-ul este `github.com/dantoman/evidenta` și pentru că are serviciu
Postgres nativ — cel mai puțin de configurat între runner și baza de date.

### Cum obține runner-ul o bază corectă

Nu prin `initdb` manual. Imaginea `postgres:18` acceptă `POSTGRES_INITDB_ARGS`, exact ca
`docker-compose.yml`, deci clusterul de CI se creează cu **aceeași colație ca producția**
(`ro-x-icu`, ADR-015).

Dacă ar diferi, `0000_locale_guard.sql` ar opri lanțul — corect, dar CI-ul ar fi roșu din primul
minut și cineva ar „repara" gardianul în loc de configurare.

### Cele trei privilegii, și în CI

Harness-ul are nevoie de trei roluri distincte (F0.2.1): admin creează baza, owner aplică
bootstrap-ul și migrațiile, app rulează testele. În runner, adminul este superuserul imaginii;
celelalte două se creează de bootstrap. Variabilele sunt aceleași folosite local.

**Ce nu se face:** rularea testelor ca superuser pentru că „e mai simplu în CI". Ar trece toate și
n-ar demonstra nimic (T1). Harness-ul refuză oricum — dar merită scris, pentru că presiunea de a
face asta apare exact când pipeline-ul e roșu vineri seara.

### Ce rulează

Două joburi, deliberat separate:

| Job | Ce rulează | De ce separat |
|---|---|---|
| `quality` | `ruff check`, `ruff format --check`, `mypy` | Nu are nevoie de bază de date; eșuează în secunde |
| `tests` | bootstrap pe bază curată, migrații, `pytest` | Are nevoie de Postgres; e cel care contează |

Jobul `tests` rulează **și `make bootstrap` pe o bază goală**, nu doar suitele. Fără asta, un
bootstrap stricat s-ar descoperi la primul mediu nou, nu la commit-ul care l-a stricat.

## Consecințe

- `infra/ci/` primește configurarea; `.github/workflows/` o referă.
- **F0.0.4 și F0.2.6 se deblochează.** Ultimul blocaj din F0 dispare.
- Proba SQL (`infra/rls/smoke_test.sql`) se poate retrage când echivalentele Python trec în CI —
  regula de migrare din backlogul F0.2 rămâne condiția.
- `uv` se instalează în runner prin acțiunea oficială `astral-sh/setup-uv`, cu cache pe `uv.lock`.

## Ce rămâne în afara deciziei

**Nimic despre deploy.** Acesta este un pipeline de verificare, nu de livrare. Mediile, secretele și
strategia de release sunt decizie separată, în afara lui F0.

## Surse

- `000-open-decisions.md`: `OD-16`
- `CLAUDE.md` C13, T1; Amendament §D.3
- [ADR-015](015-colatie-icu.md) — colația trebuie să fie identică în CI
