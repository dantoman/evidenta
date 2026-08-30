# ADR-070 — Trei feluri, nu o familie: unde e al doilea operand

- **Status:** **Acceptat** — decizie de proces și de proiectare, a proprietarului, sub
  [ADR-002](002-guvernanta-deciziilor.md)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Restrânge:** `OD-86`
- **Afectează:** `fiscal/parameters` (`valid_from` și citarea), `F2.B1`, `F2.B2`, `OD-92`
- **Legate:** [ADR-069](069-persoana-asigurata-nu-e-angajatul.md),
  [ADR-068](068-anexa-citita-categoria-e-a-raportului.md) §8.4,
  [ADR-059](059-linia-poarta-data-inregistrarii.md)

> **REZERVĂ NEATINSĂ (`OD-85`):** acest ADR e despre metodă şi despre unde stau operanzii — nu afirmă
> nicio valoare din anexa nr. 1 la Legea nr. 489/1999. Pragul de 70% apare doar ca **exemplu al
> distincţiei valoare/margine**, nu ca valoare afirmată.
>
> **Notă de reconciliere:** referinţele proprietarului la `§4`, `§6` şi `§6.5` sunt la
> `CONTEXT-evidenta.md`, **care nu există în acest repository**. Conţinutul lor e consemnat aici, în
> §4 şi §6; dacă documentul acela e ţinut în altă parte, cele două se reconciliază, nu se dublează.

## 1. Gruparea era greșită, și greșeala e instructivă

Sesiunea a numit patru defecte „aceeași familie: defectul e perfect consistent cu tot ce verificăm".
**Erau grupate după *cum au fost găsite* — toate la revizie — nu după ce sunt.**

Testul care le desparte: **unde e al doilea operand?**

| Defect | Al doilea operand | Ce a lipsit |
|---|---|---|
| Marginea fabricată (`valid_from` din data redacţiei) | **nu există în sistem** — articolul final al legii modificatoare e în afara lui | operandul |
| Domeniul invariantului art. 22 | **nu există** — invariantul n-are câmp de domeniu, iar „baza" nu poartă tipul raportului | operandul |
| Declaraţia construită din angajaţi | **amândoi există** — sarcinile CAS şi rândurile nominale sunt în bază | **întrebarea** |
| ADR ↔ date încărcate (`OD-86`) | amândoi există, întrebarea e pusă | **comparaţia**, care nu se face |

**Trei feluri, cu trei răspunsuri diferite.** Un singur mecanism pentru toate ar fi fost construit
pentru cel greşit.

## 2. Ce se face cu fiecare

1. **Operand lipsă → nu se prinde, se face imposibil de scris.** §3.
2. **Întrebare nepusă → se pune.** O reconciliere obişnuită, fără nicio structură nouă. §5.
3. **Comparaţie pusă şi nefăcută → mecanismul `OD-86`**, nivelul 1. Şi **doar** aceasta.

## 3. Două impuneri structurale, amândouă fără implicit

**Nu se construiesc gardieni pentru primele două.** Un gardian care poate fi construit poate fi
dezactivat; **o coloană obligatorie nu.**

- **`valid_from` primeşte câmp de citare obligatoriu — actul şi articolul care fixează marginea.**
  **Măsurat, golul e mai precis decât părea:** `fiscal_parameter.act` există, dar docstring-ul lui îl
  defineşte ca *actul din registru* din care vine **valoarea**. Marginea poate veni din **alt act** —
  exemplul viu: pragul de 70% se citeşte în redacţia LP318, dar marginea lui stă în articolul final al
  LP187/2025. **Un singur slot de citare acolo unde sunt necesare două**, iar cel existent e ocupat de
  celălalt înţeles. Forma exactă a celui de-al doilea e `OD-92`.
- **Invariantul primeşte câmp de domeniu obligatoriu — tipul raportului.** Art. 22 e al raportului de
  muncă; „baza CAS" nu poartă tipul, deci nu există ce compara.

