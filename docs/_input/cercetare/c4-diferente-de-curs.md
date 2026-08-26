# `C4` — Diferențe de curs valutar și de sumă: text normativ citat

- **Data cercetării:** 2026-08-26
- **Sursa primară:** SNC „Diferențe de curs valutar și de sumă", în textul consolidat servit de
  Ministerul Finanțelor: <https://mf.gov.md/sites/default/files/legislatie/SNC%20ordin%20MF%20118.pdf>
- **Consolidat până la:** Ordinul MF nr. 48 din 12.03.2019, **în vigoare 01.01.2020**
- **Alimentează:** ADR-036 §11 (`C4`), și — neintenționat — **`OD-22`**

> **Avertisment de versiune, și contează.** Circulă două texte materialmente diferite. `old.mf.gov.md`
> servește varianta consolidată doar până la OMF 204/23.12.2015. Textul curent a fost rescris de
> **OMF nr. 48 din 12.03.2019**, care a modificat punctele 1, 3, 11, 12, 14¹, 28 și a abrogat 5(4)
> și 16. **Punctele 11 și 12 sunt exact cele care decid ce se reevaluează** — deci cine citește
> varianta veche implementează altceva.

---

## 1. Cele două noțiuni nu se disting prin aritmetică

**Punctul 4:**

> **Diferenţă de curs valutar** – diferenţă care rezultă din recalcularea valutei străine în monedă
> naţională la diferite cursuri oficiale ale leului moldovenesc.
>
> **Diferenţă de sumă** – diferenţă care rezultă din recalcularea creanţelor şi datoriilor exprimate
> în valută străină sau unităţi convenţionale la diferite cursuri oficiale ale leului moldovenesc
> **sau cursuri de schimb stabilite în contractele încheiate între rezidenţii Republicii Moldova**.

**Punctul 17** confirmă restrângerea la rezidenți:

> Diferenţele de sumă apar în cazul încheierii **între rezidenţii Republicii Moldova** a contractelor
> în care părţile au convenit asupra unor datorii pecuniare exprimate în valută străină sau unităţi
> convenţionale.

Discriminatorul e **contrapartea și admisibilitatea unui curs contractual**, nu formula. Aceeași
înmulțire produce concepte contabile diferite după cine sunt părțile.

## 2. Constatarea structurală cea mai importantă

**Diferențele de curs se reevaluează la data raportării. Diferențele de sumă — nu.**

**Punctul 22:**

> La data raportării creanţele şi datoriile aferente operaţiunilor exprimate în valută străină sau
> unităţi convenţionale **nu se supun recalculării**.

**Punctul 23:**

> …echivalentul în moneda naţională a avansului se determină prin aplicarea cursului de schimb la
> data plăţii acestuia şi **ulterior nu se recalculează**.

**Consecință de proiectare:** un singur job „reevaluează soldurile în valută" care ar atinge și
contractele în unități convenționale între rezidenți **produce înregistrări neconforme**. Sunt două
mecanisme, nu unul parametrizat.

## 3. Ce se reevaluează, în textul de după 2020

**Punctul 11** — elemente monetare, recalculate:

> numerarul, creanţele şi datoriile, **cu excepţia avansurilor acordate şi primite** pentru
> procurări/livrări de active şi servicii, investiţiile financiare, **cu excepţia acţiunilor şi
> cotelor părţi**
> *[în redacţia Ordinului MF nr.48 din 12.03.2019, în vigoare 01.01.2020]*

**Punctul 12** — elemente nemonetare, **nu** se recalculează:

> imobilizările necorporale şi corporale, goodwill-ul, stocurile, **avansurile acordate/primite**,
> elementele de capital propriu
> *[în redacţia aceluiaşi ordin]*

**Amendamentul din 2020 a mutat avansurile de pe partea monetară pe cea nemonetară.** Cine
implementează după textul din 2015 reevaluează avansuri care nu trebuie reevaluate.

Momentele de măsurare sunt trei (**pct. 6**): înregistrarea inițială, achitarea integrală sau
parțială, și data raportării. Realizate la decontare (**pct. 8**), nerealizate la raportare
(**pct. 14**), recunoscute în fiecare perioadă până la achitare (**pct. 15**).

## 4. Nu e „fără alternativă" — sunt trei puncte de variabilitate

Ipoteza din ADR-036 spunea „tratament determinat de lege, fără alternativă". **Recunoașterea** chiar
e determinată — favorabile la venituri, nefavorabile la cheltuieli, fără alegere. Dar:

