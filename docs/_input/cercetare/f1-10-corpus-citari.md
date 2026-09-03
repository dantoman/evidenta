# `F1.10` — Corpusul de regresie: pasajele citate, transcrise

- **Data cercetării:** 2026-08-30
- **Pentru:** `backend/tests/corpus/` — fiecare caz al corpusului citează unul sau mai multe titluri
  de mai jos (`### …`), iar `tests/corpus/test_corpus_integrity.py` verifică mecanic că fiecare
  citare are un pasaj transcris aici. **Un titlu de mai jos nu se redenumește** fără cazurile care
  îl citează.
- **Sursele primare**, aceleași copii ca la `od-22-planul-de-conturi.md` și `c1-c3-c5-stocuri.md`:
  - Planul general de conturi contabile — PDF-ul consolidat al Ministerului Finanțelor,
    <https://mf.gov.md/sites/default/files/legislatie/Planul%20general%20de%20conturi%20contabile.pdf>
    (63 pagini; extras ca text cu `pdftotext -layout`, 2026-08-30). Actul: Ordinul MF nr. 119 din
    06.08.2013.
  - Standardele Naționale de Contabilitate — PDF-ul consolidat al Ministerului Finanțelor
    (263 pagini, consolidat până la OMF 73/2022), aceeași extragere. Actul: Ordinul MF nr. 118 din
    06.08.2013.
- **Ce este și ce nu este fișierul:** transcriere, nu interpretare. Textul din citate e cel extras
  (cu ortografia actului: `ţ`, `ş`, `sînt`, `vînzări`); ce e al nostru stă în afara citatelor. Unde
  un caz al corpusului se sprijină pe un ADR, citează secțiunea ADR-ului, nu acest fișier.

---

## Planul general de conturi — capitolul I

### Plan — Dispoziţii generale

> Planul general de conturi contabile cuprinde 9 clase: 1. Active imobilizate; 2. Active circulante;
> 3. Capital propriu; 4. Datorii pe termen lung; 5. Datorii curente; 6. Venituri; 7. Cheltuieli;
> 8. Conturi de gestiune; 9. Conturi extrabilanţiere.
>
> Clasele 1-5 cuprind conturile de bilanţ, clasele 6-7 – conturile de rezultate, clasa 8 – conturile
> de gestiune şi clasa 9 – conturile extrabilanţiere.
>
> Conturile de bilanţ sînt destinate generalizării informaţiei privind activele, capitalul propriu şi
> datoriile entităţii. La data raportării soldurile debitoare sau creditoare ale acestor conturi se
> iau în calcul la determinarea indicatorilor din bilanţ.
>
> Conturile de rezultate sînt destinate generalizării informaţiei privind veniturile şi cheltuielile
> entităţii. La data raportării rulajele creditoare ale conturilor de venituri şi rulajele debitoare
> ale conturilor de cheltuieli se iau în calcul la determinarea indicatorilor din situaţia de profit
> şi pierdere.
>
> Conturile de gestiune sînt destinate generalizării informaţiei privind costurile de producţie,
> adaosul comercial, încasările din vînzarea bunurilor în numerar, costurile refacturate şi alte
> elemente contabile cu caracter tranzitoriu. **La data raportării conturile de gestiune se închid cu
> conturile de bilanţ şi/sau de rezultate.**
>
> Conturile din clasele 1-8 funcţionează în partidă dublă, conform căreia înregistrările se
> efectuează concomitent în debitul unui cont şi creditul altui cont.

## Planul general de conturi — capitolul III, normele conturilor

### Plan 216

> Contul 216 “Produse” este un cont de activ. În debitul acestui cont se înregistrează
> intrarea/majorarea valorii produselor în corespondenţă cu creditul conturilor: 612, 811, 812, 833
> etc.
>
> În creditul contului 215 “Produse” *[sic, în act]* se înregistrează ieşirea/diminuarea valorii
> produselor în corespondenţă cu debitul conturilor: 121, 123, 711, 712, 713, 714, 722, 723, 811,
> 812, 833 etc.
>
> Soldul contului 216 “Produse” este debitor şi reprezintă valoarea produselor determinată în
> conformitate cu standardele de contabilitate.

### Plan 221

> Contul 221 “Creanţe comerciale” este un cont de activ. În debitul acestui cont se înregistrează
> apariţia/majorarea creanţelor comerciale în corespondenţă cu creditul conturilor: 331, 534, 611,
> 612, 622 etc.
>
> În creditul contului 221 “Creanţe comerciale” se înregistrează stingerea/diminuarea creanţelor
> comerciale în corespondenţă cu debitul conturilor: 222, 241, 242, 243, 331, 523, 712, 714, 722, 833
> etc.
>
> Soldul contului 221 “Creanţe comerciale” este debitor şi reprezintă suma creanţelor comerciale
> determinată în conformitate cu standardele de contabilitate.

### Plan 242

> Contul 242 “Conturi curente în monedă naţională” este un cont de activ. În debitul acestui cont se
> înregistrează încasarea numerarului în conturi curente în monedă naţională în corespondenţă cu
> creditul conturilor: 141, 142, 161, 162, 221, 223, 224, 226, 231, 234, 241, 244, 245, 251, 252,
> 313, 314, 411, 412, 423, 425, 511, 512, 523, 537, 543, 622, 623 etc.
>
> În creditul contului 242 “Conturi curente în monedă naţională” se înregistrează utilizarea
> numerarului din conturi curente în monedă naţională în corespondenţă cu debitul conturilor: 141,
> 142, 162, 224, 225, 226, 234, 241, 244, 251, 252, 315, 411, 412, 423, 425, 511, 512, 521, 522,
> 523, 531, 532, 533, 534, 536, 537, 542, 543, 544, 713, 714, 722, 723 etc.
>
> Soldul contului 242 “Conturi curente în monedă naţională” este debitor şi reprezintă suma
> numerarului în conturi curente în monedă naţională determinată în conformitate cu standardele de
> contabilitate.