**Două rafinări ale proprietarului, amândouă îngustând ce poate fi scris greşit:**

1. **Nu ca fază separată — primul commit din `F2.B1`.** Două sloturi de citare proiectate în vid, cu
   zero consumatori, sunt propria familie de defecte: **o schemă validată de nimic.** `F2.B1` are
   consumatori reali imediat — clauzele art. 49, câmpurile ordinului, domeniul invariantului art. 22.
   **Coloanele întâi, dar primul lucru scris după ele trebuie să le exercite pe amândouă.**
2. **Domeniul invariantului e cheie străină, nu enumerare liberă.** Cu şir sau enum deschis, cineva
   scrie `orice_bază_CAS` şi defectul e înapoi — vizibil, dar înapoi. Cu **referinţă spre tipurile de
   raport care există deja în model** (contract de muncă, contract civil), un domeniu inexistent e
   **violare de cheie străină**, nu o valoare acceptată. Nu elimină reziduul — cineva încă poate alege
   greşit dintre două tipuri reale — dar îngustează de la *„orice şir"* la *„un tip care există"*, şi
   **atât poate face structura** (§4).

**De ce fără implicit, şi de ce nu e o preferinţă:** *implicitul rezonabil e cea mai bună deghizare a
unei alegeri netăcute.* **Argumentul e deja scris în acest repo, măsurat**, pe
`fiscal_parameter.source_confidence`:

> *„parameters are loaded through the privileged SQL paths, and whoever loads a rate should have to
> say whether it was read in the act. **A default would let the row arrive without anyone
> deciding.**"*

Acolo, implicitul e aplicat în Python şi **migrarea îl scoate din bază**, tocmai ca un `INSERT` brut
care omite coloana să cadă. Acelaşi tipar, al treilea caz.

## 4. Plafonul: structura **nu** ia decizia

**Dacă invariantul primeşte câmp de domeniu şi cineva scrie `domeniu = orice_bază_CAS`, defectul e
înapoi.** Structura nu împiedică alegerea greşită.

Ce face structura e altceva, şi e suficient: **mută decizia din tăcere într-un diff.**

- Un domeniu **greşit** se citeşte, se caută, apare la revizie.
- Un domeniu **inexistent** nu apare nicăieri.

Reziduul rămâne al reviziei — dar e *„a ales greşit"*, nu *„n-a ales"*. Prima se prinde citind; a doua
nu are ce fi citit.

> **„Mecanizabil" are două înţelesuri, şi doar unul e pe masă:** *detectabil automat* — da, 3 din 4;
> *imposibil de greşit* — nu, niciunul. Sesiunea le confundase când a întrebat dacă familia e
> mecanizabilă.

### 4.1 Domeniul regulii de dovadă — lărgit, nu dublat

Regula practicată până acum era *„dovedeşte că gardianul poate cădea"*. **Domeniul ei e mai larg
decât gardienii:**

> **Orice mecanism care produce încredere trebuie dovedit căzând — gardian, remediu, aserţiune,
> generator.**

**Motivul, şi e mai general decât cazul care l-a scos la iveală:** un remediu instalat, un gardian
crezut dar netestat, chiar şi un rând de registru care numeşte problema — **orice lucru care creează
senzaţia că problema e tratată opreşte măsurarea.** De aceea cerinţa de dovadă e cea mai mare exact
**acolo unde se produce încrederea**, nu acolo unde riscul tehnic pare mai mare.

**Cele două cazuri care au produs lărgirea, amândouă din 2026-08-30:**

- **Un remediu fals.** Poarta raporta verde pentru roşu; sesiunea a diagnosticat greşit şi a propus
  *„rulez poarta pe bucăţi"*, care **nu repara nimic** — `make typecheck | tail` întoarce 0 şi singur.
  Un diagnostic greşit se repară când cineva măsoară; **un remediu fals se instalează şi opreşte
  măsurarea**, lăsând în urmă încredere în plus. Dovada că poate cădea a arătat asta în două comenzi.