| Punct | Ce variază | Unde trăiește |
|---|---|---|
| **pct. 13** | Periodicitatea reevaluării: „la data raportării, cît şi cu o altă periodicitate prevăzută în politicile contabile (lunar, trimestrial etc.)" | **Politică contabilă** — stratul 3 |
| **pct. 19** | Cursul aplicat la achitare: la data achitării, la data livrării, sau stabilit de părți în mărime fixă | **Termen contractual** — pe document, nu pe tenant |
| **pct. 14¹** | Instituțiile publice cu autonomie financiară: diferențele aferente subvențiilor se recunosc ca majorare/diminuare a subvențiilor | **Derogare obligatorie**, după tipul entității |

**Punctul 21** are o consecință pe care handlerul trebuie s-o știe:

> În cazul aplicării cursului de schimb la data livrării activelor sau a unui curs stabilit de părţi
> în mărime fixă, **diferenţe de sumă nu apar**, deoarece vînzătorul şi cumpărătorul recunosc
> creanţele şi datoriile în baza aceluiaşi curs de schimb.

Deci alegerea contractuală din pct. 19 poate face ca diferența să **nu existe deloc** — nu e o
variantă de calcul, e o ramură care nu produce nicio postare.

## 5. Conturile — toate patru confirmate, plus o a treia pereche

Din **Planul general de conturi contabile**, aprobat prin **Ordinul MF nr. 119 din 06.08.2013**:
<https://mf.gov.md/sites/default/files/legislatie/Planul%20general%20de%20conturi%20contabile.pdf>

| Cont | Denumire | Ce e |
|---|---|---|
| **6226** | Venituri din diferenţe de curs valutar | curs, venit |
| **6227** | Venituri din diferenţe de sumă | sumă, venit |
| **7224** | Cheltuieli din diferenţe de curs valutar | curs, cheltuială |
| **7225** | Cheltuieli din diferenţe de sumă | sumă, cheltuială |

**A treia pereche, pe care n-o avea nimeni** — ecartul dintre cursul oficial BNM și cursul efectiv
de cumpărare-vânzare al băncii, care stă în rezultatul **operațional**, nu în cel financiar:

| Cont | Denumire |
|---|---|
| **6127** | Venituri aferente diferenţelor favorabile dintre cursul oficial al BNM şi cursul de cumpărare-vînzare a valutei străine |
| **7147** | Cheltuieli aferente diferenţelor nefavorabile dintre cursul oficial al BNM şi cursul de cumpărare-vînzare a valutei străine |

**Trei concepte, nu două**, iar 6127/7147 aterizează în altă secțiune a contului de profit și
pierdere decât 6226/7224.

> **În Moldova, clasa 6 e venituri și clasa 7 e cheltuieli** — invers față de convenția din România.
> Merită scris, fiindcă e genul de presupunere pe care o aduce cineva din afară.

## 6. Standardul tace despre fiscalitate

Căutat în textul integral după `fiscal`, `impozit`, `Codul fiscal`, `TVA`: singura apariție e o
paranteză într-un exemplu. **Niciun articol despre divergență contabil-fiscal, nicio trimitere la
Codul fiscal, nicio prevedere de impozit amânat.** Singurul indicator „aici se aplică alte reguli"
e **pct. 27**, și trimite la alt SNC, nu la fiscalitate.

## Ce nu s-a putut verifica

- **Tratamentul din Codul fiscal.** Un rezultat de căutare susține `art. 21 alin. (3³)`. Textul
  primar **nu a fost citit** — `legis.md` întoarce 403 la preluare automată. Numărul de articol
  rămâne **neverificat**. Ce s-a verificat direct e doar că *standardul* tace.
- **Dacă OMF 48/2019 e ultima modificare.** PDF-ul servit de MF e consolidat până acolo și nu s-a
  găsit ceva mai nou, dar registrul oficial consolidat a blocat preluarea. „Curent la 2026" e
  **dedus** din faptul că e fișierul pe care MF îl servește, nu confirmat.
- **Anexa 1** — „Modul de contabilizare a diferenţelor de curs valutar la data raportării". E
  autoritatea standardului asupra liniilor de bilanț care se reevaluează. **De extras integral
  înainte de a specifica handlerul de reevaluare.**
- **Punctul 14** menționează „acţiunilor evaluate la valoarea justă", iar pct. 11 — modificat în
  2020 — exclude acțiunile de la reevaluare. Cele două interacționează și formularea pct. 14 n-a
  putut fi datată. **De verificat punctual** înainte de a implementa valuta pe investiții financiare.
