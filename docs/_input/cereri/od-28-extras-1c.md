# Cerere de extras 1C — `OD-28` / `OD-30` / `F1.G0`

- **Data:** 2026-08-26
- **Ce deblochează:** `F1.9` (importatorul 1C), `F1.G1`/`F1.G2` (grilele), și criteriul de ieșire
  din F1 — *balanță verificabilă la leu contra unei balanțe 1C reale*
- **Cui se trimite:** un cabinet de contabilitate colaborator, sau un client cu 1C
- **Statut:** draft de trimis; nimic nu se poate face în cod până nu ajunge

> **Nu se cere doar balanța.** O balanță singură validează jumătate din ce avem nevoie: sumele. Ce
> nu validează e **structura** — conturile folosite neobișnuit, câmpurile pe care nimeni nu le
> completează, ierarhiile pe care nu le anticipăm. Aceea e jumătatea care nu se poate simula, și
> care se plătește târziu: o grilă validată pe cincizeci de rânduri inventate nu e validată.

---

## Textul propus

Bună ziua,

Construim o platformă de contabilitate pentru Republica Moldova și am ajuns în punctul în care
avem nevoie de date reale ca să validăm importul din 1C. Sunt la stadiul în care structura contează
mai mult decât volumul — vreau să văd cum arată o bază adevărată, nu una construită de mine după
cum îmi imaginez că arată.

V-aș ruga, dacă se poate, un set de la **o singură companie**, pentru **un an încheiat**:

1. **Planul de conturi** aşa cum e configurat la companie, cu subconturile proprii — nu planul
   standard, ci exact ce s-a modificat.
2. **Balanța de verificare** la sfârșit de an, cu rulaje și solduri.
3. **Fișa a două-trei conturi** cu mișcare bogată — de regulă un cont de clienți, unul de furnizori
   și unul de bancă.
4. **Câteva facturi cu multe linii**, ca **export de date** (XML, DBF, JSON — orice format
   structurat), **nu PDF**. Cinci-șase ajung. Aici se vede ce câmpuri există și care rămân goale.
5. **Documentele primare care au produs balanța** — sau măcar o lună din ele, ca să pot verifica
   lanțul de la document până la sold.
6. **Versiunea de 1C și configurația** — care ediție, ce configurație (tipică sau modificată), și
   dacă s-a lucrat cu ea modificată.

Datele pot fi **anonimizate**: denumirile de parteneri, IDNO-urile și sumele pot fi înlocuite, cu
o singură condiție — ca înlocuirea să fie **consecventă** (același partener să rămână același
partener peste tot) și ca **structura să nu se schimbe**: același număr de linii, aceleași conturi,
aceleași câmpuri goale acolo unde erau goale. Structura e ce mă interesează.

Și, dacă e posibil, **disponibilitatea de a răspunde la câteva întrebări** după ce mă uit peste
date. De obicei apar două-trei lucruri pe care nu le înțeleg din fișiere.

Vă mulțumesc,

---

## Note pentru noi, nu pentru destinatar

**De ce „un an încheiat" și nu „ultimele luni":** închiderea de exercițiu e cea care produce
postările pe care nu le putem ghici — lanțul de la conturile de rezultate spre profitul net. Fără un
an complet nu vedem niciodată forma aia pe date reale.

**De ce exportul de facturi separat de balanță:** balanța arată sume agregate. Liniile de factură
arată **lățimea reală a coloanelor** și câte dimensiuni analitice folosește efectiv cineva — cele
două lucruri de care depinde `EntryGrid` și pe care volumul simulat nu le arată.

**Ce facem dacă nu vine:** alternativa e explicită, nu implicită. Date inventate cu volum realist
validează performanța virtualizării și lățimea coloanelor — jumătate. Cealaltă jumătate, structurile
neanticipate, se pierde: un generator scris de aceeași persoană care proiectează grila reproduce
exact așteptările pe care grila ar trebui să le înfrunte. Dacă ajungem acolo, se alege știind ce se
sacrifică — vezi `07-f1-grile.md`.
