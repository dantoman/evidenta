# `F2.X2 (k)` — IRM19 și Codul muncii art. 49: ce câmpuri cere un act contractului de muncă

- **Data cercetării:** 30 august 2026
- **Pentru:** `F2.X2 (k)`, `F2.B1` (câmpurile lui `employment_contract`), `F2.C2` (raportarea
  angajatorului), [ADR-065](../../decisions/065-schema-salarizarii.md) §11 — punctul care spune
  că lista de câmpuri e *derivată din ce consumă calculul, nu transcrisă dintr-un act citit*
- **Actele:** Ordinul MF nr. 126/2017 (formularele IPC18 / **IRM19** / CAS18-AN și cele trei
  clasificatoare), Ordinul MF nr. 33/2019 (actul care introduce IRM19), Codul muncii nr. 154/2003
  **art. 49**, Convenția colectivă (nivel național) nr. 4/2005 (modelul contractului)
- **Descărcări:** scratchpad-ul sesiunii, `x2k/` — consolidarea SFS a Ordinului 126/2017
  (`omf126.pdf`), formularul IRM19 (`irm19_form_wb.pdf`), instrucțiunea de pe `raportare.gov.md`
  (`rap_anexa4.bin`), proiectul MF din februarie 2019 (`instructiune_irm.doc`), proiectul MF 2026
  (`att_32144.bin`), Codul muncii consolidat (`cm_usmf.pdf`), convențiile colective CNSM
  (`cc_sindicate.pdf`), dosarul guvernamental `NU-455-MMPS-2025_0.pdf`

---

