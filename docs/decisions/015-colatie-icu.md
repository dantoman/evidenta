# ADR-015 — Colația: ICU explicit, ales la crearea bazei

- **Status:** Acceptat — 2026-08-24, după corectarea premisei prin măsurare
- **Data:** 2026-08-24
- **Propune:** proprietarul proiectului, corectat prin măsurare
- **Închide:** `OD-39`
- **Afectează:** crearea bazei de date, fiecare coloană de denumire, fiecare index pe denumire

## Context

Ridicată ca al treilea punct din discuția despre limba rusă: „dacă indecșii pe denumiri presupun
ordonare românească, textul chirilic se sortează imprevizibil. ICU rezolvă asta, dar trebuie ales
conștient la crearea coloanelor, nu descoperit când apare primul client rusofon."

Concluzia — alege ICU conștient — este corectă. **Premisa nu este.** Măsurat pe PostgreSQL 18.6, cu
denumiri românești cu diacritice și chirilice amestecate:

| Colație | Ordine |
|---|---|
| `en_GB.UTF-8` (implicită la `initdb`) | Ana < Sandu < Șerban < Ștefan < Zaharia < Андрей < Ольга < Ярослав |
| `ro-x-icu` | identică |
| `und-x-icu` | identică |
| **`C`** | Ana < Sandu < **Zaharia < Șerban < Ștefan** < Андрей < Ольга < Ярослав |

**Chirilicul nu se sortează imprevizibil.** Sub orice colație lingvistică, el se așază după latină,
consecvent. Ceea ce se rupe este altceva, și se rupe **azi, fără niciun client rusofon**: sub
colația `C`, `Zaharia` vine înaintea lui `Șerban`, pentru că `Ș` (U+0218) are octeți mai mari decât
`Z`. Sortarea alfabetică românească este greșită într-o listă pur românească.

Deci riscul real nu este „apare un client rusofon". Este „cineva creează o coloană cu `COLLATE "C"`
pentru viteză, sau baza se creează cu provider `builtin`, și lista de parteneri se ordonează greșit
pentru fiecare client, în română".

## Al doilea motiv, care nu ține de limbă deloc

Colațiile glibc **își schimbă comportamentul între versiuni de sistem de operare**. Un index pe o
coloană text construit sub o versiune de glibc devine subtil incorect după un upgrade al imaginii de
bază: interogările pot rata rânduri care există. PostgreSQL urmărește versiunea colației și
avertizează la nepotrivire, dar avertismentul apare *după* upgrade.

ICU este versionat explicit și urmărit de PostgreSQL, ceea ce face problema vizibilă și
gestionabilă în loc de tăcută.

Pentru un sistem contabil unde se restaurează medii, se clonează producția în staging și se
depanează clienți pe imagini care nu sunt identice, aceasta este consecința mai gravă dintre cele
două.

## Opțiuni

1. **Baza se creează cu provider ICU și colație implicită `und-x-icu`** (rădăcină, agnostică de
   limbă). Toate coloanele text moștenesc. Un singur loc de decis, imposibil de uitat pe o coloană.
   Prețul: `und` nu aplică reguli specifice unei limbi — pentru română diferența față de `ro-x-icu`
   nu apare la datele de mai sus, dar poate apărea la cazuri marginale.
2. **Provider ICU cu `ro-x-icu` ca implicit.** Corect pentru română; devine o alegere ciudată pentru
   tenantul care lucrează exclusiv în rusă, deși măsurătoarea arată că nu îl afectează practic.
3. **`COLLATE` per coloană**, pe fiecare denumire. Control maxim, dar exact tiparul care se uită la
   a patruzecea tabelă — și uitarea nu produce eroare, produce ordonare greșită.
4. **Se lasă implicitul sistemului.** Ce se întâmplă azi: `en_GB.UTF-8` cu provider `builtin` pe
   mașina de dezvoltare. Ordonează corect, dar depinde de locale-ul mașinii pe care s-a rulat
   `initdb` — deci dev, CI și producția pot diferi fără ca nimeni să observe.

## Decizie

**Opțiunea 2: colația implicită a bazei este `ro-x-icu`.**

Motivul, împotriva recomandării inițiale pentru `und`: datele sunt românești în covârșitoare
majoritate, iar când vor exista denumiri în rusă, ele vor sta în **tenanți separați**, nu amestecate
în aceeași listă. Ordonarea corectă a limbii dominante este câștigul real; ordonarea corectă a unui
amestec care nu apare în practică nu este.

### Este o decizie „la creare", ca și cheia de partiționare

Colația implicită a bazei **nu se schimbă ulterior fără reconstruirea tuturor indecșilor pe text**.
Se consemnează cu aceeași greutate ca decizia de partiționare din Amendament §B.3: nu e un parametru
de configurare, e o proprietate a bazei fixată la `CREATE DATABASE`.

### Codurile nu primesc colație lingvistică

IDNO, coduri de conturi, coduri de articole, SKU, numere de documente: `COLLATE "C"`, **explicit pe
coloană**. Comparație pe octeți — previzibilă și rapidă.

Un cod de cont ordonat lingvistic este o subtilitate care produce rapoarte în ordine ciudată, iar
cauza se caută în raport, nu în definiția coloanei. Regula inversă față de denumiri, din același
motiv: fiecare coloană primește colația potrivită naturii ei, niciodată pe cea implicită din
neatenție.

`schema-reviewer` verifică: **coloanele de tip cod au colație explicită.** Absența ei este finding,
nu preferință.

## Consecințe

- Baza se creează cu provider ICU. **Forma exactă, verificată pe PostgreSQL 18.6:**

  ```sql
  CREATE DATABASE evidenta LOCALE_PROVIDER icu ICU_LOCALE 'ro' TEMPLATE template0;
  ```

  ```
  initdb --locale-provider=icu --icu-locale=ro --encoding=UTF8 --locale=C.UTF-8
  ```

  **`ro`, nu `ro-x-icu`.** `ro-x-icu` este numele *obiectului de colație* pe care PostgreSQL îl
  creează și pe care îl folosești în clauze `COLLATE`; ca `ICU_LOCALE` este o confuzie de categorie.
  Trece — ICU parsează `x-icu` ca extensie privată și o ignoră — dar lasă în `pg_database.datlocale`
  valoarea `ro-x-icu` în loc de `ro`, adică o bază care arată altfel decât cea din documentație
  fără să se comporte altfel. Genul de nepotrivire care costă o oră la prima depanare.

- Intră în `infra/bootstrap/`, ca pas premergător: este proprietate a **bazei**, nu a schemei — deci
  nu poate fi o migrare, și nu poate fi corectată de una.
- `docker-compose.yml`: `POSTGRES_INITDB_ARGS` corespunzător, ca mediul local să nu difere.
- `schema-reviewer`: două verificări simetrice — `COLLATE "C"` pe o coloană de denumire este
  finding; **absența** unei colații explicite pe o coloană de cod este finding.
- **De verificat înainte de acceptare:** costul asupra indecșilor. ICU este măsurabil mai lent decât
  `C` la comparație; pe `journal_line` nu contează (nu se sortează pe text), pe listele de parteneri
  și articole trebuie măsurat, nu presupus.

## Surse

- Măsurătoare proprie, PostgreSQL 18.6, 2026-08-24 — tabelul de mai sus
- [ADR-014](014-limba-rusa.md), punctul 3 din „trei lucruri cu cost zero"
