# `F2.X2 (a)` și `(g)` — Operațiunile cu numerar și ordinul de plată: actele, ce prescriu, ce n-a putut fi citit

- **Data cercetării:** 30 august 2026
- **Pentru:** `F2.X2 (a)`, `F2.X2 (g)`, `F2.A5`, `F2.A4`

---

> ## Statutul sursei — de citit înainte de a folosi orice cifră de aici
>
> **Niciun text de lege sau de hotărâre de Guvern n-a putut fi citit din Registrul de stat al actelor
> juridice.** `legis.md` întoarce **403** la `WebFetch`, la `curl` (inclusiv `downloadpdf/`) și nu are
> nicio captură utilă în Wayback: pentru HG 764/1992 nu există **nicio** captură (API `available` și
> CDX goale pentru șase forme de URL); pentru Legea 34/2024 și Legea 287/2017 capturile există
> (2022–2024), dar sunt **cochilii de 5 KB** — pagina încarcă textul prin script, iar scriptul n-a fost
> arhivat. `sfs.md` și `parlament.md` întorc 403 direct; SFS a fost citit **din Wayback** (captura
> cea mai recentă listată de CDX pentru pagina BGPF 408: **03.03.2024**; fișierul arhivat e tăiat la
> exact 1 MB, dar răspunsurile 34.1.5–34.1.6 sunt întregi). **Monitorul Oficial** e citit doar la
> nivel de **cuprins** (metadate), textul e cu plată.
>
> **Ce e primar și ce nu, pe fiecare act:**
> - **Regulamentul BNM 108/2023 (ordinul de plată)** — **text primar**, două fișiere de pe `bnm.md`
>   (PDF și DOCX consolidat) plus pagina actului. Singurul act din acest fișier citit integral.
> - **Legea 34/2024 (plafoanele de numerar)** — **nu s-a citit textul adoptat.** Cifrele vin din
>   **comunicatul oficial al Ministerului Finanțelor din 28.03.2025** (sursă administrativă, la un pas de
>   act) și din **proiectul Guvernului din 2023** (`old.gov.md`, text pre-adoptare — numerotarea
>   articolelor și cel puțin un termen **diferă** de legea adoptată, vezi §3.4).
> - **HG 764/1992 (Normele de casă)** — **nu s-a citit nimic primar.** Ce prescrie e reprodus de SFS în
>   BGPF, **într-un răspuns arhivat**; răspunsul curent al SFS **nu mai citează HG 764**. Statutul actului
>   (în vigoare / abrogat) **nu e stabilit** — vezi §2.2.
> - **Legea 287/2017 art. 11 (documente primare)** — doar parafraza SFS a alin. (1) și (4); lista de
>   elemente obligatorii din alin. (7) **nu s-a obținut**.
>
> **Consecință operațională pentru `F2.A5`:** nu există, în ce s-a putut citi, **nicio formă
> reglementată în vigoare** pentru dispoziția de încasare, dispoziția de plată sau registrul de casă
> (§2.4, §4). Plafoanele de numerar sunt ale Legii 34/2024, în vigoare de la **01.04.2025**, dar
> **articolul** fiecărui plafon în textul adoptat nu e confirmat (§3). Modulul poate reține
> valorile ca `confidence = provisional`, nu ca parametru `active`.

**Filtrul România a fost aplicat.** Fiecare sursă reținută e de pe `bnm.md`, `mf.gov.md`, `sfs.md`
(via Wayback), `gov.md`/`old.gov.md`, `monitorul.gov.md`, `statistica.gov.md`. Niciuna nu menționează
ANAF, MFP, OMFP 2634/2015 sau Legea 70/2015. Respinse explicit: `legislatie.just.ro` (apărut într-o
căutare după `lex.justice.md`), `amcham.md`, `comertbank.md`, `monitorul.fisc.md`, `contabilsef.md`,
`asg.md`, `ccfiscali.md`, `ibn.idsi.md`, `storage.mtender.gov.md` (formulare încărcate de ofertanți).
Mirror comercial folosit **doar pentru localizare**: niciunul — numerele de act au venit din căutări pe
domeniile oficiale.

---

## 1. Tabelul actelor

| Întrebare | Act | Identitate obținută | Text citit | Statut sursă |
|---|---|---|---|---|
| (a) casa: registru, dispoziții | **HG nr. 764 din 25.11.1992**, „Normele pentru efectuarea operațiunilor de casă în economia națională a RM" | număr, dată, titlu (`legis.md` doc_id 16140) | **nu** | SFS/BGPF, răspuns **arhivat** |
| (a) plafoane numerar | **Legea nr. 34/2024** privind efectuarea decontărilor în numerar și pentru modificarea unor acte normative | MO **nr. 86-88 din 01.03.2024**, poz. **129**; Decret nr. 1350-IX din 29.02.2024, poz. 128 | **nu** (proiect 2023 + comunicat MF) | MF comunicat 28.03.2025 |
| (a) plafon anterior | Legea nr. 845/1992, art. 10 pct. 5 | — (abrogat de Legea 34/2024, conform proiectului) | nu | SFS/BGPF |
| (a) documente primare | Legea nr. 287/2017, art. 11 | `legis.md` doc_id 120938 | **nu** | SFS/BGPF parafrază; BNS |
| (g) ordinul de plată | **Regulamentul BNM**, aprobat prin **HCE BNM nr. 108 din 08.06.2023** | MO **nr. 220-222 din 29.06.2023, art. 632**; în vigoare **05.08.2023**; modif. HCE 229/2025, MO 523-525/132 din 09.10.2025, în vigoare **09.04.2026** | **da**, integral | text primar, `bnm.md` |
| (g) predecesor | Regulamentul cu privire la transferul de credit, **HCA BNM nr. 157 din 01.08.2013** | MO **nr. 191-197 din 06.09.2013, art. 1370**; în vigoare 15.09.2013 | da (DOC de pe `bnm.md`) | text primar, abrogarea **neconfirmată** |

