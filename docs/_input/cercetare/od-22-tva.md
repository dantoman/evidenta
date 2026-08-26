# `OD-22` — TVA: cote, scutiri, prag de înregistrare, termene

- **Data cercetării:** 26 august 2026
- **Pentru:** `OD-22` (valorile fiscale efective), `F1.6`, `F2`

---

> ## Statutul sursei — de citit înainte de a folosi orice cifră de aici
>
> **Textul consolidat oficial al Codului fiscal n-a putut fi atins.** Trăiește exclusiv pe `legis.md`
> (Registrul de stat al actelor juridice), care întoarce **Cloudflare 403** la orice metodă. S-a
> confirmat că e singura sursă oficială: **și SFS, și Ministerul Finanțelor nu găzduiesc textul**, ci
> doar fac link către `legis.md`. **Monitorul Oficial** e accesibil, dar **textul integral e în spatele
> unui paywall** — s-au putut citi doar metadatele edițiilor.
>
> Cifrele de mai jos vin de la **Serviciul Fiscal de Stat**, care **citează verbatim** articolele
> Codului în **Baza generalizată a practicii fiscale (BGPF)** — unde fiecare răspuns e aprobat prin
> ordin SFS datat, iar versiunile vechi rămân arhivate cu data arhivării — și în articolele oficiale
> anuale „Modificările efectuate în Codul fiscal pentru anul X".
>
> **Clasificare onestă: sursă oficială administrativă, la un pas de actul primar.** Nu e portal
> contabil, dar nu e nici textul legii. **Niciun citat din acest fișier nu provine din textul legii, ci
> din reproducerea lui de către SFS.**
>
> **Consecință operațională:** `R15` cere pentru fiecare parametru actul, **numărul de Monitorul
> Oficial, data publicării și data intrării în vigoare**. Numerele MO **lipsesc pentru toate actele
> modificatoare** (vezi „Ce nu s-a putut verifica", pct. 2). Deci nimic de aici nu poate trece în
> `fiscal_parameter` cu status `active` până nu se obțin.

**Filtrul România a fost aplicat.** Fiecare sursă folosită e de pe `sfs.md`, `mf.gov.md`,
`trade.gov.md`, `monitorul.gov.md`. Nicio sursă reținută nu menționează ANAF, MFP sau Legea 227/2015.
Respinse explicit: `lex.md`/MoldLex (mirror comercial), `anta.gov.md` (export cu amendamente doar până
în 2014), `oda.md` (fișier din 2008), `lege.md`, `legalbadger.org`.

---

## 1. Tabelul valorilor

| Parametru | Valoare | Articol | În vigoare de la | Statut sursă |
|---|---|---|---|---|
| Cota standard | **20%** | art. 96 lit. a) | neschimbată în perioada cercetată | SFS/BGPF, ordin 66 din 05.02.2026 |
| Cota redusă — **unica** | **8%** | art. 96 lit. b) | vezi §5 | SFS/BGPF, ordin 66 din 05.02.2026 |
| — HoReCa (cazare și alimentație) | 8% | art. 96 lit. b) | **31.12.2023** *(anterior 12%)* | SFS, articol 2024 |
| — produse igienă feminină | 8% | art. 96 lit. b) | **01.01.2025** | SFS, articol 2024 |
| — dispozitive medicale (extindere) | 8% | art. 96 lit. b) | 2026, Legea nr. 187/2025 | SFS/MF, articol 2026 |
| Cota zero | **nu mai există ca literă a art. 96** | înlocuită de art. 104 | probabil 01.01.2021 — **neconfirmat** | vezi §3 |
| Scutiri fără drept de deducere | art. 103 alin. (1) pct. 1)–33) | art. 103 | structură din 2020 + delte | `trade.gov.md` 2020 + SFS |
| **Prag înregistrare obligatorie** | **1 700 000 lei** | art. 112 alin. (1) | **01.03.2026** (Legea nr. 12/2026) | SFS, comunicat + BGPF |
| — anterior | 1 500 000 lei | art. 112 alin. (1) | 01.01.2026 – 28.02.2026 | SFS/MF, articol 2026 |
| — anterior | 1 200 000 lei | art. 112 alin. (1) | până la 31.12.2025 | SFS/BGPF *(arhivat 29.01.2026)* |
| Perioadă de referință | **oricare 12 luni consecutive** | art. 112 alin. (1) | — | SFS/BGPF |
| Termen înregistrare | **ultima zi a lunii în care a avut loc depășirea** | art. 112 alin. (1) | — | SFS/BGPF |
| Prag înregistrare benevolă | **nu există prag separat** | art. 112 alin. (2) | **01.05.2015** *(anterior 100 000 lei)* | SFS/BGPF |
| Perioada fiscală | luna calendaristică | art. 114 alin. (1) | — | **neverificat verbatim** |
| Termen depunere declarație | **data de 25 a lunii următoare** | art. 115 alin. (1) | **01.01.2018** *(anterior: ultima zi a lunii)* | SFS/BGPF |

