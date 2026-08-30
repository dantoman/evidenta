# ADR-065 — Schema salarizării: obligația angajatorului și reținerea din salariat sunt două structuri, nu una parametrizată

- **Status:** **Acceptat** — **decizie de domeniu** contabil și fiscal, semnată de proprietar în rol de
  contabil practicant ([ADR-010](010-contabilul-practicant.md), sub [ADR-002](002-guvernanta-deciziilor.md)).
  **Revizuit înainte de semnare de `fiscal-reviewer`, `accounting-reviewer` și `schema-reviewer`: cinci
  CRITICAL, toate confirmate pe sursă și corectate.** Unul dintre ele a redeschis `DNB-05` — argumentul
  de volum pe care se luase decizia era fals (§8.1); decizia a rămas aceeaşi, motivele sunt altele
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** `DNB-05` (granularitatea postării, §8), `OD-81` (forma substitutivă, §3.2 — prin refuz explicit)
- **Deschide:** `OD-83` (ramificarea pe statut fiscal, §3.2.1), `OD-84` (accesul pe rapoartele cu dimensiune de angajat, §8.6)
- **Afectează:** `operations/payroll` (nescris), catalogul de roluri de cont, `platform/tenancy`
  (categoria de plătitor CAS), `F2.B1`–`F2.B6`
- **Legate:** [ADR-039](039-valuta-si-perioade.md) §9.1, [ADR-044](044-data-de-rezolutie.md) §6,
  [ADR-045](045-sursa-de-adevar-pentru-parametri.md), [ADR-048](048-formula-si-sloturile-tipizate.md),
  [ADR-060](060-vocabularul-capabilitatilor.md), [ADR-061](061-cumulativele-de-salarii.md),
  [ADR-066](066-rezerva-e-decizie-deschisa.md)

## 1. Context

`F2.B0` cere schema fixată **înaintea codului**, ca `F2.A0` pentru comerț: ce entități există, ce
poartă fiecare, ce roluri de cont se leagă, ce formă are postarea. Nimic din `operations/payroll` nu e
scris; `employee_id` există ca dimensiune numită din F1.2 și ca coloană pe `journal_line`, comentată
`# F2`, iar catalogul de roluri are un singur rol de salarii — `IMPOZIT_VENIT_SALARIU` (5342).

## 2. Decizia structurală: două naturi, nu două cote ale aceluiași lucru

**Modelul evident e greșit, și e greșit în felul care trece toate testele.** Un tabel
`contribution(kind, employer_rate, employee_rate)` pare economic și simetric. Nu descrie ce se
întâmplă.

**Ce spun actele, pentru 2026:**

| Obligație | Cine o suportă | Efect contabil |
|---|---|---|
| **CAS** — 24% privat / 29% bugetar | **angajatorul**; contribuția individuală e **0% din 01.01.2021** (Legea nr. 60/2020) | **cheltuială** a angajatorului + datorie faţă de BASS. **Nu atinge netul salariatului** |
| **CNAM** — 9% | **angajatul**, reţinut de angajator; angajatorul **0%** | **reţinere** din salariul brut + datorie faţă de FAOAM. **Nu e cheltuială a angajatorului** |
| **Impozit pe venit** — 12% (art. 15) | **angajatul**, reţinut la sursă (art. 88) | **reţinere** + datorie faţă de buget |

**Dovada cea mai greu de contestat nu e o cotă, e absența unui cod.** Ordinul ministrului finanțelor
nr. 149 din 29.12.2025, anexa nr. 5, clasificatorul codurilor economice: primele FAOAM **achitate de
angajaţi** au codul 122100; contribuţiile de asigurări sociale **virate de angajatori** au codul
121100. **Nu există cod economic pentru primă CNAM achitată de angajator, nici pentru contribuţie CAS
individuală.** Un cod economic care nu există nu poate primi bani.

Denumirea formularului o poartă la fel: IPC21 raportează primele AOAM **reţinute** şi contribuţiile
CAS **calculate**.

### 2.1 Structura pe natură, nu pe instituție — ca să nu se învechească

Asimetria de mai sus e **un fapt al anului 2026**, iar un model construit pe el ar fi corect azi și
greșit după prima lege care mută o cotă dintr-o parte în alta. Deci separarea **nu** e „CAS e al
angajatorului, CNAM e al salariatului". E:

> **O obligație a angajatorului și o reţinere din salariat sunt două fapte economice diferite, cu
> postări diferite.** Una creează cheltuială; cealaltă nu creează niciuna — mută o parte din brut de
> la salariat către un buget.

Două structuri:

- **`EmployerCharge`** — calculată *peste* brut, în sarcina angajatorului. Postare: **debit cheltuială,
  credit datorie**. Azi conține exact o intrare: `cas.employer`.
- **`EmployeeWithholding`** — reţinută *din* brut, în sarcina salariatului. Postare: **debit datorii
  salariale, credit datorie**. Azi: `cnam.employee`, `income_tax.withheld`.

**Ce se câștigă:** dacă mâine reapare o contribuție individuală CAS, ea intră ca `EmployeeWithholding`
cu cheia `cas.employee` — ceea ce e exact corect — fără schemă nouă. Dacă apare o primă CNAM a
angajatorului, intră ca `EmployerCharge`. **Cine suportă e dată; forma postării e cod** (`R28`).

**Ce se pierde, spus explicit:** un ecran care vrea să arate „CAS: angajator X, salariat Y" pe un rând
trebuie să citească două structuri. Corect — fiindcă cele două valori n-au aceeași natură, iar rândul
care le alătură e prezentare, nu model.

### 2.2 A treia structură, care lipsea: recunoașterea brutului

Prima redactare a acestui ADR numea două structuri și presupunea tăcut a treia — **salariul brut
însuși**, fără de care nici cheltuiala, nici datoria salarială nu există. Ridicat de
`accounting-reviewer`; e chiar faptul de care depinde toată înregistrarea.

