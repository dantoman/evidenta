# `OD-35` — Scara de densitate: ce livrează sistemele reale

- **Data cercetării:** 2026-08-26
- **Relaţia cu ADR-042:** decizia are deja un ADR `Propus` — `docs/decisions/042-scara-de-densitate.md`,
  cu **32 / 28 / 24**. Cercetarea de mai jos **confirmă forma** (trei trepte, tokeni, font neschimbat)
  şi **contestă una dintre cele trei cifre**. Proprietarul a spus „implementează" pe `042`, deci ce
  urmează e material de revizuire, nu blocaj.
- **Convenţia de provenienţă:** fiecare rând e marcat la §7 — citit din sursa livrată, calculat, sau
  neverificat.

---

## 1. Cifrele livrate

| Sistem | Trepte | Înălţimi rând (px) | Antet | Font la cea mai densă | Unitate |
|---|---|---|---|---|---|
| **Carbon (IBM) v11** | 5 | **24 / 32 / 40 / 48 / 64** | egal cu rândul | 14px la **fiecare** treaptă | 8px |
| **SAP UI5 `sap.ui.table`** | 3 | **25 / 33 / 49** (cu bordura de 1px) | **32 / 32 / 48** | 14px peste tot | 8px |
| **Sage Carbon** *(vendor de contabilitate)* | 5 | **24 / 32 / 40 / 48 / 64** | — | 13px la compact | 8px |
| **Fluent 2** | 3 | **24 / 34 / 44** | egal cu rândul | 12px la xs | 4px |
| **MUI X Data Grid** | 3 | **36,4 / 52 / 67,6** | 39,2 / 56 / 72,8 | 14px, neschimbat | 8px |
| **Ant Design Table** | 3 | **39 / 47 / 55** *(calculat)* | egal cu rândul | 14px peste tot | 4px |
| **AG Grid Balham** *(temă de finanţe)* | 1 | **28** | 32 | 12px | 4px |
| **AG Grid Quartz** *(implicit curent)* | 1 | **42** | 48 | 14px | 8px |
| **SLDS (Salesforce)** | 2 | ~29 *(calculat)* | — | 13px | 4px |
| **Atlassian** | 0 publicate | fără scară de densitate pentru tabele | — | — | 8px |

**Formule de derivare, utile indiferent de valori.** AG Grid v33+, din pachetul livrat:
`rowHeight = max(iconSize, cellFontSize) + spacing × 3,25 × rowVerticalPaddingScale`. MUI:
`COMPACT_DENSITY_FACTOR = 0,7`, `COMFORTABLE_DENSITY_FACTOR = 1,3`. Ant: `2 × padding + 22px`.

## 2. Forma comună, neaşteptat de strânsă

- **Trei trepte e răspunsul modal** (SAP, Fluent, MUI, Ant). Carbon şi Sage livrează cinci, SLDS două.
  **Nimeni nu livrează patru.**
- **Înălţimile recurente sunt 24, 32, 40, 48** — apar la Carbon, Sage **şi** SAP, trei sisteme
  independente, aliniate exact. **24 e podeaua: niciun sistem verificat nu coboară sub.**
- **28 e orfan.** Doar AG Grid Balham. Nu e pe scara nimănui.
- **Fontul, în general, NU scalează cu densitatea.** SAP o spune explicit; Carbon ţine
  `body-compact-01` (14px/18px) de la 24px până la 64px. Doar Fluent şi Sage îl scalează.
- **Paşii sunt de 8px sau mai laţi.** Carbon 8/8/8/16; SAP 8/16; Fluent 10/10; MUI ~16. **Nimeni nu
  foloseşte paşi de 4px.**

## 3. Ţinte de atingere şi lizibilitate

- **WCAG 2.2 SC 2.5.8, nivel AA: 24×24 px CSS.** Excepţii: spaţiere, inline, echivalent, **control de
  user-agent**, esenţial. SC 2.5.5, nivel AAA: 44×44.
