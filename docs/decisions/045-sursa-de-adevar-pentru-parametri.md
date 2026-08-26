# ADR-045 — Actul de rang legal dă parametrii; regulamentul dă procedura

- **Status:** Acceptat — decizie de domeniu, luată de proprietar (contabil practicant)
- **Data:** 2026-08-26
- **Afectează:** `R15`, `C14`, corpusul de regresie fiscală, încărcarea lui `fiscal_parameter`
- **Legate:** [ADR-044](044-data-de-rezolutie.md), `docs/_input/cercetare/od-22-impozitul-pe-venit.md`,
  `OD-22`

## 1. Defectul, găsit în act, nu presupus

**HG nr. 697/2014** — regulamentul de reținere a impozitului pe venit din salariu, actul pe care îl
citește oricine implementează calculul salarial — prevede la **pct. 11** că persoana aflată în relații
de căsătorie are dreptul la scutire suplimentară **„în mărimea indicatorului prevăzut la art. 34 alin.
(1) sau (2)"**, cu condiția ca soțul să nu beneficieze de scutire personală.

Dar **scutirea din art. 34 alin. (1) nu se acordă.** Serviciul Fiscal de Stat o codifică `x` în
propriile tabele de scutiri, de ani. Există **doar** cea din alin. (2), condiționată de calitatea
soțului sau a soției de persoană din categoriile art. 33 alin. (2) — Cernobîl, dizabilitate, veteran,
pensionar-victimă a represiunilor politice.

**Textul de rang inferior a rămas în urma Codului fiscal.** Nu e o greșeală de redactare izolată: e
comportamentul normal al unui sistem de acte cu ranguri diferite, unde modificarea legii nu antrenează
automat rescrierea hotărârilor de aplicare.

## 2. Regula

> **Sursa de adevăr pentru parametri este actul de rang legal.** Codul fiscal pentru impozite, Legea
> nr. 489/1999 pentru contribuțiile sociale, Legea nr. 1593/2002 pentru primele medicale.
>
> **Regulamentele — hotărâri de Guvern, ordine ministeriale — se folosesc doar pentru procedură.**
> Niciodată pentru **cuantumuri** și niciodată pentru **drepturi**.

Procedura pe care regulamentele chiar o guvernează, și pe care nimic din regula asta nu o slăbește:
formularele și anexele lor, termenele de depunere, ordinea pașilor, metoda de calcul cumulativ, ce
document depune angajatul. Din aceeași HG 697/2014, **pct. 12** e un exemplu bun de procedură care
obligă: suma scutirilor anuale **se transmite în cuantum întreg, fără a fi divizată între soți** — nu e
proporțională. Aia e regulă de aplicare, și se respectă.

## 3. De ce nu se impune în schemă

Tentația evidentă e un `CHECK` pe `fiscal_parameter_source.act_type`, care să refuze o sursă de tip
„hotărâre" sau „ordin". **Nu ține, și se vede pe două cazuri deja în proiect:**

- **Planul general de conturi vine din Ordinul MF nr. 119 din 06.08.2013** — un ordin. Iar `R15`
  enumeră explicit **mapările de conturi** printre parametrii fiscali. O mapare de conturi cu sursă
  „ordin" este perfect legitimă.
- **Cotele CNAS și CNAM stau în anexe la Legea nr. 489/1999 și Legea nr. 1593/2002**, nu în Codul
  fiscal. Un `CHECK` pe „doar Codul fiscal" le-ar refuza pe amândouă.

Regula e mai fină decât „ce act": e despre **ce fel de parametru** — cuantumuri și drepturi pe de o
parte, procedură și mapări pe de alta. Iar `fiscal_parameter` **nu are coloana aceea**. Are
`parameter_key` și `value_type`, iar `value_type` descrie **forma valorii** (`money`, `percentage`,
`table`), nu natura ei juridică.

Deci ori se adaugă modelului o dimensiune nouă — **și atunci merită o decizie proprie, nu un efect
secundar al acesteia** — ori regula stă unde e pusă la §4.

## 4. Cum se impune: prin corpusul de regresie

`C14` cere corpusul de regresie fiscală rulat la fiecare modificare de parametru sau de algoritm.
**Acolo se vede efectul, și de-aia e locul potrivit:** cineva care „corectează" motorul după HG
697/2014 și reintroduce scutirea de soț/soție care nu se acordă produce un **rezultat greșit**, iar
corpusul îl prinde ca atare — nu ca sursă greșită, ci ca număr greșit, care e chiar ce contează.

Un caz din corpus trebuie deci să conțină **un contribuabil căsătorit al cărui soț nu beneficiază de
scutire personală și nu este din categoriile art. 33 alin. (2)** — cazul în care HG 697 pct. 11 sugerează
o scutire, iar Codul nu o dă. Rezultatul așteptat: **fără scutire de soț/soție.**

## 5. Ce mai apără regula, dincolo de cazul care a produs-o

Aceeași căutare a scos două constatări care ating direct modelul, ambele din categoria „ar fi produs
calcule plauzibile și greșite":

- **Unicitatea nu există.** Numărul de contribuabili care pot folosi scutirea pentru **aceeași** persoană
  întreținută **nu e limitat prin lege**: ambii părinți pot folosi scutirea pentru același copil, toți
  copiii pentru același părinte. **O constrângere `UNIQUE` acolo ar fi invenția noastră, nu o cerință
  legală** — genul de constrângere care arată a igienă de schemă și e de fapt o regulă de business
  inventată, care refuză un caz permis fără ca utilizatorul să poată afla de ce.
- **Excluderea din baza de calcul.** La determinarea venitului persoanei întreținute intră veniturile
  impozabile **și** neimpozabile, din RM și din afară — **cu excepția alocațiilor din bugetul de stat**
  pentru dizabilități congenitale sau din copilărie și pentru cele severe și accentuate. Un motor care
  însumează tot venitul **ar respinge exact categoria pentru care scutirea e majorată**: ar refuza
  21 780 lei tocmai persoanei îndreptățite la ei, fiindcă alocația de stat o împinge peste plafonul de
  **12 400 lei** (2025).

Ambele sunt reguli pe care **numai actul le spune**, și pe care un implementator care citește
regulamentul sau interfața SFS nu le-ar deduce.

## 6. Ce nu decide acest ADR

**Nu decide cum se marchează natura juridică a unui parametru** — vezi §3. Dacă modelul primește
vreodată dimensiunea aceea, e o decizie proprie, cu propriul ADR.

**Nu spune că regulamentele sunt neîncrezătoare.** Spune că au altă competență. HG 697/2014 rămâne
sursa obligatorie pentru forma cererii, pentru termenul de 10 zile la schimbarea scutirilor, pentru
metoda cumulativă și pentru fișa personală de evidență.