- **`SalaryAccrual`** — brutul recunoscut pentru perioada de muncă. Postare: **debit cheltuială pe
  destinație, credit datorii salariale**, pe suma brută.

Reţinerile **nu** creează linii de cheltuială: ele mută o parte din brut de pe datoria salarială către
o datorie faţă de un buget. De aceea netul nu e o valoare stocată, ci **soldul rămas pe datoriile
salariale** după reţineri — verificat pe exemplul din §8.2.

## 3. Cota CAS nu e globală — dar nici pur a companiei

> **REZERVĂ (`OD-85`) — restrânsă 2026-08-30 prin
> [ADR-068](068-anexa-citita-categoria-e-a-raportului.md):** anexa nr. 1 la Legea nr. 489/1999 **a
> fost obţinută**, în **versiunea 2020**. Maparea punctelor de mai jos e confirmată acum la sursă, nu
> doar din actul de aplicare. Ce rămâne rezervat sunt **valorile curente pentru pct. 1.5, 1.8 şi
> 1.9** — redacţia curentă a anexei e neobţinută.
>
> **Şi §3.1 de mai jos e depăşit:** ADR-068 §3 arată că **categoria e a raportului, nu a companiei**,
> şi nu din cazuri marginale, ci din regimul normal al unui rezident de parc IT.
>
> **Provenienţa, restaurată.** Prima redactare scria „Anexa nr. 1 la Legea nr. 489/1999 o dă pe
> categorie de plătitor", ca şi cum anexa ar fi fost citită. **Nu e.** Cercetarea o spune explicit la
> „Ce nu s-a putut verifica" pct. 1: *textul verbatim al anexei nr. 1 n-a fost obţinut*; cotele de
> 24%, 29%, 39%, 32%, 18% şi 6% sunt citate din **Ordinul CNAS nr. 31-A din 18.02.2026**, act care
> **aplică** anexa, nu din anexa însăşi — `legis.md` întoarce 403, Monitorul Oficial e cu plată.
> [ADR-044](044-data-de-rezolutie.md) §6 purta rezerva şi cerea confirmarea *înainte de scrierea
> handlerului de salarii*; acesta e handlerul, deci rezerva stă aici, nu se pierde.

Categoriile, **cu numerele de punct corectate** — prima redactare punea 29% la pct. 1.2, ceea ce e
greşit şi ar fi produs o mapare punct → cotă falsă:

| Punct | Cotă | Cine |
|---|---|---|
| **1.1** | **24%** | angajator privat, ÎS, ÎM, organizaţii comerciale, învăţământ superior, instituţii medico-sanitare |
| **1.1** | **29%** | angajator din autorităţi/instituţii bugetare, licee, gimnazii, colegii publice, misiuni diplomatice |
| **1.2** | 39% / 32% | aviaţie civilă, **pentru funcţiile în condiţii speciale** |
| **1.5** | 24%, din care 6% compensat de la buget → virează **18%** | agricultură, ≥ 70% activităţi în grupele CAEM 01.1–01.6 (2026) |
| **1.9** | 6% | **zilieri** — datorată de beneficiarul de lucrări |
| **1.4** | — | **rezidenţi ai parcurilor IT: nu se aplică o cotă la brut** (§3.2) |

Ordinul CNAS nr. 31-A pct. 9, verbatim, e chiar ce fixează primele două rânduri: *„în categoria
plătitorilor prevăzută la **punctul 1.1** se includ angajatorii (…) conform **tarifului de 29% sau
24%**"*. **Ambele stau sub acelaşi punct şi se disting prin sector**, nu prin număr de punct.

Şi categoria **se schimbă în cursul anului**: pct. 1.8 (transport de persoane în regim de taxi) e
exclus din **01.07.2026** prin Legea nr. 318/2025, iar acei angajatori trec la pct. 1.1 cu 24%.

### 3.1 Categoria e a companiei — pentru domeniul declarat al F2, cu limitările numite

`company_cas_payer_category` cu `valid_from` / `valid_to` acoperă tranziţia taxi şi distincţia
privat/bugetar. **Prima redactare afirma mai mult decât e adevărat** — că e stare a companiei, punct.
Din propria sursă, două categorii nu sunt ale companiei: *(ridicat de `fiscal-reviewer`)*

- **aviaţia (pct. 1.2)** se aplică *funcţiilor* în condiţii speciale, nu întregii companii;
- **zilierii (pct. 1.9)** pot coexista cu salariaţi obişnuiţi în aceeaşi companie.

**Decizia nu se inversează.** Categoria rămâne atribut al companiei **pentru domeniul declarat al
F2** — angajaţi cu contract individual de muncă, la un angajator dintr-o singură categorie. Cele două
de mai sus sunt **limitări de domeniu consemnate, nu omisiuni**: aviaţia e improbabilă pentru profilul
ţintă; zilierii nu sunt — evenimente, curăţenie, muncă sezonieră.

> **Forma extinderii, scrisă acum ca să nu fie redescoperită:** dacă zilierii intră vreodată în
> domeniu, categoria devine **atribut pe raportul de muncă**, nu pe companie, iar cea de pe companie
> rămâne implicitul. Migrarea e aditivă în direcţia asta şi nu e în cealaltă — de aceea se scrie acum,
> nu atunci.

**Tiparul de implementat, numit exact:** `company_vat_registration` are protecţia de suprapunere nu în
model, ci în `infra/migrations/0010_tenancy.up.sql` — `EXCLUDE USING gist (company_id WITH =,
daterange(valid_from, valid_to, '[)') WITH &&)`. Cine copiază doar `models.py` livrează fără ea, iar
compania poate purta tăcut două categorii active simultan; baza ar răspunde atunci arbitrar la „ce
cotă are azi", şi răspunsul ar arăta ca un număr corect. *(Ridicat de `schema-reviewer`.)*