> ## Statutul sursei — de citit înainte de a folosi orice câmp de aici
>
> **Textul adoptat al niciunuia dintre cele patru acte n-a fost citit în forma publicată.**
> `legis.md` întoarce **403 Cloudflare** la 30.08.2026 pe toate căile încercate — pagină, căutare,
> `downloadpdf` — inclusiv cu antet complet de browser (`User-Agent`, `Accept`, `Accept-Language`,
> `Referer`, `Sec-Fetch-*`); Wayback nu are nici pagini utile, nici PDF-uri pentru id-urile cerute.
> `sfs.md` întoarce **403** direct. Monitorul Oficial e cu plată pe text.
>
> **Ce s-a schimbat față de `f2-x2-formularele-sfs.md`: Wayback Machine este accesibil în această
> sesiune.** Ceea ce acolo era blocat (`web.archive.org` refuzat de unealtă, `curl` 000/503) a
> funcționat acum prin `curl`, iar asta a deschis `sfs.md`. **Dosarul de față stă în bună parte pe
> instantanee Wayback ale paginilor `sfs.md`**, nu pe fragmente indexate.
>
> Ce **s-a putut citi**, în ordinea forței probante:
>
> 1. **`monitorul.gov.md`, pagina de ediție** — cuprinsul public. **Toate identitățile MO de aici
>    vin de acolo**, citite la 30.08.2026, cu excepțiile marcate. Ediția `monitor/2102` (MO 59-65
>    din 22.02.2019) a fost deschisă și citită rând cu rând.
> 2. **`raportare.gov.md`** — portalul de raportare electronică administrat de SFS. Servește
>    **anexele Ordinului 126/2017 în formă consolidată**. Certificatul e emis pe
>    `O=SERVICIUL FISCAL DE STAT`, dar serverul **nu trimite intermediarul**; descărcarea s-a făcut
>    adăugând certificatul intermediar Certum luat din AIA-ul propriu al lanțului, **nu**
>    dezactivând verificarea.
> 3. **`sfs.md` prin Wayback** — formularul IRM19 (instantaneu **16.06.2024**), instrucțiunea
>    (instantanee 04.03.2022 și 15.06.2024) și **textul consolidat al Ordinului 126/2017 cu tot
>    aparatul de chenare de modificare** (instantaneu **28.11.2021**). Consolidarea nu poartă
>    atribuire; forma ei (`***`, `[Anexa nr.X în redacţia Ordinului …, în vigoare …]`) este cea a
>    Registrului de stat al actelor juridice. **Se marchează: consolidare, republicată de
>    instituția care primește formularul, copie din 28.11.2021.**
> 4. **`mf.gov.md` și `particip.gov.md`** — **proiectele**. Proiectul din februarie 2019 al
>    instrucțiunii IRM19 poartă numărul ordinului **în alb** („nr.____ din __ februarie 2019") și
>    note redacționale („de revăzut mecanismul de aprobare"). **Un proiect nu e actul adoptat.**
> 5. **`gov.md`, dosarele de ședință de guvern** — proiectul de lege și avizele. Folosite pentru
>    art. 49: un aviz din dosar citează articolul „în redacția actuală". **Citare de terț într-un
>    document oficial, nu textul legii.**
> 6. **Consolidări de terți ale Codului muncii** — `usmf.md` (universitate, fișier pus în ianuarie
>    2020, **tăietura consolidării: 2019**) și `cpbmd.info` (fișier pus în ianuarie 2026, dar
>    **tipar `legis.md` al versiunii în vigoare din 01.08.2016** — data încărcării nu spune nimic
>    despre data consolidării). **Textul art. 49 de mai jos vine din prima.**
> 7. **`cnsm` / `old.sindicate.md`** — broșura „Convenții colective (nivel național)", Chișinău
>    2021, „convenții aplicabile la situația din noiembrie 2021". CNSM e **parte semnatară** a
>    convenției nr. 4/2005, nu terț oarecare; rămâne totuși o publicație de parte, nu Monitorul.
> 8. **Fragmente indexate de motorul de căutare** — nivelul cel mai slab, folosit o singură dată,
>    marcat, la pct. 2.4.
>
> **Consecință operațională.** Lista de câmpuri a **IRM19 este obținută integral** (preambul +
> 12 coloane + două clasificatoare), în formă consolidată la 2021. Lista clauzelor din **art. 49
> alin. (1) este obținută integral**, în formă consolidată la 2019, cu **o literă despre care avem
> semne că s-a schimbat de atunci** (§2.4). **Anexa nr. 4¹ — „Cerințele la completarea Informației
> (Forma IRM19)", validările portalului — există, e dovedită de două acte, și textul ei integral
> nu a fost obținut.**

**Filtrul România a fost aplicat.** Aruncate explicit din rezultate: `legislatie.just.ro`
(Codul muncii român, Legea nr. 53/2003), `lege5.ro`, `rubinian.com`, `costelgilca.ro`,
`iprotectiamuncii.ro`, `pwc.ro`, `hamangiu.ro`, `cdep.ro`, `kpmg.com/ro`. Atenție: căutarea
„Codul muncii art. 49" întoarce **preponderent** rezultate românești, iar art. 49 din Codul muncii
**român** e despre suspendarea contractului — un articol cu alt obiect, ușor de confundat.
Folosite **doar ca indiciu** spre act, niciodată ca sursă a unei cifre: `contabilsef.md`,
`contabilitate.md`, `monitorul.fisc.md`, `bizlaw.md`, `accafe.md`, `delucru.md`.

---

## 0. Tabelul de identitate

| Act | Monitorul Oficial (nr., dată, poziție) | Intrare în vigoare | Sursa identității |
|---|---|---|---|
| **Ordinul MF nr. 126 din 04.10.2017** — aprobă Forma IPC18 și Instrucțiunea ei | **nr. 383-388 din 03.11.2017, poz. 1947** | **01.01.2018** — pct. 4 al ordinului, **citat** | cuprins MO + antetul consolidării SFS |
| **Ordinul MF nr. 33 din 19.02.2019** — **introduce IRM19** (anexele nr. 3, 4, 7, 8) | **nr. 59-65 din 22.02.2019, Partea III, poz. 364a** | **22.02.2019** pentru pct. 1 și anexele 7–8; **01.04.2019** pentru anexele 3 și 4 — din chenarele consolidării | pagina de ediție `monitor/2102` |
| **Ordinul MF nr. 98 din 28.06.2019** — completează formularul cu tipul dării de seamă | **nr. 218-222 din 05.07.2019, poz. 1143** | **05.07.2019**; anexa nr. 3 **„se aplică începând cu prima perioadă de raportare luna iulie 2019"** | cuprins MO + chenare |
| **Ordinul MF nr. 19 din 28.01.2020** — modifică anexele nr. 1, 8, 9 | **nr. 24-34 din 31.01.2020, poz. 86** | **31.01.2020** — din chenare | cuprins MO + chenare |
| **Ordinul MF nr. 77 din 17.06.2020** | **nr. 152 din 20.06.2020, poz. 555** | neobținută | cuprins MO |
| **Ordinul MF nr. 96 din 30.07.2020** — ultima perioadă IPC18 = decembrie 2020; anexa nr. 9 în redacție nouă | **negăsită** | **01.01.2021** — din chenare | doar chenarele consolidării |
| **Ordinul MF nr. 14 din 31.01.2024** — *„cu privire la modificarea unor ordine ale ministrului finanțelor"*; introduce **Anexa nr. 4¹** | **nr. 50-53 din 02.02.2024, poz. 106** | neobținută | cuprins MO (titlu **nu** numește Ordinul 126/2017) |
| **Ordinul MF nr. 56 din 27.04.2026** — actualizează Anexa nr. 4¹ și Anexa nr. 6 | **publicat 30.04.2026** | **la data publicării** | **pagina CNAS**, nu MO |
| **Codul muncii nr. 154-XV din 28.03.2003** | **nr. 159-162 din 29.07.2003, art. 648** | **01.10.2003** — art. 391 alin. (1), **citat** (§2.1) | antetul a două consolidări independente |
| **Convenția colectivă (nivel național) nr. 4 din 25.07.2005** — modelul contractului individual de muncă | **nr. 101-103 din 29.07.2005, art. 827** | **la data publicării** — art. 5, **citat** | căutare MO + antetul broșurii CNSM |
| **Convenția colectivă nr. 13 din 09.07.2012** — completări la modelul contractului | **nr. 149-154 din 20.07.2012, art. 572** | **la data publicării** — art. 2, **citat** | căutare MO + textul convenției |
| **Convenția colectivă nr. 18 din 28.02.2020** — modificări la modelul contractului | **nr. 70-74 din 06.03.2020, art. 242** | **06.03.2020** | căutare MO + antetul broșurii CNSM |
| **Convenția colectivă nr. 16 din 25.05.2018** — model de contract pentru **perioada îndeplinirii unei anumite lucrări** | **nr. 195-209 din 15.06.2018, art. 972** | neobținută | căutare MO + broșura CNSM |

---

## 1. IRM19 — „Informația privind stabilirea drepturilor sociale și medicale aferente raporturilor de muncă"

### 1.1 Ce act o aprobă, și de ce nu e evident

**IRM19 nu are ordin propriu.** Ea este **anexa nr. 3 la Ordinul MF nr. 126 din 4 octombrie 2017**
— ordinul care aprobă cu totul altceva în titlul lui: Forma IPC18. Titlul, din cuprinsul MO
(`monitorul.gov.md`, ediția 383-388, 30.08.2026):

> **1947.** Ordin cu privire la aprobarea formularului tipizat (Forma IPC18) Darea de seamă privind
> reţinerea impozitului pe venit, a primelor de asigurare obligatorie de asistenţă medicală şi a
> contribuţiilor de asigurări sociale de stat obligatorii calculate şi a Instrucţiunii cu privire la
> modul de completare a formularului nominalizat **(nr. 126, 4 octombrie 2017)**

Antetul consolidării republicate de SFS confirmă independent:
*„nr. 126 din 04.10.2017 (în vigoare 01.01.2018) — Monitorul Oficial al R. Moldova nr. 383-388
art. 1947 din 03.11.2017"*. Temeiul legal, din preambulul citit: **art. 92 alin. (5) și art. 133
alin. (2) din Codul fiscal**. Clauza proprie, **citată**: *„4. Prezentul ordin intră în vigoare la
1 ianuarie 2018."*

Pct. 1 al ordinului, în redacția consolidată la 2021, enumeră **nouă anexe**:

| Anexa | Ce aprobă |
|---|---|
| nr. 1 | Formularul tipizat **Forma IPC18** |
| nr. 2 | Instrucțiunea de completare a Formei IPC18 |
| **nr. 3** | **Formularul tipizat (Forma IRM19)** Informația privind stabilirea drepturilor sociale și medicale aferente raporturilor de muncă |
| **nr. 4** | **Instrucțiunea** de completare a Informației (Forma IRM19) |
| nr. 5 | Formularul tipizat **Forma CAS18-AN** |
| nr. 6 | Instrucțiunea de completare a Formei CAS18-AN |
| **nr. 7** | **Clasificatorul raporturilor de muncă** |
| **nr. 8** | **Clasificatorul motivelor eliberării din câmpul muncii** |
| nr. 9 | Clasificatorul categoriilor persoanelor asigurate |

Chenarele consolidării datează fiecare adăugire:

- `[Pct.1 completat prin Ordinul Ministerului Finanţelor nr.98 din 28.06.2019, în vigoare 05.07.2019]`
- `[Pct.1 modificat prin Ordinul Ministerului Finanţelor nr.33 din 19.02.2019, în vigoare 22.02.2019]`
- `[Pct.1 completat prin Ordinul Ministerului Finanţelor nr.71 din 26.03.2018, în vigoare 30.03.2018]`

**Actul care naște IRM19 este deci Ordinul MF nr. 33 din 19 februarie 2019**, cu titlul neutru
*„Ordin cu privire la modificarea Ordinului Ministerului Finanțelor nr.126 din 4 octombrie 2017"*
— **MO nr. 59-65 din 22 februarie 2019, Partea III, poziția 364a**, citit pe pagina de ediție
`https://monitorul.gov.md/ro/monitor/2102` la 30.08.2026, sub rubrica „Acte ale Ministerului
Finanţelor al Republicii Moldova", între poz. 364 și 365. *Numărul de poziție are sufix literal
(`364a`) — nu e greșeală de transcriere.*

> **Confirmare directă pe formular.** Antetul formularului descărcat de pe `sfs.md` spune:
> *„Anexa nr.3 la Ordinul Ministerului Finanțelor nr.126 din 4 octombrie 2017 (modificată prin
> Anexa nr.1 la Ordinul Ministerului Finanțelor nr.33 din 19 februarie 2019)"*. Proiectul MF al
> instrucțiunii — fișierul `Instructiune IRM.doc` de pe `mf.gov.md`, cu data de creare
> **19.02.2019**, exact ziua ordinului — poartă în antet „Anexa nr.2 la Ordinul Ministerului
> Finanțelor **nr.____ din __ februarie 2019**". Proiectul și actul se leagă prin dată, nu prin
> număr: numărul nu apare nicăieri în proiect.

**Ce înlocuiește.** Din instrucțiune, pct. 7, **citat**: *„Informaţia aferentă raporturilor de
muncă (reflectată în col.8-10), până la 1 aprilie 2019, se va prezenta Serviciului Fiscal de Stat
în Tabelul nr. 2 din Darea de seamă (Forma IPC 18) şi în Informaţia (Forma DSA 19)."* Deci: până
la 01.04.2019 — tabelul nr. 2 din IPC18 plus formularul DSA19; de la 01.04.2019 — IRM19.

### 1.2 Istoricul modificărilor formularului și instrucțiunii

Din chenarele consolidării SFS (copie **28.11.2021**), coroborate cu cuprinsurile MO:

| Anexa | Chenar, verbatim | MO al actului |
|---|---|---|
| nr. 3 (formular) | `[Anexa nr.3 introdusă prin Ordinul Min.Fin. nr.152 din 22.12.2017, în vigoare 01.01.2018]` | 451-463 din 29.12.2017, poz. 2302 |
| nr. 3 | `[Anexa nr.3 în redacţia Ordinului Min.Fin. nr.152 din 12.09.2018, în vigoare 01.01.2019]` | 358-364 din 21.09.2018, poz. 1398 |
| nr. 3 | `[Anexa nr.3 în redacţia Ordinului Min.Fin. nr.33 din 19.02.2019, în vigoare 01.04.2019]` | 59-65 din 22.02.2019, poz. 364a |
| nr. 3 | `[Anexa nr.3 completată prin Ordinul Mini.Fin. nr.98 din 28.06.2019, se aplică începând cu prima perioadă de raportare luna iulie 2019]` | 218-222 din 05.07.2019, poz. 1143 |
| nr. 4 (instrucțiune) | aceleași patru chenare, cu **`în vigoare 05.07.2019`** pentru completarea din OMF 98/2019 | idem |
| nr. 7 | `[Anexa nr.7 introdusă prin Ordinul Ministerului Finanţelor nr.33 din 19.02.2019, în vigoare 22.02.2019]` | idem |
| nr. 8 | `[Anexa nr.8 introdusă prin Ordinul Ministerului Finanţelor nr.33 din 19.02.2019, în vigoare 22.02.2019]` + `[Anexa nr.8 modificată prin Ordinul Ministerului Finanţelor nr.19 din 28.01.2020, în vigoare 31.01.2020]` | 24-34 din 31.01.2020, poz. 86 |
| nr. 9 | introdusă prin OMF 98/2019 (05.07.2019), în redacția OMF 19/2020 (31.01.2020), apoi în redacția **OMF 96 din 30.07.2020, în vigoare 01.01.2021** | ultimul: **MO negăsit** |

**Observația care contează pentru datare.** Chenarul „**introdusă prin OMF nr.152 din 22.12.2017,
în vigoare 01.01.2018**" spune că **anexa nr. 3 exista înainte de a se numi IRM19**: formularul
însuși poartă „Forma **IRM 2019**", iar denumirea curentă „IRM19" e cea a redacției din 2019.
Ordinul 33/2019 nu creează anexa, o **rescrie integral** — și adaugă cele două clasificatoare fără
de care nu se poate completa.

**După 30.07.2020 consolidarea tace** — e o copie din 2021. Ce se știe în plus, din alte surse:

- **Ordinul MF nr. 14 din 31.01.2024** — cuprinsul MO, ediția 50-53 din 02.02.2024:
  *„**106.** Ordin cu privire la modificarea unor ordine ale ministrului finanțelor (nr. 14,
  31 ianuarie 2024)"*. **Titlul nu numește Ordinul 126/2017** — de aceea nu apare în căutarea după
  „126 din 4 octombrie 2017". Că acesta e actul care introduce **Anexa nr. 4¹** rezultă din nota
  informativă a proiectului 2026 (§1.8) și dintr-un rezumat de motor de căutare — *fragment
  indexat*, nu act citit.
- **Ordinul MF nr. 56 din 27.04.2026** — **pagina CNAS** `cnas.gov.md/ro/node/646`, citită
  30.08.2026, **citat**: *„În Monitorul Oficial din 30 aprilie 2026 a fost publicat Ordinul
  Ministerului Finanțelor nr. 56 din 27 aprilie 2026 cu privire la modificarea Ordinului
  Ministerului Finanțelor nr. 126/2017 și Ordinului Ministerului Finanțelor nr. 94/2020,
  prevederile căruia intră în vigoare la data publicării. Ordinul dat prevede actualizarea
  Cerințelor la completarea Informației privind stabilirea drepturilor sociale și medicale aferente
  raporturilor de muncă (Forma IRM 19) care sunt aprobate prin Anexa nr. 4¹ la Ordinul Ministrului
  finanțelor nr.126/2017 (…)"*. **Paragraf de instituție, nu act.**

### 1.3 Formularul — câmpurile, verbatim

Sursa: **`sfs.md/uploads/blank/100/document/formularpdf-5ffd8c1d72ca7.pdf`**, instantaneu Wayback
**16.06.2024**. Antet: *„Anexa nr.3 la Ordinul Ministerului Finanțelor nr.126 din 4 octombrie 2017
(modificată prin Anexa nr.1 la Ordinul Ministerului Finanțelor nr.33 din 19 februarie 2019)"*.
Formularul este **bilingv română–rusă pe fiecare rubrică**.

**Preambul** (rubrici de document, o dată per depunere):

| Rubrica | Text pe formular |
|---|---|
| 1 | `Denumirea contribuabilului` |
| 2 | `Codul fiscal/IDNO` |
| 3 | `Serviciul Fiscal de Stat` — subdiviziunea |
| 4 | `Codul CNAS` |
| 5 | `Tipul dării de seamă ___ primară (bifați)` |
| 6 | `Tipul dării de seamă ___ de corectare (bifați)` |
| 7 | `Numărul dării de seamă care se corectează (se completează)` |
| 8 | `Data prezentării` |
| 9 | `Semnătura persoanei responsabile` (subsolul formularului) |

Rubricile 5–7 sunt **adăugirea Ordinului nr. 98/2019**, aplicabilă din perioada de raportare
**iulie 2019**. Rubrica „Luna, anul de gestiune", prezentă în **proiectul** din februarie 2019, **nu
există pe formularul adoptat** — și nici în instrucțiunea consolidată. *Diferență proiect ↔ act,
verificată prin comparație directă a celor două fișiere.*

**Tabelul** — 12 coloane, grupate pe formular în patru blocuri de antet:

| Col. | Bloc de antet | Denumirea coloanei pe formular |
|---|---|---|
| 1 | — | `Nr. d/o` |
| 2 | **Datele personale ale angajatului** | `Numele, prenumele persoanei fizice` |
| 3 | idem | `Numărul de identificare de stat a persoanei fizice (IDNP)` |
| 4 | idem | `Cod personal de asigurare socială (CPAS)` |
| 5 | **Informație aferentă stabilirii indemnizațiilor adresate familiilor cu copii** | `Categoria persoanei asigurate` |
| 6 | idem | `Perioada de îngrijire a copilului, concediul paternal — de la data de` |
| 7 | idem | `… — de la data de` (data de încheiere) |
| 8 | **Informație aferentă raporturilor de muncă** | `Codul raporturilor de muncă` |
| 9 | idem | `Motivul eliberării din funcție` |
| 10 | idem | `Data atribuirii la codul indicat în col. 8` |
| 11 | — | `Codul funcției care acordă dreptul la pensie în condiții speciale` |
| 12 | — | `Data atribuirii la categoria indicată în col.11` |

*Notă de citire: antetul coloanelor 6 și 7 e identic pe formular („de la data de" / „с даты") —
care e început și care e sfârșit se află doar din instrucțiune, pct. 8 („data începerii şi
încheierii perioadelor declarate").*

### 1.4 Instrucțiunea — regula fiecărei coloane, verbatim

Sursa principală: **`raportare.gov.md`**, „Anexa nr.4 la Ordinul Ministerului Finanțelor nr.126 din
4 octombrie 2017, modificată prin Anexa nr.2 la Ordinul Ministerului Finanțelor nr.____ din __
februarie 2019" — PDF servit de portalul SFS, descărcat 30.08.2026. *Portalul reproduce anexa cu
numărul ordinului lăsat în alb, exact ca proiectul.* Verificată contra instantaneului `sfs.md` din
15.06.2024 (versiunea rusă) și contra consolidării din 28.11.2021 — **cele trei coincid**.

**Dispoziții generale, citate:**

> **1.** Prezenta Instrucțiune stabilește modul de completare a Informaţiei privind stabilirea
> drepturilor sociale şi medicale aferente raporturilor de muncă (Forma IRM19) care se întocmește
> pe un formular aprobat de Ministerul Finanţelor.

> **2.** Informația nominalizată se prezintă în termen de pînă la **10 zile lucrătoare** de la data
> angajării sau modificării/încetării raporturilor de muncă, emiterii ordinului de acordare a
> concediului de îngrijire a copilului sau concediului paternal. **Termenul de prezentare a
> informației nominalizate (Forma IRM19) se determină începând cu ziua următoare după data indicată
> în ordin.** În cazul persoanelor care se angajează și se eliberează pe parcursul a 10 zile din
> data angajării, în Forma IRM19 **se efectuează două înscrieri**.

> **3.** Forma IRM19 se completează **în corespundere cu ordinele întocmite de către angajator**
> pentru următoarele situațiile ce ține de raporturile de muncă:
> a) în cazul angajării sau modificării/încetării raporturilor de muncă;
> b) aflare a persoanei în perioada unui risc asigurat (îngrijire a copilului până la 3 ani,
> îngrijire a copilului de la 3 la 4 ani, concediul paternal);
> c) stabilire a unei funcții care acordă dreptul la pensie în condiții speciale. **În cazul dat nu
> se întocmește ordinul de către angajator.**