---

## 2. Operațiunile de casă — HG 764/1992

### 2.1 Identitatea

Singura identitate obținută e titlul din indexul `legis.md`: **„HG764/1992"**, `doc_id=16140` (și
`cautare/rezultate/16141`), cu descrierea reprodusă de motorul de căutare: *Hotărârea Guvernului nr. 764
din 25 noiembrie 1992 privind aprobarea Normelor pentru efectuarea operațiunilor de casă în economia
națională a Republicii Moldova*. **Numărul Monitorului, data publicării, data intrării în vigoare, lista
modificărilor: neobținute.** Sursa BGPF (mai jos) leagă actul de **Decretul Președintelui nr. 105 din
30.04.1992**.

Provenință: căutare web restrânsă la domenii oficiale (30.08.2026); `legis.md` 403 la toate metodele.

### 2.2 Statutul actului — nestabilit, cu un semnal contrar

Pagina BGPF **34.1.5 „Ce acte reglementează efectuarea operațiunilor de casă?"** are două versiuni pe
aceeași pagină (captura Wayback din 03.03.2024 a `sfs.md/ro/intrebare-baza-de-date-generalizare/408/`):

**Versiunea curentă** (etichetată *Ordin nr. 413, din 03.11.2022*) enumeră **patru acte, fără HG 764**:

> Actele normative care reglementează efectuarea operaţiunilor de casă în economia naţională a
> Republicii Moldova sunt: Legea nr.845-XII din 03.01.1992 cu privire la antreprenoriat şi
> întreprinderi. Legea nr.62-XVI din 21.03.2008 privind reglementarea valutară. Hotărîrea Guvernului
> nr.141 din 27.02.2019 cu privire la aplicarea echipamentelor de casă şi de control la efectuarea
> decontărilor. Hotărîrea Băncii Naţionale nr.157 din 01.08.2013 cu privire la aprobarea, modificarea,
> completarea şi abrogarea unor acte normative ale Băncii Naţionale a Moldovei

**Versiunea arhivată** (secțiunea „Arhiva", aceeași etichetă de ordin — *inferență:* eticheta e a
ordinului care a arhivat-o) citează Decretul 105/1992 și HG 764:

> În scopul asigurării executării prevederilor Decretului, prin Hotărârea Guvernului nr. 764 din 25
> noiembrie 1992, au fost aprobate Normele pentru efectuarea operațiunilor de casă în economia națională
> a Republicii Moldova (Norme).

La fel, **34.1.6**: versiunea curentă trimite la Legea 287/2017 art. 11 („entitatea va întocmi un
document primar conform prevederilor Legii"), versiunea arhivată reproduce Normele. **Comunicatul MF din
28.03.2025 despre Legea 34/2024 nu menționează HG 764.** BNS declară formularele Departamentului
Statisticii din 1995/1997 nevalabile (§4).

> **Ce înseamnă și ce nu.** SFS a scos HG 764 din răspunsurile sale în 2022. Asta e **compatibil** cu
> o abrogare, dar **nu o dovedește** — poate fi doar reformulare. Căutarea unui act de abrogare
> („se abrogă" + „nr. 764 din 25 noiembrie 1992") pe `gov.md`, `legis.md`, `sfs.md`, `mf.gov.md`,
> `cancelaria.gov.md`, `particip.gov.md`, `monitorul.gov.md` **n-a întors nimic**; proiectul HG
> 141/2019 (`old.gov.md`, `intr41_17.pdf`) nu conține „764". **Nu se scrie în cod nici că HG 764 e
> în vigoare, nici că nu e.** Se închide când se citește antetul de pe `legis.md`.

### 2.3 Ce prescriu Normele — reproducerea SFS, răspunsul arhivat 34.1.6

Nu există numere de puncte în reproducere. Citatul, integral:

> Conform Normelor pentru efectuarea operațiunilor de casă în economia națională a Republicii Moldova,
> aprobate prin Hotărârea Guvernului nr. 764 din 25 noiembrie 1992, operațiunile de casă sunt
> reglementate de documentele, formularele-tip interdepartamentale ale căror forme sunt aprobate și
> coordonate cu Ministerul Finanțelor, care în mod obligatoriu sunt folosite (fără schimbări) în toate
> întreprinderile, indiferent de subordonarea lor departamentală și formele de proprietate.
>
> Pentru efectuarea decontărilor contra numerar fiecare întreprindere trebuie să aibă casierie.
>
> Fiecare întreprindere tine un singur registru de casă, în care se ține evidența tuturor încasărilor
> și eliberărilor de numerar.
>
> De regulă, primirea numerarului este confirmată prin dispoziția de încasare, iar eliberarea de numerar
> – prin dispoziția de plată, întocmite respectiv.
>
> Înscrierile în registrul de casă se fac de către casier imediat după primirea sau eliberarea banilor
> pe fiecare dispoziție sau alt document de substituire. Zilnic, la sfârșitul zilei de lucru, casierul
> face totalul operațiunilor, transcrie restul de bani din casă pentru ziua următoare și predă
> contabilității, contra chitanță, exemplarul doi detașabil (copia înscrierilor din registrul de casă
> pentru ziua respectivă) cu documentele de casă de încasare și de cheltuieli, notificând acest lucru
> contra semnătură în registrul de casă.
>
> Răspunderea pentru respectarea disciplinei de casă este pusă în sarcina conducătorilor,
> contabililor-șef, conducătorilor serviciilor financiare și casierilor.

Tot răspunsul arhivat, despre numerarul eliberat spre decontare (atribuit Normelor, fără punct):

> Termenul de prezentare a raportului referitor la utilizarea numerarului primit pentru achiziționarea
> producției agricole, ambalajului și bunurilor de la populație, precum și pentru cheltuielile de
> deplasare nu va depăși 30 de zile calendaristice de la data primirii acestuia. Numerarul neutilizat
> trebuie să fie restituit în casa întreprinderii cel târziu în 5 zile de la expirarea termenului de
> prezentare a raportului referitor la utilizarea numerarului.

Și Decretul 105/1992, în răspunsul arhivat 34.1.5 — singurul loc unde apare un **termen de păstrare a
numerarului în casă**:

> c) au dreptul să păstreze în casele lor banii în numerar, primiți din instituțiile bancare pentru
> retribuirea muncii, plata îndemnizațiilor de asigurare socială, burselor pensiilor, cel mult trei zile
> lucrătoare, inclusiv ziua primirii banilor la instituția bancară;
>
> d) nu au dreptul să țină în casele lor bani în numerar, până la sosirea termenului de efectuare a
> plăților, întreprinderile, instituțiile și organizațiile care au încasări bănești permanente (…)