## 2. Cotele — art. 96

Sursa: SFS, BGPF 28.17.1, aprobat prin **Ordin SFS nr. 66 din 05.02.2026**.

> a) **cota-standard** – în mărime de **20%** din valoarea impozabilă a mărfurilor şi serviciilor
> importate şi a livrărilor efectuate pe teritoriul Republicii Moldova;
>
> b) **cote reduse** în mărime de: **8%** – la pîinea şi produsele de panificaţie (…), la laptele şi
> produsele lactate (…); **8%** – la mărfurile înregistrate în Nomenclatorul de stat al medicamentelor
> (…); **8%** – la mărfurile de la poziţiile tarifare 300215000, 3005, 300610 (…); **8%** – la livrarea
> pe teritoriul Republicii Moldova a **gazelor naturale** (…); **8%** – la producţia din **zootehnie**
> în formă naturală, masă vie, **fitotehnie şi horticultură** (…); **8%** – la **zahărul din sfeclă de
> zahăr** (…); **8%** – la **biocombustibilul solid** (…); **8%** – la **serviciile de cazare** (…);
> **8%** – la **produsele alimentare şi/sau băuturi**, cu excepţia producţiei alcoolice (…); **8%** –
> la tampoane igienice, tampoane interne pentru femei şi absorbante (…) şi **cupe menstruale**.

> **Observație pentru modelarea datelor:** există o **singură cotă redusă (8%)** cu **zece categorii
> distincte**. **Nu se modelează „cota redusă" ca scalar** — e o cotă cu listă de aplicabilitate legată
> de **poziții tarifare NC** și de **secțiunea I CAEM**. Cota de 12% nu mai există.

## 3. Cota zero — a dispărut ca literă

**Art. 96 curent are doar lit. a) și b).** Categoriile foste „cota zero" sunt acum **„livrări scutite de
TVA cu drept de deducere", art. 104**. Versiunea arhivată a BGPF conținea litera dispărută:

> „c) cota zero – la mărfurile şi serviciile livrate în conformitate cu art.104."

**Art. 104** (BGPF, Ordin SFS nr. 221 din 08.04.2025) scutește cu drept de deducere, între altele:
exportul și transporturile internaționale, serviciile de aerodrom și navigație aeriană; energia
electrică, energia termică și apa caldă pentru bunuri cu destinație locativă; proiectele de asistență
tehnică și investițională; zonele economice libere; serviciile industriei ușoare în perfecționare
activă; Portul Internațional Liber Giurgiulești și Aeroportul Mărculești.

> **Lista e depășită față de 01.01.2026.** Articolul SFS pentru 2026 anunță o scutire nouă, cu drept de
> deducere, pentru **importul de gaze naturale, energie electrică, energie termică sau energie pentru
> răcire**, care **nu se regăsește încă în BGPF**. Litera nouă și numărul ei sunt necunoscute.
> Literele c), d), e), h) lipsesc din lista curentă — abrogate la date nestabilite.

## 4. Scutirile fără drept de deducere — art. 103

Singura enumerare completă citită e un PDF găzduit pe `trade.gov.md`, **datat 26.04.2020**.

**Structura (stare 2020):** alin. (1) cu puncte **1)–33)**, dintre care **7), 23), 25), 28) abrogate** —
deci **~29 de poziții active, nu ~80**. Unele puncte au subdiviziuni pe litere (pct. 12 „serviciile
financiare" are propria listă). Alineate suplimentare: (2), (3), (5), (6), (8), (9²)–(9¹⁰).

Pozițiile care ating un IMM: **1)** locuința, pământul, locațiunea și arenda; **2)** produsele
alimentare pentru copii; **5)** instituțiile de învățământ; **9)** îngrijirea bolnavilor și bătrânilor;
**10)** serviciile medicale, cu excepția celor cosmetice; **12)** serviciile financiare; **13)**
serviciile poștale; **16)** cazarea în cămine și serviciile comunale; **17)** transportul de pasageri
pe teritoriul țării; **20)** producția de carte și publicațiile periodice; **29)** mijloacele fixe
utilizate nemijlocit la fabricarea produselor.