> **4.** Informația indicată în corespundere cu ordinele întocmite de către angajator servește drept
> temei pentru **stabilirea drepturilor sociale, atribuirea statutului de șomer și stabilirea
> ajutorului de șomaj**, precum și **acordarea/suspendarea statutului de persoană asigurată în
> sistemul asigurării obligatorii de asistență medicală**.

> **5.** Contribuabilii care utilizează metode automatizate de raportare electronică, potrivit
> **art.187 din Codul fiscal**, prezintă Serviciului Fiscal de Stat în mod electronic Informaţia
> (…). În cazul în care contribuabilul nu dispune de semnătură electronică, acesta prezintă
> Informația menționată subdiviziunii Serviciului Fiscal de Stat **pe suport de hârtie**.

> **6.** Informația din formularul respectiv, prezentată pe parcursul lunii de gestiune, aferentă
> categoriei persoanei asigurate (reflectată în col.5) **nu se include** de către angajatori în
> Darea de seamă (Forma IPC18), în Tabelul nr.3 (…).

**Modul de completare a coloanelor, citat integral:**

> col. 1 – numărul curent al înscrierii efectuate;
> col. 2 – numele şi prenumele persoanei fizice, **conform datelor din actul de identitate**;
> col. 3 – numărul de identificare al persoanei (IDNP) din actul de identitate. **Câmpul este
> obligatoriu pentru completare**;
> col. 4 – numărul codului personal de asigurate socială atribuit fiecărei persoane la momentul
> înregistrării in Registrul de stat at evidenței ìndividuale.
> col. 5 – codul categoriei în care se regăseşte persoana asigurată în conformitate cu
> **Clasificatorul categoriei persoanelor asigurate**. Se indică categoria corespunzătoare riscului
> asigurat în care se află persoana. **Nu se completează pentru persoanele angajate şi eliberate.**
> col. 6, 7 – data începerii şi încheierii perioadelor declarate conform codului din col. 5, **care
> pot depăşi perioada de gestiune**. Nu se completează pentru persoanele angajate şi eliberate.
> col. 8 – codul raporturilor de muncă conform **Clasificatorului raporturilor de muncă, potrivit
> anexei nr.7 la prezentul ordin**;
> col. 9 – сodul motivului eliberării din funcţie conform **Clasificatorului cu privire la motivul
> eliberării din câmpul muncii, potrivit anexei nr.8 la prezentul Ordin**;
> col. 10 – data atribuirii la codul indicat în col. 8;
> col. 11 – codul funcţiei în care se regăsesc persoanele asigurate în conformitate cu
> **Clasificatorul funcţiilor care dă dreptul la pensie în condiții avantajoase, aprobat de CNAS**.
> Rubrica dată se completează doar de către contribuabilii care angajează persoane în funcţiile
> prevăzute în Clasificator;
> col. 12 – data atribuirii la codul indicat în col. 11.

> **Notă:** Informaţia (Forma IRM19) **pentru persoanele ce nu deţin numărul personal de
> identificare (IDNP) se prezintă, suplimentar, agențiilor teritoriale şi reprezentanților CNAM, pe
> suport de hârtie.**

**Trei diferențe între versiuni, măsurate, nu presupuse:**

1. **Proiectul din februarie 2019** spunea la col. 4 „Câmpul este obligatoriu pentru completare";
   versiunea consolidată **a scos** propoziția din col. 4 și a păstrat-o doar la col. 3.
2. **Versiunea rusă de pe `sfs.md` (15.06.2024)** are la гр.4 o propoziție **absentă din versiunea
   română**: *„В случае отсутствия индивидуального кода указывается 0 («ноль»)"* — dacă lipsește
   codul personal de asigurare socială, se indică 0. **Regula de completare a CPAS-ului lipsă
   există doar în textul rus citit.**
3. **Proiectul** trimitea la clasificatoare „aprobate de Ministerul Finanțelor" / „elaborate de
   CNAS", cu nota redacțională „de revăzut mecanismul de aprobare"; **actul** trimite la **anexele
   nr. 7 și nr. 8 la același ordin** — pentru col. 8 și col. 9. **Pentru col. 11 trimiterea a rămas
   la un clasificator CNAS, fără anexă.** Vezi §1.7.

