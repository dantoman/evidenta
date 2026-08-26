# Decizii de arhitectură (ADR)

Fiecare decizie care are efect asupra schemei, a izolării, a conformității sau a limitelor de scop
primește un fișier numerotat în acest director. O decizie luată într-o conversație și nescrisă aici
nu există: sesiunea următoare o va redeschide, sau — mai rău — o va contrazice tacit.

## Când se scrie un ADR

- când se închide o decizie din `000-open-decisions.md`
- când o sarcină de implementare descoperă o alegere care nu era în registru și care nu poate fi
  amânată
- când se acceptă o **excepție** de la un invariant din `CLAUDE.md`
- când se schimbă o decizie luată anterior (ADR nou care înlocuiește, nu editare a celui vechi)

Nu se scrie ADR pentru alegeri reversibile fără cost: numele unei variabile, structura unui test,
ordinea câmpurilor. Regula practică: dacă schimbarea de mâine ar cere o migrare de date sau ar
invalida cod scris între timp, e ADR.

## Ce nu se face

- Nu se închide o decizie din `000-open-decisions.md` fără ADR.
- Nu se închide o decizie tacit, în cod. Dacă o sarcină ar cere-o, sarcina se oprește și se
  întreabă — vezi `CLAUDE.md`, secțiunea 4.
- Nu se editează un ADR acceptat pentru a-i schimba conținutul. Se scrie unul nou, cu status
  `Înlocuiește ADR-nnn`, iar cel vechi trece în `Înlocuit`.
- Nu se deduc reguli fiscale, praguri, cote sau formate de raportare. O decizie despre conformitate
  citează actul normativ sau nu se ia.

## Format

Fișier: `NNN-titlu-scurt-in-kebab-case.md`, numerotat crescător, fără reutilizarea numerelor.

```markdown
# ADR-NNN — Titlu

- **Status:** Propus | Acceptat | Respins | Înlocuit de ADR-NNN
- **Data:** AAAA-LL-ZZ
- **Decide:** cine a luat decizia
- **Închide:** OD-NN din 000-open-decisions.md (dacă e cazul)
- **Afectează:** modulele, tabelele sau fazele atinse

## Context

Ce problemă a impus decizia. Ce se știa și ce nu. Ce documente sau surse au fost consultate.

## Opțiuni evaluate

1. **Opțiunea A** — descriere. Avantaje. Dezavantaje. Cost de schimbare ulterioară.
2. **Opțiunea B** — idem.

O singură opțiune înseamnă că nu a fost o decizie, ci o constatare. Reformulează sau nu scrie ADR.

## Decizie

Ce s-a ales, la obiect. O propoziție, apoi detaliile necesare implementării.

## Consecințe

- ce devine posibil
- ce devine imposibil sau scump
- ce trebuie modificat în cod, schemă sau documentație ca urmare
- ce se verifică automat, și de către ce test sau agent

## Surse

Acte normative, secțiuni din documentele de intrare, benchmark-uri, discuții.
```

## Index