**Ce reiese pentru `F2.A5`, cu statutul de mai sus:** un singur registru de casă per întreprindere;
înscriere imediată, per dispoziție; **închidere zilnică** cu sold reportat; exemplarul doi detașabil predat
contabilității cu documentele zilei, contra semnătură; dispoziția de încasare și cea de plată ca
documente de bază. **Forma registrului, coloanele, cine semnează dispozițiile, numerotarea, arhivarea,
limita soldului de casă: neobținute** — motorul de căutare a indexat din pagina `legis.md` fragmente
despre un „registru de evidență a dispozițiilor de încasare și de plată", despre completarea „cu cerneală
sau pix" și despre obligația dispozițiilor de a indica temeiul și anexele, dar numai ca rezumat în
engleză, fără numere de puncte — **nu se citează**.

### 2.4 Formularele — nu există formă în vigoare identificată

Normele trimit la formulare-tip interdepartamentale. Biroul Național de Statistică, pagina „Formularele
tipizate de documente primare" (`statistica.gov.md/ro/formularele-tipizate-de-documente-primare-76_3877.html`,
citită 30.08.2026, pagină nedatată):

> Formularele tipizate de evidenţă primară aprobate de Departamentul Statisticii în anul 1995 şi 1997 nu
> sunt valabile, întrucît nu conţin toate elementele obligatorii prevăzute în art.19, alin.6 ale Legii
> contabilităţii nr. 113-XVI din 27.04.2007. În conformitate cu acest articol entitatea utilizează
> formulare tipizate de documente primare, aprobate de Ministerul Finanţelor. În lipsa formularelor
> tipizate sau dacă acestea nu satisfac necesităţile entităţii, entitatea elaborează şi utilizează
> formulare de documente, aprobate de conducerea ei, cu respectarea cerinţelor art.19, alin.(6). Astfel,
> entitate poate utiliza ca model formularele tipizate de evidenţă primară aprobate de Departamentul
> Statisticii în anul 1995 şi 1997 cu ajustarea şi aprobarea acestora în modul stabilit.

> Răspunsul e scris sub **Legea 113/2007, abrogată** de Legea 287/2017; norma echivalentă e azi art. 11
> alin. (4) (§4). Aceeași pagină: formularele **cu regim special** au trecut de la BNS la SFS prin **HG
> nr. 1008 din 28.12.2012** (modificând HG 294/1998), de la 08.02.2013 — lista lor (act de achiziție, bon
> de plată, chitanțe 1-SF/2-SF, factura de expediție) **nu conține** dispoziția de încasare, dispoziția
> de plată sau registrul de casă.

**Niciun ordin al Ministerului Finanțelor care să aprobe un formular curent de „Dispoziție de încasare",
„Dispoziție de plată" sau „Registru de casă" n-a fost găsit** pe `mf.gov.md`, `sfs.md`, `legis.md`,
`statistica.gov.md`. Cele două ordine MF aterizate în căutări nu sunt acesta: OMF 118/2017 (factura
fiscală, deja în repo, `v1-factura-fiscala-omf-118-2017.md`) și OMF 215/2015 (execuția de casă a bugetelor
prin trezorerie; PDF de pe `mf.gov.md`, citit — nu privește entitățile).

> **Consecință pentru `F2.A5`:** dacă nu apare un formular MF, forma dispozițiilor și a registrului o
> stabilește entitatea, cu elementele obligatorii din art. 11 alin. (7) al Legii 287/2017 — **listă pe
> care acest fișier n-a putut-o citi.** Nu se generează documentul cu un set de câmpuri dedus.

---

## 3. Plafoanele de numerar — Legea nr. 34/2024

### 3.1 Identitatea

Cuprinsul Monitorului Oficial **nr. 86-88, vineri 01 martie 2024** (`monitorul.gov.md/ro/monitor/2864`,
citit 30.08.2026), Partea I, verbatim:

> 128. Decret pentru promulgarea Legii privind efectuarea decontărilor în numerar și pentru modificarea
> unor acte normative (nr. 1350-IX, 29 februarie 2024)
>
> 129. Lege privind efectuarea decontărilor în numerar și pentru modificarea unor acte normative (nr. 34,
> 29 februarie 2024)

*Inferență:* în Partea I a MO numărul din cuprins e numărul articolului, deci **art. 129** (legea) și
**art. 128** (decretul). **Data legii apare în cuprins ca 29 februarie 2024** — aceeași cu a decretului;
data adoptării în Parlament nu e confirmată de nicio sursă citită. `legis.md` o indexează ca
`LP34/2024`, `doc_id=142089` (și 146596, probabil versiune consolidată — *inferență*).

### 3.2 Intrarea în vigoare