### 1.5 Anexa nr. 7 — Clasificatorul raporturilor de muncă (col. 8)

Sursa: consolidarea SFS, copie 28.11.2021. Introdusă prin OMF 33/2019, în vigoare 22.02.2019.
**Zece coduri, bilingv:**

| Cod | Situația privind raporturile de muncă |
|---|---|
| **01** | ANGAJARE PE PERIOADĂ NEDETERMINATĂ |
| **05** | ANGAJARE PE PERIOADĂ DETERMINATĂ |
| **02** | ÎNCETAREA RAPORTURILOR DE MUNCĂ |
| **03** | SUSPENDAREA CONTRACTULUI INDIVIDUAL DE MUNCĂ * |
| **04** | ANULAREA SUSPENDĂRII CONTRACTULUI INDIVIDUAL DE MUNCĂ |
| **06** | ANGAJARE PE PERIOADĂ NEDETERMINATĂ, MILITAR ** |
| **07** | ANGAJARE PE PERIOADĂ DETERMINATĂ, MILITAR |
| **08** | ÎNCETAREA RAPORTURILOR DE MUNCĂ, MILITAR |
| **09** | SUSPENDAREA RAPORTURILOR DE MUNCĂ, MILITAR |
| **10** | ANULAREA SUSPENDĂRII RAPORTURILOR DE MUNCĂ, MILITAR |

*Ordinea codurilor în act este exact cea de mai sus — `01, 05, 02, 03, 04, 06 …`, nu crescătoare.*

Nota `*`, **citată**, delimitează exact ce suspendări **se raportează** și care **nu**:

> se utilizează în cazurile **suspendării activității unității**, **încorporării în serviciul
> militar în termen**, precum şi în cazurile de suspendare a contractului individual de muncă
> (**cu excepția** suspendării contractului individual de muncă în circumstanţe ce nu depind de
> voinţa părţilor, suspendării contractului individual de muncă din iniţiativa salariatului în caz
> de aflare în concediu pentru îngrijirea unui membru bolnav al familiei cu durata de pînă la doi
> ani, conform certificatului medical, şi în caz de aflare în concediu parţial plătit pentru
> îngrijirea copilului pînă la vîrsta de 3 ani)

Nota `**` definește „militar": *„personalul militar din cadrul Ministerului Apărării, funcționarii
publici cu statut special, polițiștii de frontieră și militarii din cadrul Ministerului Afacerilor
Interne și Administrației Naționale a Penitenciarelor, ofițerii de informație și securitate,
ofițerii de protecție ai Serviciului de Protecție și Pază de Stat"*. Notă finală, **citată**:
*„Codurile 06-10 se indică de către contribuabili doar în cazul militarilor."*

### 1.6 Anexa nr. 8 — Clasificatorul motivelor eliberării din câmpul muncii (col. 9)

Introdusă prin OMF 33/2019 (22.02.2019), modificată prin OMF 19/2020 (31.01.2020). **Treisprezece
coduri, fiecare legat de un articol de lege:**

| Cod | Situația | Temeiul citat în clasificator |
|---|---|---|
| **111** | Concedierea în legătură cu lichidarea unităţii | art. 86 alin. 1 lit. b) CM |
| **112** | Concedierea în legătură cu încetarea activităţii angajatorului persoană fizică | art. 86 alin. 1 lit. b) CM |
| **113** | Concedierea în legătură cu reducerea numărului sau a statelor de personal | art. 86 alin. 1 lit. c) CM |
| **114** | **Demisie** | art. 85 CM |
| **115** | Încetarea contractului individual de muncă | art. 82 CM, **cu excepţia lit. b)** |
| **116** | Pierderea locului de muncă din alte motive de concediere conform CM | — |
| **211** | Pierderea locului de muncă din motivul decesului angajatorului persoană fizică, declararea acestuia decedat sau dispărut fără urmă | art. 82 lit. b) CM |
| **311** | Încetarea contractului de serviciu din funcţia publică în legătură cu lichidarea instituţiei | art. 63 alin. (1) lit. a), b) L. nr. 158/2008 |
| **312** | Încetarea contractului de serviciu din funcţie publică în legătură cu reducerea statelor | art. 63 alin. (1) lit. c) L. nr. 158/2008 |
| **313** | Încetarea contractului de serviciu cu funcţionarul public prin demisie | art. 65 L. nr. 158/2008 |
| **314** | Încetarea contractului de serviciu cu funcţionarul public din alte motive | — |
| **411** | Încetarea raportului de serviciu al funcţionarului public cu statut special în cazul lichidării entităţii sau reducerii postului | art. 38 alin. (1) lit. f) L. nr. 288/2017 |
| **412** | Încetarea raporturilor de serviciu al funcţionarului public cu statut special prin demisie | art. 38 alin. (1) lit. a) L. nr. 288/2017 |
| **413** | Încetarea raportului de serviciu al funcţionarului public cu statut special din alte motive | art. 38 L. nr. 288/2017 |

> **Atenție la o eroare din act.** Codul 115 e „Încetarea contractului individual de muncă
> **(art.82 din CM**, cu excepţia lit.b)" în română și **„(ст.83 ТК**, за исключением лит.b)" în
> rusă. Textele **nu coincid**: română spune art. 82, rusa spune art. 83. Codul 211 trimite în
> ambele limbi la art. 82 lit. b), ceea ce face **art. 82 varianta coerentă**. Se transcrie art. 82;
> discrepanța se consemnează.

### 1.7 Categoria persoanei asigurate (col. 5) și codul funcției (col. 11)

**Col. 5** trimite la **Clasificatorul categoriei persoanelor asigurate**. În consolidarea din 2021
acesta e **anexa nr. 9**, iar titlul tabelului e deja *„Categorii utilizate la completarea Dării de
seamă (forma IPC21)"* — adică anexa e comună IPC21 și IRM19. Codurile relevante pentru IRM19, adică
cele trei riscuri asigurate enumerate la pct. 3 lit. b) din instrucțiune, apar la **coada** anexei,
cu tariful marcat `*` („Tariful contribuţiei se aprobă anual prin Legea bugetului asigurărilor
sociale de stat"):

| Cod | Denumirea categoriei |
|---|---|
| **157** | PERSOANĂ CARE SE AFLĂ ÎN CONCEDIU PENTRU ÎNGRIJIREA COPILULUI PÎNĂ LA 3 ANI |
| **158** | PERSOANĂ CARE SE AFLĂ ÎN CONCEDIU SUPLIMENTAR NEPLĂTIT PENTRU ÎNGRIJIREA COPILULUI DE LA 3 PÎNĂ LA 4 ANI |
| **165** | PERSOANĂ CARE SE AFLĂ ÎN CONCEDIU PATERNAL |

*Restul clasificatorului (101 contract individual de muncă, 105 contract civil, 116 plăți după
eliberare, 123 cumul, 147 sector agrar etc.) aparține IPC21 și e deja acoperit de
`f2-x2-formularele-sfs.md`. Nu se retranscrie aici.*

**Col. 11** trimite la *„Clasificatorul funcţiilor care dă dreptul la pensie în condiții
avantajoase, **aprobat de CNAS**"*. **Acest clasificator nu este anexă la Ordinul 126/2017** — spre
deosebire de cele din col. 8 și col. 9, care au primit anexe proprii în 2019. **Actul care îl
aprobă nu a fost identificat** (vezi „Ce nu s-a putut verifica", pct. 6).

### 1.8 Anexa nr. 4¹ — „Cerințele la completarea Informației (Forma IRM19)"

**Există; textul integral nu a fost obținut.** Două acte o numesc:

1. **Nota informativă a proiectului MF 2026** (`particip.gov.md/ro/download_attachment/32145`,
   citită 30.08.2026), **citat**: *„(…) fapt ce impune ajustarea **Cerințelor tehnice pentru
   completarea Informației IRM19** cu privire la stabilirea drepturilor sociale și medicale
   aferente raporturilor de muncă (**Cerințe aprobate prin Anexa nr.4¹ la Ordinul Ministrului
   finanțelor nr.126/2017**)."* Semnată de ministrul Adrian Gavriliță.
2. **Pagina CNAS** `cnas.gov.md/ro/node/646`, citată la §1.2.

**Ce se știe din conținutul ei** — din **proiectul** de ordin 2026
(`particip.gov.md/ro/download_attachment/32144`, PDF, 7 pagini, citit 30.08.2026), care rescrie
două puncte. **Text de proiect, nu de act:**

> **1) în Anexa nr. 4¹:**
> a) punctul 5 se completează cu următorul text: *„Dacă nu se completează col. 5 nu pot fi
> completate coloanele 6 și 7. În caz că coloana menționată nu este completată se prezintă eroare
> «Col.5 este obligatorie pentru completare în cazul în care sunt completate col.6 și col. 7» și,
> respectiv, nu permite salvarea documentului. **Validare strictă.**"*
> b) punctul 6 va avea următorul cuprins: *„Col. 6 și col. 7 Perioada de îngrijire a copilului,
> concediu paternal, **formatul datei obligatoriu este «dd.mm.yyyy»**. Data începerii perioadei
> declarate (col.6) urmează să fie **mai mică** decât data încheierii perioadei declarate (col.7).
> **Pentru concediul paternal perioada declarată poate fi nu mai mică de 5 zile și nu mai mare de
> 45 de zile.** Totodată perioada din col. 6 nu poate fi mai mică decât anul de completare. Col.7
> poate depăși anul de completare a documentului pentru perioada de îngrijire a copilului, pentru
> **concediile de adopție sau plasarea copilului în serviciul de tutelă/curatelă**, pentru
> concediul paternal. (…)"*