| ADR | Titlu | Status | Data | Închide |
|---|---|---|---|---|
| [000](000-open-decisions.md) | Registrul deciziilor deschise | Viu | 2026-08-24 | — |
| [001](001-grila-de-date.md) | Grila de date: TanStack Table, cu două componente interne | Acceptat | 2026-08-24 | — (restrânge OD-19) |
| [002](002-guvernanta-deciziilor.md) | Guvernanța deciziilor: cine aprobă ce | Acceptat | 2026-08-24 | OD-33 |
| [003](003-rls-tenancy-tables.md) | Politica RLS pentru tabelele care definesc tenancy-ul | Acceptat | 2026-08-24 | DN-12, OD-07 |
| [004](004-company-context.md) | Contextul de companie în sesiune | Acceptat | 2026-08-24 | DN-11, OD-08 |
| [005](005-stack-versions.md) | Versiunile stack-ului: regula, apoi valorile | Acceptat | 2026-08-24 | OD-14 |
| [006](006-reversal-two-dates.md) | Stornoul are două date distincte | Acceptat | 2026-08-24 | DNB-09, structural |
| [007](007-reversal-period.md) | Perioada în care se postează stornoul | **Propus** — 3 întrebări deschise | 2026-08-24 | DNB-09, politica |
| [008](008-retention-fiscal-parameters.md) | Retenția: mecanism acum, termene ca date | Acceptat | 2026-08-24 | DN-22, mecanismul |
| [009](009-componente-si-stil.md) | Biblioteca de componente și stratul de stil: shadcn/ui + Tailwind | Acceptat | 2026-08-24 | OD-34 |
| [010](010-contabilul-practicant.md) | Contabilul practicant: rolul este acoperit de proprietar | Acceptat | 2026-08-24 | OD-32 |
| [011](011-tooling-python.md) | Tooling Python: uv, ruff, pytest, mypy strict selectiv | Acceptat | 2026-08-24 | OD-15 |
| [012](012-sql-in-django-migrations.md) | SQL-ul de politici trăiește în migrațiile Django | Acceptat | 2026-08-24 | OD-18 |
| [013](013-python-version-pin.md) | Versiunea de Python: motivul actual și condiția de revizuire | Acceptat | 2026-08-24 | — (completează ADR-005) |
| [014](014-limba-rusa.md) | Limba rusă: interfața amânată cu hedge | Acceptat | 2026-08-24 | DN-01/OD-13, parțial |
| [015](015-colatie-icu.md) | Colația: `ro-x-icu`, aleasă la crearea bazei | Acceptat | 2026-08-24 | OD-39 |
| [016](016-limba-contabilitatii.md) | Limba contabilității: cerință legală, nu preferință | Acceptat | 2026-08-24 | OD-13, OD-38 |
| [017](017-terminologie.md) | Terminologia: două straturi independente | Acceptat | 2026-08-24 | — *(deschide OD-42)* |
| [018](018-engagementuri-multiple.md) | Un tenant poate avea engagementuri cu mai multe firme | Acceptat | 2026-08-25 | DN-06 |
| [019](019-vocabular-scope.md) | Vocabularul de `module_key` și de drepturi în scope | Acceptat | 2026-08-25 | DN-07 |
| [020](020-roluri-ca-date.md) | Rolurile sunt date compozabile, peste un catalog fix de permisiuni | Acceptat | 2026-08-25 | DN-08 |
| [021](021-mfa-obligatoriu.md) | MFA obligatoriu pentru toți utilizatorii | Acceptat | 2026-08-25 | DN-09 |
| [022](022-numerotare-sabloane.md) | Numerotarea: șabloane configurabile per companie | Acceptat | 2026-08-25 | OD-02 |
| [023](023-ci-github-actions.md) | CI pe GitHub Actions, cu Postgres ca serviciu | Acceptat | 2026-08-25 | OD-16 |
| [024](024-gardian-de-dependente.md) | Contractele de dependență, impuse printr-un gardian propriu | Acceptat | 2026-08-25 | OD-17 |
| [025](025-subdomeniu-in-dezvoltare.md) | Subdomeniul tenantului în dezvoltare locală: `*.evidenta.localhost` | Acceptat | 2026-08-25 | OD-20 |
| [026](026-autentificare-inainte-de-context.md) | Autentificarea precede contextul, deci trece prin căi privilegiate înguste | Acceptat | 2026-08-25 | — *(deschide OD-48)* |
| [027](027-fiscal-ca-strat-de-schema.md) | `fiscal` intră în lista straturilor de compunere de schemă | Acceptat | 2026-08-25 | — |
| [028](028-modelat-in-f0.md) | Ce înseamnă „modelat în F0”; nu se creează app-uri pentru faze viitoare | Acceptat | 2026-08-25 | OD-11 |
| [029](029-dimensiuni-analitice.md) | Dimensiuni: listă închisă plus cinci sloturi generice per companie | Acceptat | 2026-08-25 | DNB-02 |
| [030](030-atasamente.md) | Atașamentele stau la nivel de companie, nu de tenant | Acceptat | 2026-08-25 | DN-16 |
| [031](031-stack-frontend.md) | Stack frontend minimal: react-query, react-router, fetch, Intl | Acceptat | 2026-08-25 | OD-19 |
| [032](032-cheia-de-partitionare.md) | Cheia de partiționare: desemnată acum, aplicată la prag | Acceptat | 2026-08-25 | OD-01 |
| [033](033-limba-la-generare.md) | Limba la generare: contextul românesc se forțează, nu se moștenește | Acceptat | 2026-08-25 | — *(operaționalizează ADR-016)* |
| [034](034-denumire-legala-si-interna.md) | Nomenclatoarele au denumire legală și denumire internă | Acceptat | 2026-08-25 | — *(`OD-40` rămâne deschisă)* |
| [035](035-fara-delegare-tranzitiva.md) | Delegarea nu este tranzitivă | Acceptat | 2026-08-25 | — *(deschide `OD-54`)* |
| [036](036-forma-postarii.md) | Forma postării stă în cod; restul configurării stă în date | **Propus** — `C1`–`C5` cer SNC citat | 2026-08-25 | `DNB-04` *(la `Acceptat`; deschide `OD-55`)* |
| [037](037-conventii-de-platforma.md) | Convenții de platformă: rotunjire, zecimale, granularitatea postării | **Propus** — blocat pe `V1`–`V4` | 2026-08-25 | `DNB-08` *(parțial, la deblocare)* |
| [038](038-vocabularul-de-evenimente.md) | Nucleul deține vocabularul de `event_type`; handlerul se selectează după dată | Acceptat | 2026-08-25 | `DNB-01` |
| [039](039-valuta-si-perioade.md) | Moneda funcțională MDL, exercițiu cu date explicite, trei date pe linia de jurnal | Acceptat | 2026-08-25 | `DN-04`, `DN-05` |
| [040](040-crearea-tenantului-si-a-companiei.md) | Crearea unui tenant și a unei companii este cale privilegiată (`P-9`) | Acceptat | 2026-08-25 | `OD-53` |
| [043](043-privilegiile-functiilor-rls.md) | Operațiile pe obiectele lui `evidenta_rls` se fac sub rolul lui; `REVOKE` de la non-proprietar e un warning | Acceptat | 2026-08-26 | deschide `OD-64` |
| [042](042-scara-de-densitate.md) | Scara de densitate ca tokeni `--spacing-*`: 40/32/24, implicit `compact` la 32px | Acceptat | 2026-08-26 | `OD-35` |
| [041](041-ziua-ca-argument.md) | Ziua intră ca argument; niciun predicat de acces nu citește ceasul | Acceptat | 2026-08-26 | `OD-63` |
| [044](044-data-de-rezolutie.md) | Regula se rezolvă după data perioadei, niciodată după data calculului | Acceptat | 2026-08-26 | `OD-66` |
| [045](045-sursa-de-adevar-pentru-parametri.md) | Actul de rang legal dă parametrii; regulamentul dă procedura | Acceptat | 2026-08-26 | — (impune `C14`) |
| [046](046-istoricul-increderii-in-sursa.md) | Încrederea în sursă are istoric: o confirmare nu schimbă valoarea, deci nu e o versiune nouă | Acceptat | 2026-08-26 | — (`R1`: declară o excepție) |

*Indexul se actualizează la fiecare ADR nou. Un ADR care nu apare aici este invizibil.*

[ADR-010](010-contabilul-practicant.md) închide `OD-32`: rolul de contabil practicant este acoperit
de proprietarul proiectului. **ADR-007 și ADR-008 sunt deci deblocate** — trec în `Acceptat` la
confirmarea lui, nu automat prin acest fișier.

Numărul de ADR-uri în `Propus` **nu mai este** măsura riscului contabil; cu rolurile colapsate, a
doua semnătură nu mai este verificare independentă. Măsura devine acoperirea corpusului de regresie
fiscală — vezi `ADR-010`.
