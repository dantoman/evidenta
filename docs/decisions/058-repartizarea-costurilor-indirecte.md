# ADR-058 — Repartizarea costurilor indirecte de producție: formula actului ca logică versionată, baza ca date deschise, restul la 714

- **Status:** Acceptat — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md), care
  implementează clasificarea `C5` aprobată de proprietar ([ADR-036](036-forma-postarii.md) §11) în
  ordinea fixată de acesta (2026-08-29: C4, C5, C2, C1); **nu decide niciun tratament**: cele două
  etape, absorbția și baza sunt ale standardului, iar ce e alegere de inginerie e numit ca atare
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului (F1.4.4, al doilea handler din ordinea fixată)
- **Închide:** —
- **Afectează:** `accounting/posting/absorption.py` (nou — regula versionată), `accounting/posting/services/production.py`
  (nou — handlerul și serviciul), `accounting/events` (`SourceModule.PRODUCTION`, migrarea `0003`),
  `accounting/slots/data/roles_snc_2020.csv` (un rol nou, catalogul la 46),
  `fiscal/parameters/data/snc_stocuri.toml` (nou — actul și rândul de logică),
  `tests/isolation/test_overhead_allocation.py`
- **Legate:** [`c1-c3-c5-stocuri.md`](../_input/cercetare/c1-c3-c5-stocuri.md) (pct. 29–31, citate),
  [`c5-costuri-indirecte-conturi.md`](../_input/cercetare/c5-costuri-indirecte-conturi.md) (normele
  conturilor 811, 821, 714), [ADR-036](036-forma-postarii.md) §10.1 (granița listă închisă / listă
  deschisă), [ADR-047](047-stampila-parametrului-la-postare.md) (ștampila),
  [ADR-048](048-formula-si-sloturile-tipizate.md) (dimensiunea pe partea care o declară),
  [ADR-056](056-inchiderea-lunii-si-a-exercitiului.md) (invariantul clasei 8),
  [ADR-057](057-diferentele-realizate-la-decontare.md) (handlerul pur de registru)

---

## 1. Context

Al doilea handler are un rol precis în ordinea proprietarului: C4 a arătat că motorul poate emite
formule pe care nu le cere nicio linie de document; C5 trebuie să arate că **o regulă cu calcul
propriu funcționează cu date deschise**. Calculul e al actului — SNC „Stocuri" pct. 30 scrie formula
de subabsorbție; datele sunt ale entității — pct. 31 lasă baza de repartizare la politicile
contabile, cu „de exemplu" în față.

Ce spune standardul, citat în [`c1-c3-c5-stocuri.md`](../_input/cercetare/c1-c3-c5-stocuri.md):

- **pct. 29** — două etape, obligatorii: între costul produselor și cheltuielile curente; apoi pe
  tipuri de produse;
- **pct. 30(1)** — costurile indirecte **variabile** se includ în cost „în suma totală, indiferent de
  gradul de utilizare a capacităţilor de producţie";
- **pct. 30(2)** — cele **constante** „în baza capacităţii normale de producţie": integral dacă
  volumul efectiv atinge capacitatea normală, altfel „în baza cotei calculate ca raportul dintre
  volumul efectiv şi capacitatea normală. Suma rămasă se consideră drept cheltuieli curente";
- **pct. 31** — baza etapei a doua e cea „stabilită în politicile contabile ale entităţii (de
  exemplu, proporţional salariilor de bază ale muncitorilor (…), sumei totale a costurilor directe
  de producţie, numărului de maşini-ore lucrate, cantităţii de produse fabricate)".

Conturile, din normele Planului general de conturi, transcrise în
[`c5-costuri-indirecte-conturi.md`](../_input/cercetare/c5-costuri-indirecte-conturi.md): creditul
lui **821** înregistrează repartizarea „în corespondenţă cu debitul conturilor: 714, 811, 812 etc.";
debitul lui **811** primește „costurile directe şi indirecte de producţie" cu 821 în listă; **714**
generalizează cheltuielile operaționale „care nu pot fi atribuite la costul vînzărilor, cheltuielile
de distribuire sau cheltuielile administrative". Listele sunt explicit neexhaustive.

Ce exista deja: rolurile `COSTURI_INDIRECTE_PRODUCTIE` (821) și `PRODUCTIE_DE_BAZA` (811) în catalog;
registrul de logică fiscală cu un singur rând (direcția de rotunjire, ADR-037); invariantul clasei 8
la închiderea lunii (ADR-056), care **refuză** o lună cu sold pe 821 — deci, până azi, nicio lună cu
producție nu se putea închide.