### Plan 311

> Contul 311 “Capital social” este un cont de pasiv. În creditul acestui cont se înregistrează
> constituirea/majorarea capitalului social în corespondenţă cu debitul conturilor: 313, 314, 321,
> 322, 323, 332, 536 etc.
>
> Soldul contului 311 “Capital social” este creditor şi reprezintă mărimea capitalului social
> determinată în conformitate cu standardele de contabilitate.

### Plan 333

> Contul 333 “Profit net (pierdere netă) al perioadei de gestiune” este un cont de pasiv. În creditul
> acestui cont se înregistrează apariţia/majorarea profitului net şi decontarea pierderii nete a
> anului de gestiune în corespondenţă cu debitul conturilor: 332, 351 etc.
>
> În debitul contului 333 “Profit net (pierdere netă) al perioadei de gestiune” se înregistrează
> apariţia/majorarea pierderi nete şi utilizarea/diminuarea profitului net al anului de gestiune în
> corespondenţă cu creditul conturilor: 332, 334, 351 etc.
>
> Soldul contului 333 “Profit net (pierdere netă) al perioadei de gestiune” reprezintă mărimea
> profitului nerepartizat (pierderii neacoperite) al perioadei de gestiune determinată în
> conformitate cu standardele de contabilitate. Acest sold poate fi creditor – se reflectă în
> situaţiile financiare cu semnul plus (fără paranteze) sau debitor – se reflectă în situaţiile
> financiare cu semnul minus (între paranteze).

### Plan 351

> Contul 351 “Rezultat financiar total” este un cont de pasiv. În creditul acestui cont se
> înregistrează decontarea veniturilor acumulate şi pierderii nete a perioadei de gestiune în
> corespondenţă cu debitul conturilor: 333, 611, 612, 621, 622, 623 etc.
>
> În debitul contului 351 “Rezultat financiar total” se înregistrează decontarea cheltuielilor
> suportate şi profitului net al perioadei de gestiune în corespondenţă cu creditul conturilor: 333,
> 711, 712, 713, 714, 721, 722, 723, 731 etc.
>
> Contul 351 “Rezultat financiar total” la sfîrşitul perioadei de gestiune nu are sold.

### Plan 521

> Contul 521 “Datorii comerciale curente” este un cont de pasiv. În creditul acestui cont se
> înregistrează apariţia/majorarea datoriilor comerciale curente în corespondenţă cu debitul
> conturilor: 111, 112, 121, 122, 123, 125, 211, 212, 213, 217, 221, 331, 421, 712, 713, 714, 721,
> 722, 811, 812, 821 etc.
>
> În debitul contului 521 “Datorii comerciale curente” se înregistrează stingerea/diminuarea
> datoriilor comerciale curente în corespondenţă cu creditul conturilor: 221, 224, 234, 241, 242,
> 243, 331, 411, 412, 511, 512, 612, 622 etc.
>
> Soldul contului 521 “Datorii comerciale curente” reprezintă suma datoriilor comerciale curente
> determinată în conformitate cu standardele de contabilitate.

### Plan 534

> Contul 534 “Datorii faţă de buget” este un cont de pasiv. În creditul acestui cont se înregistrează
> apariţia/majorarea datoriilor faţă de buget în corespondenţă cu debitul conturilor: 221, 223, 225,
> 231, 234, 241, 242, 244, 531, 541, 713, 714, 832 etc.
>
> În debitul contului 534 “Datorii faţă de buget” se înregistrează stingerea/diminuarea datoriilor
> faţă de buget în corespondenţă cu creditul conturilor: 225, 232, 241, 242, 244 etc.

### Plan 611

> Contul 611 “Venituri din vînzări” este destinat generalizării informaţiei privind veniturile din
> vînzarea produselor mărfurilor, prestarea serviciilor/executarea lucrărilor aferente activităţii
> operaţionale a entităţii.
>
> În creditul contului 611 “Venituri din vînzări” se înregistrează recunoaşterea veniturilor din
> vînzări pe parcursul perioadei de gestiune în corespondenţă cu debitul conturilor: 221, 223, 231,
> 241, 535, 537, 832 etc.
>
> În debitul contului 611 “Venituri din vînzări” se înregistrează decontarea veniturilor din vînzări
> la finele perioadei de gestiune în corespondenţă cu creditul contului 351.

### Plan 612

> În creditul contului 612 “Alte venituri din activitatea operaţională” se înregistrează
> recunoaşterea altor venituri din activitatea operaţională pe parcursul perioadei de gestiune în
> corespondenţă cu debitul conturilor: 111, 112, 121, 122, 123, 125, 131, 132, 141, 142, 151, 211,
> 212, 213, 215, 216, 217, 221, 223, 226, 231, 233, 234, 241, 242, 251, 252, 511, 512, 521, 522,
> 531, 532, 533, 534, 535, 536, 537, 538, 542, 543, 544 etc.
>
> În debitul contului 612 “Alte venituri din activitatea operaţională” se înregistrează decontarea
> altor venituri din activitatea operaţională la finele perioadei de gestiune în corespondenţă cu
> creditul contului 351.

