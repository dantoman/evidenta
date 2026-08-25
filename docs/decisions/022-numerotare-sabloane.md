# ADR-022 — Numerotarea documentelor: șabloane configurabile per companie

- **Status:** Acceptat — decizie de produs și model, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `OD-02` (V2 §15.4, Amendament §E)
- **Afectează:** `platform/numbering`, F0.6.2, fiecare tip de document

## Context

Decizia era formulată „per companie sau per filială". Avea un blocaj preliminar semnalat la
inventar: **filiala nu există ca entitate** în modelul de tenancy — există `Tenant` și `Company`, nu
`Branch`. O decizie între două variante, dintre care una referă ceva nemodelat, nu se poate lua ca
atare.

## Decizie

**Numerotarea este un șablon configurabil, nu o formulă fixă.** Compania își definește forma
numărului; platforma o aplică și garantează unicitatea.

Un șablon se poate defini:

- **general**, pentru toate tipurile de document ale companiei, sau
- **per tip de document**, cu prefix, sufix și lungime proprii.

Rezoluția: șablonul specific tipului, dacă există; altfel cel general. Un tip fără niciunul este
eroare de configurare, nu un implicit inventat.

### Ce configurează un șablon

| Element | Rol |
|---|---|
| `prefix`, `suffix` | text liber — aici încape o filială, un punct de lucru, o serie fiscală |
| `digits` | lungimea zonei numerice, cu completare cu zerouri |
| `separator` | între componente |
| `include_year`, `year_format` | dacă anul face parte din număr, și în ce formă |
| `reset_policy` | `never`, `yearly`, `monthly` |

### Filiala nu se modelează

`prefix` acoperă nevoia fără să adauge un nivel în stratul zero. Consecința acceptată: **platforma
nu știe ce înseamnă seria.** Nu poate raporta pe filială, nu poate valida că o filială e reală, nu
poate impune că un utilizator emite doar pe seria lui.

Dacă filiala devine cerință reală — raportare pe filială, drepturi pe filială — aceea este o decizie
nouă, cu entitate proprie, care afectează Spec A §5 și fiecare tabelă company-scoped. Nu este o
extensie a acesteia, și se consemnează ca atare tocmai ca să nu fie confundată.

## Ce nu se negociază, indiferent de șablon

1. **Unicitatea se impune în bază**, prin constrângere pe `(company_id, document_type, series,
   fiscal_year, number)`. Un serviciu care „verifică apoi inserează" produce duplicate la prima
   scriere concurentă — și un număr de factură duplicat este defect de conformitate, nu de
   interfață.
2. **Alocarea numărului nu se face prin `MAX(number) + 1`.** Contorul este rând propriu, blocat la
   alocare. `MAX+1` sub concurență dă același număr la două tranzacții.
3. **Șablonul unei perioade nu se schimbă retroactiv.** Documentele emise păstrează numărul cu care
   au fost emise; schimbarea șablonului se aplică de la următoarea perioadă de resetare.
4. **Golurile sunt permise și trasabile.** Un document anulat nu eliberează numărul. Renumerotarea
   este imposibilă prin construcție — un registru contabil cu numere reatribuite nu este registru.

## Consecințe

- **Modele:** `numbering_template` (per companie, opțional per tip), `numbering_counter` (contorul
  blocabil, per șablon și perioadă).
- Serviciul de alocare rulează în tranzacția documentului, nu înainte de ea.
- F0.6.2 se deblochează.
- **De verificat cu contabilul practicant înainte de F2:** dacă legislația RM impune o formă sau o
  continuitate anume a numerotării facturilor fiscale, șablonul liber devine o constrângere, nu o
  facilitate. Nu am o sursă citabilă și nu presupun.

## Surse

- V2 §15.4; Amendament §E; Spec A §11 (`DN-02`)
- `_bootstrap/00-inventory.md` G-18 — observația că „filiala" nu e modelată
