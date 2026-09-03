# ADR-095 — Pipeline-ul de documente tipărite: ReportLab, un font propriu, ieșire identică byte-cu-byte

- **Stare:** Acceptat — tehnic (arhitectură delegată), varianta reversibilă; proprietarul confirmă
  sau răstoarnă, cu declanșatorul din §6
- **Data:** 2026-09-03
- **Decis de:** sesiunea de implementare (pasul `5b` din
  [`../_bootstrap/14-planul-golurilor.md`](../_bootstrap/14-planul-golurilor.md)), prin delegare
  explicită a proprietarului: *„alege biblioteca PDF; consemnează fiecare decizie într-un ADR cu
  implicit reversibil"*
- **Închide:** `OD-74` — jumătatea PDF; jumătatea Excel rămâne, fără rând nou, la primul client care
  o cere (§5)
- **Deschide:** nimic
- **Atinge:** `C22`, `C38`, `C39` *(primesc mecanism)*; `platform/documents/printing/` (nou);
  `operations/sales/services/printing.py`, `operations/payroll/services/payslip_pdf.py`;
  `pyproject.toml` / `uv.lock` (`reportlab`; `types-reportlab`, `pypdf` în grupul de dezvoltare);
  `F2.P1` din [`../_bootstrap/09-f2-backlog.md`](../_bootstrap/09-f2-backlog.md)

## 1. Contextul

`C22` spune că documentele tipărite — factura, ordinul de plată, balanțele, situațiile, declarațiile
— nu se randează din React: au format impus și se generează printr-un pipeline server-side separat.
`C38` cere ca acel pipeline să **deschidă explicit** contextul lingvistic românesc și să formateze
numere și date printr-un modul cu convenții `ro-MD` fixe ([ADR-033](033-limba-la-generare.md)).
`C39` cere pe document **denumirea legală**, niciodată cea internă
([ADR-034](034-denumire-legala-si-interna.md)).

Până azi nu exista niciun PDF generat de server. F1.8 a livrat exporturile ca CSV tocmai fiindcă
CSV-ul nu cere nicio dependență, și a deschis `OD-74`: biblioteca pentru Excel și pipeline-ul pentru
PDF „nu se aleg în treacăt". [ADR-013](013-python-version-pin.md) anticipa dependențele de PDF ca motiv de a
rămâne pe Python 3.13. Pasul `5b` cere pipeline-ul, factura fiscală după OMF nr. 118 din 28.08.2017
(`V1`, citită: [`v1-factura-fiscala-omf-118-2017.md`](../_input/cercetare/v1-factura-fiscala-omf-118-2017.md))
și fluturașul (Codul muncii art. 142 alin. (3), citit:
[`f2-x2-concedii-indemnizatii-fluturas.md`](../_input/cercetare/f2-x2-concedii-indemnizatii-fluturas.md) §5).

Constrângerile primite odată cu delegarea: **fără biblioteci de sistem** (fără pango/cairo/GTK —
WeasyPrint iese, dacă nu se dovedește contrariul), **pin exact** în `uv.lock` (`C28`), **ieșire
deterministă** (același document de două ori → aceiași octeți), **font propriu, încorporat**, care
acoperă diacriticele românești cu virgulă dedesubt (`ș`, `ț`, U+0218–U+021B).

## 2. Ce s-a măsurat înainte de a decide

Pe această mașină, cu `reportlab 5.0.1` din PyPI (roți `manylinux` pentru CPython 3.13, dependențe
`pillow` și `charset-normalizer`, toate cu roți, nicio bibliotecă de sistem):

- un document cu text `Ș ț ă â î — Șerban Țărănescu SRL, cantitate 1234,56`, randat de două ori cu
  `invariant=1` și fontul DejaVu Sans încorporat ca subset: **octeți identici** (23 247 B,
  `sha256 9bc77b95…`);
- antetul PDF poartă `/CreationDate (D:20000101000000+00'00')` și `/ModDate` identic — epoca fixă
  pe care `invariant` o scrie — iar `/ID` din trailer e derivat din conținut;
- `pypdf 6.16.2` extrage textul înapoi **cu diacriticele intacte**, fiindcă ReportLab scrie
  `ToUnicode` pentru subsetul TTF. Fără asta, o căutare de octeți în fluxul de conținut n-ar dovedi
  nimic: fontul încorporat scrie identificatori de glife, nu text.

Fontul: `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` și `-Bold.ttf` (Debian
`fonts-dejavu-core`), licență Bitstream Vera + modificările DejaVu în domeniul public — copiate în
`platform/documents/printing/fonts/` împreună cu fișierul de licență. Nu se rezolvă din sistemul de
operare: ieșirea ar depinde de imaginea containerului, contrariul lui *invariant*.

## 3. Opțiuni evaluate

