# Cursuri valutare — ce stă aici și ce nu

**Cursurile nu se livrează cu depozitul.** Cursul oficial al leului e o dată zilnică, publicată de
BNM pentru fiecare zi bancară; un fișier de cursuri în repo ar fi vechi în ziua următoare
commit-ului și ar da impresia că o instalare are cursuri fără să le fi încărcat cineva. Tabela
`exchange_rate` pornește goală, iar `rate_on` refuză o zi fără curs (`currency.rate_not_found`) în
loc să întindă ultimul curs peste ea — care curs se aplică într-o zi fără publicare e decizia
Codului fiscal și a politicii contabile, nu a rândului cel mai apropiat (ADR-039 §3.2).

## Ușa — calea privilegiată `P-3`

```
uv run python manage.py load_exchange_rates <fisier.csv> [--actor cine]
```

Rulează sub rolul de date de referință (`evidenta_refdata`, ADR-049), pe conexiunea `refdata`, și
lasă un rând în `privileged_access_log` la fiecare rulare, cu numărul de rânduri citite, create și
neschimbate. Idempotentă pe `(currency, rate_date, rate_type)`: un rând identic e numărat și lăsat
în pace; un rând cu **altă valoare** pentru aceeași zi e refuzat (`currency.rate_conflict`), nu
suprascris — o înregistrare postată stă pe cursul de atunci (`R10`, prin analogie). Corecția e un
rând nou de tip `manual`, cu sursa lui.

Conectorul BNM (`OD-76`) va alimenta același serviciu dintr-o preluare în loc de fișier.

## Formatul

CSV cu antet, exact aceste coloane, în ordinea asta:

```
currency,rate_date,rate,rate_type,source
EUR,2026-01-20,19.5000,bnm_official,BNM curs oficial 20.01.2026
```

- `currency` — cod ISO 4217, trei litere;
- `rate_date` — `AAAA-LL-ZZ`, ziua pentru care e publicat cursul;
- `rate` — lei per o unitate de valută (direcția din ADR-039 §3.1), cel mult opt zecimale;
- `rate_type` — `bnm_official` sau `manual`; `contractual` nu se încarcă din fișier, e stipulație
  de document (`document.rate_term = fixed`);
- `source` — buletinul sau cine a citit cursul și de unde; poate fi gol.

## `sample_rates.csv`

Fișierul de alături e **doar pentru teste**: valori de fixtură (cele din ADR-057, 19,5000 și
19,6234), nu cursuri publicate. Nu se încarcă pe o instalare reală.