### Plan 622

> În creditul contului 622 “Venituri financiare” se înregistrează recunoaşterea veniturilor
> financiare pe parcursul perioadei de gestiune în corespondenţă cu debitul conturilor: 111, 112,
> 121, 122, 123, 125, 131, 141, 142, 151, 161, 162, 172, 211, 212, 213, 215, 216, 217, 221, 223, 226,
> 231, 232, 233, 234, 241, 242, 243, 251, 252, 262, 421, 423, 422, 421, 511, 512, 521, 522, 523, 536,
> 544 etc.
>
> În debitul contului 622 “Venituri financiare” se înregistrează decontarea veniturilor financiare
> la finele perioadei de gestiune în corespondenţă cu creditul contului 351.

### Plan 711

> În debitul contului 711 “Costul vînzărilor” se înregistrează costul vînzărilor recunoscut pe
> parcursul perioadei de gestiune în corespondenţă cu creditul conturilor: 216, 217, 261, 811, 812
> etc.
>
> În creditul contului 711 “Costul vînzărilor” se înregistrează decontarea costului vînzărilor la
> finele perioadei de gestiune în corespondenţă cu debitul contului 351.

### Plan 714

> Contul 714 “Alte cheltuieli din activitatea operaţională” este destinat generalizării informaţiei
> privind cheltuielile legate de desfăşurarea activităţii operaţionale care nu pot fi atribuite la
> costul vînzărilor, cheltuielile de distribuire sau cheltuielile administrative.
>
> În debitul contului 714 “Alte cheltuieli din activitatea operaţională” se înregistrează
> recunoaşterea altor cheltuieli ale activităţii operaţionale pe parcursul perioadei de gestiune în
> corespondenţă cu creditul conturilor: 111, 112, 121, 122, 123, 125, 141, 142, 151, 211, 213, 214,
> 215, 216, 217, 224, 226, 231, 233, 234, 241, 242, 244, 245, 246, 251, 252, 511, 512, 521, 522,
> 531, 532, 533, 534, 536, 538, 542, 543, 544, 811, 812 etc.
>
> În creditul contului 714 “Alte cheltuieli din activitatea operaţională” se înregistrează
> decontarea altor cheltuieli ale activităţii operaţionale la finele perioadei de gestiune în
> corespondenţă cu debitul contului 351.

### Plan 722

> În debitul contului 722 “Cheltuieli financiare” se înregistrează recunoaşterea cheltuielilor
> financiare pe parcursul perioadei de gestiune în corespondenţă cu creditul conturilor: 111, 112,
> 121, 122, 123, 125, 131, 143, 151, 172, 211, 212, 213, 215, 216, 217, 221, 223, 226, 231, 232, 233,
> 234, 241, 242, 243, 244, 251, 252, 262, 421, 422, 423, 511, 512, 521, 522, 523, 535, 536, 544 etc.
>
> În creditul contului 722 “Cheltuieli financiare” se înregistrează decontarea cheltuielilor
> financiare la finele perioadei de gestiune în corespondenţă cu debitul contului 351.

### Plan 731

> În debitul contului 731 “Cheltuieli privind impozitul pe venit” se înregistrează recunoaşterea
> cheltuielilor privind impozitul pe venit la finele perioadei de gestiune în corespondenţă cu
> creditul conturilor: 428, 534 etc.
>
> În creditul contului 731 “Cheltuieli privind impozitul pe venit” se înregistrează decontarea
> cheltuielilor privind impozitul pe venit la finele perioadei de gestiune în corespondenţă cu
> debitul conturilor: 172, 351 etc.

### Plan clasa 8

> Conturile din clasa 8 “Conturi de gestiune” sînt destinate generalizării informaţiei privind
> costurile de producţie, adaosul comercial, încasările din vînzarea bunurilor în numerar, costurile
> refacturate etc. care cuprind: conturi de calculaţie, conturi de repartizare şi alte conturi de
> gestiune.
>
> La data raportării conturile de gestiune se închid cu conturile de bilanţ şi/sau de rezultate.

### Plan 811

> Contul 811 “Activităţi de bază” este un cont de activ (calculaţie). În debitul acestui cont se
> înregistrează soldul iniţial al producţiei în curs de execuţie şi costurile directe şi indirecte de
> producţie în corespondenţă cu creditul conturilor: 113, 124, 126, 133, 211, 212, 213, 214, 215,
> 216, 217, 226, 521, 522, 531, 532, 533, 538, 812, 821 etc.
>
> În creditul contului 811 “Activităţi de bază” se înregistrează costul efectiv al produselor
> fabricate/serviciilor prestate, rebutului definitiv, deşeurilor recuperabile, precum şi soldul
> final al producţiei în curs de execuţie în corespondenţă cu debitul conturilor: 212, 215, 216,
> 711, 714, 723 etc.

### Plan 821

> Contul 821 “Costuri indirecte de producţie” este un cont de activ (colectare – repartizare). În
> debitul acestui cont se înregistrează majorarea costurilor indirecte de producţie în corespondenţă
> cu creditul conturilor: 113, 124, 133, 211, 213, 214, 226, 261, 521, 522, 531, 532, 533, 538, 544
> etc.
>
> În creditul contului 821 “Costuri indirecte de producţie” se înregistrează repartizarea costurilor
> indirecte de producţie în corespondenţă cu debitul conturilor: 714, 811, 812 etc.

## Planul general de conturi — capitolul II, nomenclatorul