Comunicatul MF (`mf.gov.md`, „Comunicat informativ privind noile reglementări aferente decontărilor în
numerar", *Vin, 28/03/2025 - 16:34*):

> Începând cu 01 aprilie 2025 intră în vigoare prevederile Legii nr. 34/2024 privind efectuarea
> decontărilor în numerar şi pentru modificarea unor acte normative, care stabilesc cadrul normativ de
> bază privind efectuarea decontărilor aferente operaţiunilor de plată pe teritoriul Republicii Moldova,
> modul şi limitele de efectuare a decontărilor, controlul respectării noilor prevederi, precum şi
> sancţiunile aplicabile.

**Clauza din lege n-a fost citită.** Proiectul Guvernului (2023) avea la art. 11 alin. (1) *„Prezenta lege
intră în vigoare la expirarea a 3 luni de la data publicării"* — textul adoptat e altul (13 luni după
publicare), deci **proiectul nu e o sursă pentru clauzele finale.**

### 3.3 Plafoanele — din comunicatul MF, verbatim

Cui se aplică:

> persoanelor juridice, indiferent de tipul de proprietate sau forma juridică de organizare, cu excepţia
> autorităţilor şi instituţiilor publice; reprezentanţelor permanente şi sucursalelor persoanelor juridice
> nerezidente; organizaţiilor necomerciale; persoanelor fizice care desfăşoară o activitate de
> întreprinzător; persoanelor fizice care desfăşoară o activitate profesională în sectorul justiţiei sau
> în domeniul sănătăţii (…); persoanelor fizice care nu desfăşoară o activitate de întreprinzător şi care
> cumpără bunuri imobile sau mijloace de transport de la alte persoane fizice (…)

Plăți:

> În cazul în care este vorba despre operațiunile de plăți efectuate între agenți economici, atunci
> limita de efectuare a plăților în numerar este de 100 000 lei cumulativ lunar.
>
> În cazul în care este vorba despre operațiuni de plăți efectuate de la un agent economic către o
> persoană fizică ce nu desfășoară activitate de întreprinzător, limita de efectuare a plăților în
> numerar este de 100 000 lei cumulativ lunar, cu excepțiile reflectate în tabelul următor.

| Obiectul plății agent economic → persoană fizică | Limită (MF, tabelul 2) |
|---|---|
| deșeuri și reziduuri de metale feroase/neferoase, reziduuri industriale cu metale | 100 000 lei cumulativ anual |
| ambalaj returnabil, deșeuri de hârtie, carton, cauciuc, plastic, sticlă, acumulatoare uzate | 100 000 lei cumulativ anual |
| dividende | 100 000 lei cumulativ anual per asociat/acționar |
| plăți în temeiul contractelor de împrumut | 100 000 lei cumulativ anual |
| producție de fitotehnie și horticultură în formă naturală | 200 000 lei cumulativ anual |
| producție zootehnică în formă naturală, masă vie și sacrificată | 300 000 lei cumulativ anual |
| către persoană fizică cu activitate în achiziții de fitotehnie/horticultură/regn vegetal/zootehnie | 600 000 lei cumulativ anual |

Încasări:

> În cazul operațiunilor de încasări percepute de un agent economic de la o persoană fizică ce nu
> desfășoară activitate de întreprinzător, limita încasărilor în numerar este de 100 000 lei pentru o
> plată.
>
> În cazul operațiunilor de încasări percepute de persoanele ce desfășoară activitate profesională în
> sectorul justiţiei sau în domeniul sănătăţii, limita de încasare a plăţilor în numerar pentru
> serviciile prestate este de 100 000 lei cumulativ anual, aceasta aplicându-se per fiecare beneficiar
> (persoană fizică sau juridică) în parte.

Fără limită:

> remunerare a muncii şi plată a altor drepturi salariale generate în temeiul relaţiilor de muncă;
> acordare de credite de către bănci, organizaţii de creditare nebancară, asociaţii de economii şi
> împrumut (…); prestare a serviciilor de plată şi de emitere a monedei electronice (…); atragere de
> depozite (…); efectuare a decontărilor cu autorităţile şi instituţiile publice; plată a cauţiunilor, a
> garanţiilor (…); achitare a obligaţiilor fiscale, a plăţilor şi a amenzilor faţă de bugetul public
> naţional.

Imobile și mijloace de transport între persoane fizice: 100, respectiv 50 de salarii medii lunare pe
economie prognozate (16 100 lei pentru 2025, HG nr. 845/2024), peste care plata e prin transfer „cu
excepţia sumei de până la 200 000 lei, care poate fi achitată în numerar"; comisionul de retragere
plafonat la 0,1%.

„Anual" în 2025:

> pentru anul 2025, prin noțiunea de „anual" prevăzută la unele limite de efectuare a operațiunilor de
> plăți și încasări, se vor lua în considerare plățile, încasările înregistrate în perioada 01 aprilie
> 2025 – 31 decembrie 2025.

> **Pentru registrul de parametri:** plafoanele „anuale" au în 2025 o fereastră de **nouă luni**, nu un
> an calendaristic. Un `valid_from` pe 01.04.2025 nu e suficient — agregarea „cumulativ anual" trebuie
> să știe că perioada de referință a anului 2025 începe la 01.04, nu la 01.01. Aceeași lecție ca la
> pragul TVA din `od-22-tva.md` §7.3.

### 3.4 Casieria — eliberarea numerarului spre decontare

Comunicatul MF:

> agentul economic, dar și persoanele fizice ce desfășoară activitate de întreprinzător în sectorul
> justiției și în domeniul sănătății, pot elibera numerar spre decontare pentru un termen ce nu va depăși
> 30 de zile, cu excepția cheltuielilor pentru deplasările peste hotarele Republicii Moldova.
>
> Ulterior, numerarul rămas și neutilizat după efectuarea cheltuielilor prenotate, necesită a fi
> restituit în casieria entității în termen de 5 zile lucrătoare de la expirarea termenului pentru care
> acesta a fost eliberat.