- **Un generator neverificat.** Lista „stare nedovedită" a fost comparată cu una manuală şi a ieşit
  *„zero diferenţă"* — dar lista manuală îl conţinea pe al doilea membru **doar fiindcă mecanismul cu
  care se compara îl găsise cu o zi înainte**. **O comparaţie între două surse dintre care una derivă
  din cealaltă nu e o verificare** — arată exact ca un acord independent. Falsificat separat, cu o
  migrare-sondă care scrie date în afara uşii: generatorul o vede.

## 5. Reconcilierea, de scris acum

**Al patrulea test numit al lui `F2.B1`**, şi singurul dintre cele patru defecte care se prinde **fără
să se construiască nimic**:

> **Orice persoană cu sarcină CAS în perioada `P` apare ca rând nominal în declaraţia `P` — şi
> invers.**

**Reciproca contează la fel de mult:** un rând nominal fără sarcină e tot un defect. Se scrie azi, pe
date reale, fără structură nouă.

**De ce n-a fost scrisă:** populaţia se numea *„angajaţi"* şi părea evident completă. Nimeni n-a cerut
verificatorul, fiindcă domeniul lui părea trivial.

## 6. Forma a zecea, pentru taxonomia din `CONTEXT-evidenta.md` §6

> **„Un gardian care n-a fost pus fiindcă domeniul lui părea trivial."**

**Distinctă de „un verificator care nu poate cădea".** Acolo, verificatorul există şi nu funcţionează.
Aici, **verificatorul ar fi căzut corect din prima — nimeni nu l-a scris.** Formele 1–9 sunt despre
gardieni care există şi nu funcţionează; a zecea e despre unul care funcţiona şi n-a fost cerut.

## 7. `OD-86` se restrânge

Din cele patru instanţe, **una singură** e în domeniul lui. Nu se extinde ca să le acopere pe toate:
două nu sunt probleme de comparaţie, iar a treia e o reconciliere obişnuită care n-are nevoie de
mecanismul lui.

## 8. Predicţia, ca să poată fi infirmată

> **A cincea instanţă a familiei trebuie să se descompună la fel: operand lipsă, întrebare nepusă, sau
> comparaţie pusă şi nefăcută.**

**Dacă apare una care nu intră în niciuna, reformularea e greşită, nu incompletă** — şi se rescrie, nu
se extinde cu o a patra categorie. Consemnată aici ca predicţie datată, 2026-08-30, exact ca să aibă
ce infirma.

### 8.1 Patru instanţe în aceeaşi zi, **niciuna căutată**, câte una pe fiecare categorie

| Instanţa | Categoria | Cum a fost găsită |
|---|---|---|
| Clauza de excludere de la pct. 1.9 **există** — demonstraţia sesiunii era falsă | **comparaţie nefăcută** | căutând tabelul de cote |
| Formularul IALS21 şi instrucţiunile lui definesc **nouă din şaisprezece** coloane diferit | **întrebare nepusă** | căutând valorile lui `P` |
| Backfill-ul a parcurs zero rânduri şi **a raportat succes** | **operand lipsă** | rulând migrarea |
| Un act citat care nu e nici pe lista celor obţinute, nici pe a celor neobţinute | **întrebare nepusă** | citind |

**Fiecare dintre cele trei categorii a primit o instanţă independentă, într-o singură zi, şi niciuna
n-a fost căutată.** Prima confirmare a predicţiei era slabă — o găsisem în timp ce scriam predicţia,
deci o căutam. Acestea nu.

### 8.2 Ce ar infirma-o de aici înainte, scris ca să fie recunoscut

> **Un defect consistent cu tot ce verificăm, în care ambii operanzi EXISTĂ, întrebarea E pusă,
> comparaţia E făcută — şi tot trece.**

Dacă apare, reformularea e **greşită, nu incompletă**.

## 8bis. Testul de enumerare, rulat — şi ce a găsit în loc

