# ADR-038 — Nucleul deține vocabularul de `event_type`

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Fază:** F1 — Accounting Core
- **Închide:** `DNB-01` (Spec B §1.4)
- **Blochează:** Posting Engine, contractul document → postare, importatorul 1C
- **Legate:** [ADR-036](036-forma-postarii.md) (`event_type` e intrarea motorului),
  [ADR-039](039-valuta-si-perioade.md)

## 1. Problema

`event_type` este **intrarea** Posting Engine și granița registrului append-only. Un eveniment
intră, o postare imutabilă iese.

Întrebarea nu e cum se numesc evenimentele, ci **cine are dreptul să introducă unele noi și ce
garanții trebuie să ofere**. Dacă orice modul emite ce vrea, motorul nu mai poate garanta că fiecare
eveniment are o regulă de postare — iar rezultatul e cel mai prost mod de eșec dintr-un sistem
contabil: documente nepostate în tăcere, sau postate pe un cont de rezervă. Se descoperă în martie
că din noiembrie ceva nu s-a postat.

Spec B §1.4 enumeră trei variante: (A) fiecare modul își declară tipurile și `accounting` le acceptă
pe toate; (B) vocabular central în `accounting/events`; (C) central pentru tipurile cu efect
contabil, liber pentru rest.

## 2. Decizia

**Nucleul contabil deține registrul. Registrul e declarat în cod și e închis. Modulele își
înregistrează tipurile printr-un contract explicit.**

### 2.1 De ce înregistrarea nu încalcă `D2`

Spec B obiecta la varianta (B) că „fiecare modul nou cere o modificare în `accounting`, ceea ce se
apropie periculos de dependența interzisă de `D2`". Obiecția e reală pentru o **listă centrală
editată de `accounting`**, și dispare la înregistrare, fiindcă direcția se inversează:

```
sales/apps.py:  accounting.events.register(EventType(...))
```

`accounting` nu importă niciodată `sales`. Direcția `operations → accounting.events` este exact ce
`D3` permite explicit — `D3` interzice `accounting.ledger`, nu `accounting.events`. Gardianul de
dependențe o verifică deja.

## 3. Contractul de înregistrare

| Element | Conținut |
|---|---|
| Nume | Cu spațiu de nume, forma din Spec B §1.4: `<domeniu>.<acțiune>` — `sales.invoice_issued`, `purchases.invoice_received`, `payroll.run_approved` |
| Schema payload | Câmpurile evenimentului și tipurile lor |
| Roluri de cont solicitate | Sloturi semantice, nu conturi ([ADR-036](036-forma-postarii.md) §5.1) |
| Invarianți suplimentari | Peste cei șase verificați de motor |
| Handler | Referința la handlerul de postare |

**Forma numelui e cea din Spec B — două segmente, `snake_case` în al doilea.** Nu
`sales.invoice.issued`. Specul e scris, iar o a doua convenție de numire într-un vocabular închis
înseamnă că jumătate din tipuri se scriu greșit înainte să observe cineva.

### 3.1 Handlerul stă în cod, nu într-un rând de tabelă

Referința se rezolvă dintr-un tabel de implementări **declarat în cod**, exact ca la
`accounting.money_rounding` (F0.9). Motivul e de securitate și a fost măsurat acolo: o referință de
implementare citită dintr-un rând scriibil printr-o cale privilegiată transformă un singur `INSERT`
în execuție de cod arbitrar în rolul aplicației — iar gardianul de dependențe, care parcurge AST-ul,
nu vede un import dinamic deloc.

## 4. Selecția handlerului se face după data efectivă — `R17`, `R18`

**Aceasta este cea mai importantă corectură față de forma inițială a propunerii.**

§5 spune că un tratament schimbat produce `v2`. Dar cine alege între `v1` și `v2` când se
recalculează noiembrie 2026 în 2030? Dacă alegerea cade pe emitent, am scris exact
`if year >= 2027` pe care `R17` îl interzice.

Selecția se face **după data efectivă a perioadei calculate**, prin registrul care există din F0.8:

```
event_type + accounting_date  →  fiscal_logic_version  →  handler
```

Este forma pe care Spec B §4 o desenează deja: `event_type + accounting_date ∈ [valid_from, valid_to)`.
`R18` — recalcularea unei perioade trecute folosește algoritmul valabil atunci — nu se poate ține
altfel.