- **Constrângerea concretă la un rând de 24px:** după bordura de 1px rămân **23px**, sub minimul AA.
  Foaia de stil proprie a lui Carbon o spune cu voce tare — eticheta de checkbox la xs e
  `block-size: 23px` cu comentariul `// 24px row - 1px border`. Deci **un rând de 24px nu poate găzdui
  un buton-iconiţă propriu conform**, decât dacă îl salvează excepţia de spaţiere sau dacă e control
  nativ. E un compromis livrat (Carbon xs, Fluent extra-small, SAP condensed trăiesc toate cu el) —
  **dar se scrie în ADR, nu se descoperă mai târziu**.
- **Lizibilitatea nu e constrângerea care leagă.** 14px/18px într-un rând de 24px e chiar ce livrează
  IBM. Constrângerea e **ţinta interactivă**, nu litera.

## 4. Cum se exprimă densitatea ca tokeni

| Tipar | Cine | Verdict |
|---|---|---|
| Multiplicator pe o unitate de bază | AG Grid, MUI | Elegant, dar cuplează tot. AG Grid a trebuit să adauge portiţe, iar documentaţia lui recunoaşte: *„To change the height of rows… you **must** use `rowHeight`"* |
| Prop de mărime per componentă | Carbon, Ant, Fluent, Sage | Cel mai răspândit, cel mai previzibil |
| **Comutator de mod pe container** | SAP (`sapUiSizeCompact` pe un strămoş), SLDS | **Cel care supravieţuieşte.** Un atribut pe un înveliş redefineşte variabilele; toţi descendenţii moştenesc, fără prop-drilling |

> **Constatare dură pe Tailwind v4:** `--density-*` **nu este spaţiu de nume de temă**, deci tokenii
> propuşi în ADR-042 §3 **generează zero clase utilitare** — emit doar variabile CSS, folosibile prin
> `var()` sau sintaxă arbitrară. Spaţiile care generează utilitare: `--color-*`, `--font-*`,
> `--text-*`, `--font-weight-*`, `--tracking-*`, `--leading-*`, `--tab-size-*`, `--breakpoint-*`,
> `--container-*`, **`--spacing-*`**, `--radius-*`, `--shadow-*`. **Doar `--spacing-*` produce `h-`,
> `py-`, `min-h-`, `gap-`.**

> **Al doilea lucru portant:** o grilă virtualizată are nevoie de **înălţime fixă**, nu derivată din
> padding — TanStack Virtual cere `estimateSize`. SAP o face corect: `padding: 0 .5rem`, **zero padding
> vertical**, înălţime fixă, centrare verticală. O înălţime derivată din `py-*` se bate cu virtualizatorul.

## 5. Cifre tabulare şi coloane numerice

**GOV.UK Design System** e singurul care livrează asta ca CSS impus şi inspectabil:

```css
.govuk-table__cell--numeric { font-variant-numeric: tabular-nums }
.govuk-table__cell--numeric, .govuk-table__header--numeric { text-align: right }
```

Antetul e **aliniat la dreapta fără `tabular-nums`** — alinierea şi lăţimea cifrelor sunt preocupări
separate.

- **`font-variant-numeric: tabular-nums` e proprietatea corectă**, nu `font-feature-settings: "tnum"`.
- **Cifrele implicite ale lui Inter sunt proporţionale** — README-ul propriu listează cifrele tabulare
  printre funcţiile OpenType opţionale. Deci `@utility tabular` din `index.css` e **necesar, nu
  decorativ**: fără el, coloanele de sume se mişcă orizontal de la un rând la altul.
- **Carbon nu documentează nicio regulă de aliniere numerică** — verificat pe ambele pagini.
- Fiindcă `format/index.ts` fixează deja 2 zecimale prin `Intl`, **alinierea la dreapta e echivalentă
  cu alinierea la virgulă** pentru sume. Răspunsul ieftin şi corect; nu e nevoie de `text-align: "."`.

## 6. Recomandarea

