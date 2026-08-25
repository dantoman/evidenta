# ADR-017 — Terminologia: două straturi independente

- **Status:** Acceptat — 2026-08-24, decizie de produs și schemă, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** niciuna. Deschide `OD-42` (entitatea din spatele lui `assignment`)
- **Afectează:** Spec A, schema, fiecare ecran, fiecare document generat, `CLAUDE.md` §2.7

## Context

Produsul are trei tipuri de actori care se confundă ușor în vorbire: clientul SaaS, entitatea
juridică cu ledger, și organizația care prestează servicii contabile. Fără vocabular fixat, fiecare
ecran alege altă formulare și produsul vorbește inconsecvent cu utilizatorul — iar în schemă apar
sinonime care par entități distincte.

Problema are două fețe care nu se rezolvă la fel. În cod, termenul trebuie să fie precis și stabil.
În interfață, trebuie să fie ce spune utilizatorul cu voce tare. Cele două cerințe nu produc
aceleași cuvinte.

## Opțiuni evaluate

1. **Un singur vocabular, folosit peste tot.** *Avantaje:* nimic de tradus, zero ambiguitate între
   discuția tehnică și ecran. *Dezavantaje:* ori interfața vorbește ca schema — „tenantul dumneavoastră"
   —, ori schema vorbește ca interfața și pierde precizia (`client` înseamnă lucruri diferite pentru
   contabil și pentru platformă). *Cost de schimbare:* mare — atinge și schema, și fiecare ecran.
2. **Două straturi, cu hartă fixă de traducere.** *Avantaje:* fiecare strat optimizează pentru
   cerința lui; harta e verificabilă. *Dezavantaje:* trebuie ținută minte și impusă; un termen de
   model scăpat în interfață e defect vizibil. *Cost de schimbare:* mic pentru cuvinte de interfață,
   mare pentru cele de model.

## Decizie

**Opțiunea 2.** Două straturi independente, cu hartă fixă.

### Stratul de model — engleză, în cod și schemă

| Entitate | Ce e |
|---|---|
| `tenant` | Clientul SaaS, proprietarul datelor. Are subdomeniu. |
| `company` | Entitatea juridică cu ledger propriu. Un tenant poate avea mai multe. |
| `firm` | Organizația care prestează servicii contabile. Persoană juridică sau fizică. |
| `engagement` | Relația `firm` → `tenant`. Delegată, revocabilă, cu perioadă. |
| `assignment` | Repartizarea internă `user` → `tenant` în cadrul unei firme. |
| `platform` | Furnizorul platformei. Planul de control, grantul de suport. |
| `supplier` | **Rezervat exclusiv** furnizorului din achiziții. Nu se folosește pentru altceva. |

> **Notă obligatorie pe `firm`: este organizație, nu persoană.** Contabilul individual este o firmă
> cu un singur membru. Modelul nu are cale separată pentru „contabil persoană fizică"; are o firmă
> cu `Membership` unic. Orice cod care tratează contabilul individual ca alt tip de actor este
> defect.

### Stratul de interfață — română, pe ecran

| Cine vede | Ce scrie |
|---|---|
| Clientul, despre sine | **compania mea** / **companiile mele** |
| Clientul, despre contabil | **contabilul meu** |
| Contabilul, despre portofoliu | **clienții mei** |
| Relația, în ambele sensuri | **contract de deservire** |
| Furnizorul platformei | *nu apare*, cu o singură excepție |

**Excepția**, formulată concret și nu generic:

> „Echipa Evidenta solicită acces temporar la datele companiei pentru rezolvarea solicitării #1234."

Concretețea este cerința: un ecran de consimțământ care spune „platforma solicită acces la datele
dumneavoastră" cere aprobare pentru orice, oricând. Numărul solicitării leagă accesul de un motiv.

**Cuvintele `tenant`, `firm`, `engagement` și `assignment` nu apar niciodată în interfață** — nici
în etichete, nici în mesaje de eroare, nici în e-mailuri, nici în documente generate.

### Regula care le ține legate

**Termenii de model și cei de interfață sunt straturi independente. Nu se aliniază unul după
celălalt.** Traducerea este o **hartă fixă**, nu o convenție de moment.

Consecința practică: redenumirea unei entități în schemă nu schimbă interfața, iar reformularea unui
ecran nu schimbă schema. Cine vrea să schimbe harta modifică acest ADR, nu ecranul la care lucrează.

## Consecințe

- Devine posibil: verificarea mecanică a stratului de interfață. Fiindcă `C32` cere ca șirurile să
  stea în fișiere de resurse, interdicția termenilor de model devine un grep peste acele fișiere,
  nu o revizuire manuală de componente.
- Devine imposibil, prin regulă: `supplier` folosit pentru firma de contabilitate sau pentru
  furnizorul platformei; „contabil persoană fizică" ca al doilea tip de actor.
- De modificat ca urmare: `CLAUDE.md` §2.7 primește `C35`–`C37` — doar partea scurtă: rezervarea lui
  `supplier`, `firm` ca organizație, interdicția termenilor de model în interfață. Tabelele complete
  rămân aici; `CLAUDE.md` nu este glosar.

### Două lucruri pe care acest ADR le semnalează, fără să le rezolve

**1. `assignment` nu are entitate în Spec A.** Spec A §1.6 are `Membership` (`user` ↔ `tenant`) și
§1.7 `CompanyAccess` (`user` ↔ `company`, cu `granted_via ∈ ('membership','engagement')`). Niciuna
nu este repartizarea internă a unei firme: `CompanyAccess` este un fapt de **autorizare**, citit de
politicile RLS, în timp ce `assignment` este un fapt **organizațional** — cine răspunde de acest
client — care poate exista fără acces și poate lipsi când accesul există.

Acest ADR fixează **cuvântul**, nu schema. Dacă `assignment` devine entitate proprie sau rămâne o
citire a lui `CompanyAccess` este `OD-42`, decis în Spec A. Termenul nu se folosește în cod până
atunci.

**2. `platform` este deja nume de modul.** `CLAUDE.md` §3 are `platform` ca app Django de care
depinde tot, iar `C29` cere mypy strict pe el. Ca actor, `platform` înseamnă altceva: furnizorul.
Ambiguitatea este acceptată, nu rezolvată — contextul le separă în practică. Dar o entitate de
schemă nu se numește `platform`; grantul de suport primește nume propriu, decis când se modelează.

## Surse

- `specs/spec-a-tenancy.md` §1.1–1.7 (`Tenant`, `Company`, `Firm`, `Engagement`, `Membership`,
  `CompanyAccess`).
- `specs/spec-b-accounting.md` §10 — `supplier_idno` în cheia naturală a facturii primite,
  consecvent cu rezervarea de mai sus.
- `CLAUDE.md` §2.7 (`C15`, `C32`), §3 (modulul `platform`).
- [ADR-014](014-limba-rusa.md) — șirurile în fișiere de resurse, ce face verificabilă interdicția.
- Conversație 2026-08-24.