**Ce spune asta despre natura anexei:** Anexa nr. 4¹ nu e o a doua instrucțiune — e **specificația
validărilor portalului de raportare electronică**, pe puncte numerotate per coloană, cu textul
exact al mesajului de eroare și cu clasificarea validării („Validare strictă"). Este echivalentul,
pentru IRM19, al **Anexei nr. 4 „Lista validărilor" a IPC21** identificată în
`f2-x2-formularele-sfs.md` §2.2. **Este singura specificație oficială a comportamentului sistemului
SFS la depunerea IRM19.**

Temeiul proiectului 2026, **citat din preambul**: *„art. IV alin. (2) din **Legea nr. 156/2025**
pentru modificarea unor acte normative (aspecte legate de acordarea concediului paternal)
(Monitorul Oficial al Republicii Moldova, 2025, nr. 340-342, art. 409), a art. XIII alin. (1) din
**Legea nr. 318/2025** pentru modificarea unor acte normative (domeniul fiscal) (Monitorul Oficial
al Republicii Moldova, 2025, nr. 659-661, art. 792)"*. *Prima e o identitate MO nouă pentru acest
depozit; a doua confirmă independent identitatea din `f2-x1-identitatile-actelor.md`.*

### 1.9 Termen, canal, corectare

- **Termenul:** **10 zile lucrătoare**, numărate **din ziua următoare datei indicate în ordin**
  (instrucțiune, pct. 2, citat). **Nu de la data contractului, nu de la data intrării în vigoare a
  contractului — de la data ordinului angajatorului.**
- **Faptul generator** e **ordinul**, nu contractul (pct. 3, citat). Excepție explicită: funcția
  care dă drept la pensie în condiții speciale, unde *„nu se întocmește ordinul de către
  angajator"* — deci un rând IRM19 fără ordin în spate.
- **Canalul:** electronic prin trimitere la **art. 187 din Codul fiscal**; pe hârtie doar în lipsa
  semnăturii electronice. Actul **nu numește serviciul electronic** — aceeași observație ca la
  celelalte formulare SFS.
- **Suplimentar pe hârtie la CNAM** pentru persoanele fără IDNP (nota finală, citată).
- **Corectarea** se face prin depunerea unei alte informații, cu bifa „de corectare" și
  **numărul dării de seamă care se corectează** (rubricile 6–7 din preambul).
- **Nu la CNAS.** Se depune la SFS; CNAS o primește prin schimbul instituțional — vezi
  `od-22-cnas-cnam.md` §5.

---

## 2. Codul muncii art. 49 — conținutul contractului individual de muncă

### 2.1 Identitate și intrare în vigoare

**Codul muncii al Republicii Moldova nr. 154-XV din 28.03.2003.** Identitatea era deja fixată în
`f2-x1-identitatile-actelor.md` din citarea oficială a unui proiect MMPS de pe `gov.md`, cu
mențiunea că **data 29.07.2003 vine doar din surse neoficiale** și că **art. 391 apare doar pe
`lege.md`**. Ambele lacune se închid aici, în limitele sursei:

- **Antetul a două consolidări independente**, ambele în format de tipar al Registrului de stat:
  `usmf.md` — *„Monitorul Oficial al R.Moldova nr.159-162/648 din 29.07.2003"*; `cpbmd.info` —
  *„Publicat : 29.07.2003 în MONITORUL OFICIAL Nr. 159-162 art. 648"*. **Copii de terți, nu
  Monitorul** — dar două, concordante, în format de act.
- **Art. 391 alin. (1), citat** din consolidarea `usmf.md`:
  > **(1)** Prezentul cod intră în vigoare la **1 octombrie 2003**, cu excepţia prevederilor
  > referitoare la acordarea concediului parţial plătit pentru îngrijirea copilului pînă la
  > atingerea vîrstei de 3 ani din art.124 alin.(2) şi art.127 alin.(1), care vor intra în vigoare
  > cu începere de la **1 ianuarie 2004**.

  Chenar: `[Art.391 modificat prin Legea nr.60-XVI din 21.03.2008, în vigoare 01.07.2008]`.

> **Capcană de datare, măsurată.** Copia `cpbmd.info` a fost încărcată în **ianuarie 2026** și e
> **mai veche** decât cea de pe `usmf.md`, încărcată în **ianuarie 2020**: antetul ei declară
> *„Versiune în vigoare din data 01.08.16 în baza modificărilor prin LP152 din 01.07.16,
> MO245-246/30.07.16 art.517"*. **Data încărcării fișierului nu spune nimic despre data
> consolidării.** Textul de mai jos vine din copia `usmf.md`, a cărei tăietură e **2019** (cel mai
> recent chenar `în vigoare` din tot fișierul e din 2019).

### 2.2 Art. 49, textul integral

Sursa: **`usmf.md/sites/default/files/2020-01/126 (Codul muncii).pdf`**, consolidare cu tăietura
2019, descărcată 30.08.2026. **Titlul articolului este „Conţinutul contractului individual de
muncă"**, nu „clauzele obligatorii"; lista de clauze e alin. (1).

> **Articolul 49. Conţinutul contractului individual de muncă**
>
> **(1)** Conţinutul contractului individual de muncă este determinat prin acordul părţilor,
> ţinîndu-se cont de prevederile legislaţiei în vigoare, şi include:
> **a)** numele şi prenumele salariatului;
> **b)** datele de identificare ale angajatorului;
> **c)** durata contractului;
> **d)** data de la care contractul urmează să-şi producă efectele;
> **d¹)** specialitatea, profesia, calificarea, funcţia;
> **e)** atribuţiile funcţiei;
> **f)** riscurile specifice funcţiei;
> **f¹)** denumirea lucrării ce urmează a fi îndeplinită (în cazul contractului individual de muncă
> pentru perioada îndeplinirii unei anumite lucrări – art.312–316);
> **g)** drepturile şi obligaţiile salariatului;
> **h)** drepturile şi obligaţiile angajatorului;
> **i)** condiţiile de retribuire a muncii, inclusiv salariul funcţiei sau cel tarifar,
> suplimentele, premiile şi ajutoarele materiale (în cazul în care acestea fac parte din sistemul
> de salarizare al unităţii), precum şi periodicitatea achitării plăţilor;
> **j)** compensaţiile şi alocaţiile, inclusiv pentru munca prestată în condiţii grele, vătămătoare
> şi/sau periculoase;
> **k)** locul de muncă. Dacă locul de muncă nu este fix, se menţionează că salariatul poate avea
> diferite locuri de muncă şi se indică adresa juridică a unităţii sau, după caz, domiciliul
> angajatorului;
> **l)** regimul de muncă şi de odihnă, inclusiv durata zilei şi a săptămînii de muncă a
> salariatului;
> **m)** perioada de probă, după caz;
> **n)** durata concediului de odihnă anual şi condiţiile de acordare a acestuia;
> *[Lit.o) alin.(1) art.49 abrogată prin Legea nr.157 din 20.07.2017, în vigoare 18.08.2017]*
> **p)** condiţiile de asigurare socială;
> **r)** condiţiile de asigurare medicală;
> **s)** clauzele specifice (art.51), după caz.
>
> **(2)** Contractul individual de muncă poate conţine şi alte prevederi ce nu contravin
> legislaţiei în vigoare.
>
> **(3)** Este interzisă stabilirea pentru salariat, prin contractul individual de muncă, a unor
> condiţii sub nivelul celor prevăzute de actele normative în vigoare, de convenţiile colective şi
> de contractul colectiv de muncă.

Chenarele de modificare, în ordinea din act:
`[Art.49 modificat prin Legea nr.52 din 01.04.2016, în vigoare 22.04.2016]` ·
`[Art.49 completat prin Legea nr.205 din 20.11.2015, în vigoare 18.12.2015]` ·
`[Art.49 completat prin Legea nr.60-XVI din 21.03.2008, în vigoare 01.07.2008]` ·
`[Art.49 completat prin Legea nr.8-XVI din 09.02.2006, în vigoare 02.06.2006]`.

**Numărul de clauze în vigoare: 19** — a, b, c, d, d¹, e, f, f¹, g, h, i, j, k, l, m, n, p, r, s.
Litera **o) e abrogată** (L. nr. 157/2017, în vigoare 18.08.2017) şi **q** lipsește din alfabetul
folosit (se sare de la p) la r)) — convenție obișnuită în actele RM. Numerotarea **nu e contiguă**:
`d¹` și `f¹` sunt inserții ulterioare, iar o implementare care presupune litere consecutive va
greși.

### 2.3 Ce **nu** e în art. 49 — clauzele specifice, art. 51

> **Articolul 51. Clauze specifice ale contractului individual de muncă**
> **(1)** În afara clauzelor generale prevăzute la art.49, părţile pot negocia şi include în
> contractul individual de muncă clauze specifice, cum ar fi:
> a) clauza de mobilitate; b) clauza de confidenţialitate; c) clauze referitoare la compensarea
> cheltuielilor de transport, la compensarea serviciilor comunale, la acordarea spaţiului locativ;
> d) alte clauze care nu contravin legislaţiei în vigoare.
> **(2)** În schimbul respectării unora dintre clauzele prevăzute la alin.(1), salariatul poate
> beneficia de dreptul la o **indemnizaţie specifică** şi/sau de alte drepturi (…). În cazul
> nerespectării acestor clauze, salariatul poate fi privat de drepturile acordate şi, după caz,
> obligat să repare prejudiciul cauzat angajatorului.

