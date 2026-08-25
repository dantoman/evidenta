# ADR-008 — Retenția documentelor: mecanism acum, termene ca date

- **Status:** **Acceptat** — 2026-08-24. Co-semnătura cerută de `ADR-002` este acoperită prin
  [ADR-010](010-contabilul-practicant.md). Decizia priveşte **mecanismul**; valorile rămân în
  `OD-21` și cer o sursă legală citabilă
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului, în ambele roluri (`ADR-010`)
- **Închide:** `DN-22` (Spec A §9.5) în partea de mecanism. `OD-21` rămâne deschis pentru valori
- **Afectează:** F0.6.1 (clasa de retenție pe document), F3 (offboarding), Spec A §9.4–§9.6

## Context

Documentele contabile din Republica Moldova au termene legale de păstrare. Spec A le-a marcat ca
`DN-22`, iar registrul ca `OD-21`, notând că blochează offboarding-ul.

Reevaluând: **nu blochează nimic acum și nu are nevoie de cifre pentru a fi modelat.** Impactul este
în F3, nu în F0. Ce trebuie decis acum este unde trăiesc termenele, nu care sunt.

## Opțiuni evaluate

1. **Tabelă proprie `retention_policy`** (varianta din Spec A §9.5). Funcționează, dar duplică un
   mecanism existent: date versionate pe interval, cu sursă normativă și selecție după dată
   efectivă. Ar avea propriul model de versionare, propria noțiune de sursă și propriul risc de a
   diverge de cel fiscal.
2. **Termenele ca parametri fiscali**, în sensul invariantului 15. Aceeași structură, aceeași
   disciplină de proveniență, același registru de selecție după dată efectivă, aceeași acoperire
   prin corpusul de regresie.
3. **Constante în cod.** Exclus de R15 și de `CLAUDE.md` §4.

## Decizie

**Opțiunea 2.** Termenele de păstrare sunt **parametri fiscali**.

- **Pe document:** `retention_class` — un câmp pe entitatea de document core (F0.6.1), nu un termen.
- **Termenul:** se rezolvă din `fiscal_parameter`, cu cheia `retention.<class>`, la data efectivă
  relevantă. Aceeași structură ca orice alt parametru: `valid_from` / `valid_to`, `source_id` către
  actul normativ cu număr de Monitorul Oficial și dată de publicare.
- **Valorile rămân deschise** (`OD-21`), completate ca date, cu confirmare de la contabil sau jurist.

`retention_policy` din Spec A §9.5 se elimină. Un mecanism, nu două.

### Un singur lucru afirmat despre conținut

Termenele **diferă substanțial** între documentele contabile obișnuite și cele de personal și
salarizare. De aceea `retention_class` are de la început cel puțin două valori distincte, iar un
termen unic pe tenant ar fi greșit indiferent de cifră.

Aceasta este singura afirmație cu conținut juridic din ADR. Rămâne de confirmat contra unei surse
citabile odată cu valorile din `OD-21` — dar nu blochează mecanismul, pentru că `retention_class`
suportă oricâte clase.

## Consecințe

**Devine posibil:**

- offboarding-ul se implementează în F3 fără să aștepte cifrele: mecanismul e complet, valorile se
  încarcă atunci când există
- o modificare legislativă a termenelor este `INSERT`, nu deployment (R15)
- fiecare termen își poartă temeiul legal, deci întrebarea „de ce ștergem asta acum" are răspuns

**Devine imposibil:** un termen de retenție fără sursă normativă — aceeași constrângere ca pentru
orice parametru fiscal.

**Ce trebuie modificat:**

- Spec A §9.5 — se rescrie; `retention_policy` dispare
- Spec A §1.1 — `tenant.retention_policy_id` dispare
- Spec B §5.1 — `retention.<class>` intră în domeniul de chei al parametrilor fiscali
- backlog F0.6.1 — `retention_class` pe documentul core; **singura consecință care atinge F0**

**Ce se verifică automat:** `fiscal-reviewer` tratează cheile `retention.*` ca orice parametru —
fără sursă, nu se activează. Niciun termen scris în cod.

## Surse

- Spec A §9.5 (`DN-22`), §1.1
- Spec B §5.1
- `_input/evidenta-master-plan-v2.md` §12.2
- `CLAUDE.md` R15, [ADR-002](002-guvernanta-deciziilor.md)