**Se păstrează forma cu trei trepte din ADR-042. Se schimbă cifra din mijloc şi numele implicitului.**

### 40 / 32 / 24, nu 32 / 28 / 24

`compact: 28` e valoarea slabă, din patru motive:

1. **28 e orfan** — doar AG Grid Balham. 24, 32 şi 40 sunt livrate fiecare de Carbon, Sage **şi** SAP.
2. **Paşii de 4px sunt sub pragul perceptual.** Trei opţiuni pe care utilizatorul nu le distinge sunt
   o opţiune cu două momeli.
3. **Aritmetica proprie a ADR-ului o spune:** 32→28 aduce **+4 rânduri**; 32→24 aduce **+9**.
4. **O scară fără nimic peste 32 n-are mod de citire.** Sage — vendor de contabilitate — are implicit **40**.

Rânduri utile (corp = viewport − 120 chrome − 48 antet aplicaţie − 32 antet coloane − 40 totaluri):

| Ecran | util | 24px | 32px | 40px |
|---|---|---|---|---|
| 1366×768 *(laptop de birou mai vechi)* | 528 | **22** | 16 | 13 |
| 1920×1080 | 840 | **35** | 26 | 21 |
| 2560×1440 | 1200 | **50** | 37 | 30 |

Rândul de 768px contează pentru hardware-ul de birou din Moldova: la 32px ies **doar 16 rânduri**,
ceea ce face din `dense` un mod real de lucru, nu un moft de utilizator avansat.

### Nume, antet, font

`comfortable: 40` / **`compact: 32` (implicit)** / `dense: 24` — implicitul se mută de la
`comfortable` la `compact`, exact ca SAP, al cărui implicit desktop se numeşte literal *compact* şi e
fix 32px.

**Antet = `max(rând, 2rem)`** → 40 / 32 / 32. Reproduce SAP exact (`ColumnHeaderHeight: 2rem`,
`Cozy: 3rem`, **fără** variantă condensed — antetul rămâne deliberat la 32 când rândurile coboară la
24), şi satisface şi regula Carbon la treptele de sus.

