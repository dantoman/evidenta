# `OD-22` — Planul general de conturi: actul, lanțul de închidere, clasa 8

- **Data cercetării:** 2026-08-26
- **Sursa primară:** PDF-ul consolidat publicat de Ministerul Finanțelor ca anexă pe pagina proprie
  a actului — <https://mf.gov.md/sites/default/files/legislatie/Planul%20general%20de%20conturi%20contabile.pdf>
  (63 pagini, cele trei capitole complete, cu notele de modificare inline)
- **Pagina actului:** <https://mf.gov.md/ro/content/planul-general-de-conturi-contabile-aprobat-prin-ordinul-nr119>

---

## 1. Actul — răspunsul pe care `OD-22` îl cerea

**Nu Ordinul 118.** Acela aprobă SNC-urile. Planul de conturi e aprobat printr-un **act separat,
emis în aceeași zi**:

> **Ordinul Ministerului Finanţelor nr. 119 din 06.08.2013 privind aprobarea Planului general de
> conturi contabile**

| | |
|---|---|
| **Publicarea ordinului** | Monitorul Oficial nr. 177-181, art. 1225, din **16.08.2013** |
| **Publicarea Planului (anexa)** | Monitorul Oficial nr. 233-237, art. 1534, din **22.10.2013** |
| **Intrare în vigoare** | 01.01.2014 |
| **Aplicare** | recomandare de la 1 ianuarie 2014, **obligatoriu de la 1 ianuarie 2015** |

Cele două trimiteri la Monitorul Oficial nu sunt o dublare: ordinul s-a publicat în august, anexa în
octombrie. Practica proprie de redactare a Ministerului folosește **referința din august** pentru
ordin — așa îl citează în propriul proiect de modificare din 2021.

Planul anterior (Ordinul nr. 174 din 25.12.1997) a fost abrogat de la 1 ianuarie 2015.

**Istoricul modificărilor**, citit din notele inline:

| Ordin modificator | În vigoare |
|---|---|
| MF nr. 146 din 16.10.2013 | 01.01.2014 |
| MF nr. 166 din 28.11.2013 | 01.01.2014 |
| MF nr. 188 din 30.12.2014 — **introduce contul 336** | 01.01.2015 |
| MF nr. 26 din 04.03.2015 | — |
| MF nr. 100 din 28.06.2019 — **întregul nomenclator e în această redacție** | 01.01.2020 |

## 2. Lanțul de închidere — confirmat, cu două rafinări care contează

Denumirile exacte, din capitolul II:

| Cod | Denumire |
|---|---|
| 331 | Corecţii ale rezultatelor anilor precedenţi |
| 332 | Profit nerepartizat (pierdere neacoperită) al anilor precedenţi |
| 333 | Profit net (pierdere netă) al perioadei de gestiune |
| 334 | Profit utilizat al perioadei de gestiune |
| 335 | Rezultat din tranziţia la noile reglementări contabile |
| 336 | Excedent net (deficit net) al perioadei de gestiune |
| 351 | Rezultat financiar total |

**Clasa 6 → 351** (capitolul III, CLASA 6):

> …iar în debit – **decontarea la finele perioadei de gestiune a veniturilor acumulate la rezultatul
> financiar total**.

**Clasa 7 → 351**, simetric. **731 → 351** explicit, în corespondență cu debitul conturilor **172,
351** etc.

**351 nu are sold:**

> **Contul 351 „Rezultat financiar total" la sfîrşitul perioadei de gestiune nu are sold.**

### Rafinarea 1 — „reformarea bilanțului" e trigger doar pentru două verigi

Actul numește *reformarea bilanţului* **exclusiv** pentru:

- **334 → 333**: „decontarea profitului utilizat **la reformarea bilanţului** în corespondenţă cu
  debitul contului 333";
- **335 → 332**: „**La reformarea bilanţului** soldul acestui cont se decontează la contul 332".

Pentru **333 ↔ 332** actul listează doar corespondența, în ambele sensuri. **Nu se codifică un
trigger pe care actul nu-l afirmă.**

### Rafinarea 2 — listele de corespondență sunt explicit neexhaustive

Fiecare listă se termină în „etc.", iar capitolul I le numește *principalele* conturi corespondente:

> În capitolul III sînt caracterizate clasele, grupele de conturi şi conturile de gradul I şi
> prezentate **principalele** conturi corespondente pe debitul şi creditul fiecărui cont sintetic.

**Consecință pentru `fiscal_parameter`:** datele derivate din aceste liste **nu se tratează ca
mulțime închisă**. O validare care ar refuza o corespondență fiindcă nu e în listă ar refuza ceva ce
actul permite.

## 3. Contul 336 — organizațiile necomerciale

Există, e explicit **pentru organizaţiile necomerciale**, și e analogul structural al lui 333.
Corespondenții lui sunt **341 „Fonduri"** și **351** — nu 332/334. Deci ramura necomercială e
`clasa 6/7 → 351 → 336 (↔ 341)`, distinctă de `→ 333 → 332`.

Introdus prin **Ordinul MF nr. 188 din 30.12.2014, în vigoare 01.01.2015**, același ordin care a
aprobat *Indicaţiile metodice privind particularităţile contabilităţii în organizaţiile
necomerciale* — actul care guvernează cum se determină soldul lui.

> **Inconsecvență în act, de consemnat ca atare, nu de reconciliat tăcut.** Lista de corespondență a
> contului **351 numește doar 333, niciodată 336**. OMF 188/2014 a inserat contul 336 fără să
> actualizeze lista lui 351. Legătura e purtată doar de textul propriu al lui 336 și de „etc."-ul
> final.

## 4. „Reformarea bilanțului" — actul nu o definește