### 3.2 Rezidenţii parcurilor IT — a doua **formă** de calcul, nu a şaptea categorie

Pct. 1.4: pentru salariaţii rezidenţilor parcurilor IT, CAS, CNAM şi impozitul pe venit **se acoperă
din impozitul unic** al companiei (Legea nr. 77/2016; venit lunar asigurat 11 832 lei în 2026 = 68% ×
17 400, HG nr. 773/2025), iar art. 15 din Codul fiscal îi privează de scutirile art. 33–35.
Declaraţia e **IU17**, nu IPC21.

**Nu e caz marginal:** ţinta F2 e *o companie de servicii*, iar serviciile IT sunt exact profilul care
intră în parc.

**Întrebarea corectă e câte forme de calcul intră în F2, nu câte categorii** — categoriile sunt date,
formele sunt structură. Clasificate pe formă, nu pe instituţie, tabelul din cercetare dă:

| Formă | Ce o defineşte | Categorii care o folosesc |
|---|---|---|
| **1. Sarcină a angajatorului** — cotă peste brut | `EmployerCharge`, §2 | pct. 1.1 (24/29), 1.2 (39/32), 1.3, 1.5 (18), 1.9 zilieri (6) |
| **2. Reţinere din salariat** — cotă din brut | `EmployeeWithholding`, §2 | CNAM 9%, impozit 12% |
| **3. Substitutivă** — obligaţia e înlocuită de un impozit al companiei, pe altă bază | **nemodelată** | pct. 1.4 (parcuri IT), pct. 1.10 (antreprenori independenţi) |
| *(4. Sumă fixă pe perioadă)* | — | pct. 1.6–1.8: **nu sunt raporturi de muncă**, sunt persoane care se asigură singure → **în afara salarizării** |

**Rezultatul măsurătorii: pentru salariaţi există exact trei forme, iar a treia lipseşte.** Citit cum
a fost pusă întrebarea — moduri, nu structuri — sunt **două: obişnuit şi substitutiv**, unde
„obişnuit" conţine formele 1 şi 2. **Bănuiala se confirmă**, iar forma 4 e rezultatul negativ util:
părea a patra şi nu e, fiindcă acei oameni nu sunt angajaţi.

#### 3.2.1 Ce ar cere schemei forma substitutivă — măsurat

| Ce | Cost | Măsurat |
|---|---|---|
| Starea de rezident, cu dată efectivă (`company_it_park_residency`) | **mic** — acelaşi tipar ca `company_vat_registration` | necesar **şi dacă se refuză**: ca să refuzi, trebuie să ştii |
| Venitul lunar asigurat per angajat, **nederivat din salariu** | **mic** — un câmp pe linia de salariu | azi nimic nu poartă o bază care nu vine din brut |
| **Discriminatorul de tratament** | **mare — aici e costul** | `selected_treatment(event_type, accounting_date, capability_snapshot)`; `HandlerVersion.requires` e `frozenset[str]` comparat **doar cu capabilităţile**. Un regim fiscal **nu e capabilitate** ([ADR-060](060-vocabularul-capabilitatilor.md): criteriul de apartenenţă e *ce cere iniţializare*, iar un statut fiscal nu se vinde şi nu se activează). Deci motorul **n-are pe ce ramifica** |
| Declaraţia IU17 în loc de IPC21 | mediu | e al lui `F2.C2`, nu al salarizării |
| Impozitul unic însuşi | **zero pentru salarizare** | se calculează pe venitul companiei → `operations/tax` |
| Scutirile pierdute | mic | rezolvarea scutirilor trebuie să cunoască regimul |

> **Constatarea care contează:** dacă motorul poate ramifica doar pe capabilităţi, atunci **orice**
> diferenţă de tratament condusă de un statut fiscal n-are unde să meargă. Nu e o problemă a parcurilor
> IT — e o limită a selecţiei de tratament, pe care parcurile IT o scot prima la iveală. A o rezolva
> înseamnă o a doua dimensiune ştampilată pe `accounting_event` alături de `capability_snapshot`,
> pentru `R18` — deci ADR peste ADR-038 şi ADR-060, plus o coloană.

**Asimetria costului a decis.** A **refuza** costă o tabelă cu dată efectivă şi un cod de eroare — iar
tabela e necesară oricum. A **include** cere a doua dimensiune ştampilată pe `accounting_event` pentru
`R18`, deci ADR peste ADR-038 şi ADR-060 plus o coloană: **decizie de motor, care merită luată pentru
forma generală, nu grăbită pentru un caz.**

> **Decis de proprietar, 2026-08-30 (`OD-81`): forma substitutivă NU intră în F2.**
>
> - `company_it_park_residency`, cu dată efectivă, pe tiparul lui `company_vat_registration`;
> - **rularea de salarii refuză explicit** o companie cu statut activ, cu **cod de eroare propriu**
>   (`C10`) — nu o calculează greşit, nu o ignoră;
> - nimic din calcul nu se scrie pentru acest regim.
>
> **Ce nu se poate e să lipsească fără să strige** — profilul-ţintă al F2 e exact o companie de
> servicii, iar serviciile IT sunt profilul care intră în parc.

**Constatarea care depăşeşte parcurile IT** — că motorul ramifică doar pe capabilităţi, deci **orice**
diferenţă de tratament condusă de un statut fiscal n-are unde să meargă — **nu se închide aici**: e
limitare structurală de motor, deschisă ca **`OD-83`**, de luat **înainte de al doilea caz, nu la el**.
Parcurile IT sunt primul.

### 3.3 Plafonul

**Nu e plafon anual pentru contribuţia angajatorului.** Plafonul istoric de 5 salarii medii prognozate
era legat exclusiv de contribuţia individuală de 6%, abolită la 01.01.2021, şi a dispărut odată cu ea.
*Inferenţă din absenţă, coroborată cu abolirea — marcată ca atare în cercetare, şi marcată aici.*
Consecinţă: nicio structură de cumulare pentru CAS ([ADR-061](061-cumulativele-de-salarii.md) o spune
din partea cealaltă).