Rândurile de mai jos sunt din `od-23-nomenclatorul-planului-de-conturi.md` (517 rânduri, controlate
round-trip). Un subcont poartă norma contului de gradul I din care face parte; numele subcontului
spune ce se înregistrează în el.

### Plan nomenclator 2211/2212

> 2211 Creanţe comerciale din ţară · 2212 Creanţe comerciale din străinătate — subconturi ale 221.

### Plan nomenclator 5211/5212

> 5211 Datorii comerciale în ţară · 5212 Datorii comerciale în străinătate — subconturi ale 521.

### Plan nomenclator 5341/5344

> 5341 Datorii privind impozitul pe venit din activitatea de întreprinzător şi profesională ·
> 5344 Datorii privind taxa pe valoarea adăugată — subconturi ale 534.

### Plan nomenclator 6111/7111

> 6111 Venituri din vînzarea produselor — subcont al 611 · 7111 Valoarea contabilă a produselor
> vîndute — subcont al 711.

### Plan nomenclator 6226/7224

> 6226 Venituri din diferenţe de curs valutar — subcont al 622 · 7224 Cheltuieli din diferenţe de
> curs valutar — subcont al 722.

### Plan nomenclator 6227/7225

> 6227 Venituri din diferenţe de sumă — subcont al 622 · 7225 Cheltuieli din diferenţe de sumă —
> subcont al 722.

### Plan nomenclator 6127/7147

> 6127 Venituri aferente diferenţelor favorabile dintre cursul oficial al BNM şi cursul de
> cumpărare-vînzare a valutei străine — subcont al 612 · 7147 Cheltuieli aferente diferenţelor
> nefavorabile dintre cursul oficial al BNM şi cursul de cumpărare-vînzare a valutei străine —
> subcont al 714.

---

## SNC „Stocuri"

### SNC Stocuri pct. 29

> 29. Costurile indirecte de producţie sînt legate de fabricarea produselor/prestarea serviciilor
> […] Repartizarea costurilor indirecte de producţie se efectuează în două etape:
> 1) repartizarea costurilor între costul produselor/serviciilor/producţiei în curs de execuţie şi
> cheltuielile curente;
> 2) repartizarea costurilor pe tipuri de produse fabricate/servicii prestate.

### SNC Stocuri pct. 30

> 30. Pentru repartizarea între costul produselor/serviciilor/producţiei în curs de execuţie şi
> cheltuielile curente, costurile indirecte de producţie se subdivizează în:
>
> 1) costuri variabile, mărimea cărora depinde de modificarea volumului producţiei (de exemplu,
> amortizarea mijloacelor fixe calculată în raport cu cantitatea de produse fabricate, costul
> materialelor consumate). Aceste costuri se includ în costul produselor fabricate/serviciilor
> prestate/producţiei în curs de execuţie în suma totală, indiferent de gradul de utilizare a
> capacităţilor de producţie;
>
> 2) costuri constante, mărimea cărora relativ nu depinde de modificarea volumului producţiei (de
> exemplu, amortizarea mijloacelor fixe cu destinaţie generală de producţie calculată prin metoda
> liniară, costurile de întreţinere şi exploatare a clădirilor şi utilajului secţiilor de producţie).
> Astfel de costuri se repartizează între costul produselor/serviciilor şi cheltuielile curente în
> baza capacităţii normale de producţie, care reprezintă volumul producţiei/serviciilor ce poate fi
> realizat, în medie, pe parcursul a cîteva perioade de gestiune sau sezoane în condiţii normale de
> activitate, ţinînd cont de pierderile capacităţii cauzate de reparaţiile (deservirea tehnică)
> planificate ale utilajului. Dacă volumul efectiv al producţiei/serviciilor este egal sau depăşeşte
> capacitatea normală, suma efectivă a costurilor indirecte de producţie constante se include integral
> în cost. În cazul în care volumul efectiv al producţiei este mai mic decît capacitatea normală,
> costurile indirecte de producţie constante se includ în cost în baza cotei calculate ca raportul
> dintre volumul efectiv al produselor/serviciilor şi capacitatea normală. Suma rămasă a costurilor
> indirecte de producţie constante se consideră drept cheltuieli curente.

### SNC Stocuri pct. 31

> 31. Repartizarea costurilor indirecte de producţie pe tipurile de produse fabricate/servicii
> prestate se efectuează proporţional cu baza stabilită în politicile contabile ale entităţii (de
> exemplu, proporţional salariilor de bază ale muncitorilor încadraţi în activităţile de bază şi
> auxiliare, sumei totale a costurilor directe de producţie, numărului de maşini-ore lucrate,
> cantităţii de produse fabricate). Repartizarea costurilor indirecte de producţie se contabilizează
> ca majorare a cheltuielilor curente, costurilor […]

### SNC Stocuri pct. 57

> 57. Prezentul standard intră în vigoare la 1 ianuarie 2014.

### SNC Stocuri Anexa 1