**Delte cunoscute după 2020**, fiecare de verificat separat înainte să intre ca parametru:

| Modificare | Punct | În vigoare |
|---|---|---|
| Excludere scutire cantine ale instituțiilor bugetate din sfera social-culturală | alin. (1) pct. 11) | 01.01.2025 |
| Excludere scutire organizații din sfera științei și inovării *(mutată pe acreditare ANACEC)* | alin. (1) pct. 27) | 01.01.2025 |
| Excludere scutire ateliere curative de pe lângă spitalele de psihiatrie | alin. (8) | 01.01.2025 |
| Scutire expresă mijloace fixe cap. 84–90 NC destinate capitalului social | alin. (1) pct. 29) | 01.01.2025 |
| Scutire mărfuri autohtone anterior exportate, reintroduse în 3 luni | alin. (2) lit. b¹) | 22.11.2023 |
| **Abrogare** scutire energie electrică importată/livrată către OTS, ORD, furnizori | alin. (1) pct. 18) | 01.01.2026 |

## 5. Pragul de înregistrare — art. 112

Sursa: BGPF 28.1, **Ordin SFS nr. 118 din 03.03.2026**.

> …este obligat să se înregistreze în calitate de plătitor TVA dacă el, **într-o oricare perioadă de 12
> luni consecutive**, a efectuat livrări de mărfuri, servicii în sumă ce **depăşeşte 1,7 mil. lei**, cu
> excepţia livrărilor scutite de TVA fără drept de deducere şi a celor care nu constituie obiect
> impozabil (…). **Subiectul este obligat să anunțe oficial Serviciul Fiscal de Stat (…) şi să se
> înregistreze nu mai târziu de ultima zi a lunii în care a avut loc depăşirea. Subiectul se consideră
> înregistrat din prima zi a lunii următoare celei în care a avut loc depăşirea.**

**Reguli de calcul al plafonului — relevante direct pentru implementare:**

- **Se exclud** livrările scutite **fără** drept de deducere și cele care nu sunt obiect impozabil.
- **Se includ** livrările scutite **cu** drept de deducere — SFS e explicit.
- **Importul de servicii se adaugă**; **importul de mărfuri NU** generează obligație.
- **Refacturarea cheltuielilor nu intră** în plafon.
- **Cotizațiile de membru** ale unei organizații necomerciale nu intră dacă nu presupun o livrare
  *(Scrisoarea Ministerului Finanțelor nr. 04-06/128 din 01.04.2025)*.
- Nu se aplică deținătorilor patentei de întreprinzător.
- **Nou în 2026:** beneficiarul mărfurilor conform art. 110 alin. (4) e obligat să se înregistreze
  **înainte** de a efectua procurările.

**Înregistrarea benevolă (alin. 2) nu are prag** din **01.05.2015**; anterior era 100 000 lei pe 12 luni
consecutive, cu condiția decontării prin virament.

## 6. Perioada fiscală și termenul declarației

**Termenul (art. 115 alin. (1))**, din 01.01.2018 — anterior era ultima zi a lunii:

> Declaraţia se întocmeşte pe un formular oficial, care este prezentat la Serviciul Fiscal de Stat **nu
> mai tîrziu de data de 25 a lunii care urmează după încheierea perioadei fiscale.**

**Perioada fiscală (art. 114 alin. (1)): textul verbatim NU s-a obținut.** Există doar dovezi indirecte
— prima perioadă fiscală începe în prima zi a lunii următoare depășirii și se termină în ultima zi a
aceleiași luni; ultima perioadă, simetric. Consistent cu luna calendaristică, **dar neconfirmat**.

## 7. Istoricul — și de ce contează forma lui

### 7.1 HoReCa: 12% → 8%, prin Legea nr. 212/2023

> A fost modificată **cota TVA pentru HORECA de la 12% la 8% (în vigoare începând cu 31 decembrie
> 2023)**.

> **Atenție la dată: tranziția e 31 decembrie 2023, nu 1 ianuarie 2024.** Un registru care recalculează
> decembrie 2023 trebuie să separe **30.12.2023 (12%)** de **31.12.2023 (8%)**. O fereastră de parametru
> aliniată la an dă rezultat greșit pentru o zi.

### 7.2 Anul 2025: nicio modificare de cotă sau de prag

Articolul oficial SFS pentru 2025 **nu conține nicio modificare a art. 96 și niciuna a art. 112**.
Modificările TVA pentru 2025 privesc art. 95 alin. (2) lit. i), art. 102 alin. (7) și (8¹), art. 103 și
art. 117. Actul de politică fiscală pentru 2025 e **Legea nr. 214/2024**.