> **Atenţie la omonimie, ca să nu se citească greşit paragraful de mai sus:** există un plafon **viu**
> de „5 salarii medii lunare prognozate" — dar la **altceva**: baza de calcul a indemnizaţiilor de
> asigurări sociale, Legea nr. 289/2004 art. 7. Acela e text statutar citit, nu inferenţă, şi e al lui
> `F2.B3`.

## 4. `employee` — persoana, la nivelul companiei

**Angajatul e al companiei, nu al tenantului.** Angajatorul legal e compania: ea reţine, ea depune
IPC21, ea răspunde. O persoană care lucrează la două companii ale aceluiași tenant are **două relații
de muncă**, cu două reţineri și două declarații — iar scutirile se acordă **la un singur loc de muncă**
(HG nr. 697/2014 pct. 9), ceea ce e o proprietate a relației, nu a persoanei.

Poartă: `tenant_id`, `company_id` (`R1`), `idnp`, numele legal, **rezidența fiscală**.

**Identitatea, scrisă ca constrângere, nu ca afirmație.** Prima redactare spunea „identitatea de
business e `(company, idnp)`" fără să declare vreodată constrângerea, și relaxa `idnp` la `NULL`
pentru nerezidenți fără să pună nimic în loc — deci exact pentru rândurile pentru care se făcea
excepția **nu rămânea nicio cheie naturală**, iar aceeași persoană putea fi introdusă de două ori la
reangajare, cu două șiruri de rețineri și două notificări IRM19 pentru o singură relație. Ridicat de
`schema-reviewer`. Corect:

- `UNIQUE (company_id, idnp) WHERE idnp IS NOT NULL` — rezidenții;
- pentru cine n-are IDNP: `identity_document_type` + `identity_document_number`, cu
  `UNIQUE (company_id, identity_document_type, identity_document_number) WHERE idnp IS NULL`;
- un CHECK care cere **exact una** dintre cele două identități, ca rândul fără niciuna să nu existe.

**Colaţia, pe tiparul lui `Company.idno`** (`C34`, [ADR-015](015-colatie-icu.md)): `idnp` și numărul
documentului sunt **coduri** — `COLLATE "C"`, aplicat în SQL-ul migrării; numele legal e **denumire**
și rămâne pe colaţia bazei. Fără asta, orice raport ordonat după IDNP iese sortat lingvistic, tăcut.

Datele sunt sensibile: accesul se auditează (`platform/audit`), iar `C37` rămâne — niciun termen de
model în interfață.

## 5. Scutirile sunt o cerere cu dată efectivă, nu bifă pe angajat

Art. 88 și Regulamentul aprobat prin **Hotărârea Guvernului nr. 697 din 22.08.2014** (Monitorul
Oficial nr. 256-260/745 din 29.08.2014): angajatul depune *„cererea privind acordarea scutirilor la
impozitul pe venit reţinut din salariu"* (anexa nr. 6), nu mai târziu de data începerii lucrului.
Scutirile **se acordă sau se anulează începând cu luna următoare** celei în care s-a depus sau retras
cererea (pct. 18); la schimbare, cerere nouă în 10 zile (pct. 22).

> **Deci nu e stare, e istorie.** O bifă pe angajat n-ar putea răspunde „ce scutiri avea în martie",
> iar `R18` cere exact asta la recalcularea unei luni trecute. Aceeași formă ca `R25` — activarea e
> entitate cu dată efectivă, nu boolean.