> **Modul de repartizare a costurilor indirecte de producţie**
>
> Date iniţiale. În luna septembrie 201X la o entitate de producţie au fost fabricate 3 tipuri de
> produse: “A”, “B” şi “C”. Costurile indirecte de producţie constante au constituit 120000 lei, iar
> cele variabile – 80000 lei. Conform politicilor contabile, costurile indirecte de producţie se
> repartizează pe tipuri de produse în baza volumului produselor fabricate.
>
> Tabelul 1 — capacitatea normală de producţie, unităţi / volumul produselor fabricate efectiv,
> unităţi: “A” 7000 / 7000; “B” 5000 / 4000; “C” 8000 / 6000.
>
> Tabelul 2 — Repartizarea costurilor indirecte de producţie (lei); coloanele: 1 denumirea;
> 2 capacitatea normală; 3 volumul efectiv; 4 = (3:∑3)×∑4 constante, total; 5 = (3:2)×4 aferente
> costului produselor fabricate; 6 = 4–5 aferente cheltuielilor curente; 7 = (3:∑3)×∑7 variabile;
> 8 = 5+7 incluse în costul produselor fabricate.
>
> | | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
> |---|---|---|---|---|---|---|---|
> | “A” | 7000 | 7000 | 49411,76 | 49411,76 | 0 | 32941,18 | 82352,94 |
> | “B” | 5000 | 4000 | 28235,30 | 22588,24 | 5647,06 | 18823,53 | 41411,77 |
> | “C” | 8000 | 6000 | 42352,94 | 31764,71 | 10588,23 | 28235,29 | 60000,00 |
> | Total | 20000 | 17000 | 120000 | 103764,71 | 16235,29 | 80000 | 183764,71 |
>
> \* În cazul cînd volumul produselor fabricate efectiv este mai mare decît capacitatea normală de
> producţie, costurile indirecte constante se includ integral în cost, dar nu trebuie să depăşească
> suma din coloana 4.
>
> Conform datelor din exemplu şi a calculelor efectuate, în septembrie 201X entitatea contabilizează:
> - consumurile indirecte de producţie decontate la cheltuieli curente în suma de 16235,29 lei – ca
>   majorare a cheltuielilor curente şi diminuare a costurilor indirecte de producţie;
> - costurile indirecte de producţie incluse în costul produselor fabricate în suma de 183764,71
>   lei – ca majorare a costurilor activităţilor de bază şi diminuare a costurilor indirecte de
>   producţie.

*Observații ale transcrierii, nu ale actului:* (a) tabelul aplică cota `3:2` **pe fiecare produs**,
cu capacitatea normală a produsului, nu o cotă unică pe total (`17000:20000` ar da 102000, nu
103764,71); (b) pentru “C”, `42352,94 × 6000/8000 = 31764,705` — tabelul scrie **31764,71**, deci
rotunjirea din act la echidistanță e în sus; (c) coloana 4 însumează 120000 exact, cu banul
rămas din împărțire pus pe “B” (28235,2941 → 28235,30), nu pe “A”, cota cea mai mare — actul nu
prescrie regula restului; motorul îl pune pe cota cea mai mare (ADR-058 §2.5, decizia
proprietarului, confirmată 2026-08-30): **abatere cunoscută și motivată**, nu eșec tolerat.

---

## SNC „Diferenţe de curs valutar şi de sumă"

### SNC Diferenţe de curs pct. 8

> 8. Achitarea creanţelor şi datoriilor în valută străină se înregistrează prin aplicarea cursului
> oficial al leului moldovenesc la data achitării. Diferenţele de curs valutar favorabile şi
> nefavorabile care apar la data achitării creanţelor şi datoriilor se recunosc ca venituri sau
> cheltuieli curente.

### SNC Diferenţe de curs pct. 9

> 9. Diferenţele de curs valutar favorabile se contabilizează în modul următor:
> 1) în cazul creşterii cursului valutar – ca majorare concomitentă a numerarului, creanţelor
> curente, altor elemente monetare şi veniturilor curente;
> 2) în cazul scăderii cursului valutar – ca diminuare a datoriilor curente şi majorare a
> veniturilor curente.
>
> Exemplul 1. O entitate, în luna decembrie 201X, a importat mărfuri în valoare de 10000 dolari SUA
> cu achitarea ulterioară. Cursul oficial al leului moldovenesc la data: întocmirii declaraţiei
> vamale – 11,5525 lei/dolar SUA; achitării datoriilor – 11,3378 lei/dolar SUA.
>
> În baza datelor din exemplu, entitatea contabilizează:
> - valoarea mărfurilor achiziţionate în sumă de 115525 lei (10000 dolari SUA × 11,5525 lei/dolar
>   SUA) – ca majorare concomitentă a stocurilor şi datoriilor curente;
> - achitarea datoriilor faţă de furnizorul străin în sumă de 113378 lei (10000 dolari SUA ×
>   11,3378 lei/dolar SUA) – ca diminuare concomitentă a datoriilor curente şi a numerarului;
> - diferenţa de curs valutar favorabilă în suma de 2147 lei [10000 dolari SUA × (11,5525
>   lei/dolar SUA – 11,3378 lei/dolar SUA)] – ca diminuare a datoriilor curente şi majorare a
>   veniturilor curente.

### SNC Diferenţe de curs pct. 10