## 2. Opțiuni evaluate

### 2.1 Unde stă formula din pct. 30

1. **În handler, ca aritmetică** — *respins*. Formula e a actului și un ordin o poate rescrie;
   recalcularea unei perioade trecute trebuie să folosească regula de atunci (R18). Aritmetica din
   handler ar deveni mâine un `if year >= X` (R17).
2. **Logică versionată în registrul fiscal** — *ales*. Cheia `production.overhead_absorption`,
   implementarea `normal_capacity_v1`, `valid_from 2014-01-01`, sursa OMF 118/2013 cu **ambele**
   publicări din Monitorul Oficial (2013 nr. 177-181 art. 1224; 2013 nr. 233-237 art. 1534, cea
   comună cu OMF 119/2013 — cazul care a cerut registrul de acte, ADR-049). Regula se selectează la
   **ultima zi a perioadei repartizate**, exact ca direcția de rotunjire; un build poartă toate
   regulile pe care le-a aplicat vreodată (`absorption.IMPLEMENTATIONS`), rândul spune care rulează.
   **Fără rând, refuzul e al registrului fiscal**, nu un implicit al handlerului — test explicit.
   Nu e parametru (R15): nu e o valoare cu sursă, e un algoritm (R16).

### 2.2 Baza de repartizare

1. **Enumerată în cod** — salarii, costuri directe, mașini-ore, cantități — *respins*. „De exemplu"
   e decisiv: enumerarea ar promova ilustrația la normă. E prima confirmare practică a graniței din
   [ADR-036](036-forma-postarii.md) §10.1 — metoda de evaluare (pct. 33) e listă închisă și se
   enumeră; baza de repartizare e listă deschisă și **nu**.
2. **Valori pe fapt** — *ales*. `base_name` e numele bazei din politica entității, înregistrat pe
   eveniment ca să poată fi revizuit, **nevalidat** contra unei liste; `base_value` per produs e
   cantitatea care intră în calcul. Handlerul repartizează peste orice bază care vine.
   **O bază goală** (suma valorilor zero) e **refuzată** (`posting.overhead_base_empty`), nu
   împărțită egal: „egal" ar fi o bază pe care n-a fixat-o nimeni. `base_name` gol e refuzat la fel:
   o repartizare care nu spune după ce s-a făcut nu poate fi revizuită.

### 2.3 Unde ajunge restul nerepartizat

Norma spune „cheltuieli curente"; planul spune în ce cont: **714** e în lista creditului lui 821 și
e contul cheltuielilor operaționale care nu pot fi atribuite costului vânzărilor, distribuirii sau
administrării. Rol nou `COSTURI_INDIRECTE_NEREPARTIZATE` → 714, **gradul I**, cum spune norma.
*Respins:* 711 „Costul vînzărilor" — costurile constante nerepartizate **nu sunt** cost al produselor,
tocmai asta spune pct. 30(2). Subcontul lui 714 nu-l numește niciun text citit (§5).

### 2.4 Produsul, ca dimensiune

Etapa a doua produce **o formulă per produs**, `Dt 811 / Ct 821`, cu produsul ca dimensiune `item` —
purtată de partea al cărei cont o declară ([ADR-048](048-formula-si-sloturile-tipizate.md)): pe linia
de debit dacă 811 declară slotul `item`, pe niciuna dacă nu-l declară. Un 811 fără analitic pe produs
e configurația entității, nu grija handlerului; testul verifică dimensiunea pe debit și absența ei pe
creditul lui 821.

### 2.5 Ultimul ban

`distribute`: fiecare cotă e suma proporțională redusă **o dată** la scara în vigoare (Spec B §7.4,
o rotunjire per valoare); banii pe care împărțirea îi lasă merg **pe cota cea mai mare**, iar între
cote egale **pe codul de produs cel mai mic**. Motivul e **determinismul față de date, nu o
prescripție a actului**: pct. 31 fixează baza și tace despre rest. Prima versiune dădea restul
*ultimului* produs — dar „ultimul" nu e o proprietate a datelor, e a ordinii în care s-a întâmplat să
vină produsele; aceeași repartizare cu lista sortată altfel punea banul în altă parte, deci rezultatul
era determinist față de execuție, nu față de date. Pe cota cea mai mare banul merge unde diferența
relativă e cea mai mică, iar la egalitate perfectă departajatorul e un datum al produsului — codul,
purtat pe fapt (`ProductShare.code`; identificatorul, când apelantul nu are cod) — nu poziția.
Rămâne **o singură versiune**: o convenție de inginerie, nu o alternativă de politică. Testat: 100
peste trei baze egale → 33,33 / 33,33 / 33,33 plus un ban pe codul cel mai mic, suma exact 100; aceeași
listă în altă ordine dă aceleași cote pe aceleași produse.

