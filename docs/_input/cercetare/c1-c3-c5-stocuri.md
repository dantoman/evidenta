# `C1`, `C3`, `C5` — SNC „Stocuri": text normativ citat

- **Data cercetării:** 2026-08-26
- **Sursa primară:** textul consolidat servit de Ministerul Finanțelor,
  <https://mf.gov.md/sites/default/files/legislatie/Standardele%20Na%C8%9Bionale%20de%20Contabilitate%20aprobate%20prin%20ordinul%20nr.%20118%20din%2006.08.2013.pdf>
  (263 pagini, consolidat până la **Ordinul MF nr. 73 din 10.06.2022**; antet oficial
  MO nr. 233-237 art. 1534 din 22.10.2013)
- **Verificare încrucișată a bazei din 2013:** <https://monitorul.fisc.md/upload/library/files/2015/02/m3zpc5jkrl.pdf>
- **Alimentează:** ADR-036 §11 (`C1`, `C3`, `C5`)

> **Textul din 2013 e depășit, iar diferența nu e cosmetică.** A doua oară în aceeași sesiune când
> un agent găsește asta independent — vezi și `c4-diferente-de-curs.md`, unde OMF 48/2019 a rescris
> exact punctele care decid ce se reevaluează. **Ordinul MF nr. 48 din 12.03.2019, în vigoare
> 01.01.2020**, a modificat și SNC „Stocuri" în două locuri care schimbă implementarea.

---

## `C1` — Metoda de evaluare la ieșire

### Sunt patru metode, nu trei. LIFO a fost reintrodusă.

**Punctul 33**, în redacția din 2019:

> Stocurile ieşite se evaluează la valoarea contabilă care se determină prin aplicarea **uneia din
> următoarele** metode de evaluare curentă:
> 1) metoda identificării specifice;
> 2) metoda FIFO (primul intrat – primul ieşit);
> 3) metoda costului mediu ponderat;
> 4) **metoda LIFO (ultimul intrat – primul ieşit)**.
>
> *[Pct. 33 modificat prin Ordinul MF nr. 48 din 12.03.2019, în vigoare 01.01.2020]*

Și **punctul 37¹**, introdus prin același ordin, descrie mecanica LIFO și recomandă folosirea ei
„în cazul în care preţurile stocurilor ieşite înregistrează o creştere permanentă". Anexa 3¹ conține
un exemplu numeric complet — coroborare internă că nu e artefact de extragere.

> **Este o divergență deliberată față de IAS 2**, care interzice LIFO, deși pct. 1 al standardului
> își declară derivarea din IAS 2. Merită scris în ADR: cine aduce așteptări din IFRS va presupune
> că LIFO e interzisă.

Lista rămâne **închisă** — „uneia din următoarele".

### Momentul calculului: da, e alegere de politică — și pentru CMP e listă deschisă

**Punctul 36**, FIFO:

> valoarea stocurilor ieşite poate fi determinată **după fiecare ieşire** sau **în baza soldului
> final, stabilit în urma inventarierii**.

**Punctul 37**, cost mediu ponderat:

> Costul mediu ponderat poate fi calculat **după fiecare intrare** a stocurilor, **la sfîrşitul
> perioadei de gestiune** sau **în alt mod stabilit de politicile contabile ale entităţii**.

„Sau în alt mod" înseamnă că mulțimea momentelor pentru CMP **nu e închisă**. Un sistem nu o poate
enumera exhaustiv — spre deosebire de lista metodelor.

### A treia axă are două metode, nu trei

**Punctul 39**, în redacția din 2019:

> Conform politicilor contabile, în funcţie de specificul activităţii, pentru evaluarea stocurilor
> în cursul perioadei de gestiune entitatea poate utiliza următoarele metode:
> 1) metoda costului standard;
> 2) metoda preţului cu amănuntul.
>
> *[Pct. 39 modificat prin Ordinul MF nr. 48 din 12.03.2019, în vigoare 01.01.2020]*

**`cost efectiv de intrare` nu e o metodă de la pct. 39.** Este regula de recunoaștere de bază, de
la pct. 13. Cine o pune ca a treia opțiune într-un ecran de politici oferă o alegere care nu există.

**Modificare subtilă și purtătoare de consecință:** textul din 2013 spunea „poate utiliza **una
din** următoarele metode". Cuvintele „una din" au fost **șterse** în 2019. Entitatea poate aplica
acum **ambele concomitent**, pe categorii diferite de stocuri.

### A patra axă, pe care n-o avea nimeni: granularitatea

**Punctul 34:**

> Entitatea trebuie să utilizeze aceleaşi metode de evaluare curentă pentru **toate stocurile care
> au conţinut economic şi utilizare similare**. Pentru stocurile cu conţinut economic sau cu
> utilizare diferită **pot fi aplicate metode diferite**.

Metoda se alege **per clasă de stocuri similare**, nu per entitate. Ecranul de politici nu poate fi
un singur selector.

### Consecvența — punctul 38