> 10. Diferenţele de curs valutar nefavorabile se contabilizează în modul următor:
> 1) în cazul scăderii cursului valutar – ca majorare a cheltuielilor curente şi diminuare a
> numerarului, creanţelor curente, altor elemente monetare;
> 2) în cazul creşterii cursului valutar – ca majorare concomitentă a cheltuielilor şi datoriilor
> curente.
>
> Exemplul 2. O entitate a încheiat cu un cumpărător străin un contract de livrare a produselor în
> valoare de 60000 euro. Conform contractului produsele vor fi livrate după achitarea în avans a 50%
> din valoarea contractuală a acestora. La 27 martie 201X cumpărătorul a efectuat plata în avans,
> iar la 3 aprilie 201X produsele au fost livrate. Decontarea finală a avut loc la 10 aprilie 201X.
> Cursul oficial al leului moldovenesc la data: 27.03.201X – 15,3584 lei/euro; 03.04.201X – 15,3845
> lei/euro; 10.04.201X – 15,3136 lei/euro.
>
> În baza datelor din exemplu, entitatea contabilizează: în martie 201X: primirea avansului în
> valută străină în sumă de 460752 lei (30000 euro × 15,3584 lei/euro) – ca majorare concomitentă a
> numerarului şi datoriilor curente; în aprilie 201X: livrarea produselor cumpărătorului în sumă de
> 923070 lei (60000 euro × 15,3845 lei/euro) – ca majorare concomitentă a creanţelor şi veniturilor
> curente; trecerea în cont a avansului primit anterior în sumă de 460752 lei (30000 euro × 15,3584
> lei/euro) – ca diminuare concomitentă a datoriilor şi creanţelor curente; achitarea creanţelor în
> valută străină în sumă de 459408 lei (30000 euro × 15,3136 lei/euro) – ca majorare a numerarului
> şi diminuare a creanţelor curente; diferenţa de curs valutar nefavorabilă în sumă de 2910 lei
> [30000 euro × (15,3584 lei/euro – 15,3845 lei/euro) + 30000 euro × (15,3136 lei/euro – 15,3845
> lei/euro)] – ca majorare a cheltuielilor curente şi diminuare a creanţelor curente.

*Observație a transcrierii, cu datarea verificată (2026-08-30):* cei 2910 lei sunt doi termeni —
783 lei pe partea achitată în avans (creanţa recunoscută integral la cursul livrării, avansul trecut
în cont la cursul plăţii lui) şi 2127 lei pe partea achitată la 10.04. **Exemplul 2 e textul din
2013, nemodificat** — în textul consolidat nu poartă nicio notă de modificare, spre deosebire de
pct. 11 şi 12, rescrise prin OMF nr. 48 din 12.03.2019 (în vigoare 01.01.2020), care mută avansurile
acordate/primite pe partea **nemonetară**: nu se recalculează şi se înregistrează la cursul de la
recunoaşterea iniţială. Primul termen ilustrează deci redacţia abrogată; al doilea rămâne valabil.
Corpusul reproduce al doilea termen, iar handlerul, care nu postează nimic pe partea avansată, e
redacţia în vigoare — vezi `backend/tests/corpus/README.md`.

### SNC Diferenţe de curs pct. 11

> 11. La întocmirea situaţiilor financiare elementele monetare în valută străină (numerarul,
> creanţele şi datoriile, cu excepţia avansurilor acordate şi primite pentru procurări/livrări de
> active şi servicii, investiţiile financiare, cu excepţia acţiunilor şi cotelor părţi etc.) se
> recalculează prin aplicarea cursului oficial al leului moldovenesc la data raportării.
> [Pct.11 în redacţia Ordinului Min.Fin. nr.48 din 12.03.2019, în vigoare 01.01.2020]

### SNC Diferenţe de curs pct. 12

> 12. Elementele nemonetare în valută străină (imobilizările necorporale şi corporale, goodwill-ul,
> stocurile, avansurile acordate/primite pentru procurări/livrări de active şi servicii, elementele de
> capital propriu, etc.) nu se supun recalculării la data raportării şi se înregistrează în situaţiile
> financiare conform cursului oficial al leului moldovenesc la data recunoaşterii iniţiale a acestora.
> [Pct.12 în redacţia Ordinului Min.Fin. nr.48 din 12.03.2019, în vigoare 01.01.2020]

### SNC Diferenţe de curs pct. 13

> 13. Entitatea poate recalcula elementele monetare atît la data raportării, cît şi cu o altă
> periodicitate prevăzută în politicile contabile (lunar, trimestrial etc.).
> [p. 197; transcris în `f2-x2-snc-situatii-financiare-si-diferente-de-curs.md` §8]

### SNC Diferenţe de curs pct. 14

> 14. Diferenţele de curs valutar favorabile şi nefavorabile care apar ca rezultat al recalculării
> la data raportării a elementelor monetare precum şi a acţiunilor evaluate la valoarea justă, se
> recunosc ca venituri şi cheltuieli curente şi se contabilizează în conformitate cu prevederile
> pct.9 şi 10 din prezentul standard. Modul de contabilizare a diferenţelor de curs valutar este
> prezentat în anexa 1.
> [p. 197; transcris în `f2-x2-snc-situatii-financiare-si-diferente-de-curs.md` §8]

### SNC Diferenţe de curs pct. 15

> 15. În cazul în care operaţiunea în valută străină a fost înregistrată într-o perioadă de
> gestiune, iar achitarea se efectuează în altă perioadă de gestiune, diferenţele de curs valutar se
> recunosc în fiecare perioadă de gestiune pînă la data achitării.
> [p. 198; transcris în `f2-x2-snc-situatii-financiare-si-diferente-de-curs.md` §8]

### SNC Diferenţe de curs Exemplul 3

