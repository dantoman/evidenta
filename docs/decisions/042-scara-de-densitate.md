# ADR-042 — Scara de densitate, ca set de tokeni

- **Status:** Acceptat — proprietarul a cerut implementarea după ce valorile i-au fost prezentate;
  forma era deja fixată de [ADR-009](009-componente-si-stil.md) `C26`.
  **Valorile au fost revizuite în aceeași zi** (§3), după cercetarea de prior art din
  `_input/cercetare/od-35-scara-de-densitate.md` — proprietarul a acceptat 32/28/24, iar ce s-a
  livrat este 40/32/24. Diferența e vizibilă aici tocmai fiindcă acceptarea a fost dată pe alte cifre
- **Data:** 2026-08-26
- **Închide:** `OD-35`
- **Deblochează:** `F1.G1` (`DataGrid`), primul ecran cu grilă, `F1.8` (rapoartele)
- **Legate:** [ADR-001](001-grila-de-date.md), [ADR-009](009-componente-si-stil.md), `C21`, `C26`, `C27`

## 1. De ce nu se poate amâna mai mult

`C21` cere ca spațierea din ecranele cu grile să vină din scara de densitate, iar `C26` spune că
scara **este un set de tokeni**, nu o convenție verbală. Ambele reguli sunt active de acum. Ce
lipsește sunt valorile — și lipsa lor blochează exact partea care se vede: `DataGrid`, primul ecran
cu grilă, rapoartele.

Motivul pentru care nu se aleg după construcție, scris în registru: implicitele Tailwind și shadcn
sunt calibrate pentru SaaS aerisit; comprimarea după patruzeci de ecrane construite pe ele înseamnă
rescriere, nu ajustare.

## 2. Ce decide de fapt scara: câte rânduri intră pe ecran

Aritmetică pe propriul nostru layout, nu preferință. Pe un ecran de 1080p, înălțimea utilă pentru
corpul grilei — după ce se scad chrome-ul browserului (~120px), antetul aplicației (48px), capul de
coloane (32px) și bara de totaluri (40px) — este de aproximativ **840px**:

| Înălțime de rând | Rânduri vizibile | |
|---|---|---|
| 40px | 21 | implicitul shadcn |
| 32px | 26 | |
| 28px | 30 | |
| 24px | 35 | |

Diferența dintre 21 și 35 de rânduri nu e estetică. Într-o balanță de verificare sau într-o fișă de
cont, e diferența dintre a vedea o lună întreagă și a derula.

## 3. Decizia: trei trepte — 40 / 32 / 24, implicit 32

> **Revizuit în aceeași zi, după cercetare.** Prima versiune propunea 32/28/24 sub numele
> `--density-*`, derivate din aritmetica de mai sus. Două lucruri s-au dovedit greșite la
> măsurătoare, iar valorile de mai jos le înlocuiesc. Aritmetica din §2 rămâne validă ca motivație —
> nu mai e însă și sursa cifrelor.

**Spațiul de nume este `--spacing-*`, nu `--density-*`.** Verificat în CSS-ul construit, nu presupus:
`--density-row-compact` emite variabila și **niciun utilitar**; `--spacing-row-compact` produce
`.h-row-compact{height:var(--spacing-row-compact)}`. Doar `--spacing-*` generează `h-`, `py-`,
`min-h-`, `gap-` în Tailwind v4. Cu numele greșit, §5 ar fi cerut ESLint-ului să interzică ceva ce
nimeni n-ar fi putut scrie oricum.

**Valorile sunt prior art, nu aritmetică.** Carbon, Sage și SAP livrează fiecare exact treptele
**24 / 32 / 40** — trei sisteme independente, aliniate. **28 e orfan**: doar AG Grid Balham îl are.
Niciun sistem verificat nu coboară sub 24 și niciunul nu folosește pași mai mici de 8px.