> Metoda de evaluare curentă a stocurilor **trebuie aplicată cu consecvenţă**, pentru elemente
> similare de la o perioadă de gestiune la alta. Dacă în situaţii excepţionale entitatea decide să
> modifice metoda (…) în notele la situaţiile financiare este necesar de prezentat motivul
> modificării şi efectele acesteia asupra rezultatului financiar.

---

## `C3` — Costurile de transport-aprovizionare: **nu e politică**

**Punctul 15:**

> Costurile de intrare a stocurilor achiziţionate **cuprinde** valoarea de cumpărare şi costurile
> direct atribuibile intrării (de exemplu, **costurile de transportare-aprovizionare**, asigurare
> pe durata transportării, încărcare, descărcare, comisioane intermediarilor, impozitele şi taxele
> nerecuperabile, taxele vamale…).

Verbul e **„cuprinde"** — declarativ, nu permisiv. Fără „poate", fără clauză alternativă.

**Cât de exhaustiv s-a căutat**, fiindcă punctul era decisiv:

- „transportare-aprovizionare" apare **exact o dată în 263 de pagini** — chiar aici, la pct. 15;
- **pct. 14**, lista excluderilor, nu le menționează;
- în **Planul general de conturi** (Ordin nr. 119/2013, 63 pagini) **nu există niciun cont separat**
  de costuri de transport-aprovizionare. Moldova nu are analogul practicii românești cu cont
  distinct și repartizare prin coeficient la sfârșit de lună.

**Concluzie: `C3` dispare ca element separat.** Ipoteza din ADR-036 — „două tratamente permise" —
era greșită. Ce se confundase e mecanica **metodei costului standard** (pct. 40), unde diferențele
de preț se reflectă distinct și se repartizează conform politicilor contabile — deci se absoarbe în
`C1`, axa a treia.

---

## `C5` — Costurile indirecte de producție: un handler, nu variante

**Punctul 29** — două etape, obligatorii:

> 1) repartizarea costurilor între costul produselor/serviciilor/producţiei în curs de execuţie şi
> cheltuielile curente; 2) repartizarea costurilor pe tipuri de produse fabricate/servicii prestate.

**Punctul 30(1)** — variabile, absorbite integral:

> se includ în costul produselor fabricate (…) **în suma totală, indiferent de gradul de utilizare
> a capacităţilor de producţie**.

**Punctul 30(2)** — constante, cu formula de subabsorbție scrisă în standard:

> …se repartizează (…) **în baza capacităţii normale de producţie**, care reprezintă volumul
> producţiei ce poate fi realizat, în medie, pe parcursul a cîteva perioade de gestiune sau sezoane
> în condiţii normale, ţinînd cont de pierderile capacităţii cauzate de reparaţiile planificate.
> Dacă volumul efectiv este egal sau depăşeşte capacitatea normală, suma efectivă se include
> **integral**. În cazul în care volumul efectiv este mai mic, costurile constante se includ **în
> baza cotei** calculate ca raportul dintre volumul efectiv şi capacitatea normală. **Suma rămasă
> se consideră drept cheltuieli curente.**

**Punctul 31** — baza de repartizare, **listă deschisă**:

> …proporţional cu baza stabilită în politicile contabile ale entităţii (**de exemplu**,
> proporţional salariilor de bază ale muncitorilor (…), sumei totale a costurilor directe de
> producţie, numărului de maşini-ore lucrate, cantităţii de produse fabricate).

**„De exemplu" e decisiv.** Cele patru baze sunt ilustrative. Singura cerință obligatorie e ca baza
să fie fixată în politicile contabile.

> **Contrastul cu pct. 33 e chiar granița pe care ADR-036 §10.1 o prezicea.** Metoda de evaluare e
> listă **închisă** — se enumeră în cod. Baza de repartizare e listă **deschisă** — tenantul o
> definește liber, fiindcă e o cantitate care intră în calcul, nu o structură de postare.
> Prima confirmare practică a testului de falsificare, și confirmă granița.

Exemplu numeric în Anexa 1.

---

## Ce nu s-a putut verifica

- **A doua copie independentă a textului consolidat.** `legis.md` întoarce 403 la preluare
  automată. Sursa e PDF-ul propriu al Ministerului Finanțelor, cu adnotări de modificare inline și
  antet oficial — sursă primară. Baza din 2013 a fost coroborată cu o a doua copie independentă.
- **Textul Ordinului nr. 48/2019 însuși.** S-a citit doar rezultatul consolidat și adnotările lui,
  nu ordinul modificator. O sursă secundară (`contabilsef.md`) e consistentă cu schimbarea, dar e
  semnalată ca secundară.
- **Modificări după 2022.** Cel mai nou ordin din consolidare e nr. 73 din 10.06.2022. Nu s-a putut
  verifica dacă a mai apărut ceva între timp, nici când a fost republicat PDF-ul.
- **„Indicaţii metodice privind contabilitatea costurilor de producţie şi calculaţia costului"** —
  document listat sub Ordinul 118, posibil inclus în cele 263 de pagini căutate, dar limitele lui
  n-au fost confirmate. O prevedere despre CTA acolo **nu e complet exclusă**.
- **Niciun citat de mai sus nu provine din comentarii sau bloguri.** Toate sunt transcrise din PDF-ul
  Ministerului Finanțelor.