Proiectul Guvernului (2023, `old.gov.md/.../subiect-02-nu-695-mf-2023.pdf`, art. 7) avea **15 zile
lucrătoare** — dovada că textul adoptat s-a schimbat față de proiect. Din același proiect, art. 7 alin.
(3)–(5), **nereconfirmat în legea adoptată**:

> (3) Persoanele care au primit numerar spre decontare sunt obligate să prezinte în contabilitatea
> entității o dare de seamă, cu anexarea actelor confirmative, privind sumele utilizate.
> (4) Eliberarea de numerar spre decontare aceleiași persoane se efectuează numai cu condiţia prezentării
> dării de seamă complete asupra sumelor eliberate anterior spre decontare.
> (5) Persoana responsabilă eliberează banii numai persoanei indicate în documentul primar de plată. Dacă
> banii se eliberează printr-o procură (…) în textul dispoziției, după numele, prenumele/ denumirea și
> codul fiscal al primitorului, persoana responsabilă indică numele, prenumele și codul fiscal al
> persoanei care primește banii prin procură.

> **Limita soldului de casă.** Proiectul avea la **art. 4** o obligație de a stabili anual „necesarul de
> numerar minim pentru efectuarea decontărilor pentru 3 zile lucrătoare" și de a depune surplusul în
> cont, cu amendă 500–5 000 lei (art. 8 alin. (5) din proiect). **Comunicatul MF nu menționează nimic
> din acestea.** Nu se știe dacă norma a supraviețuit adoptării. **Nu se implementează un plafon de sold
> pe baza proiectului.**

### 3.5 Sancțiunile (MF, tabelul 3)

| Încălcare | Sancțiune |
|---|---|
| plată agent economic → agent economic peste 100 000 lei cumulativ lunar | 3%–10% din suma peste limită |
| încasare peste 100 000 lei per plată / peste 100 000 lei anual (liber-profesioniști) | (tabelul MF nu pune cifră în celulă) |
| nerestituirea numerarului neutilizat în casierie | 10%–18% din suma nerestituită, aplicată entității care l-a eliberat |
| restituirea cu întârziere | 0,1% pe zi, maximum 5% per caz |

> În cazul în care amenda se achită în termen de 3 zile lucrătoare din momentul aducerii la cunoștință a
> deciziei privind cazul de încălcare fiscală, persoana sancționată poate achita doar 50% din suma
> amenzii.

Controlul: SFS, „în cadrul controalelor fiscale planificate".

### 3.6 Ce a abrogat și ce se pregătește

Proiectul 2023, art. 11 alin. (2): la intrarea în vigoare, **Legea 845/1992**: „la articolul 6,
subalineatele al optulea și al nouălea se exclude", „la articolul 10, punctul 5 se abrogă"; **Codul
contravențional**: „articolul 293 se abrogă". Avizul Guvernului la inițiativa nr. 371/25.11.2025
(`gov.md/.../2026-02/Aviz-371-2025.pdf`) confirmă indirect: vorbește despre „dispozițiilor care erau
aplicabile până la intrarea în vigoare a Legii nr. 34/2024 și care s-au abrogat odată cu intrarea în
vigoare a acesteia" și despre Legea 845/1992 ca „lege care în curând urmează a fi abrogată".

**Regimul anterior (până la 31.03.2025)** — Legea 845/1992 art. 10 pct. 5, în reproducerea SFS (34.1.6,
versiunea curentă): plăți în numerar „inclusiv prin intermediul terminalului de plată în numerar
(terminalului cash-in), în sumă ce depăşeşte cumulativ plafonul lunar de 100 000 de lei (…) se aplică
sancţiuni conform legislaţiei"; versiunea arhivată: „sancțiuni pecuniare în proporție de 10 la sută din
sumele plătite".

**Modificări ale Legii 34/2024:** niciuna identificată în sursă oficială. **În lucru, toate
neadoptate la data cercetării:** inițiativa legislativă nr. 371 din 25.11.2025 (abrogarea legii — aviz
negativ al Guvernului, MO nr. 96-99 din 26.02.2026, Partea II poz. 17); inițiativa nr. 402 din
11.12.2025 (modificare — aviz al Guvernului, ședința din martie 2026); proiectul propriu al MF „pentru
modificarea Legii nr. 34/2024", stadiu „Inițierea elaborării proiectului", pagină datată 21.04.2026.
Mirror-uri comerciale anunță „modificări operate" — **nu s-au verificat, nu se preiau.**

---

## 4. Documentele primare — Legea 287/2017, art. 11