### 2.6 Sursa evenimentului

`manual` ar spune că cineva a tastat repartizarea; nimeni n-a tastat-o — faptul vine din activitatea
de producție. Vocabularul primește `SourceModule.PRODUCTION` prin migrarea aditivă `0003`, în aceeași
formă în care `periods` a intrat prin `0002`. E o **valoare de vocabular**, nu un app: regula „fără
app-uri goale pentru module viitoare" rămâne în picioare; modulul de producție e al F2 și va emite
`AllocationFact`, nu va rescrie handlerul.

### 2.7 Handlerul rulează înainte să existe eveniment

Ca nota manuală și ca C4: un fapt de la care regula nu poate calcula — capacitate normală zero,
valori negative, produse lipsă, `float` în loc de `Decimal` — e bug al apelantului
(`posting.overhead_payload_malformed`), refuzat **înainte** de emitere, ca un eveniment înregistrat
pentru un fapt necalculabil să nu stea în coadă arătând ca muncă. Zero de repartizat → eveniment
`posted` fără înregistrare, nu eroare. Aceeași repartizare de două ori → o singură înregistrare
(cheia `production.overhead_allocated:<allocation_id>`, R19).

## 3. Decizia

1. **Evenimentul** `production.overhead_allocated`, sursa `production`, documentul sursă
   `overhead_allocation` identificat de `allocation_id`; data contabilă e **ultima zi a perioadei**
   repartizate, fiindcă regula și scara se aleg pentru perioada calculată, nu pentru ziua în care
   cineva a apăsat pe buton.
2. **Faptul** (`AllocationFact`): perioada, totalul variabil, totalul constant, capacitatea normală,
   volumul efectiv, numele bazei și valoarea bazei per produs — tot ce cere pct. 29–31, declarat
   explicit de apelant. Handlerul **nu citește soldul lui 821**: repartizează ce i se spune; dacă
   totalurile nu acoperă contul, luna nu se închide (ADR-056), iar acolo e verificarea.
3. **Handlerul** `production.overhead_allocation.v1`, pur de registru: citește din registrul fiscal
   scara, direcția de rotunjire și regula de absorbție în vigoare la data contabilă; ștampilează
   `accounting.amount_scale` ([ADR-047](047-stampila-parametrului-la-postare.md)). Formulele: câte
   una `Dt 811[item] / Ct 821` per produs pentru partea care intră în cost (variabil integral plus
   constantul absorbit), și una `Dt 714 / Ct 821` pentru restul constant nerepartizat, când există.
4. **Regula** `normal_capacity_v1`: raportul efectiv/normal, plafonat la unu, aplicat sumei constante
   și redus o dată la scara în vigoare; restul e diferența. Capacitatea normală zero nu e o
   capacitate și e refuzată.
5. **Verificat cu sume:** 1000 variabil + 500 constant la capacitate, baza 3:1 → 1125 / 375, fără
   linie de cheltuieli; volum 800 din 1000 → 400 absorbit, 1050 / 350 și **100 la 714**; variabilul
   intră integral la volum 10 din 1000 → 750 / 250; 100 peste trei baze egale → 33,33 pe fiecare și
   banul pe codul cel mai mic (§2.5), suma exact 100, invariant la ordinea listei. Sub rolul
   aplicației (T1).

## 4. Consecințe

- **O lună cu producție devine închidibilă.** După repartizare 821 e la zero — exact invariantul pe
  care `period.month_closed` îl verifică (ADR-039 §10.1, ADR-056). C5 e ce face invariantul
  satisfiabil, nu doar verificabil.
- **Granița din ADR-036 §10.1 e confirmată de cod:** metoda (pct. 33) se va enumera (C1), baza
  (pct. 31) nu se enumeră. Dacă cineva adaugă un `enum` al bazelor, contrazice actul, nu un gust.
- **Registrul de logică are al doilea rând, cu altă cheie.** Declanșatorul lui `OD-72` (încrederea pe
  versiunile de logică) e „al doilea rând **al aceleiași chei**" — o a doua versiune — deci nu s-a
  declanșat; cheia nouă are o singură versiune.