**Terminologia actului**: art. 49 = **clauze generale**; art. 51 = **clauze specifice**. Nicăieri
în text nu apare formularea „clauze obligatorii".

### 2.4 O literă despre care avem semne că s-a schimbat după 2019 — **nerezolvat**

Consolidarea citită (tăietura 2019) dă **lit. i)** terminată cu *„precum şi periodicitatea
achitării plăţilor"*. Două surse mai noi o dau altfel:

1. **Dosarul de ședință de guvern `NU-455-MMPS-2025_0.pdf`** (`gov.md`, iunie 2025), în tabelul de
   sinteză a obiecțiilor, un participant la avizare citează articolul **„în redacția actuală"**:
   > *a) în conformitate art. 49 alin. (1) lit. i) din CM (**în redacția actuală**), contractul
   > individual de muncă trebuie să includă condițiile de retribuire a muncii, inclusiv salariul
   > funcției sau cel tarifar, suplimentele, premiile și ajutoarele materiale (în cazul în care
   > acestea fac parte din sistemul de salarizare al unității), **formele și modul de achitare a
   > plăților salariale, precum și periodicitatea acestei achitări**.*

   *Citare de participant într-un document oficial, nu textul legii.*
2. Un **fragment indexat** al paginii `legis.md` a Codului muncii conține aceeași sintagmă
   *„formele și modul de achitare a plăților salariale"*. **Cel mai slab nivel din dosar.**

**Actul care a operat modificarea nu a fost identificat.** Candidatul care apare în rezultate este
**Legea nr. 243 din 28.07.2022 pentru modificarea unor acte normative** — identitate verificată pe
cuprinsul MO: *„**562.** Lege pentru modificarea unor acte normative (nr. 243, 28 iulie 2022)"*,
**MO nr. 267-273 din 26.08.2022**. Dar **sinteza CNSM a modificărilor aduse de Legea nr. 243/2022**
(`sindicate.md`, citită 30.08.2026) enumeră articolele 33, 53, 55, 60, 62, 84, 86, 104, 113, 114,
157, 211, 330 — **și nu art. 49**. **Atribuirea rămâne nefăcută.**

> **Consecință pentru `F2.B1`.** Diferența nu e cosmetică: dacă lit. i) cere astăzi și **„formele
> și modul de achitare"**, contractul trebuie să poarte **modalitatea de plată** (card / numerar /
> cont), nu doar periodicitatea. **Nu se scrie câmpul pe baza acestui dosar.** Se obține textul.

### 2.5 Modificarea în lucru — proiect, iunie 2025, transpunerea Directivei (UE) 2019/1152

**Proiect, nu act.** Dosarul `NU-455-MMPS-2025_0.pdf` (MMPS, aprobat pentru remitere la Parlament),
pct. 6 din Art. I, **citat**:

> **6. La articolul 49, alineatul (1):**
> **litera i) va avea următorul cuprins:** *„i) condițiile de retribuire a muncii, inclusiv
> **salariul de bază (salariul tarifar, salariul funcției)**, **salariul suplimentar (adaosurile şi
> sporurile la salariul de bază)** şi **alte plăti de stimulare şi compensare** - elemente
> constitutive ale veniturilor salariale, **evidențiate separat**, precum și periodicitatea plății
> salariului la care salariatul are dreptul şi **metoda de plată**;"*
> **literele l) și m) vor avea următorul cuprins:** *„l) regimul de muncă şi de odihnă,
> **programul de muncă**, inclusiv durata zilei şi a săptămânii de muncă a salariatului,
> **condițiile de prestare și de compensare sau remunerare a orelor de muncă suplimentară**,
> precum și, după caz, **programul muncii în schimburi** aplicat de la angajare;"* ·
> *„m) după caz, perioada de probă, **cu specificarea concretă a duratei și condițiilor
> desfășurării acesteia** conform prevederilor art. 60 – 63;"*
> **se completează cu litera l¹), m¹) și n¹):** *„l¹) în cazul salariaților prin **agent de muncă
> temporară**, identitatea utilizatorului;"* · *„m¹) **dreptul și condițiile de formare
> profesională**, reciclare şi perfecționare, oferite de către angajator (…);"* · *„n¹) informația
> privind **perioadele de preaviz** ce urmează a fi respectate de angajator şi salariat în cazul
> încetării activităţii (…);"*

**De ce contează acum, deși e proiect:** structura salariului pe care proiectul o cere
(**salariu de bază / salariu suplimentar / alte plăți de stimulare și compensare, evidențiate
separat**) este exact descompunerea pe care `employment_contract` ar trebui s-o poarte pentru ca
fluturașul și baza de calcul să nu fie reconstruite din text liber. **Direcția e cunoscută; data
nu.** *Declanșator: publicarea legii în MO.*

---

## 3. Modelul contractului — Convenția colectivă (nivel național) nr. 4/2005

### 3.1 Identitate și modificări

Nu este act al Guvernului, ci **convenție colectivă la nivel național**, semnată de **Guvern,
Confederația Națională a Patronatului și confederațiile sindicale**. Antetul din broșura CNSM,
**citat**: *„CONVENŢIE COLECTIVĂ Nr. 4 din 25.07.2005 cu privire la modelul Contractului individual
de muncă. Publicată în: Monitorul Oficial Nr. 101-103 din 29.07.005 art. 827. Modificată prin:
CCMEI18 din 28.02.20, MO70-74/06.03.20 art.242; în vigoare 06.03.20"* — *„29.07.005" e greșeală de
tipar în broșură; anul corect e 2005, confirmat de căutarea MO.*

Textul convenției, **citat**:

> **Art.1.** – Se aprobă modelul Contractului individual de muncă, conform anexei.
> **Art.2.** – **Se recomandă** tuturor unităţilor, indiferent de tipul de proprietate şi forma
> organizatorico-juridică, să utilizeze, la încheierea contractelor individuale de muncă (…),
> modelul Contractului individual de muncă aprobat prin prezenta Convenţie.
> **Art.4.** – Modelul Contractului individual de muncă aprobat prin prezenta Convenţie **nu se
> aplică la perfectarea relaţiilor de muncă cu conducătorii (managerii) unităţilor.**
> **Art.5.** – Prezenta Convenţie colectivă intră în vigoare la data publicării ei în Monitorul
> Oficial al Republicii Moldova.

> **Consecință de proiectare, importantă.** Art. 2 spune **„se recomandă"**, nu „se aprobă spre
> aplicare obligatorie". **Modelul nu e formular obligatoriu.** Ce e obligatoriu e **art. 49
> alin. (1)** din Cod. Modelul rămâne totuși cea mai bună dovadă a **formei sub care instituțiile
> se așteaptă să vadă acele clauze** — și, la pct. 21, se leagă explicit de art. 49.

**Modificările**, cu identitate MO verificată pe pagina de căutare `monitorul.gov.md` (30.08.2026):

| Convenția | MO | Ce schimbă |
|---|---|---|
| **nr. 13 din 09.07.2012** | nr. 149-154 din 20.07.2012, art. 572 | completează pct. 12 cu plafonul minim garantat și **introduce pct. 12¹** — lista drepturilor a căror mărime depinde de salariul stabilit. Temeiul citat în preambul: pct. 2.3 din Planul aprobat prin **HG nr. 477 din 28.06.2011** (MO 2011, nr. 110-112, art. 544), *„minimizarea practicii de achitare a salariilor «în plic» şi «muncii la negru»"* |
| **nr. 18 din 28.02.2020** | nr. 70-74 din 06.03.2020, art. 242 | rescrie pct. 21, completează pct. 12 cu *„precum şi periodicitatea achitării acestora"*, adaugă pct. 27 lit. a¹) |
| **nr. 16 din 25.05.2018** | nr. 195-209 din 15.06.2018, art. 972 | **alt model**, pentru contractul pe perioada îndeplinirii unei anumite lucrări, plus modelul Actului de recepționare a lucrării |

### 3.2 Modelul, în forma consolidată la noiembrie 2021

Sursa: broșura CNSM „Convenții colective (nivel național)", Chișinău 2021, *„convenții aplicabile
la situația din noiembrie 2021"*, editată cu suportul OIM. **Publicație a unei părți semnatare.**

Contractul model are **29 de puncte plus datele de identificare**. Structura, prescurtată la ce e
câmp:

| Pct. | Conținut |
|---|---|
| antet | data, localitatea, denumirea unităţii sau numele angajatorului persoană fizică, reprezentantul (nume, prenume, funcţie), numele şi prenumele salariatului; trimitere la **art. 45–94 CM** |
| 1 | funcţia, profesia, meseria, specialitatea, calificarea |
| 2 | locul de muncă — **denumirea subdiviziunii unităţii** |
| 3 | munca este: **a) de bază; b) prin cumul** |
| 4 | durata: **a) nedeterminată; b) determinată** (termenul concret) |
| 5 | **perioada de probă** (dacă părţile au convenit) — termenul concret |
| 6 | contractul îşi produce efectele din: **a) ziua semnării; b) data negociată de părţi** |
| 7 | **riscurile specifice funcţiei** (muncă în condiţii grele, vătămătoare şi/sau periculoase) |
| 8–11 | drepturile şi obligaţiile salariatului (art. 9) şi ale angajatorului (art. 10), plus cele suplimentare negociate |
| 12 | **condiţiile de retribuire**: salariul funcţiei sau cel tarifar, suplimentele, sporurile, adaosurile, premiile, ajutoarele materiale, compensaţiile şi alocaţiile, inclusiv pentru condiţii grele, intensitatea muncii, **„precum şi periodicitatea achitării acestora"**; cu plafonul minim garantat introdus în 2012 |
| 12¹ | de mărimea salariului depind: indemnizaţia de concediu, indemnizaţia pentru incapacitate temporară de muncă şi alte prestaţii de asigurări sociale, indemnizaţia de concediere, ajutorul de şomaj, pensia |
| 13 | **regimul de muncă**: durata normală sau redusă, tipul săptămânii, durata zilnică, timpul parţial, schimburi, munca de noapte |
| 14 | **regimul de odihnă**: repausul zilnic, repausul săptămânal |
| 15 | **concediile anuale**: a) de odihnă anual (durata); b) de odihnă anual suplimentar (durata) |
| 16–17 | asigurarea socială / medicală — *„în modul şi mărimea prevăzute de legislaţia în vigoare"* |
| 18 | **clauze specifice** (mobilitate, confidenţialitate, altele) |
| 19 | înlesniri, avantaje, indemnizaţii în schimbul clauzelor specifice de la pct. 18 |
| 20 | modificarea **numai prin acord suplimentar semnat, anexat, parte integrantă** |
| 21 | *„Va fi considerată drept modificare a prezentului Contract individual de muncă orice modificare sau completare care vizează **cel puțin una dintre clauzele prevăzute la art. 49 alin. (1) din Codul muncii**."* |
| 23–25 | deplasare / detaşare (art. 70–71); schimbare temporară fără consimțământ (art. 104 alin. (2)); transfer (art. 68, 74) |
| 26 | **suspendarea**: art. 76 / 77 / 78 |
| 27 | **încetarea**: a) art. 82, 305, 310; **a¹) prin acordul scris al părţilor, art. 82¹**; b) art. 85 şi 86 |
| 28–29 | litigii; două exemplare |
| final | **Angajatorul:** adresa, **cod fiscal**, semnătura, ștampila. **Salariatul:** adresa, **buletin de identitate** (eliberat de/la), **cod personal**, **cod personal de asigurări sociale**, semnătura |

> **Comparație utilă.** Versiunea din 2012 (copie `usmf.md`, fișier din ianuarie 2014) enumera la
> pct. 21 **șapte** tipuri de schimbare care contează drept modificare: durata, locul de muncă,
> specificul muncii, cuantumul retribuirii, regimul de muncă şi de odihnă, specialitatea/profesia/
> calificarea/funcţia, caracterul înlesnirilor. **Convenția nr. 18/2020 a înlocuit lista cu o
> trimitere la art. 49 alin. (1).** Efectul practic: **orice** clauză din art. 49 alin. (1) devine
> declanșator de act adițional — inclusiv cele care nu erau în lista de șapte (atribuţiile funcţiei,
> riscurile specifice, condiţiile de asigurare, perioada de probă, durata concediului).

---

## 4. Ce cere efectiv un act de la o înregistrare `employment_contract`

Această secțiune este răspunsul la întrebarea din ADR-065 §11. **Fiecare rând spune ce act îl cere
și la ce e folosit.** Nimic aici nu e derivat din ce consumă calculul.

### 4.1 Câmpuri cerute de **art. 49 alin. (1)** — clauzele generale ale contractului

*Cele 19 litere ocupă 17 rânduri: g)+h) și p)+r) sunt perechi și stau împreună.*

| Câmp | Litera | Observație de modelare |
|---|---|---|
| numele şi prenumele salariatului | a) | IRM19 col. 2 cere **conform actului de identitate** — deci **denumirea legală**, `C39` |
| datele de identificare ale angajatorului | b) | inclusiv **cod fiscal** (modelul, datele de identificare) |
| durata contractului | c) | **nedeterminată / determinată + termen**; determină codul 01 vs 05 la IRM19 |
| data de la care contractul îşi produce efectele | d) | **distinctă** de data semnării și de data ordinului |
| specialitatea, profesia, calificarea, funcţia | d¹) | patru valori, nu una |
| atribuţiile funcţiei | e) | text; **nu apare în IRM19** |
| riscurile specifice funcţiei | f) | condiţii grele / vătămătoare / periculoase — leagă cota CAS de condiţii speciale |
| denumirea lucrării | f¹) | doar pentru contractul art. 312–316; are **model propriu** (CC nr. 16/2018) |
| drepturile şi obligaţiile salariatului / angajatorului | g), h) | text |
| condiţiile de retribuire | i) | **redacția e nesigură** — vezi §2.4; minimum: salariul funcţiei/tarifar, suplimentele, premiile, ajutoarele materiale, **periodicitatea achitării** |
| compensaţiile şi alocaţiile | j) | inclusiv pentru condiţii grele/vătămătoare/periculoase |
| locul de muncă, cu marcajul **„nu este fix"** | k) | **un boolean plus o adresă**, nu un simplu text |
| regimul de muncă şi de odihnă, durata zilei şi a săptămînii | l) | intrare a calculului de timp |
| perioada de probă | m) | „după caz" — nullable |
| durata concediului de odihnă anual **şi condiţiile de acordare** | n) | două câmpuri |
| condiţiile de asigurare socială / medicală | p), r) | în model, trimitere la legislaţie |
| clauzele specifice (art. 51) | s) | mobilitate, confidenţialitate, transport, comunale, spaţiu locativ, altele — **cu indemnizaţia specifică asociată**, art. 51 alin. (2) |

### 4.2 Câmpuri cerute de **IRM19** ca relația să fie raportabilă

| Câmp | De unde | Observație |
|---|---|---|
| **IDNP** al salariatului | col. 3 | *„Câmpul este obligatoriu pentru completare"* — **citat**. Există o cale pe hârtie la CNAM pentru cei fără IDNP |
| **CPAS** — cod personal de asigurare socială | col. 4 | versiunea rusă: dacă lipsește, **se indică 0** |
| **Codul CNAS al angajatorului** | preambul | **distinct de IDNO**; „semnul convențional de înregistrare atribuit de CNAS fiecărui plătitor de contribuții" |
| subdiviziunea SFS de deservire | preambul | atribut al companiei, nu al contractului |
| **codul raporturilor de muncă** (01/05/02/03/04, 06–10 militari) | col. 8 + anexa nr. 7 | **evenimente**, nu stări: angajare, încetare, suspendare, anulare a suspendării |
| **data atribuirii codului** din col. 8 | col. 10 | data evenimentului de raport |
| **motivul eliberării**, cod din 13 valori | col. 9 + anexa nr. 8 | obligatoriu la încetare; **legat de articolul de lege**, nu de text liber |
| **categoria persoanei asigurate** pentru riscul asigurat | col. 5 + anexa nr. 9 | 157 / 158 / 165; **nu se completează pentru angajaţi şi eliberaţi** |
| **perioada riscului asigurat**, început şi sfârşit | col. 6, 7 | **poate depăşi perioada de gestiune**; concediul paternal 5–45 zile (proiect 2026) |
| **codul funcţiei cu drept la pensie în condiţii avantajoase** | col. 11 | clasificator CNAS, **act neidentificat** |
| **data atribuirii** la codul din col. 11 | col. 12 | |
| **tipul dării de seamă** (primară / de corectare) și **numărul celei corectate** | preambul | mecanism de corecție al raportului, distinct de storno contabil |

### 4.3 Ce iese la iveală și **nu** e în schema derivată din calcul

Cinci lucruri pe care le-a produs citirea actelor și pe care o listă derivată din ce consumă
calculul nu le are cum le produce:

1. **Faptul generator al raportării este ordinul angajatorului, nu contractul.** Instrucțiunea,
   pct. 3, **citat**: *„se completează în corespundere cu ordinele întocmite de către angajator"*;
   pct. 2: termenul curge *„începând cu ziua următoare după data indicată în ordin"*. **Deci
   înregistrarea trebuie să poarte data ordinului, numărul lui, și tipul de eveniment** — altfel
   termenul de 10 zile lucrătoare nu se poate calcula. **Contractul nu e suficient.** Excepție
   explicită: funcţia cu pensie în condiţii speciale, pct. 3 lit. c), *„nu se întocmește ordinul"*.
2. **Suspendarea şi anularea suspendării sunt evenimente raportabile** (codurile 03 și 04), cu o
   listă **negativă** de excepţii în nota anexei nr. 7 — suspendările din circumstanţe independente
   de voinţa părţilor, concediul pentru îngrijirea unui membru bolnav al familiei şi concediul
   parţial plătit până la 3 ani **nu se raportează cu codul 03**. **O implementare care raportează
   orice suspendare produce declaraţii greşite.**
3. **„Angajat şi eliberat în 10 zile" cere două înscrieri** în același formular (pct. 2). Regula
   validează observația din ADR-065 §233 despre reangajare — dar din partea cealaltă: **o singură
   relație de muncă poate genera legitim mai multe rânduri IRM19**, iar asta nu e o coliziune de
   date, e cerința actului.
4. **Ramura „militar" (codurile 06–10)** e un al doilea vocabular pentru aceleaşi patru evenimente,
   selectat după **calitatea persoanei**, nu după eveniment. `R28`: forma raportării nu e per
   tenant, dar **selectarea vocabularului e o cheie de context** care trebuie să existe.
5. **Modificarea contractului are declanșator legal explicit**: pct. 21 din modelul consolidat 2020
   — *orice* schimbare a *oricărei* clauze din art. 49 alin. (1) cere act adiţional semnat, anexat,
   parte integrantă (pct. 20). **Un `employment_contract` care se actualizează pe loc, fără istoric
   de acte adiţionale, nu poate demonstra conformitatea.**