> Exemplul 3 (p. 198): servicii prestate de 13 000 euro la 22.12, cursul 15,0540; la data raportării
> 31.12 cursul 15,3825 — diferenţă de curs favorabilă 4 270 lei, „ca majorare concomitentă a
> creanţelor şi veniturilor curente"; încasare la 03.01 la cursul 15,3158 — diferenţă nefavorabilă
> 867 lei faţă de cursul de la 31.12. Deci după reevaluare baza următoarei diferenţe e cursul
> reevaluării, nu cel iniţial. Sumele din act sunt rotunjite la leu; motorul le ţine la scara
> parametrului (`accounting.amount_scale`), deci 4 270,50 şi 867,10 — diferenţă explicată, nu
> divergenţă (README, „Explicate, nu divergențe").
> [rezumat din `f2-x2-snc-situatii-financiare-si-diferente-de-curs.md` §8, care citează p. 198]

### SNC Diferenţe de curs pct. 17

> 17. Diferenţele de sumă apar în cazul încheierii între rezidenţii Republicii Moldova a
> contractelor în care părţile au convenit asupra unor datorii pecuniare (băneşti) exprimate în
> valută străină sau unităţi convenţionale, dacă astfel de contracte nu sunt interzise de legislaţia
> în vigoare.

### SNC Diferenţe de curs pct. 19

> 19. Achitarea creanţelor şi datoriilor aferente operaţiunilor exprimate în valută străină sau
> unităţi convenţionale se contabilizează în monedă naţională prin aplicarea cursului de schimb:
> 1) la data achitării creanţelor şi datoriilor; sau
> 2) la data livrării (procurării) activelor şi/sau prestării (beneficierii) serviciilor; sau
> 3) stabilit în mărime fixă sau în alt mod de către părţile contractante.

### SNC Diferenţe de curs pct. 20

> 20. În cazul aplicării cursului de schimb la data achitării creanţelor şi datoriilor, diferenţele
> de sumă aferente operaţiunilor respective se contabilizează în modul următor:
> 1) diferenţele de sumă favorabile – ca majorare a creanţelor curente şi/sau altor active sau
> diminuare a datoriilor curente şi majorare a veniturilor curente;
> 2) diferenţele de sumă nefavorabile – ca majorare a cheltuielilor curente şi diminuare a
> creanţelor curente şi/sau altor active sau majorare a datoriilor curente.
>
> Exemplul 5. La 10 octombrie 201X două entităţi rezidente ale Republicii Moldova (neplătitoare de
> TVA) au încheiat un contract de vînzare-cumpărare a mărfurilor, valoarea acestora fiind exprimată
> în euro. La 15 octombrie 201X vînzătorul a livrat 100 unităţi de marfă în valoare de 5000 euro.
> Clauzele contractuale prevăd efectuarea plăţii în moneda naţională prin aplicarea cursului oficial
> al leului moldovenesc la data achitării. Achitarea a fost efectuată la 10 noiembrie 201X. Cursul
> oficial al leului moldovenesc la data: 15.10.201X – 15,1220 lei/euro, 10.11.201X – 15,3252
> lei/euro.
>
> În baza datelor din exemplu, se contabilizează:
> • la entitatea-vînzător: în octombrie 201X: valoarea mărfurilor vîndute în sumă de 75610 lei
> (5000 euro × 15,1220 lei/euro) – ca majorare concomitentă a creanţelor şi veniturilor curente; în
> noiembrie 201X: achitarea creanţelor privind mărfurile vîndute în sumă de 76626 lei (5000 euro ×
> 15,3252 lei/euro) – ca majorare a numerarului şi diminuare a creanţelor curente; diferenţa de sumă
> favorabilă aferentă vînzării mărfurilor în sumă de 1016 lei [5000 euro × (15,3252 lei/euro –
> 15,1220 lei/euro)] – ca majorare concomitentă a creanţelor şi veniturilor curente;
> • la entitatea-cumpărător: în octombrie 201X: valoarea mărfurilor procurate în sumă de 75610 lei
> (5000 euro × 15,1220 lei/euro) – ca majorare concomitentă a stocurilor şi datoriilor curente; în
> noiembrie 201X: achitarea datoriilor pentru mărfurile procurate în sumă de 76626 lei (5000 euro ×
> 15,3252 lei/euro) – ca diminuare concomitentă a datoriilor curente şi numerarului; diferenţa de
> sumă nefavorabilă aferentă procurării mărfurilor în sumă de 1016 lei [5000 euro × (15,1220
> lei/euro – 15,3252 lei/euro)] – ca majorarea concomitentă a cheltuielilor şi datoriilor curente.

### SNC Diferenţe de curs pct. 21

> 21. În cazul aplicării cursului de schimb la data livrării activelor (prestării serviciilor) sau a
> unui curs stabilit de părţi în mărime fixă, diferenţe de sumă nu apar, deoarece vînzătorul şi
> cumpărătorul recunosc creanţele şi datoriile în baza aceluiaşi curs de schimb.

### SNC Diferenţe de curs pct. 23

> 23. În cazul achitării anticipate (în avans) pentru activele livrate (procurate) sau serviciile
> prestate (primite) echivalentul în moneda naţională a avansului se determină prin aplicarea
> cursului de schimb la data plăţii acestuia şi ulterior nu se recalculează.

---

## SNC „Politici contabile, modificări ale estimărilor contabile, erori şi evenimente ulterioare"

### SNC Politici contabile pct. 33

> 33. Corectarea erorii comise şi depistate în perioada de gestiune curentă se efectuează în modul
> următor:
> 1) în cazul depistării corespondenţei conturilor contabile eronate – se anulează înregistrarea
> eronată prin stornare sau prin înregistrare contabilă inversă conform politicilor contabile ale
> entităţii, cu întocmirea concomitentă a înregistrării contabile corecte;
> 2) în cazul în care suma înregistrată eronat este mai mare decît suma corectă – diferenţa se
> anulează prin stornare sau prin înregistrare contabilă inversă conform politicilor contabile ale
> entităţii;
> 3) în cazul lipsei înregistrării contabile – se întocmeşte înregistrarea contabilă respectivă;
> 4) în cazul în care suma înregistrată eronat este mai mică decît suma corectă – diferenţa se
> reflectă prin înregistrarea contabilă suplimentară în aceeaşi corespondenţă […]