### 7.3 Pragul: 1,2 → 1,5 → 1,7 mln lei, **ambele salturi în același an**

- **1,2 → 1,5 mln, de la 01.01.2026** — afirmat de SFS și MF, **fără să citeze legea pentru acest punct**.
- **1,5 → 1,7 mln, de la 01.03.2026** — **Legea nr. 12/2026**, citată de SFS prin comunicat.

Cronologia e confirmată independent de arhiva BGPF: versiunea cu 1,2 mln a fost arhivată la
**29.01.2026**, cea cu 1,5 mln la **03.03.2026**.

> **Implicația cea mai importantă a întregului fișier.** Anul 2026 are **trei valori de prag active în
> trei ferestre distincte**: până la 31.12.2025 → 1,2 mln; 01.01–28.02.2026 → 1,5 mln; de la 01.03.2026
> → 1,7 mln. **Un registru de parametri cu granularitate anuală dă rezultate greșite pentru
> ianuarie–februarie 2026.** Împreună cu tranziția HoReCa de la 31 decembrie, asta e proba concretă că
> `valid_from`/`valid_to` trebuie să fie **date**, nu ani — exact ce cere `R15`, dar acum cu un caz real
> în spate, nu cu un principiu.

### 7.4 Alte modificări cu efect din 2026, relevante pentru motorul de postare

| Modificare | Act | În vigoare |
|---|---|---|
| **Taxare inversă** pentru produse energetice (art. 101⁷) | Legea nr. 139/2025 | 01.01.2026 |
| Extinderea listei dispozitivelor medicale la cota 8% | Legea nr. 187/2025 | 2026 |
| Baza impozabilă la reduceri de preț *(discount, rabat, bonus, puncte de loialitate)* | Legea nr. 318/2025 | 2026 |
| **Abrogarea** restricției de deducere pentru facturi neelectronice (art. 102 alin. (18)) | — | 01.01.2026 |

---

## Ce nu s-a putut verifica

Fiecare poziție de aici e un blocaj real, nu o omisiune.

1. **Textul consolidat oficial al Codului fiscal — inaccesibil.** `legis.md` întoarce 403 la orice
   metodă. **Niciun citat din acest raport nu provine din textul legii.**
2. **Monitorul Oficial — text integral în spatele paywall-ului.** **Nu s-a putut obține numărul și data
   ediției MO** pentru: Legea nr. 12/2026, nr. 318/2025, nr. 187/2025, nr. 139/2025, nr. 212/2023,
   nr. 214/2024, nr. 311/2024. **Pentru un dosar care cere „număr MO, dată publicare, dată intrare în
   vigoare", aceste câmpuri lipsesc — la toate.**
3. **Art. 114 alin. (1) — negăsit în sursă oficială.** Formularea „luna calendaristică" **n-a fost
   confirmată de nicio sursă citită**. **Nu se introduce ca parametru fără verificare.**
4. **Art. 114 alin. (1¹)** — perioadă trimestrială pentru nerezidenți / e-commerce: apare doar într-un
   rezumat de motor de căutare. Neverificat.
5. **Structura curentă a art. 103 — neobținută.** Numerotarea 1)–33) reflectă **starea din 2020**. Cele
   șase delte identificate **nu garantează că lista e completă**, și nu există textul curent al niciunui
   punct.
6. **Actul care a ridicat pragul de la 1,2 la 1,5 mln nu e identificat prin număr.** Legea nr. 318/2025
   e citată pentru alte modificări din același pachet, dar **atribuirea nu e confirmată — nu se presupune**.
7. **Actul care a adăugat „absorbante pentru fiecare zi" la art. 96 în 2026 nu e identificat.**
8. **Data și actul eliminării „cotei zero" din art. 96 — neconfirmate.** 01.01.2021 e **plauzibil, nu
   verificat**.
9. **Datele de abrogare ale literelor c), d), e), h) din art. 104 — necunoscute.**
10. **Lista art. 104 e depășită** față de 01.01.2026.
11. **Datele extinderii sferei subiecților de la art. 115 alin. (1)** — nestabilite.
12. **Riscul de decalaj al BGPF.** BGPF se actualizează prin ordin SFS **după** intrarea în vigoare —
    decalaj observat între câteva zile și **peste un an**. **Data ordinului SFS nu e data intrării în
    vigoare a normei și nu se folosește ca `valid_from`.**
