# ADR-074 — Identitatea vizuală și stratul de componente: sistemul de design Evidenta

- **Status:** **Acceptat** — **decizie de produs**, luată de proprietar în două pași în aceeași
  sesiune: întâi alegerea direcției *(„Primitive + bară laterală")* dintre trei variante propuse, apoi
  livrarea machetei proprii — un pachet de predare exportat din Claude Design, cu instrucțiunea
  *„Implement: `Evidenta.dc.html`"*.
- **Data:** 2026-08-31
- **Decide:** proprietarul proiectului
- **Închide:** golul lăsat deschis de [ADR-009](009-componente-si-stil.md) — *unde* stau componentele
  era decis, *care* sunt nu era; și lipsa unei identități vizuale
- **Revizuiește:** [ADR-042](042-scara-de-densitate.md) §valori (vezi §4)
- **Afectează:** `frontend/src/index.css`, `frontend/src/shared/ui/` (nou), `frontend/src/shared/DataGrid`,
  `frontend/src/app/layout/`, `frontend/src/app/auth/LoginScreen.tsx`, toate ecranele
- **Legate:** [ADR-001](001-grila-de-date.md), [ADR-009](009-componente-si-stil.md),
  [ADR-014](014-limba-rusa.md), [ADR-042](042-scara-de-densitate.md),
  [ADR-052](052-contractul-de-tastatura.md)

## 1. Ce era înainte, măsurat

Nu „arăta sărac" ca impresie. Trei numere, luate din codul de dinaintea acestui ADR:

- `frontend/src/shared/ui/` — **gol**. ADR-009 spunea că acolo stau componentele copiate; nu era
  copiată niciuna.
- **27 de constante locale** `FIELD` / `BUTTON` prin ecrane, iar același șir de buton —
  `rounded border border-border bg-surface px-3 text-sm text-accent` — era scris identic în
  **16 fișiere**. De aceea fiecare acțiune arăta ca un link, inclusiv cele care postează în registru.
- Titlul de pagină era `text-base font-semibold`: **o treaptă** peste rândurile de sub el, deci
  nimic pe ecran nu spunea unde ești.

Tokenii, în schimb, existau și erau buni: culori OKLCH, scara de densitate din ADR-042, cifre
tabulare. Fundația era pusă, stratul de componente lipsea cu totul.

## 2. De unde vine forma, și ce e canonic în ea

Din pachetul de predare `Evidența-handoff.zip` (Claude Design), care conține macheta
`Evidenta.dc.html` și sistemul de design pe care îl importă. Distincția pe care o face chiar
`readme.md`-ul sistemului și pe care o păstrăm:

| Ce | Regim |
|---|---|
| Culori (navy / aur / pergament / neutre calde), gradientele, stema | **Canonice** — măsurate din arta livrată |
| Scara de spațiere, înălțimile de rând și de control, razele, umbrele | **Canonice** — ale sistemului |
| Familiile de litere | **Substituție declarată** — nu s-au livrat fișiere de font (§7) |
| Setul de pictograme | **Substituție declarată** — Lucide, la 2px (§6) |
| Inventarul de componente și aranjarea ecranelor | **Propuneri** — adoptate aici, cu abaterile din §5 |

Culorile poartă în ele o afirmație de domeniu care nu e decorativă și pe care o adoptăm ca atare:
**creditul se citește verde, debitul roșu**. Tonurile `credit` / `debit` din `Badge` și `Figure` sunt
acelea, și nu se refolosesc pentru „bine" / „rău" în alt sens.

## 3. Ce s-a construit

**Tokenii** trec integral în `frontend/src/index.css`, ca valori, într-un singur `:root`. Peste ei stă
maparea către utilitarele Tailwind, care **păstrează numele pe care codul le folosea deja**
(`bg-surface`, `text-ink-muted`, `border-border`): schimbarea de identitate schimbă valorile, nu
apelurile, deci nu a cerut o parcurgere a ecranelor.

Scurtăturile compuse de font (`--text-body-md: 400 15px/1.55 …`) stau **în afara** blocului `@theme`
și se consumă prin utilitare proprii `type-*`. Motivul e mecanic și verificat în CSS-ul construit:
în Tailwind v4 spațiul `--text-*` generează utilitare de **mărime**, iar o scurtătură `font` pusă
acolo ar produce un `font-size` invalid. Numele începe cu `type-` și nu cu `font-` din același fel de
motiv: `font-*` e spațiul familiilor, iar `font-eyebrow` ar fi însemnat două lucruri.

**Stratul de componente** — `frontend/src/shared/ui/`: `Button` (cinci intenții, trei înălțimi),
`IconButton`, `Icon`, `Input`, `Select`, `Field`, `Card`, `Badge`, `Figure`, `EmptyState`,
`PageHeader`. Ecranele importă dintr-un singur loc, `@/shared/ui`.

**Cochilia** — bară laterală pe gradientul stemei, cu identitatea sus, intrările spațiului de lucru,
apoi secțiunile companiei deschise; antet cu comutatorul de companie. Fiecare suprafață poartă doar
ce poate ști: antetul nu știe *care* companie (tenantul vine din gazdă — `C8` — dar un tenant ține mai
multe companii), banda de secțiuni o citește din adresă.

**Grila** ia forma sistemului: cap de coloană în majuscule condensate pe fond scufundat, la
înălțime de rând — nu mai înaltă —, rând care se aprinde la trecere, și **linie de aur de 2px peste
totaluri**. Acolo apare folia stemei într-o grilă, fiindcă linia de sub o coloană de cifre e exact ce
caută ochiul.

**Autentificarea** primește panoul stâng al machetei: stema, deviza, și un citat din patru, care se
schimbă la nouă secunde.

`Figure` **nu** formatează: cheamă `@/shared/format`, singurul modul pe care `C18` îl permite, și
decide doar față, aliniere și ton. Un al doilea formator de bani ar fi fost cea mai ușoară greșeală
din tot ADR-ul — macheta îl conține, gata scris.

## 4. Scara de densitate: 36 / 44 / 52 în locul lui 24 / 32 / 40

[ADR-042](042-scara-de-densitate.md) a fixat 40 / 32 / 24 pe **prior art** — Carbon, Sage și SAP
livrează exact acele trepte. Sistemul de design Evidenta livrează 52 / 44 / 36. Nu se pot ține
amândouă.

Se ține a doua, și **numele tokenilor rămân aceleași** (`--spacing-row-comfortable|compact|dense`),
deci `C21`, gardianul ESLint din cele două fișiere de grilă și `DataGrid` nu se ating: se schimbă
valorile, într-un singur loc, exact ce scara exista ca să facă posibil.

Ce se câștigă, dincolo de „așa e macheta": **rezerva de accesibilitate a lui ADR-042 dispare**.
Acolo, `dense` la 24px minus bordură lăsa 23px, sub minimul de 24×24 din WCAG 2.2 SC 2.5.8, deci
treapta strânsă nu putea purta butoane-iconiță în rând. La 36px poate. Regula scrisă în ADR-042
(„`dense` nu poartă butoane în rând") **nu mai are cauză** și nu se propagă mai departe.

Ce se pierde, spus deschis: pe un ecran de 1080px, un tabel arată **cu ~4 rânduri mai puțin** la
treapta implicită. Într-un ERP contabil asta contează, și e motivul pentru care implicitul rămâne
treapta din mijloc, iar `dense` e la o proprietate distanță.

## 5. Ce **nu** s-a construit din machetă, și de ce

Macheta arată mai mult decât are produsul. Nimic din ce urmează nu s-a desenat „ca să arate plin":

| Din machetă | De ce nu | Când intră |
|---|---|---|
| **Panou de control** (patru dale KPI, rulaj lunar, vechimea creanțelor, termene) | Niciuna dintre cifre nu are endpoint. Un tablou de bord cu numere plauzibile într-o aplicație contabilă e cea mai scumpă formă de minciună: se citește ca un raport | Când există read models pentru fiecare cifră, cu totalurile venite de la server (`C19`) |
| **Căutarea din antet** | Nu există căutare pe server | Cu primul endpoint de căutare |
| **Clopoțel de notificări, ajutor** | Nu există notificări | — |
| **Numele și funcția utilizatorului** | `whoami` întoarce `user_id`, nu un nume | Când identitatea poartă un nume |
| **Perioada în subsolul barei laterale** („Trimestrul II 2026") | Perioada deschisă nu e cerută de cochilie de nicăieri | Când cochilia are un motiv să o ceară |
| **Ceasul de pe autentificare** | Ar fi cerut un al doilea format de dată, iar `C18` spune că formatarea are exact o casă | Dacă modulul de formatare capătă un format de zi |

Regula din spatele tabelului: **un control care arată viu și nu răspunde îi învață pe oameni să nu
aibă încredere în cochilie.** Golul se vede; falsul nu se vede și se crede.

## 6. `lucide-react` ca dependență, și de ce nu încalcă `C23`

`C23` spune că **componentele shadcn sunt cod copiat, nu dependență**. Distincția care lasă
pictogramele afară: shadcn e **opinie de design** exprimată ca markup — există o versiune a ei care e
a noastră, și de aceea se copiază și se deține. O pictogramă e **geometrie**: nu există un
`building-2` al nostru. Patruzeci de trasee scrise din memorie ar fi fost patruzeci de glife
aproape-corecte, iar „aproape" nu se vede la revizuire.

Pinuită exact (`0.544.0`), ca tot restul. Numele expuse sunt cele ale sistemului de design,
kebab-case, iar uniunea de tipuri e vocabularul întreg: o pictogramă pe care n-o randează nimic e o
pictogramă pe care n-a ales-o nimeni.

## 7. Fonturile sunt o substituție, și poartă declanșatorul

Nu s-au livrat fișiere de font. Cele patru familii — Libre Baskerville (serif de marcă), Barlow
Condensed (majusculele de panglică), Source Sans 3 (interfața), IBM Plex Mono (cifrele) — sunt cele
mai apropiate potriviri Google Fonts la literele din stemă, încărcate prin `@import`.

**Declanșator de reîntoarcere:** când există fișiere licențiate, ele se auto-găzduiesc cu `@font-face`
local și `@import`-ul dispare. Până atunci, fiecare familie are stivă de rezervă reală, deci o rețea
absentă schimbă litera, nu așezarea — verificabil oprind rețeaua, nu presupus.

## 8. Ce rămâne de făcut

- Ecranele au primit stratul de componente, panoul sub grile și vocea tipografică a machetei.
  **Antetul de pagină cu supratitlu** (`PageHeader` cu `eyebrow` + rezumat) e adoptat pe *Companii* și
  *Parteneri*, ca tipar; restul ecranelor își păstrează deocamdată antetul simplu.
- `StatTile`, `Tabs`, `Dialog`, `Toast`, `Tooltip`, `Breadcrumbs` din sistem **nu** s-au construit:
  niciun ecran nu le cere azi. Se construiesc când le cere unul, nu înainte.
- Textul rusesc rămâne unde era ([ADR-014](014-limba-rusa.md)): șirurile noi au intrat în
  `locales/ro.ts`, niciunul în componente (`C32`).