> **Cele două autorităţi chiar se contrazic aici:** Carbon spune *„the column header row should always
> match the row size"*; SAP ţine antetul la 32 când rândurile coboară. Valoarea fixă din ADR-042 e
> comportamentul SAP — **dar justificarea lui („o ancoră îşi pierde rolul la aceeaşi înălţime cu
> conţinutul") e contrazisă de ambele sisteme la treptele potrivite.** Antetul se distinge prin fundal
> şi greutate, nu prin înălţime. Recomand păstrarea valorii şi scoaterea frazei.

**Fontul rămâne 14px la toate trei.** SAP o spune explicit; Carbon, Ant şi MUI o fac. Se compune şi cu
`C27`: font constant înseamnă lăţimi stabile la coloanele numerice când se schimbă densitatea.

### Exprimarea în Tailwind v4

```css
@theme {
  /* Scara de densitate — OD-35. Valorile sunt implicite livrate: Carbon xs/sm/md
     și Sage FlatTable compact/small/medium sunt ambele 24/32/40; SAP sap.ui.table
     e 24/32/48 cu 32 ca implicit desktop. Pașii sunt la un 8px distanță, deci
     rămân pe scara de spațiere de bază. `--spacing-*` e folosit deliberat: e
     singurul spațiu de nume Tailwind v4 care generează utilitare h-/py-/min-h-. */
  --spacing-row-dense:       1.5rem;  /* 24px */
  --spacing-row-compact:     2rem;    /* 32px — implicit */
  --spacing-row-comfortable: 2.5rem;  /* 40px */

  --spacing-cell-x-dense:       0.375rem; /* 6px */
  --spacing-cell-x-compact:     0.5rem;   /* 8px — SAP folosește `0 .5rem` */
  --spacing-cell-x-comfortable: 0.75rem;  /* 12px */

  --spacing-grid-header: 2rem;   /* 32px — niciodată sub rândul compact */
  --spacing-grid-footer: 2.5rem; /* 40px — bara de totaluri citește ca hotar */
}

/* Densitatea e mod de container, cum comută SAP pe `sapUiSizeCompact`: un atribut
   pe rădăcina grilei, nu un prop coborât la fiecare componentă imbricată. */
:root, [data-density='compact'] {
  --grid-row-h: var(--spacing-row-compact);
  --grid-cell-px: var(--spacing-cell-x-compact);
  --grid-header-h: var(--spacing-grid-header);
}
[data-density='dense'] {
  --grid-row-h: var(--spacing-row-dense);
  --grid-cell-px: var(--spacing-cell-x-dense);
  --grid-header-h: var(--spacing-grid-header);      /* rămâne 32 — SAP condensed */
}
[data-density='comfortable'] {
  --grid-row-h: var(--spacing-row-comfortable);
  --grid-cell-px: var(--spacing-cell-x-comfortable);
  --grid-header-h: var(--spacing-row-comfortable);  /* egal cu rândul — Carbon */
}
```

Planul de impunere prin ESLint din ADR-042 §5 e solid — şi acum are **nume concrete de interzis**,
fiindcă `--spacing-row-*` generează `h-row-compact` etc., deci formele permise sunt gref-abile.

## 7. Ce nu s-a putut verifica

**Citit din sursa livrată sau din documentaţia oficială — încredere mare:** Carbon 24/32/40/48/64
(citit **de două ori**, din `_data-table.scss` şi din pagina proprie de stil); Fluent 44/34/24 din
`useTableCellStyles.styles.js`; factorii MUI din `densitySelector.js`; AG Grid Balham 28 / Quartz 42 /
Alpine 42 / Material 48, calculate evaluând `calc()`-ul din CSS-ul distribuit oficial; SAP 25/33/49 şi
antet 32/32/48 din `library-parameters.json` servit de SAP; scările de spaţiere Atlassian, Carbon şi
SLDS; CSS-ul numeric GOV.UK din `govuk-frontend`; WCAG 24×24 şi 44×44; lista de spaţii de nume
Tailwind v4 din documentaţia oficială.

**O treaptă mai jos:** Sage Carbon 24/32/40/48/64 şi cifrele de scalare 1C (80%, 50–400%) — raportate
cu URL-uri, **dar fişierele n-au fost deschise personal**.

**Calculat, nu citit:** **Ant Design 39/47/55** — Ant v5 e CSS-in-JS fără foaie statică; s-au verificat
tokenii de intrare şi s-a făcut aritmetica, dar **nu s-a rulat o verificare de randare**. **SLDS ~29px**
— derivat din `13px × 1,5` plus padding plus bordură; aproximativ.

**Deloc verificat:** **înălţimile de rând 1C în px** — căutate activ, negăsite; explicaţia structurală
(1C dimensionează în linii de text faţă de fontul de dialog al sistemului, deci nu există cifră fixă de
publicat) e **inferenţa agentului, nu o afirmaţie 1C**; nicio măsurătoare pe captură de ecran.
**Xero, QuickBooks Online, NetSuite** — nicio cifră publicată găsită şi **nimic nu s-a estimat**;
portalul XUI al Xero nu se rezolvă, `@xero/xui` nu e pe npm, sistemul Intuit nu e publicat. *Orice
cifră citată pentru ele în altă parte e aproape sigur citirea cuiva din DevTools pe un singur ecran.*
**Polaris şi Atlassian** pe alinierea numerică — Polaris randează pe client şi n-a întors text;
Atlassian publică scară de spaţiere dar nicio scară de densitate pentru tabele. Răspunsul de la §5 stă
pe GOV.UK plus convenţie generală.

**Rezervă de proces:** bugetul de 200 de căutări web al sesiunii s-a epuizat pe parcurs, deci
verificarea târzie a mers prin `curl`/WebFetch pe URL-uri cunoscute, nu prin descoperire.