### 4.4 Verdict pentru ADR-065 §11

**Lista din ADR-065 nu poate fi declarată completă pe baza acestui dosar, dar poate fi declarată
verificabilă:** art. 49 alin. (1) dă **19 clauze** obținute integral, iar IRM19 dă **12 coloane plus
9 rubrici de preambul** obținute integral. Ce rămâne deschis, și blochează o declarație de
completitudine, e enumerat mai jos — în special **redacția lit. i)** (§2.4) și **Anexa nr. 4¹**
(§1.8), fiindcă prima schimbă un câmp de salarizare, iar a doua e singura specificație a
validărilor la depunere.

---

## 5. Constatări colaterale, pentru fișierele vecine

*Nu se aplică nicăieri de aici; se semnalează.*

1. **`f2-x2-formularele-sfs.md`, „Ce nu s-a putut verifica" pct. 8** — „Ordinul MF nr. 126/2017 —
   presupus a fi actul codurilor surselor de venit — nu a fost cercetat deloc". **Identitatea e
   acum verificată** (MO nr. 383-388 din 03.11.2017, poz. 1947) și **atribuirea se confirmă în
   substanță, dar nu în formă**: tabelul „Cod / Tipul sursei de venit" (`11 Plăţi salariale, art.88
   din Codul fiscal / SAL`, `12 Plăţi salariale, art.24 alin.(2¹) din Legea … / SAL a)` ș.a.m.d.)
   **stă în interiorul anexei nr. 1 — formularul IPC18 însuși**, nu într-o anexă separată de
   coduri. Pentru IPC21 codurile trăiesc în Ordinul MF nr. 94/2020, nu aici.
2. **`f2-x1-identitatile-actelor.md`, pct. 5** — „Codul muncii — data ediției (29.07.2003) și
   art. 391 apar doar în surse neoficiale". **Art. 391 alin. (1) e acum citat** (§2.1), iar data
   29.07.2003 e confirmată de **două** consolidări în format de tipar al Registrului. Rămân copii
   de terți; pagina de ediție MO din 2003 **tot nu a fost localizată**.
3. **Identitate MO nouă**: **Legea nr. 156/2025** pentru modificarea unor acte normative (aspecte
   legate de acordarea concediului paternal) — **MO 2025, nr. 340-342, art. 409**, citată în
   preambulul proiectului MF 2026. *Aceeași ediție ca Legea nr. 139/2025 (art. 389).*
4. **Wayback Machine este accesibil din acest mediu la 30.08.2026.** Ce e blocat de Cloudflare pe
   `sfs.md` se poate lua din arhivă, inclusiv PDF-uri de un megabyte — cu observația că serverul
   arhivei **taie la 1 048 576 de octeți** și cere reluare (`curl -C -`) pentru restul. `legis.md`
   rămâne inaccesibil şi neaarhivat.

---

## Ce nu s-a putut verifica

Fiecare poziție e un blocaj real, cu ce s-a încercat.

1. **Textul adoptat al Ordinului MF nr. 33/2019 — necitit.** Ce s-a citit în loc: consolidarea
   Ordinului 126/2017 republicată de SFS (instantaneu Wayback **28.11.2021**) și **proiectul** MF
   din februarie 2019, cu numărul ordinului în alb. Încercat: `legis.md` (403 pe pagină, pe
   `rezultate/113775`, pe `downloadpdf/113775`, inclusiv cu antet complet de browser); `sfs.md`
   direct (403); MO — text cu plată. **Clauza proprie de intrare în vigoare a Ordinului 33/2019 nu
   a fost citită** — datele 22.02.2019 și 01.04.2019 vin din **chenarele consolidării**, nu din act.
2. **Anexa nr. 4¹ — „Cerințele la completarea Informației (Forma IRM19)" — textul integral
   neobținut.** Se cunosc doar punctele 5 și 6 **în redacția propusă** de proiectul MF 2026.
   Încercat: `particip.gov.md` (nota informativă și proiectul obținute — atașamentele 32144 și
   32145; sondate 32143, 32146, 32147 — sunt din alte dosare), căutare după titlul anexei,
   `mf.gov.md/ro/lex`, `raportare.gov.md/reports-sfs` (**HTTP 500**), `sfs.md` (403),
   `legis.md` (403). **Numărul total de puncte al anexei e necunoscut.**
3. **Care act a introdus Anexa nr. 4¹.** Ordinul MF nr. 14 din 31.01.2024 are identitatea MO
   verificată (**nr. 50-53 din 02.02.2024, poz. 106**), dar **titlul lui nu numește Ordinul
   126/2017**, iar atribuirea vine dintr-un rezumat de motor de căutare — *fragment indexat*.
   Textul ordinului: neobținut.
4. **Lista modificărilor Ordinului 126/2017 nu e completă după 30.07.2020.** Căutarea MO după
   „126 din 4 octombrie 2017" întoarce șapte ordine, ultimul fiind nr. 77 din 17.06.2020; **OMF
   nr. 96 din 30.07.2020 nu apare deloc**, deși consolidarea îl citează de patru ori. Căutarea după
   „unor ordine ale ministrului finanțelor" (2024–2026) întoarce **nr. 57/2024, nr. 48/2025,
   nr. 142/2025, nr. 35/2026, nr. 59/2026, nr. 77/2026** — **din titlu nu se poate spune care ating
   126/2017**. Verificarea ar cere textul fiecăruia.
5. **Ordinul MF nr. 56 din 27.04.2026 — nici textul, nici cuprinsul MO nu au fost citite aici.**
   Existența, obiectul (Anexa nr. 4¹ și Anexa nr. 6) și intrarea în vigoare la publicare vin dintr-o
   **pagină CNAS**. Numărul de poziție MO (186-189/30.04.2026, poz. 334) e preluat din
   `f2-x2-formularele-sfs.md` și **nu a fost reverificat**.
6. **Actul care aprobă „Clasificatorul funcţiilor care dă dreptul la pensie în condiții
   avantajoase" (col. 11) — neidentificat.** Instrucțiunea spune doar „aprobat de CNAS". Nu e anexă
   la Ordinul 126/2017. **Coloana 11 nu se poate implementa fără el.**
7. **Redacția în vigoare a art. 49 alin. (1) lit. i) — nerezolvată.** Consolidarea citită are
   tăietura 2019; două surse mai noi dau o formulare cu „formele și modul de achitare a plăților
   salariale"; actul modificator nu a fost identificat. Încercat: `legis.md` (403 pe doc_id 8238,
   113032, 121610, 135052, 137311, 142355, 142481, 151096 și pe `downloadpdf/142356`), Wayback
   (CDX gol pentru `downloadpdf/8238` și `downloadpdf/142356`; snapshot 2023 al paginii — 404),
   căutare MO după „Codul muncii" 2020–2026 (întoarce o singură lege: **nr. 194 din 10.07.2025**,
   MO nr. 430-433 din 14.08.2025, alinierea la Convenția OIM nr. 190/2019), sinteza CNSM a Legii
   nr. 243/2022 (nu menţionează art. 49), `ism.gov.md` (paginile de ghid nu citează art. 49).
8. **Nicio consolidare a Codului muncii mai nouă de 2019 nu a fost găsită.** Verificate:
   `usmf.md` (tăietura 2019), `cpbmd.info` (tăietura **01.08.2016**, deși fișierul e din ianuarie
   2026), `usch.md`, `cnpm.md` (rusă), `cartier.md`, `law-moldova.com`. **Copia cea mai nouă rămâne
   cea din 2019.**
9. **Textul modificărilor aduse modelului de contract de Convenția colectivă nr. 18/2020 — necitit
   ca act.** S-a citit doar **rezultatul consolidat**, în broșura CNSM din 2021, plus textul integral
   al Convenției nr. 13/2012 (copie `usmf.md`). Ce s-a schimbat la pct. 12, 21 și 27 s-a stabilit
   prin **diferență între două copii**, nu prin citirea actului modificator.
10. **Pagina de ediție MO pentru nr. 101-103/2005 nu a fost deschisă.** Identitatea Convenției
    nr. 4/2005 vine de pe **pagina de căutare** `monitorul.gov.md` și din antetul broșurii CNSM,
    nu de pe cuprinsul ediției. Sondarea id-urilor pentru 2005 nu a fost făcută.
11. **Modelul de contract pentru „perioada îndeplinirii unei anumite lucrări" (CC nr. 16/2018) —
    necitit.** Este relevant pentru art. 49 lit. f¹) și pentru orice contract art. 312–316. Există
    în broșura CNSM, la pagina 30 și următoarele; nu a fost extras în acest dosar.
12. **`old.cnas.gov.md` — HTTP 500** la pagina „Aspecte la completarea Formei IRM 19", singura
    explicație practică publicată de CNAS găsită. Nu s-a încercat prin Wayback.
13. **Schema tehnică a depunerii electronice (XML/XSD, lungimi de câmp, codificare)** — neobținută.
    `raportare.gov.md` servește anexele ca PDF; nu s-a găsit un pachet de scheme. **`F2.C2` nu poate
    fi implementat pe această bază fără Anexa nr. 4¹ și schema portalului.**
14. **Nu s-a verificat dacă IRM19 mai poartă numele „IRM19" după 2026.** Formularul spune „Forma
    IRM 2019", instrucțiunea „Forma IRM19", nota informativă 2026 „Informația IRM19". Cele trei
    denumiri coexistă în acte.