Sintagma apare **exact de două ori în 63 de pagini**, ambele în capitolul III, ca trigger
neexplicat. **Nicio definiție, niciun eveniment declanșator, nicio periodicitate, nicio distincție
față de închiderea de exercițiu.** Capitolul I, unde stau regulile generale, nu o menționează deloc.

Actul trimite explicit în altă parte pentru vocabular:

> În Planul general de conturi contabile este utilizată terminologia din SNC şi alte acte normative
> contabile.

**Deci definiția trebuie luată din SNC, nu de aici — și nu de pe portaluri contabile.** Rămâne
deschisă.

## 5. Clasa 8 — confirmat, fără periodicitate

Afirmat de două ori identic, în capitolul I și în capitolul III:

> Conturile de gestiune sînt destinate generalizării informaţiei privind costurile de producţie,
> adaosul comercial (…) şi alte elemente contabile **cu caracter tranzitoriu**. **La data raportării
> conturile de gestiune se închid cu conturile de bilanţ şi/sau de rezultate.**

**Nicio periodicitate fixată nicăieri** — nici „anual", nici „lunar". Ceea ce confirmă tratarea lor
ca **invariant validat**, nu ca `event_type` de închidere.

| Grupa | Cod | Denumire |
|---|---|---|
| **81 Conturi de calculaţie** | 811 | Activităţi de bază |
| | 812 | Activităţi auxiliare |
| **82 Conturi de repartizare** | 821 | Costuri indirecte de producţie |
| | 822 | Costuri indirecte aferente contractelor de construcţie |
| | 823 | Costuri de regie aferente contractelor de construcţie |
| | 824 | Alte costuri repartizabile |
| **83 Alte conturi de gestiune** | 831 | Adaos comercial |
| | 832 | Încasări din vînzarea bunurilor în numerar |
| | 833 | Returnarea şi reducerea preţurilor la bunurile vîndute |
| | 834 | Costuri aferente bunurilor transmise spre prelucrare terţilor |
| | 835 | Producţii şi unităţi de deservire |
| | 836 | Costuri refacturate |

## 6. Obligatoriu versus recomandare — confirmat, plus o asimetrie

> **Conturile de gradul I din clasele 1-7 sînt obligatorii pentru toate entităţile, iar conturile de
> gradul I din clasele 8-9 şi conturile de gradul II din toate clasele au un caracter de
> recomandare** (…)
>
> **Entităţile pot să introducă conturi suplimentare de gradul II în clasele 1-7 şi conturi de
> gradul I şi II în clasele 8-9** (…) fără dublarea şi denaturarea Planului general de conturi
> contabile.

**Asimetria pe care ADR-036 §6.3 n-o numea:** nu există permisiune de a adăuga conturi de **gradul I
în clasele 1-7**. Extinderea e permisă doar la gradul II acolo, și la ambele grade în clasele 8-9.

Și clasificarea, utilă pentru validare:

> Clasele 1-5 cuprind conturile de bilanţ, clasele 6-7 – conturile de rezultate, clasa 8 – conturile
> de gestiune şi clasa 9 – conturile extrabilanţiere. (…) Conturile din clasele 1, 2, 7 şi 8 (cu
> excepţia conturilor rectificative) sînt conturi de **activ**, iar conturile din clasele 3-6 – de
> **pasiv**.

---

## Ce nu s-a putut verifica

1. **`legis.md` e blocat de Cloudflare (403)** pentru orice preluare automată. Registrul de stat
   **n-a fost citit**. Tot ce e mai sus vine din PDF-ul propriu al Ministerului Finanțelor — sursă
   primară, dar nu versiunea consolidată a registrului.
2. **Referința MO pentru anexă** (233-237/1534/22.10.2013) e citită din antetul actului, nu dintr-un
   facsimil al Monitorului. Cea pentru ordin (177-181/1225/16.08.2013) e mai bine susținută: apare
   în antet **și** e citată verbatim de Minister în propriul proiect de modificare.
3. **Ordinul MF nr. 111 din 13.09.2021 — modificare reală, necitită în sursă primară.** PDF-ul
   consolidat al MF a fost creat la 2020-05-20, iar ultima notă din el e nr. 100/2019. Proiectul a
   fost citit de pe MF și propune trei corecții de corespondență — conturile **143**, **254**, **316**
   — dar numărul, data, referința MO și data intrării în vigoare ale ordinului **adoptat** vin de pe
   un portal contabil, sursă secundară. **Nu atinge niciun cont sau regulă din cele de mai sus.**
4. **Lista de modificări nu poate fi certificată completă după septembrie 2021.** Listarea proprie a
   MF arată doar OMF 188/2014 și OMF 100/2019 ca modificatoare — deci e demonstrabil incompletă,
   fiindcă nu conține 111/2021.
5. **Actele românești contaminează căutarea.** Ordinele MFP 1802/2014, 2649/2023, 2202/2023 și
   conturi precum 1496 sunt din **România**. Niciunul nu apare mai sus, dar o căutare ulterioară le
   va scoate.
6. **Inconsecvențele de denumire — rafinate de extragerea completă** (vezi
   [`od-23-nomenclatorul-planului-de-conturi.md`](od-23-nomenclatorul-planului-de-conturi.md)).
   Cazul **920 e altfel decât s-a presupus aici inițial:** divergența **nu e între capitole**, ci
   **în interiorul capitolului III** — titlul secțiunii spune „Creanţe contingente", concordant cu
   nomenclatorul, iar doar textul narativ spune „Active contingente". Pentru un plan de lucru
   contează forma din nomenclator. Divergențe reale între capitole există însă la **12**, **31**,
   **112** și **132**, unde capitolul III a rămas cu denumirea anterioară redacției din 2019.