**Ce trebuie stocat ca regula să fie verificabilă, nu doar respectată de cod:** cererea poartă
`filed_on` — data depunerii — pe lângă `valid_from`. Fără ea, pct. 18 („din luna următoare") e regulă
doar în aplicație: un import în masă sau o corecție scrisă direct în tabelă o ocolește, iar
recalcularea unei luni trecute (`R18`) n-are faptul stocat din care să arate că data efectivă a fost
calculată corect. Cu ea, e un CHECK. *(Ridicat de `schema-reviewer`.)*

**Două capcane, impuse în schemă fiindcă amândouă produc erori plauzibile și tăcute:**

1. **Scutirea ordinară pentru soţ/soţie nu se acordă.** Există doar cea majorată, art. 34 alin. (2).
   Vocabularul codurilor e deci **`P`, `M`, `Sm`, `N`, `H` — fără `S`**. Parametrul
   `income_tax.exemption_spouse_ordinary = 0` există deja încărcat tocmai ca scutirea care nu se
   acordă să nu fie inventată. **Iar HG 697/2014 pct. 11 încă trimite la „art. 34 alin. (1) sau (2)"**
   — regulamentul a rămas în urma Codului. [ADR-045](045-sursa-de-adevar-pentru-parametri.md) e regula
   care oprește „corectarea" motorului după regulament: cuantumurile vin din Cod, regulamentul dă
   procedura.
2. **Nicio constrângere de unicitate pe persoana întreţinută.** Numărul de contribuabili care pot
   folosi scutirea pentru aceeași persoană nu e limitat prin lege — ambii părinţi pot să o folosească
   pentru același copil. **Un `UNIQUE` acolo ar fi invenția noastră**, ar refuza un caz pe care legea
   îl permite, și utilizatorul n-ar avea cum să afle de ce.
   **Dar interdicţia se aplică între contribuabili, nu în interiorul aceleiaşi cereri:** o persoană
   întreţinută are nevoie de un identificator propriu (IDNP unde există, altfel documentul), ca să
   existe constrângerea legitimă — **fără dublură pe `(employee, dependent, code)` cu perioade care se
   suprapun**, adică introducerea de două ori a aceluiaşi copil. Prima redactare interzicea unicitatea
   fără să numească câmpul, deci o interzicea şi pe cea corectă. *(Ridicat de `schema-reviewer`.)*

## 6. Linia de salariu poartă două date, și una dintre ele nu se adaugă mai târziu

[ADR-039](039-valuta-si-perioade.md) §9.1 numește tiparul la a treia lui apariție și avertizează că a
patra ar fi aici:

| Data | Ce e | Ce conduce |
|---|---|---|
| **perioada de muncă** | data economică — pentru ce muncă e plata | declarația nominală, drepturile |
| **data de angajament** | data tehnică — când s-a acumulat | **rezoluția tarifului și a parametrilor** |

Ancorarea nu e a noastră: art. 20 alin. (5) din Legea nr. 489/1999 obligă la contribuţiile **aferente
salariilor calculate**, iar anexa nr. 1 aplică tariful la salariile **calculate lunar**. Deci
[ADR-044](044-data-de-rezolutie.md) §6: **un salariu calculat în iunie pentru muncă din martie se
acumulează în iunie** — e un fapt economic al lunii iunie, nu o recalculare a lui martie, și `R18` nu
e atins.

**La postare:** `accounting_date` = perioada deschisă în care intră angajamentul; `document_date` =
data de angajament. Perioada de muncă rămâne pe linia de salariu, unde o citește declarația nominală.

> Motivul pentru care asta e schemă și nu detaliu: **o linie de salariu deja postată n-are de unde
> să-și afle data de angajament ulterior.**

### 6.1 Argumentul pentru scutiri și cumulative — scris, fiindcă altfel blochează

Tabelul de mai sus spune că data de angajament rezolvă „tariful **și parametrii**". Justificarea de sub
el — art. 20 alin. (5) și anexa nr. 1 — e însă **strict a CAS**. Pentru scutirile art. 33–35 și pentru
metoda cumulativă din [ADR-061](061-cumulativele-de-salarii.md), prima redactare **generaliza fără să
citeze**. *(Ridicat de `fiscal-reviewer`.)* Argumentul, scris:

1. **Reţinerea se face la plată, nu la muncă.** Art. 88 alin. (1) obligă angajatorul care **plăteşte**
   salariu să calculeze şi să reţină din **aceste plăţi**. Faptul care declanşează reţinerea e plata,
   deci perioada lui e a plăţii.
2. **Metoda cumulativă e ancorată pe acelaşi lucru.** HG nr. 697/2014 pct. 38 calculează cumulativ **de
   la începutul anului fiscal sau de la data angajării** — o poziţie care înaintează cu fiecare plată.
   O plată retroactivă nu poate redeschide poziţia cumulativă a unei luni închise: ar cere rescrierea
   unui rezultat deja raportat, ceea ce `R10` interzice pe partea contabilă și ce declaraţia depusă
   interzice pe partea fiscală.
3. **Formularul o confirmă, ca indiciu marcat ca indiciu.** IALS21 col. 6 e descrisă drept *„suma
   totală a venitului îndreptat spre achitare în perioada fiscală (…) **inclusiv plăţile salariale ale
   perioadelor precedente achitate în anul curent**"* — plata retroactivă e venit al anului plăţii.
   **Descrierea vine dintr-un proiect din 2020, nu din ordinul adoptat** (`f2-x2-formularele-sfs.md` o
   marchează aşa), deci coroborează, nu demonstrează.

**Concluzie:** scutirile şi cumulativele se rezolvă pe **data de angajament**, la fel ca tariful CAS —
pe (1) şi (2), care sunt acte citate, cu (3) drept coroborare. Punctele 1 şi 2 sunt suficiente;
punctul 3 rămâne marcat ca proiect.

> **Consemnat ca lipsă de proces:** `f2-x2-formularele-sfs.md` **nu era citat deloc** în prima
> redactare, deşi e singurul fişier care descrie tabelul nominal al IPC21 — coloanele fixate chiar
> aici. Un ADR care fixează câmpurile unei linii de salariu şi nu deschide fişierul care descrie
> declaraţia care le consumă a ratat o verificare disponibilă.

## 7. Rolurile de cont, din Planul general de conturi

Actul: **Ordinul Ministerului Finanțelor nr. 119 din 06.08.2013**, nomenclatorul transcris în
`../_input/cercetare/od-23-nomenclatorul-planului-de-conturi.md`.

| Rol | Cont | Denumirea din act | Stare |
|---|---|---|---|
| `DATORII_SALARIALE` | **5311** | Datorii salariale | **nou** |
| `DATORII_CAS` | **5331** | Datorii faţă de bugetul asigurărilor sociale de stat | **nou** |
| `DATORII_CNAM` | **5332** | Datorii faţă de fondurile asigurării obligatorii de asistenţă medicală | **nou** |
| `CHELTUIELI_PERSONAL_ADMINISTRATIV` | **7131** | Cheltuieli cu personalul administrativ | **nou** |
| `CHELTUIELI_PERSONAL_COMERCIAL` | **7121** | Cheltuieli cu personalul comercial | **nou** |
| `IMPOZIT_VENIT_SALARIU` | 5342 | Datorii privind impozitul pe venit din salariu | **există** |
| `PRODUCTIE_DE_BAZA` | 811 | Activităţi de bază | **există** |
| `COSTURI_INDIRECTE_PRODUCTIE` | 821 | Costuri indirecte de producţie | **există** |

> **Cinci roluri noi, nu şapte — şi corectura nu e cosmetică.** Prima redactare propunea
> `COSTURI_INDIRECTE_PRODUCTIE` (821) ca rol nou. **Există deja** în `roles_snc_2020.csv`, cu acelaşi
> nume şi acelaşi cont. `install_default_bindings` parcurge **toate** rândurile CSV necondiţionat şi
> creează câte o legare per companie, sub constrângerea de excludere `account_role_binding_no_overlap`
> pe `(company, rol)` — deci un al doilea rând cu acelaşi nume ar fi făcut să eşueze provizionarea
> **oricărei** companii, nu doar a celor cu salarizare. Iar `COSTURI_ACTIVITATE_BAZA` (811) ar fi fost
> un al doilea nume pentru contul pe care `PRODUCTIE_DE_BAZA` îl acoperă deja — sinonim inventat
> într-un catalog al cărui principiu declarat e *un singur răspuns corect per rol*. **Ambele destinaţii
> de producţie refolosesc rolurile existente.** *(Ridicat de `schema-reviewer` şi `accounting-reviewer`.)*

### 7.1 Destinaţia costului — mecanismul nu există, şi nu se inventează tăcut

Contul de cheltuială depinde de destinaţie: `cost_destination` pe contract, vocabular închis în cod —
`administrative`, `commercial`, `production_direct`, `production_indirect`.

Prima redactare spunea că e „o cheie de context enumerată în sensul
[ADR-051](051-chei-de-context-enumerate.md)". **Nu e:** ADR-051 e `Acceptat` şi enumeră exact patru
chei — `item_group`, `partner_type`, `vat_rate`, `warehouse` — iar `cost_destination` nu e printre ele.
Măsurat: `AccountRoleBinding` **n-are nicio coloană** `context_key`/`context_value`; mecanismul lui
ADR-051 e decis, nu construit. *(Ridicat de `accounting-reviewer`.)*

Două drumuri, şi niciunul nu se ia tăcut:

1. **A cincea cheie în ADR-051** — modificarea unui ADR `Acceptat`, deci ADR propriu.
2. **Destinaţia selectează rolul, nu legarea** — handlerul cere rolul `CHELTUIELI_PERSONAL_<destinaţie>`
   după valoarea de pe contract; vocabularul rămâne enumerat în cod.

*Poziţia sesiunii: (2).* Destinaţia nu condiţionează ce cont se leagă la un rol — alege **care rol** se
cere, ceea ce e forma postării, deci cod (`R28`), nu configurare. E o decizie, nu o constatare, şi
intră în §10.

**Ce trebuie declarat explicit şi lipsea:** care conturi poartă `employee` în `dimension_slots`
(ADR-048 §3.1). Fără acea declaraţie, `employee_id` nu ajunge pe nicio formulă, oricâte sloturi ar
exista — şi de ea depinde tot §8.

## 8. Forma postării — detaliul per angajat stă în registru (`DNB-05`, închisă)

**Decis de proprietar la 2026-08-30, după ce prima decizie a fost reluată:** `employee_id` într-un slot
de dimensiune, **o formulă per angajat şi tip de sumă**. Liniile urmează formulele, la raportul pe care
motorul îl impune.

### 8.1 Premisa pe care s-a decis prima dată era falsă — consemnată, nu doar corectată

Prima alegere s-a făcut pe argumentul: *„liniile nu cresc cu numărul de angajaţi, formulele da, iar
`journal_formula` e tabela făcută pentru asta"*, cu cifrele „6 salariaţi ≈ 10 linii şi 36 de formule;
200 de salariaţi ≈ 10 linii şi 1 200 de formule" din `../_bootstrap/09-f2-backlog.md`.

**Argumentul era fals, şi e scris aici ca să nu fie citit peste un an ca fapt.** Măsurat în motor:

- `posting/formula.py` — `merge()` pliază două formule doar dacă coincid pe **tot** tuplul cheie,
  **inclusiv `item.slots`**. Cu `employee` purtat, formulele a doi angajaţi nu se pliază niciodată.
- `posting/formula.py` — `lines_to_write()` scrie **exact două** linii per formulă supravieţuitoare:
  *„Two `journal_line` rows per formula: the debit side, then the credit side."*
- `infra/schema/append_only.toml` declară deja acelaşi raport ca proprietate de sistem:
  `journal_formula` e *„aproximativ jumătate din volumul liniilor"*.

**Raportul formulă:linie e fix, 1:2.** „10 linii şi 1 200 de formule" nu poate exista — 1 200 de
formule dau 2 400 de linii. Cele două jumătăţi ale argumentului nu puteau fi amândouă adevărate.
*(Ridicat de `accounting-reviewer`, verificat direct în cod.)*

**Şi al doilea motiv invocat atunci era greşit:** că agregarea „rupe lanţul `R13`". Nu-l rupe. `R13`
cere `Journal Line → Journal Entry → Accounting Event → Source Document → Sursă`, iar lanţul se termină
la **documentul sursă** — aici, rularea de salarii. Agregarea ar fi rămas conformă.

> Decizia a rămas aceeaşi; **motivele sunt altele.** Distincţia contează fiindcă un motiv fals
> supravieţuieşte deciziei pe care a produs-o şi e refolosit la următoarea.

### 8.2 Motivele reale, pe structura măsurată

1. **Volumul e proporţional, nu multiplicativ.** `../_bootstrap/11-volume-model.md`: la mediana reală
   a pieţei — **6 salariaţi** — salarizarea adaugă ~600–900 de linii/an peste 1 080. La 200 de
   angajaţi, ~19 000–29 000/an peste 54 000 din documente: **+35–55%, nu un ordin de mărime.** Modelul
   spune el însuşi că *„nu există problemă de volum per tenant"*; nu se schimbă clasa de mărime a
   tabelei.
2. **Fişa contului rămâne navigabilă direct** — rândul rulării, drill-down la formule per angajat,
   exact cum ADR-053 §3.1 descrie agregarea pe document cu coborâre la formule. Cu detaliul în
   `payroll`, aceeaşi întrebare ar cere un **read model** — al treilea mecanism pentru ce primul face
   direct.
3. **Direcţia e cea reversibilă.** De la detaliu se poate agrega oricând; **agregat → detaliu nu
   recuperează ce nu s-a scris niciodată.**

### 8.3 Granularitatea nu e configurabilă, şi motivul e `R10`

Nu e o preferinţă lăsată deschisă „în caz că": ledgerul postat e imutabil, deci schimbarea ei după
prima rulare postată **nu e migrare, e campanie de storno şi repostare** — pentru fiecare rulare, a
fiecărei companii. Un comutator care pare inofensiv în cod ar fi, la a treia lună de pilot, o lucrare
de recuperare.

### 8.4 Ce trebuie declarat ca să funcţioneze

Conturile care poartă `employee` în `dimension_slots` (ADR-048 §3.1) — cel puţin `DATORII_SALARIALE` şi
cele două de cheltuială cu personalul. Fără declaraţia aceea, `employee_id` nu ajunge pe nicio formulă,
oricâte sloturi ar exista.

### 8.5 Exemplul, verificat

Un angajat, sector privat, destinaţie administrativă:

| | Debit | Credit |
|---|---|---|
| Brut (`SalaryAccrual`) | 7131 20 000,00 | 5311 20 000,00 |
| CAS angajator 24% (`EmployerCharge`) | 7131 4 800,00 | 5331 4 800,00 |
| CNAM 9% reţinut (`EmployeeWithholding`) | 5311 1 800,00 | 5332 1 800,00 |
| Impozit reţinut (`EmployeeWithholding`) | 5311 2 184,00 | 5342 2 184,00 |

Σ debit = Σ credit = 28 784,00 (`R11`), iar soldul rămas pe 5311 — 16 016,00 — **este** netul.
*(Verificat de `accounting-reviewer`.)*

### 8.6 Consecinţa de acces, care vine odată cu detaliul

Cu detaliul în registru, **salariul individual devine vizibil oricui deschide fişa contului 5311** —
un ecran de contabilitate generală, nu unul de salarizare. Nu inversează decizia din §8: e preţul ei,
şi se plăteşte cu control de acces, nu cu agregare.

Rapoartele care expun dimensiunea `employee` — fişa contului, Cartea Mare, corespondenţele, exporturile
— au nevoie de **control de acces propriu**, distinct de dreptul de a citi registrul. `F2.B1` cere deja
audit pe datele personale (`platform/audit`); aceasta e cerinţa simetrică pe partea de citire.

**Nu se proiectează aici** — e teritoriul modelului de permisiuni (ADR-020), nu al schemei de
salarizare. → **`OD-84`**, de închis înainte de primul ecran care afişează dimensiunea de angajat
(`F2.G`).

## 9. `payroll` ca **capabilitate**

[ADR-060](060-vocabularul-capabilitatilor.md): `payroll` e în vocabularul închis, **nu** în
`COMPLIANCE_CAPABILITIES`. Se activează cu `effective_from` la început de lună;
`initialisation_state = required` la start în cursul anului, complet doar cu cumulativele încărcate
([ADR-061](061-cumulativele-de-salarii.md), `F2.B6`). **Odată activată, ieşirile ei declarative nu se
dezactivează şi nu se plătesc separat** — `R24` pe ieşiri, în cod.

## 10. Ce cere semnătura proprietarului, enumerat

**Toate confirmate de proprietar la 2026-08-30**; ADR-ul trece în `Acceptat`.

1. **`DNB-05` — detaliul per angajat stă în registru** (§8), pe motivele din §8.2, nu pe cel fals din
   §8.1.
2. **`OD-81` — forma substitutivă nu intră în F2** (§3.2), cu refuz explicit.
3. **CAS-ul angajatorului pe acelaşi cont de cheltuială ca salariul** pe care se calculează (7131 etc.),
   nu pe un cont separat. **Poziţia sesiunii, nu citat** — actul nu prescrie repartizarea; planul de
   conturi n-are subcont de gradul II pentru contribuţiile angajatorului sub 712/713, iar 7131 e
   *„cheltuieli cu personalul"*, nu *„salarii"*.
4. **Destinaţia costului selectează rolul, nu legarea** (§7.1, drumul 2) — alternativa fiind a cincea
   cheie în ADR-051.
5. **Vocabularul destinaţiei**, patru valori. **Lipseşte deliberat costul vânzărilor** (711x, ex. 7113
   „Costul serviciilor prestate"): o companie de servicii care face costing pe proiect ar putea vrea
   manopera facturabilă în costul vânzărilor, nu în cheltuiala perioadei. *(Ridicat de
   `accounting-reviewer`; e o alegere de fazare, dar e a proprietarului.)*
6. **Netul rămâne pe 5311**; 5312 doar pentru salariul neridicat.
7. **Codurile de scutire** `P`, `M`, `Sm`, `N`, `H`, cu `S` absent deliberat.

## 11. Ce **nu** decide acest ADR, cu declanşatorul fiecăruia

- ~~**Câmpurile contractului nu vin dintr-un act citit.**~~ **Declanşatorul a fost tras: `F2.X2 (k)`
  făcută, 2026-08-30** — [`f2-x2-k-contractul-si-irm19.md`](../_input/cercetare/f2-x2-k-contractul-si-irm19.md).
  Art. 49 alin. (1) e obţinut integral (19 clauze, dintr-o consolidare terţă oprită în 2019, cu lit. i)
  **semnalată ca schimbată ulterior şi actul modificator neidentificat**); IRM19 e obţinut integral
  pentru starea din 2021 — 12 coloane, 9 rubrici de preambul, şi cele două clasificatoare. IRM19 **nu
  are ordin propriu**: e Anexa nr. 3 la Ordinul Ministerului Finanţelor nr. 126 din 04.10.2017
  (Monitorul Oficial nr. 383-388 din 03.11.2017, poz. 1947), rescrisă prin Ordinul nr. 33 din
  19.02.2019 (Monitorul Oficial nr. 59-65 din 22.02.2019, Partea III, poz. 364a).

  **Cinci lucruri pe care lista derivată din calcul nu le avea, şi două dintre ele schimbă schema:**

  1. **Faptul generator al raportării e ordinul angajatorului, nu contractul** — termenul de 10 zile
     lucrătoare curge *„începând cu ziua următoare după data indicată în ordin"*. Înregistrarea trebuie
     să poarte **data ordinului, numărul lui şi tipul evenimentului**; contractul singur nu ajunge.
     **Schimbă schema.**
  2. **Orice schimbare a oricărei clauze din art. 49 alin. (1) cere act adiţional semnat**, anexat şi
     parte integrantă. **Un `employment_contract` actualizat pe loc, fără istoric de acte adiţionale,
     nu poate demonstra conformitatea. Schimbă schema.**
  3. Suspendarea şi anularea ei sunt raportabile (codurile 03/04) cu o listă **negativă** de excepţii —
     o implementare care raportează orice suspendare produce declaraţii greşite.
  4. „Angajat şi eliberat în 10 zile" cere **două înscrieri** în acelaşi formular: o singură relaţie de
     muncă poate genera legitim mai multe rânduri, şi asta nu e coliziune de date.
  5. Ramura „militar" (codurile 06–10) e un al doilea vocabular selectat după **calitatea persoanei**,
     nu după eveniment — o cheie de context care trebuie să existe.

  **Lista rămâne verificabilă, nu completă**, şi ce blochează declaraţia de completitudine e numit:
  redacţia curentă a lit. i) şi **Anexa nr. 4¹** (specificaţia validărilor la depunere, text
  neobţinut). Niciuna nu blochează **construcţia** înregistrării — blochează depunerea, ca la celelalte
  canale.
