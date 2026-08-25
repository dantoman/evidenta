# ADR-024 — Contractele de dependență se impun printr-un gardian propriu, în suită

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `OD-17`
- **Afectează:** F0.0.5, și fiecare modul adăugat de acum înainte

## Context

`CLAUDE.md` §3 declară graful de dependențe aciclic și enumeră `D1`–`D6`. Atât declara: nimic nu îl
citea. Primul import în direcția greșită ar fi fost prins de cine își amintea regula, sau deloc.

Costul e asimetric în timp. Un ciclu se previne cu o linie și se scoate cu o refactorizare care
atinge fiecare modul adăugat după el — pentru că fiecare l-a putut folosi între timp.

## Opțiuni

**A. `import-linter`.** Unealta standard pentru contracte de straturi; regulile se declară în
`pyproject.toml`.

**B. Gardian propriu, în suită.** Parcurgere AST peste `backend/evidenta`, contract într-un fișier
propriu, fiecare regulă cu probă că poate eșua — același tipar cu gardianul de model din F0.2.2.

## Decizie

**Opțiunea B.** Trei motive, în ordinea greutății:

1. **`D6` nu se poate exprima ca strat.** „Comunicarea între module nu se face prin import direct de
   modele" nu este o direcție în graf; este o formă de import. Un contract de straturi îl vede pe
   `accounting` ca pe un singur lucru și nu poate distinge `accounting.events` de `accounting.ledger`
   — deci nici `D3` nu intră. Măsurat: `D3`, `D4` și `D6` rămâneau neacoperite.
2. **Ce nu se declară nu se sare.** Un pachet nou sub `evidenta/` care nu apare în contract este
   raportat (`D0`), nu ignorat. Un contract de straturi tace exact despre modulul pe care nimeni
   n-a știut să-l declare — cazul pentru care gardianul există.
3. **Zero dependențe noi.** Verificarea rulează din aceeași suită, fără bază de date, în ~0,1 s.

Nu a cântărit în decizie, dar s-a confirmat la scriere: gardianul vede importurile relative și pe
cele din interiorul funcțiilor. A doua formă este exact cum se face un ciclu să funcționeze la
rulare.

## Unde stă contractul

`infra/modules/dependencies.toml` — singurul loc. Consumatorul este `backend/tests/deps_guard/`.
Modificarea fișierului este ADR, ca la `infra/rls/exceptions.toml`: un gardian ale cărui așteptări
stau în propria sursă este un gardian care se editează ca să treacă suita.

## `D6` — ce este comunicare și ce este schemă

Aplicat literal, `D6` declara defecte zece importuri existente, toate în `models.py` și toate ținte
de `ForeignKey` către `Tenant`, `Company` și `User`.

**`D6` interzice comunicarea prin modelele altui modul** — un serviciu care citește sau scrie tabela
altcuiva ocolește granița pe care evenimentele contabile și serviciile publice o există ca s-o țină.
**O țintă de cheie străină este compunere de schemă**, iar Django cere clasa modelului ca s-o
exprime.

Excepția are două condiții, ambele impuse:

1. numai un modul `models` poate compune schemă. `services/` care importă modelele altui modul
   rămâne încălcare — este chiar cazul pe care regula îl vizează;
2. numai către `platform` și `masterdata`, straturile către care tabelele arată prin natura lor.
   `sales.models → purchases.models` rămâne încălcare: două module de business care își împart
   tabelele prin cheie străină sunt cuplate, oricât de „schemă" ar arăta importul.

Lista a fost `["platform"]` singur, câteva minute. A căzut la măsurătoare, nu la discuție:
`Articol → Unitate de măsură` și `Partener → Registru de contrapărți` au ieșit ca încălcări, și
niciuna nu este comunicare. Lărgirea listei rămâne ADR, iar suita are test pentru cazul care a
motivat îngustarea inițială.

## Consecințe

- `make deps-check` rulează gardianul fără bază de date; `make test` îl include; CI îl rulează în
  jobul rapid.
- Layout-ul modulelor operaționale **nu** este decis aici. Dacă apare `evidenta/sales/` în loc de
  `evidenta/operations/sales/`, gardianul raportează `D0` și alegerea se consemnează în contract —
  în loc să fie dedusă din primul commit care a nimerit-o.
- Ce nu acoperă: importurile dinamice (`importlib`, `__import__` cu nume calculat). Sunt invizibile
  oricărei analize statice, inclusiv lui `import-linter`. Nu apar în cod azi.