Consecință: un `event_type` are unul sau mai multe handlere, disjuncte pe interval de valabilitate.
Rezolvarea la zero sau la două este eroare cu cod stabil, nu alegere implicită — aceeași regulă ca
la parametrii fiscali.

## 5. Validarea la pornire, și unde rulează

**Un `event_type` înregistrat fără handler activ este eroare.** Verificat:

1. fiecare tip înregistrat are cel puțin un handler;
2. intervalele de valabilitate ale handlerelor unui tip nu se suprapun și nu lasă goluri;
3. fiecare rol solicitat există în catalogul de roluri;
4. fără nume duplicate;
5. fiecare tip are schema de payload declarată.

**Nu în `AppConfig.ready()`.** Acolo ar cădea *fiecare* comandă `manage.py`, inclusiv `migrate` —
deci un deploy care aduce cod fără handler n-ar mai putea rula migrarea care l-ar repara. Rulează
în două locuri:

- **în CI**, ca test propriu, fără bază de date — acolo trebuie să eșueze, la commit;
- **la pornirea proceselor care servesc**, web și worker, nu la comenzile de administrare.

Eșecul rămâne zgomotos și devreme, fără să blocheze calea de reparare.

## 6. Imutabilitate semantică

**Un `event_type` emis în registru nu-și schimbă niciodată semantica.** Registrul e append-only; o
semantică schimbată retroactiv face anul trecut necitibil corect, iar la un control fiscal asta e o
problemă, nu o inconveniență.

| Stare | Înseamnă |
|---|---|
| `active` | Poate fi emis; are handler pentru data curentă |
| `deprecated` | Nu mai poate fi emis; handlerele rămân pentru interpretarea istoricului |

**Nu există „șters".** Un tip emis vreodată rămâne permanent.

## 7. Familii speciale

### 7.1 Note contabile manuale

`manual.journal_entry` — numele din Spec B §1.5, un singur tip. Payloadul conține liniile compuse de
om; handlerul le validează și le postează fără să le derive. Șabloanele de operațiuni tipice
([ADR-036](036-forma-postarii.md) §7) produc acest tip, nu tipuri proprii.

### 7.2 Storno

`*.reversed` — fiecare tip stornabil are perechea lui. Handlerul inversează semnele postării
originale și o referă explicit. Două legături, cum cere `R14`: spre documentul sursă **și** spre
înregistrarea anulată.

### 7.3 Import — familia care cere o convenție proprie

Documentele importate **nu trec prin handlerele normale**, fiindcă suma preluată din 1C este
autoritativă și nu se recalculează: un handler ar deriva ce trebuie preluat ca atare.

> **Convenția se stabilește aici, nu prin trimitere.** Forma inițială a propunerii o cita dintr-un
> „ADR de convenții de platformă" care nu există — verificat, cuvântul nu apare nicăieri în
> `docs/decisions/` sau `docs/specs/`. Iar pe citarea aceea se sprijină o familie care ocolește
> handlerele, adică o excepție de la `R9`. O regulă fără ADR nu are autoritate.

**Convenția:** pentru familia `import.*`, suma din sursă este autoritativă. Handlerul postează
liniile primite fără derivare și marchează proveniența, astfel încât liniile rezultate să fie
distincte în registru — necesar pentru audit și pentru orice comparație ulterioară cu sursa.

Nu este o ocolire a Posting Engine: evenimentul trece prin motor, iar cei șase invarianți din
[ADR-036](036-forma-postarii.md) §4.2 se verifică la fel. Ce nu se face este **derivarea**
sumelor. Un import care nu echilibrează este refuzat ca orice altă postare — ceea ce este chiar
verificarea utilă la migrare.

## 8. Ce nu decide acest ADR

- lista concretă de `event_type` pentru F1 — se derivă din documentele primare, în backlog;
- forma postării per tip — [ADR-036](036-forma-postarii.md);
- structura payloadului per tip — specificația fiecărui modul.

## 9. Consecințe asumate

- **Adăugarea unui tip cere cod, nu configurare.** Consecvent cu ADR-038 §4.
- **Deprecierea în loc de ștergere** face registrul de tipuri să crească monoton. Cost real, mic.
- **Un tratament nou cere un handler nou cu interval de valabilitate**, nu o editare a celui
  existent. Este chiar prețul lui `R18`, plătit vizibil.