1. **WeasyPrint** (HTML + CSS → PDF). *Avantaje:* layout din CSS, familiar. *Dezavantaje:* cere
   pango/cairo/GTK din sistem — exact constrângerea primită; ieșirea ar depinde de versiunea
   bibliotecilor de sistem, deci determinismul ar fi al imaginii, nu al codului. **Respinsă fără
   măsurare**: constrângerea e a proprietarului, nu a sesiunii.
2. **fpdf2** (Python pur; `fonttools`, `Pillow`, `defusedxml`). *Avantaje:* API mic, fonturi TTF cu
   subset, tabele. *Dezavantaje:* nu livrează `py.typed` și n-are stub-uri în typeshed — sub `mypy`
   strict pe `platform` (`C29`) ar fi cerut `ignore_missing_imports` pentru un pachet, adică o
   gaură în verificator; determinismul cere setarea manuală a datei de creare și a identificatorului.
3. **ReportLab** (BSD; `pillow`, `charset-normalizer`; roți fără dependențe de sistem). *Avantaje:*
   `invariant=1` e o proprietate **documentată** a bibliotecii, făcută pentru regresie — data fixă,
   `/ID` din conținut; platypus dă tabele cu antet repetat pe pagini, paragrafe cu împachetare,
   stiluri; `types-reportlab` există în typeshed, deci `platform` rămâne strict fără excepție;
   proiect matur, cu API stabil de ani. *Dezavantaje:* API mai vechi ca stil; stub-urile sunt
   pentru 4.5 pe o bibliotecă 5.0 — au trecut verificarea pe tot ce folosește pipeline-ul, dar
   pot rămâne în urmă la un upgrade. *Cost de schimbare:* mic — §4.

## 4. Decizia

**ReportLab**, pinuit în `uv.lock` (`reportlab==5.0.1`; `pyproject.toml` poartă planșeul scris de
`uv add`); `types-reportlab` și `pypdf` în grupul `dev` — al doilea doar pentru teste, ca cititor
independent al ieșirii.

**Forma pipeline-ului este ce face costul de schimbare mic.** `platform/documents/printing/`
expune o valoare — `PrintableDocument`: titlu, subtitlu, blocuri de câmpuri etichetate, două
blocuri alăturate, o tabelă cu antet și rânduri de total, totaluri, linii de semnătură, text — și
o singură funcție, `render(document) -> bytes`. **Un modul de business construiește valoarea și nu
importă biblioteca**: `operations/sales/services/printing.py` construiește factura,
`operations/payroll/services/payslip_pdf.py` fluturașul. Biblioteca apare într-un singur fișier,
`render.py`. Înlocuirea ei e rescrierea acelui fișier, cu aceleași teste.

Ce impune `render`:

- **`translation.override("ro")` la intrare** — `C38`, ADR-033. Formatorul de sub el
  (`platform/documents/formatting.py`) nu citește nicio limbă, deci azi override-ul nu schimbă
  nimic; gardianul din `tests/architecture/test_document_language.py` randează același document cu
  `ru` și `en` active și cere aceiași octeți.
- **Celulele sunt tipizate, nu preformatate**: `Decimal` și `date` ajung până în renderer și doar
  acolo devin text, prin `decimal_ro` / `date_ro`. Un apelant care și-ar formata sumele ar fi al
  doilea formator. Banii au două zecimale; o cantitate sau o cotă se tipăresc cu câte zecimale
  poartă și fără zerouri de umplutură (`1.000000` → `1`, `20.00` → `20`) — precizia cantității e a
  unității ([ADR-055](055-precizia-cantitatii-e-a-unitatii.md)), nu a formularului.
- **`invariant=1`, producător fix (`Evidenta`), fără număr de versiune în metadate**: o versiune în
  antet ar schimba octeții la fiecare upgrade fără nicio schimbare de conținut.
- **Răspunsul HTTP** e `application/pdf`, `Content-Disposition: inline`, cu numele fișierului derivat
  din identificatorii documentului și redus la ASCII (`Fluturaș` → `fluturas`): un antet cu
  diacritice e un antet pe care unii clienți îl aruncă.

### 4.1 Factura fiscală — ce e din act și ce e convenție

Din `V1` (anexa nr. 1, anexa nr. 2 pct. 15, 17, 18, 23, 24): cele opt coloane 10.1–10.8 cu
antetele actului, verbatim; valoarea liniei ca produs, TVA-ul liniei ca produs, valoarea cu TVA ca
sumă — **nerecalculate aici**: liniile le poartă deja, derivate o dată de regula versionată de
rotunjire, iar totalul documentului e aceeași adunare pe care o arată registrul (`C19`, `C20`);
rândul 12 „TOTAL (pe factura fiscală)" ca sumă a coloanelor 10.5, 10.7, 10.8.