- **Ce nu intră, explicit:** activitățile **auxiliare** (812) — planul le listează la creditul lui
  821, handlerul are un singur cont de calculație; un fapt cu secții auxiliare nu se poate exprima
  azi și se refuză prin lipsa rolului, nu se aproximează. Ieșirea din 811 (costul produselor
  fabricate spre 216, producția în curs) e a lui C1 și a modulului de stocuri. Nimic din handler nu
  atinge conturile de bilanț.
- **Migrarea `0003`** e aditivă și reversibilă: scoate și repune `CHECK`-ul vocabularului, ca `0002`.

## 5. Ce se raportează, nu se decide

1. **Rândul de logică e `draft` pe baza de dezvoltare.** Încărcat cu `load_fiscal_parameters
   snc_stocuri.toml` (P-4); activarea e a proprietarului
   (`activate_fiscal_parameters snc_stocuri.toml --approver <id>`), ca la convențiile de platformă.
   Suita își seedează rândul activ. Până la activare, pe baza de dezvoltare handlerul refuză cu
   „nicio regulă în vigoare" — corect, nu defect. *Activat la 2026-08-30, cu aprobatorul
   `22222222-2222-2222-2222-222222222222`, după confirmarea celor patru pași: variabilele integral
   (pct. 30(1)); constantele × min(1, volum efectiv / capacitate normală), o rotunjire `half_up` la 2
   zecimale; restul la 714; ce intră în cost pe produse proporțional cu baza din politică, fiecare cotă
   rotunjită o dată.*
2. **Subcontul lui 714** nu-l numește niciun text citit: 714 are 7141–7148, iar 7148 „Alte cheltuieli
   operaţionale" e plauzibil — plauzibil nu e citat. Rolul se leagă la gradul I; compania își leagă
   subcontul în stratul 2.
3. **Indicațiile metodice privind contabilitatea costurilor de producție** — la care trimite grupa 81
   — **nu au fost citite**. Pot prescrie mai mult decât pct. 29–31 (repartizarea pe secții, 812,
   ordinea între etape). Ce e aici e conform cu SNC „Stocuri" și cu Planul general de conturi, nu
   verificat contra Indicațiilor.
4. **Capacitatea normală** e a politicii entității („volumul ce poate fi realizat, în medie, pe
   parcursul a cîteva perioade de gestiune") — nu parametru fiscal, nu valoare a platformei. Azi vine
   pe fapt, la fiecare repartizare; unde stă stabil (pe companie? pe exercițiu? pe secție?) e
   întrebarea modulului de producție din F2, nu a handlerului. Nu se deschide OD: nu blochează nimic.
5. **Forma migrării `0003` nu scalează**, observație a revizuirii de schemă: `RemoveConstraint` +
   `AddConstraint` repune `CHECK`-ul fără `NOT VALID`, deci PostgreSQL revalidează fiecare rând sub
   `ACCESS EXCLUSIVE` pe `accounting_event`. Inofensiv azi (tabela e mică, forma e identică cu
   `0002`), dar `accounting_event` primește un rând per eveniment de business, pentru totdeauna; a
   treia valoare adăugată vocabularului ar trebui să intre prin `ADD CONSTRAINT … NOT VALID` urmat de
   `VALIDATE CONSTRAINT` (`SHARE UPDATE EXCLUSIVE`, neblocant). Nu se schimbă acum: nu blochează
   nimic, iar `C31` nu se aplică (nu e fișier din `infra/migrations/`).
6. **`regression_case_set = corpus/production.overhead_absorption/1` e gol.** SNC „Stocuri" are un
   exemplu numeric în Anexa 1 (menționat, netranscris în cercetare) — candidatul firesc pentru
   primul caz citat al corpusului (F1.10), fiindcă rezultatul lui e al actului, nu al sesiunii.

## 6. Golul 2014–2017 rămâne cum e

Regula de absorbție e valabilă din **01.01.2014** (`omf-118-2013`); direcția de rotunjire
(`accounting.money_rounding`, `half_up`) și scara (`accounting.amount_scale`) din **28.10.2017**
(`omf-118-2017`). O repartizare datată între cele două găsește regula și **nu găsește direcția**, iar
registrul refuză — `resolve_logic` nu are rând în vigoare pentru `accounting.money_rounding` la acea
dată. **Comportamentul e corect și rămâne așa**: nu se inventează o direcție pentru 2014–2017 și nu se
mută `valid_from` al direcției înapoi ca să „meargă" — ar fi o cotă scrisă în cod sub altă formă.
Consemnat aici ca nimeni să nu-l repare peste doi ani; testul
`test_a_period_before_the_rounding_direction_is_refused_not_guessed` îl păzește, iar mesajul de refuz
numește cheia lipsă și data.