Textul legii: **necitit** (`legis.md` `doc_id=120938`, 403; capturile Wayback 2020–2022 sunt cochilii;
pagina MF „Legea contabilității și raportării financiare Nr. 287" doar face link spre `legis.md`).

Parafraza SFS, BGPF 34.1.6, versiunea curentă:

> Potrivit prevederilor art. 11 alin. (1) și (4) din Lege, faptele economice se contabilizează în temeiul
> documentelor primare. Entitatea utilizează formulare tipizate de documente primare aprobate de
> Ministerul Finanțelor și alte autorități publice sau poate elabora și utiliza formulare de documente
> primare, aprobate de conducerea acesteia, cu respectarea prevederilor alin.(7) și (8).
> Suplimentar elementelor prevăzute la alin. (7), documentele primare pot conține și alte elemente, în
> funcție de prevederile actelor normative și necesitățile informaționale ale entității.

**Alin. (7) — lista elementelor obligatorii — neobținut.** Singura sursă oficială găsită care o
citează (Ghidul SFS pentru gospodăriile țărănești, PDF) e arhivată în Wayback **trunchiată la 1 MB**,
ilizibilă. Sancțiunea pentru neîntocmire (SFS, același răspuns): Codul contravențional art. 295 alin.
(1)–(2), 25–50 u.c. persoana cu funcție de răspundere, 50–75 u.c. persoana juridică.

---

## 5. Ordinul de plată — Regulamentul BNM 108/2023

### 5.1 Identitatea, verbatim din antetul actului (`bnm.md`, DOCX consolidat și pagina actului)

> REGULAMENT cu privire la transferul de credit, debitarea directă și atribuirea codurilor IBAN
> Publicat în Monitorul Oficial al Republicii Moldova nr.220-222 din 29.06.2023, art.632
> Modificat prin: HCE al BNM nr. 229 din 02.10.2025, MO al RM nr.523-525/132 din 09.10.2025, în vigoare
> din 09.04.2026
> Înregistrat la Ministrul Justiției al Republicii Moldova nr. 1803 din 22 iunie 2023
> APROBAT prin Hotărârea Comitetului executiv al Băncii Naționale a Moldovei nr. 108 din 8 iunie 2023
> În vigoare: din 5 august 2023

Pagina actului trimite la `legis.md` `doc_id=151132`. **Textul Hotărârii nr. 108 (dispozitivul, cu
clauza de intrare în vigoare și abrogările) nu e publicat pe pagina BNM** — „5 august 2023" e antetul,
nu clauza. Fișiere citite: `bnm.md/files/Reg_TrCrDDSEPA+IBAN_ro.pdf` (20 pagini, text, fără note de
modificare — *inferență:* redacția 2023), `bnm.md/files/Reg_TrCrDDSEPA+IBAN_ro (1).docx` (consolidat,
antetul de mai sus, cu HCE 229/2025), `bnm.md/files/Reg_TrCrDDSEPA+IBAN_ro_1.pdf` (23 pagini, **scanat**,
fără strat de text, necitit).

> **Capcană de fișier.** `bnm.md/files/normative_act/anexe_108.pdf`, deși numit „108", conține
> **anexele Regulamentului din 2013** (note „modificat prin HCA al BNM nr. 56 din 05.03.2015",
> „Inspectoratul Fiscal Principal de Stat", număr „maximum 10 simboluri"). Nu se folosește pentru
> regulamentul curent.

### 5.2 Predecesorul și abrogarea lui — neconfirmată

Antetul DOC-ului de pe `bnm.md` (`Reg_ TrCR_RO_04_09 - ftch.doc`):

> Regulamentul cu privire la transferul de credit, aprobat prin HCA al BNM nr.157 din 01.08.2013
> Publicat în Monitorul Oficial al Republicii Moldova nr.191-197 din 06.09.2013, art.1370
> În vigoare: din 15 septembrie 2013
> Modificat și completat prin: HCA al BNM nr. 190 din 23 septembrie 2014, MO al RM nr. 325-332/1530 din
> 31.10.2014; HCA al BNM nr. 56 din 05 martie 2015, MO al RM nr.94-97/681 din 17.04.2015, în vigoare din
> 01.01.2016; HCA al BNM nr. 158 din 16 iunie 2016, MO al RM nr.184 – 192/1151 din 01.07.2016, în vigoare
> din 01.08.2016; HCE al BNM nr. 203 din 09 august 2018, MO al RM nr. 321-332/1314 din 24.08.2018; HCE al
> BNM nr. 179 din 27 iunie 2019, MO al RM nr.223-229/1270 din 12 iulie 2019, în vigoare din 01.09.2019

Pagina veche a actului pe `bnm.md` întoarce azi **„Nu am găsit pagina"**; capturile Wayback (2016–2021)
n-au putut fi descărcate (conexiune întreruptă, două încercări). Regulamentul 108/2023 acoperă același
obiect și mai mult; **actul care abrogă HCA 157/2013 nu s-a citit** — ar trebui să fie chiar HCE
108/2023. SFS încă cita „Hotărîrea Băncii Naţionale nr.157" în 2022 (§2.2).

### 5.3 Ce prescrie despre ordinul de plată — Capitolul II, verbatim (PDF; DOCX identic în substanță)

> 6. Transferul de credit poate fi efectuat atât în moneda națională, cât şi în valută, conform
> prevederilor actelor normative.
> 7. În funcţie de solicitarea clientului, transferul de credit în moneda naţională poate fi efectuat în
> regim de urgenţă (transfer urgent) sau în regim normal (transfer normal).
> 8. Prestatorul de servicii de plată al plătitorului trebuie să includă pentru un ordin de plată de tip
> transfer de credit elemente obligatorii stabilite în anexa nr. 1 sau anexa nr. 2.
> 9. Ordinul de plată utilizat la efectuarea transferului de credit atât în moneda naţională, cât şi în
> valută, trebuie să conţină elementele obligatorii menţionate în anexa nr. 1, respectiv anexa nr. 2,
> fiind prezentat pe suport hârtie sau transmis în formă electronică prin intermediul sistemelor
> automatizate de deservire la distanţă sau prin intermediul altor sisteme electronice de plată ale
> prestatorilor de servicii de plată.
> 10. Odată ce elementele obligatorii menţionate în anexa nr.1/anexa nr.2 devin disponibile în formă
> electronică, operațiunile de plată trebuie să permită o procesare electronică complet automată (…)
> 11. Modul de completare al ordinului de plată utilizat la efectuarea transferului de credit, destinat
> transferului mijloacelor băneşti în/din bugetul public naţional, este reglementat de către Ministerul
> Finanţelor cu respectarea cerinţelor stabilite în prezentul regulament.
> 12. Ordinul de plată se întocmeşte în limba română. La întocmirea ordinului de plată utilizat pentru
> efectuarea transferului de credit internațional, elementele utilizate în sistemele de plăţi
> internaţionale se completează într-o limbă străină, conform practicii internaţionale. În ordinul de
> plată nu se admit corectări şi/sau ştersături.
> 13. Ordinul de plată pe suport hârtie se prezintă la prestatorul de servicii de plată al plătitorului
> în numărul de exemplare necesar părţilor.
> 14. Ordinul de plată se prezintă/transmite spre executare la prestatorul de servicii de plată al
> plătitorului de către plătitor sau de către persoana împuternicită a acestuia în ziua în care a fost
> emis (…)
> 15. Prestatorii de servicii de plată vor ține evidența transferurilor de credit efectuate în baza
> ordinelor de plată pe suport hârtie și a celor transmise de către plătitor în mod electronic (…)
> conform prevederilor Legii contabilității și raportării financiare nr. 287/2017, în modul stabilit de
> prestatorul de servicii de plată.

> **Formular sau set de date?** **Set de date.** Regulamentul nu conține nicio machetă, nicio dimensiune
> de rubrică, niciun „formular nr."; prescrie **elemente**, pe hârtie sau electronic (pct. 9), cu limita
> de lungime a fiecărui element. Singura formă impusă e a plăților către buget, delegată MF (pct. 11) —
> act separat, necăutat aici. Pentru `F2.A4`, ordinul de plată MDL e un **document de date cu 13
> elemente obligatorii**, în română (pct. 12, consonant cu `C38`), fără corecturi.

### 5.4 Anexa nr. 1 — elementele ordinului de plată în moneda națională, redacția consolidată (DOCX)

> Elementele ordinului de plată utilizat la efectuarea transferului de credit prin intermediul SAPI
> I. Obligatorii:
> 1. Denumirea documentului de plată.
> 2. Tipul documentului de plată nr.1.
> 3. Numărul ordinului de plată, maximum 12 simboluri.
> 4. Data emiterii ordinului de plată (ziua şi anul în cifre, luna în litere).
> 5. Suma de plată în cifre, maximum 15 simboluri, urmată de suma exprimată în litere, maximum 150
> simboluri.
> 6. Denumirea/numele şi prenumele plătitorului/beneficiarului plății conform documentului care certifică
> înregistrarea/identitatea acestuia, cu indicarea apartenenţei plătitorului/beneficiarului plății la
> categoria de rezident/nerezident conform legislaţiei valutare, maximum 105 simboluri.
> 7. Codul IBAN al plătitorului/beneficiarului plății, 24 simboluri. În cazul în care utilizatorul
> serviciilor de plată se deserveşte la un prestator de servicii de plată nebancar ce nu participă la
> sistemul de compensare cu decontare pe bază netă, se indică de către acesta numărul codului IBAN al
> prestatorului de servicii de plată nebancar atribuit de un prestator de servicii de plată în vederea
> prestării serviciilor de plată.
> 8. Codul fiscal al plătitorului, respectiv codul fiscal al beneficiarului plății, maximum 13 simboluri.
> În cazul în care plătitorul/beneficiarul plății este o persoană nerezidentă, care nu deține cod fiscal,
> se indică alte date de identificare a plătitorului/beneficiarului plății*, câmpul respectiv va avea în
> total maximum 30 simboluri.
> 9. Destinaţia plăţii – se indică scopul plăţii/transferului şi se face referință la documentele
> relevante în baza cărora se efectuează plata/transferul, în cazul presatorului intermediar – se indică
> și denumirea/numele și prenumele plătitorului, precum și numărul contului de plăți/codul IBAN al
> plătitorului, iar în cazul în care utilizatorul serviciilor de plată se deserveşte la un prestator de
> servicii de plată nebancar ce nu participă la sistemul de compensare cu decontare pe bază netă, se
> indică şi beneficiarul plății, precum şi numărul contului de plăţi sau codul IBAN al acestuia, maximum
> 420 simboluri.
> 10. Tipul transferului, cu indicarea regimului de transfer - de tip normal/urgent.
> 11. Menţiunile emitentului - se aplică semnătura/ile persoanelor cu drept de semnătură şi, după caz (în
> cazul în care emitentul dispune de ştampilă), ştampila emitentului; în cazul ordinului de plată întocmit
> şi transmis în mod electronic, se efectuează autentificarea electronică a documentului de plată în
> conformitate cu condiţiile contractuale şi legislaţia în vigoare.
> 12. Data executării – se completează de către prestatorul de servicii de plată (…)
> 13. Menţiunile prestatorului de servicii de plată al plătitorului - se aplică, pe toate exemplarele
> părţilor implicate, semnătura şi ştampila prestatorului de servicii de plată privind acceptarea sau
> refuzul ordinului de plată, se indică codul tranzacţiei (maximum 3 simboluri) în conformitate cu
> Regulamentul cu privire la SAPI, aprobat prin Hotărârea Comitetului executiv al Băncii Naționale a
> Moldovei nr. 179/2019, şi data primirii ordinului de plată (…)
> II. Opţionale:
> Denumirea prestatorului de servicii de plată al plătitorului/prestatorului de servicii de plată al
> beneficiarului plății, maximum 105 simboluri.
> LEI al plătitorului și al beneficiarului în cazul în care aceștia sunt persoane juridice, sau, în lipsa
> LEI, orice identificator oficial echivalent disponibil.**
> *Prin alte date de identificare se înțeleg: (i) adresa plătitorului/beneficiarului plății, inclusiv
> denumirea țării (ii) numărul documentului personal oficial al plătitorului/beneficiarului plății (iii)
> data și locul nașterii plătitorului/beneficiarului plății.
> **În cazul în care LEI/identificatorul oficial echivalent disponibil este furnizat de plătitor,
> prestatorul de servicii de plată îl va include în mod obligatoriu în ordinul de plată.

**Diferențe între PDF (redacția 2023) și DOCX (consolidat cu HCE 229/2025, în vigoare 09.04.2026)** —
*inferență* că sunt ale HCE 229/2025, DOCX-ul nu poartă note per punct, doar un „Abrogat." după pct. 24:
pct. 8 — în PDF: „În cazul în care plătitorul/beneficiarul plății este o persoană nerezidentă, câmpul
respectiv va avea în total maximum 30 simboluri. (…) care nu deţine cod fiscal, rubrica dată nu se
completează"; în DOCX: se cer „alte date de identificare" (nota *); elementul opțional **LEI** — nou în
DOCX; pct. 12 — „internațional" (PDF) devine „transfrontalier" (DOCX); SAPI — „sistemul automatizat de
plăți interbancare" (PDF) / „interne" (DOCX). Elementele 1–13 și lungimile lor sunt **identice** în ambele.

Pentru istoric, Anexa nr. 2 la Regulamentul din 2013 (fișierul `anexe_108.pdf`) avea aceleași elemente
numerotate 1–16 (cu 8 și 10 excluse prin HCA 56/2015), numărul ordinului „maximum 10 simboluri", „numărul
contului de plăţi (…) maximum 21 simboluri sau codul IBAN (…) maximum 24 simboluri", codul băncii
„maximum 11 simboluri", destinația „maximum 210 simboluri", codul subdiviziunii „atribuit de către
Inspectoratul Fiscal Principal de Stat, maximum 4 simboluri". **Un import de ordine vechi trebuie să
accepte 10 caractere la număr și 210 la destinație; unul curent, 12 și 420.**

Anexa nr. 2 (transfer internațional, 21 elemente obligatorii + 4 opționale) e citită și e în fișierul
de lucru; nu se reproduce aici — `F2.A4` privește MDL.

### 5.5 Ce urmează

`bnm.md`, anunț din **04.02.2026**: inițierea modificării Regulamentului 108/2023 (aliniere la
Regulamentul (UE) 260/2012), fără conținut publicat. Anunț din **27.07.2026** (consultare până la
**13.08.2026**): proiect HCE „pentru modificarea unor acte normative ale BNM (aspecte privind transferul
de credit și debitarea directă)", aplicabil „la data intrării în vigoare a tratatului de aderare" —
*rezumatul paginii, textul proiectului necitit*. Niciunul nu e adoptat la data cercetării.

---

## Ce nu s-a putut verifica

Fiecare poziție e un blocaj real, cu ce s-a încercat.

1. **Textul HG 764/1992 — necitit.** `legis.md` 403 la `WebFetch`, la `curl` (`getResults`,
   `downloadpdf/16140`); Wayback: API `available` și CDX fără nicio captură pentru `doc_id=16140`
   (ro/ru), `rezultate/16140`, `rezultate/16141`, `downloadpdf/16140`; `lex.justice.md` (portalul
   vechi al MJ) — căutarea n-a produs un id de document. **Numerele punctelor, forma registrului, cine
   semnează, numerotarea, arhivarea, limita soldului: toate lipsesc.**
2. **Statutul HG 764/1992 (în vigoare/abrogat) — nestabilit.** Căutare de act abrogator pe șapte
   domenii oficiale: nimic. Semnalul contrar (SFS a scos actul din răspunsuri în 2022) e descris în §2.2
   și **nu se tratează ca abrogare**.
3. **Formularul dispoziției de încasare / de plată / registrului de casă — niciun act în vigoare
   găsit.** BNS declară nevalabile formularele din 1995/1997; niciun ordin MF de aprobare găsit pe
   `mf.gov.md`, `sfs.md`, `legis.md`, `statistica.gov.md` (căutări cu „formular tipizat", „KO-1/CO-1",
   „formular interdepartamental").
4. **Legea 34/2024 — textul adoptat necitit.** `legis.md` `doc_id=142089` și `146596`: 403; capturi
   Wayback 15.03.2024, 13.08.2024, 14.11.2024 (ru): cochilii de 5–6 KB; `parlament.md` 403 și fără
   captură; SFS „Ordinele BGPF 1298" fără captură. **Articolul fiecărui plafon, clauza de intrare în
   vigoare, lista completă a abrogărilor, soarta art. 4 din proiect (necesarul minim de numerar) —
   neconfirmate.** Proiectul din 2023 diferă demonstrabil de legea adoptată (15 → 30 de zile).
5. **Data adoptării Legii 34/2024.** Cuprinsul MO o dă ca „29 februarie 2024", identic cu decretul.
   Nicio altă sursă oficială citită nu dă data. Se reține cum apare, cu semnul de întrebare.
6. **Modificări ale Legii 34/2024 după 01.04.2025 — niciuna confirmată, două inițiative parlamentare
   și un proiect MF în lucru** (§3.6). Ce anunță mirror-urile comerciale ca „modificări operate" nu s-a
   verificat.
7. **Legea 287/2017 art. 11 alin. (7) — lista elementelor obligatorii ale documentului primar,
   neobținută.** `legis.md` `doc_id=120938`: 403, capturi Wayback-cochilie; ghidul SFS care o citează e
   arhivat trunchiat la 1 048 576 de octeți (descărcare pe intervale — serverul raportează exact
   această lungime); pagina MF a legii face doar link.
8. **Regulamentul BNM 108/2023 — dispozitivul Hotărârii nr. 108** (clauza de intrare în vigoare,
   abrogarea HCA 157/2013) **necitit**: pagina BNM publică doar regulamentul; `legis.md` `doc_id=151132`
   403 și fără captură.
9. **HCE 229/2025 — conținutul exact al modificării** necitit; diferențele PDF/DOCX din §5.4 îi sunt
   atribuite prin inferență. Pagina anunțului din 04.02.2026 nu enumeră schimbările.
10. **PDF-ul scanat `Reg_TrCrDDSEPA+IBAN_ro_1.pdf`** (23 pagini, probabil versiunea semnată) —
    fără OCR disponibil în mediu; necitit.
11. **Reglementarea MF a ordinului de plată către buget** (pct. 11 din Regulament) — necăutată; e alt
    act.
12. **Regimul anterior în cifre** (Legea 845/1992 art. 10 pct. 5, 10%) e doar reproducerea SFS; textul
    legii necitit. Relevant numai pentru perioade până la 31.03.2025.