**Convenție, marcată ca atare în cod:** etichetele blocurilor de părți („Furnizor",
„Cumpărător/beneficiar"), liniile de semnătură, nota pentru retur (nota de credit are aceeași formă
ca livrarea, [ADR-073](073-forma-postarii-documentelor-comerciale.md) §7, iar `V1` nu spune nimic despre retur).
**Netipărit:** coloanele 10.9–10.12 (ambalaj, locuri, masă brută) — nucleul documentelor nu le
poartă; rândul 11 „TOTAL (pe pagină)" — o factură pe o pagină îl are egal cu rândul 12, una mai
lungă arată doar rândul 12; coloana 10.2 apare, dar linia de vânzare nu poartă încă unitatea de
măsură, deci e goală. Rândurile de antet ale formularului (punct de încărcare, delegat, foaia de
parcurs…) **nu au fost citite** în `V1` și nu se inventează.

**Refuzuri:** ciorna n-are număr, deci nu e documentul — `sales.not_printable`, 409 (`C10`);
documentul anulat își păstrează numărul și nu se înmânează nimănui — același refuz. Ce nu e vizibil
în context e 404, ca orice cititor al proiectului (IZ-04).

**Denumirile:** ale companiei prin `company_heading` (nou în `platform/tenancy/services/companies.py`
— denumirea legală și IDNO), ale partenerului prin `partner_in_context` (`legal_name`, `C39`), codul
TVA al partenerului **la data documentului** (`vat_registration_on`), nu de azi
([ADR-044](044-data-de-rezolutie.md)).

### 4.2 Fluturașul — ce e din lege și ce e convenție

Art. 142 alin. (3) prescrie trei elemente, în scris, la fiecare achitare: părțile componente ale
salariului, mărimea **și temeiurile** reținerilor, suma totală de primit. Nu prescrie formular,
denumire, suport, semnătură, limbă (`F2.X2 (h)` §5.2: la 30.08.2026 niciun act MF/SFS/Guvern nu
aprobă unul). Documentul are deci trei titluri — ale legii — iar restul (așezarea, blocul informativ
cu contribuțiile angajatorului, titlul „Fluturaș de salariu") e convenția platformei.

**Temeiul unei rețineri** se tipărește ca denumirea reținerii și cota aplicată; articolul care o
întemeiază **nu** se scrie — nu e în datele fluturașului, iar regula proiectului e să nu se scrie o
referință legală din memorie (`CLAUDE.md` §4). Când `fiscal` va purta referința actului pe parametru
(`OD-22`), fluturașul o poate tipări de acolo.

Fluturașul se construiește din **același dict** pe care îl produce `payslip()` pentru ecran și
pentru redarea text (`C20`): JSON-ul, textul și PDF-ul nu pot diverge.

## 5. Ce rămâne din `OD-74`

Jumătatea **Excel**. Nu se alege aici: o bibliotecă Excel n-are nimic în comun cu pipeline-ul de
tipar, iar `OD-74` spunea deja *„la primul client care cere Excel"*. Rapoartele F1.8 pot intra în
pipeline-ul de tipar când cineva le cere ca PDF — fiecare e un `PrintableDocument` de construit;
nu s-a cerut, deci nu s-a construit. Nu primește rând nou: e aceeași întrebare, cu jumătate răspuns,
și se redeschide de cine o pune.

## 6. Reversibilitate și declanșator

- **Biblioteca:** reversibilă la costul lui `render.py` — valoarea `PrintableDocument`, cele două
  constructoare de business și testele nu știu de ReportLab. Declanșator: un upgrade la care
  `types-reportlab` nu mai acoperă ce folosește `render.py`, sau un document a cărui formă platypus
  n-o poate produce (formular tipizat cu poziții absolute, cod de bare).
- **Determinismul** e proprietate testată, nu promisă: testul randează de două ori și compară
  octeții. Dacă un upgrade îl strică, testul cade înainte ca arhiva să primească două versiuni ale
  aceluiași document.
- **Fontul:** DejaVu Sans e alegere de acoperire, nu de estetică; se schimbă în `render.py` și în
  `fonts/`, cu licența nouă alături. Un font schimbat schimbă octeții tuturor documentelor
  regenerate — de aceea documentele deja emise se arhivează (`OD-52`), nu se regenerează.
- **Forma facturii** urmează ce s-a citit; orice rând de antet adăugat după citirea completă a
  anexei nr. 1 e o schimbare de constructor, nu de pipeline.

## 7. Ce nu s-a putut verifica

- **Textul curent al OMF 118/2017** rămâne cel din `V1`: PDF-ul SFS din 2021, OMF nr. 158/2024
  necitit (pagină cu plată). Coloanele 10.1–10.8 nu poartă notă de modificare în textul citit.
- **Randarea pe un cititor real de PDF** — s-a verificat prin `pypdf` (text, ordine, diacritice) și
  prin deschiderea fișierului de probă, nu printr-o suită de randare vizuală.
- **Roțile `reportlab` pe imaginea de producție** — verificate pe această mașină (Linux x86_64,
  CPython 3.13); `uv.lock` poartă hash-urile, deci o platformă fără roată ar cădea la `uv sync`, nu
  la runtime.