- **Clasificarea append-only a tabelelor proprii ale salarizării.** `infra/schema/append_only.toml` nu
  e atins de acest ADR, iar linia de salariu per angajat e singura candidată. **Trebuie decis înainte
  de `F2.B1`, nu la prima migrare:** direcţia cheilor străine e ireversibilă în practică — o tabelă cu
  FK-uri intrând nu se repartiţionează, se redesenează (`R21`). *(Ridicat de `schema-reviewer`; e chiar
  premisa „schema fixată înaintea codului".)*
- **Concediile şi indemnizaţiile** — `F2.B3`; consolidările se opresc în 2019.
- **Forma fluturaşului** — convenţie cu minimul din Codul muncii art. 142 alin. (3), în `F2.B4`.
- **Cotele efective** rămân `draft` până la actul proprietarului (`OD-22`).

## 12. Consecinţe

- **Devine posibil, după semnături:** `F2.B2`, `F2.B4`, `F2.B6`. `F2.B1` aşteaptă în plus `F2.X2 (k)`
  şi clasificarea append-only.
- **Devine imposibil:** un model simetric „cotă angajator + cotă salariat"; o cotă CAS globală; o bifă
  de scutire fără istorie; un rând de angajat fără nicio cheie naturală; un al doilea rol cu nume
  identic în catalog; o companie rezidentă de parc IT care rulează salarii tăcut.
- **De modificat ca urmare:** catalogul de roluri primeşte **cinci** rânduri noi (nu şapte); `DNB-05`
  rămâne deschisă până la §8.3; `OD-81` nouă; `09-f2-backlog.md` — `F2.X2 (k)`.
- **Se verifică:** `C12` pe rulare → eveniment → înregistrare, cu sumele per rol egale cu totalurile
  rulării; exemplul din §8.2 ca prim caz; un caz de corpus per regulă (`F2.C5`); recalcularea unei luni
  trecute cu parametrii de atunci (`R18`).

## 13. Surse

- Legea nr. 489/1999, anexa nr. 1 (categoriile de plătitori şi tarifele), art. 20 alin. (5); Legea
  nr. 60/2020 (contribuţia individuală = 0 din 01.01.2021); Legea nr. 320/2025; Legea nr. 318/2025
  (excluderea pct. 1.8 din 01.07.2026); Ordinul CNAS nr. 31-A din 18.02.2026 pct. 9, 13 — prin
  `../_input/cercetare/od-22-cnas-cnam.md`.
- Legea nr. 1593/2002, anexa nr. 1; Legea nr. 321 din 29.12.2025 art. 4 — CNAM 9% angajat, 0%
  angajator; idem.
- **Ordinul ministrului finanţelor nr. 149 din 29.12.2025**, anexa nr. 5, clasificatorul codurilor
  economice (121100, 122100) — dovada bugetară a asimetriei; idem.
- Codul fiscal art. 15, art. 33–35, art. 88, art. 92; Hotărârea Guvernului nr. 697 din 22.08.2014
  pct. 9, 11, 12, 18, 22, 38 şi anexa nr. 6 — prin
  `../_input/cercetare/od-22-impozitul-pe-venit.md`. **Citatele vin din reproducerea SFS, nu din
  Monitorul Oficial**: `legis.md` întoarce 403 şi nu e arhivat.
- Ordinul Ministerului Finanţelor nr. 119 din 06.08.2013 — Planul general de conturi, prin
  `../_input/cercetare/od-23-nomenclatorul-planului-de-conturi.md`.
- Codul muncii art. 142 alin. (3) — prin `../_input/cercetare/f2-x2-concedii-indemnizatii-fluturas.md`.
- `../_input/cercetare/f2-x2-formularele-sfs.md` — IPC21 (tabelul nominal) şi IALS21 col. 6, folosite în
  §6.1 ca **coroborare marcată**: descrierile vin din proiectele din 2020, nu din ordinele adoptate.
  **Consemnat ca lipsă de proces: prima redactare nu deschidea acest fişier deloc**, deşi e singurul
  care descrie declaraţia ce consumă câmpurile fixate aici.
- `../_input/cercetare/od-22-cnas-cnam.md`, „Ce nu s-a putut verifica" pct. 1 — **rezerva de
  provenienţă** pe anexa nr. 1 la Legea nr. 489/1999, restaurată în §3 (vezi `OD-82`).
- `../_bootstrap/09-f2-backlog.md` `F2.B0`; `../_bootstrap/11-volume-model.md`.
- Decizia proprietarului pe `DNB-05`, 2026-08-30.