**Implicitul e 32.** La SAP treapta se numește literal „compact" și e implicitul de desktop. Sage,
care este vendor de contabilitate, are implicit 40 și livrează 24/32/40/48/64 — deci treapta de sus
există pentru citit rapoarte și nume care se rup pe două rânduri, ceea ce prima versiune nu avea.

```css
@theme {
  --spacing-row-comfortable: 2.5rem; /* 40px */
  --spacing-row-compact:     2rem;   /* 32px — implicit */
  --spacing-row-dense:       1.5rem; /* 24px */

  --spacing-cell-x-comfortable: 0.75rem;
  --spacing-cell-x-compact:     0.5rem;
  --spacing-cell-x-dense:       0.375rem;

  /* Antetul urmeaza randul, cu prag jos. */
  --spacing-header-comfortable: 2.5rem;
  --spacing-header-compact:     2rem;
  --spacing-header-dense:       2rem;

  --spacing-grid-footer: 2.5rem;
}
```

### 3.1 Antetul urmează rândul — și motivarea inițială era greșită

Prima versiune ținea antetul fix la 32 cu argumentul că „o ancoră vizuală își pierde rolul dacă
ajunge la aceeași înălțime cu conținutul". **Carbon spune explicit contrariul:** capul de coloană
trebuie să aibă aceeași înălțime ca rândul. Se distinge prin fundal și greutate, nu prin înălțime.

Valoarea rămâne aproape aceeași — `max(rând, 2rem)`, deci 40/32/32, comportamentul SAP, care ține
antetul la 32 când rândurile coboară la 24 — dar pragul există fiindcă sub 32px un cap de coloană cu
text scurt devine greu de țintit, nu ca să se distingă.

### 3.2 Înălțimea e `height`, nu `padding`

Rândul primește o înălțime fixă cu `padding-block: 0` și centrare verticală, cum face SAP. O
înălțime derivată din `py-*` se bate cu `estimateSize` din TanStack Virtual și face măsurarea
rândului dinamică fără câștig — adică plătește exact la volumul pentru care virtualizarea există.

### 3.3 `dense` nu poartă butoane în rând

La 24px, minus 1px bordură, rămân **23px** — sub minimul de 24×24 al WCAG 2.2 SC 2.5.8. Carbon
trăiește cu exact acest compromis și își scrie `23px` în sursă. Constrângerea se scrie aici ca să nu
fie descoperită de la un audit: acțiunile pe rând se restrâng la `compact` și `comfortable`.

## 4. Ce NU decide

Nu decide mărimea fontului, care ține de tipografie și e deja tokenizată. Nu decide comportamentul de
tastatură — `OD-36`, deschisă, precondiție a lui `EntryGrid`. Nu decide dacă densitatea e aleasă de
utilizator sau fixată per ecran: aceea e o întrebare de produs care apare abia când există mai mult
de un ecran cu grilă, iar răspunsul ei nu schimbă tokenii.

## 5. Cum se verifică

Tokenii sunt inutili dacă un ecran scrie oricum `py-2`. `C21` se verifică prin ESLint peste
`frontend/src`, la fel cum `C16` verifică deja importul direct de `@tanstack/react-table`: o regulă
`no-restricted-syntax` care refuză clasele literale de spațiere verticală în fișierele de grilă.

Regula se scrie **odată cu `DataGrid`**, nu înainte — altfel n-are ce refuza, iar un gardian care
n-a refuzat niciodată nimic e unul a cărui formă n-o cunoaște nimeni.

## 6. Ce urmează dacă se acceptă

`F1.G1` — `DataGrid` peste `@tanstack/react-table`, deja instalat — apoi primul ecran real: planul de
conturi, peste `/api/v1/accounting/coa/`, care există, e testat și **n-are încă niciun consumator**.

Criteriul de terminare al lui `F1.G1` cere randare peste un extras 1C real, la volum (`OD-28`), și
**rămâne deschis**: componenta se poate construi și demonstra pe date sintetice, dar sarcina nu se
închide până nu există extrasul. Aceeași formă de închidere parțială ca la `F1.5.1`, numită ca atare.