---

## SNC „Venituri"

### SNC Venituri pct. 17

> 17. Veniturile din vînzarea bunurilor se ajustează prin stornarea valorii bunurilor returnate
> şi/sau cu suma reducerii preţurilor acestora în cazul în care livrarea şi returnarea (reducerea
> preţurilor) bunurilor au avut loc în aceeaşi perioadă de gestiune. În cazul în care vînzarea şi
> returnarea (reducerea preţurilor) bunurilor au avut loc în perioade de gestiune diferite,
> veniturile nu se ajustează, iar pierderile din returnarea bunurilor vîndute sau din reducerea
> preţurilor acestora se înregistrează ca cheltuieli curente sau se recuperează din contul
> provizioanelor constituite anterior în aceste scopuri.
>
> Exemplul 8. În iunie 201X o entitate – fabrică de mobilă a comercializat 10 seturi de mobilă
> pentru oficiu. Valoarea de vînzare a unui set de mobilă constituie 3600 lei, iar costul efectiv –
> 2500 lei. În luna iulie a aceluiaşi an cumpărătorul a depistat 3 seturi de mobilă necalitativă
> care au fost returnate vînzătorului.
>
> În baza datelor din exemplu, entitatea-vînzător contabilizează: în iunie 201X: veniturile din
> vînzarea mobilei în sumă de 36000 lei (3600 lei × 10 set.) – ca majorare concomitentă a creanţelor
> şi veniturilor curente; costul efectiv al mobilei vîndute în sumă de 25000 lei (2500 lei × 10 set.)
> – ca majorare a cheltuielilor curente (costului vînzărilor) şi diminuare a stocurilor. în iulie
> 201X: valoarea mobilei returnate de cumpărător în sumă de 10800 lei (3600 lei × 3 set.) – ca
> stornare a creanţelor şi a veniturilor curente; costul mobilei returnate de cumpărător – ca
> stornare a cheltuielilor curente (costului vînzărilor) şi a stocurilor.

---

## SNC „Capital propriu şi datorii"

### SNC Capital propriu pct. 21

> 21. Profitul net (pierderea netă) al perioadei de gestiune se determină ca diferenţa dintre
> veniturile şi cheltuielile curente ale entităţii recunoscute în perioada de gestiune curentă.

### SNC Capital propriu pct. 23

> 23. La reformarea bilanţului profitul net (pierderea netă) al perioadei de gestiune se decontează
> şi se contabilizează: 1) ca diminuare a profitului net al perioadei de gestiune şi majorare a
> profitului nerepartizat sau diminuare a pierderii neacoperite a anilor precedenţi; 2) ca diminuare
> a profitului nerepartizat sau majorare a pierderii neacoperite a anilor precedenţi şi diminuare a
> pierderii nete a perioadei de gestiune.
>
> Exemplul 7. O entitate a înregistrat în anul 201X venituri şi cheltuieli în sumă, respectiv, de
> 190000 lei şi 110000 lei, profitul constituind 80000 lei. Conform deciziei consiliului entităţii în
> iulie 201X au fost calculate dividende intermediare în sumă de 10000 lei.
>
> În baza datelor din exemplu, entitatea contabilizează: în iulie 201X: calcularea dividendelor
> intermediare în sumă de 10000 lei – ca majorare concomitentă a profitului utilizat al perioadei de
> gestiune şi datoriilor faţă de proprietari; **la 31 decembrie 201X: decontarea veniturilor curente
> în sumă de 190000 lei – ca diminuare a veniturilor curente şi majorare a rezultatului financiar
> total al perioadei de gestiune; decontarea cheltuielilor curente în sumă de 110000 lei – ca
> diminuare concomitentă a rezultatului financiar total al perioadei de gestiune şi a cheltuielilor
> curente;** la reformarea bilanţului: decontarea profitului utilizat al perioadei de gestiune în
> sumă de 10000 lei – ca diminuare concomitentă a profitului utilizat al perioadei de gestiune şi a
> profitului net al perioadei de gestiune; decontarea profitului net al perioadei de gestiune în
> sumă de 70000 lei (190000 lei – 110000 lei – 10000 lei) – ca diminuare a profitului net al
> perioadei de gestiune şi majorare a profitului nerepartizat al anilor precedenţi.

*Observație a transcrierii:* reformarea bilanţului (334, 333 → 332) e `OD-73`, în afara lanţului
livrat în F1.5.4; corpusul reproduce cele două decontări de la 31 decembrie şi rezultatul pe 333.

---

## SNC „Prezentarea situaţiilor financiare"

### SNC Prezentarea situaţiilor financiare pct. 18

> 18. Întocmirea şi prezentarea situaţiilor financiare cuprind următoarele etape:
> 1) efectuarea lucrărilor premergătoare întocmirii situaţiilor financiare cum ar fi: inventarierea
> generală a activelor, capitalului propriu şi datoriilor, decontarea cheltuielilor şi veniturilor
> anticipate aferente perioadei de gestiune, determinarea şi reflectarea diferenţelor de curs
> valutar, întocmirea înregistrărilor de corectare, determinarea cotei curente a activelor
> imobilizate şi datoriilor pe termen lung, închiderea conturilor de gestiune etc.;
> 2) completarea formatelor situaţiilor financiare;
> 3) întocmirea notei explicative la situaţiile financiare;
> 4) aprobarea, semnarea şi prezentarea situaţiilor financiare;
> 5) reformarea bilanţului/bilanţului prescurtat.