Proprietarul a cerut, înainte de orice renumerotare: **enumeră membrii fiecărei familii; dacă
extensiunile coincid, e o familie cu două nume, şi numerotarea din `PROGRESS.md` are prioritate.**

**Testul nu se poate încheia, şi motivul e el însuşi constatarea: niciuna dintre familii nu are
listă. Toate au numărător.**

Ce s-a găsit căutând în repo:

| Familie | Numărătoare atinsă | Membri identificabili prin căutare |
|---|---|---|
| „proprietate presupusă în amonte, neimpusă în schemă, consumator în aval care se sparge tăcut" | **a zecea** (scara sumei, ADR-059) | ~3: scara sumei; `default=0` pe `decimal_places`; semnul cumulativelor (ADR-061 §2) |
| „legat şi nepornit" | **a şasea** (ADR-049) | 1 |
| „trece fiindcă nimic nu strigă" | **a noua** — şi **nu e în repo**, e în memoria sesiunii | ~5: colaţia, fusul orar, starea divergentă de migrări, calea neatinsă, `git commit -- <căi>` |

**Trei numărătoare, nu două** — a doua, „legat şi nepornit", nu fusese numită de niciunul dintre noi
în discuţia asta. Şi una dintre aparităţii spune literal *„a opta apariţie a familiei, numită de
proprietar"* **fără să numească familia**, deci nici măcar apartenenţa acelui membru nu se poate citi.

> **E aceeaşi formă cu tot restul zilei, şi de asta merită scrisă aici:** un numărător afirmă *„aceasta
> e a N-a de acest fel"*, iar **al doilea operand — primele N−1 — n-a fost niciodată scris.** Nimic nu
> poate contrazice numărul. E §1, rândul întâi: operand lipsă.

### 8bis.1 Relaţia, dedusă din definiţii — **marcată ca inferenţă**, fiindcă membrii lipsesc

Nu se pot compara extensiunile. Se pot compara **definiţiile**:

- „proprietate presupusă în amonte, **neimpusă în schemă**" cere ca proprietatea să fie una pe care
  schema **ar putea** s-o impună;
- „trece fiindcă **nimic nu strigă**" cere doar absenţa semnalului, oricare ar fi cauza.

Fusul orar, starea divergentă de la migrări, calea neatinsă de teste şi semantica lui
`git commit -- <căi>` sunt în a doua **şi nu sunt proprietăţi impozabile în schemă**. Deci:

> **Probabil două familii, cu relaţie de incluziune — prima proprie în a doua —, nu una cu două
> nume.** Dacă e aşa, **nu se unifică numerele**: se scrie relaţia. Iar dacă enumerarea infirmă
> incluziunea, se rescrie relaţia, nu se fuzionează seriile.

**Ce lipseşte ca testul să se încheie:** rosterul familiei „nimic nu strigă" din
`CONTEXT-evidenta.md`, şi enumerarea retroactivă a celor zece apariţii ale primei. **Amândouă sunt
muncă de scris, nu decizii** — nu primesc rând în registru.

## 9. Consecinţe

- **Devine posibil:** reconcilierea la `F2.B1`, azi, fără structură nouă.
- **Devine imposibil**, când impunerile din §3 sunt scrise: un `valid_from` fără actul care îl
  fixează; un invariant fără domeniu.
- **De modificat ca urmare:** `F2.B1` — al patrulea test; `OD-86` restrânsă; `OD-92` primeşte forma
  celor două câmpuri de citare.
- **Nu se construieşte** niciun gardian pentru primele două feluri. Coloană, nu verificare.

## 10. Surse

- Instrucţiunea proprietarului, addendum §10, 2026-08-30.
- Măsurat în cod: `fiscal/parameters/models.py` — `act` (nullable, definit ca sursa **valorii**),
  `source_confidence` (implicit în Python, scos din bază de migrare, cu motivul scris).
- [ADR-068](068-anexa-citita-categoria-e-a-raportului.md) §8.4, [ADR-069](069-persoana-asigurata-nu-e-angajatul.md) §3.
