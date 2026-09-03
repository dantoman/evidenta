# Stare proiect

> Acest fișier este mecanismul prin care munca supraviețuiește resetării contextului între sesiuni.
> Se citește la începutul fiecărei sesiuni și se actualizează la sfârșit. O sesiune care nu îl
> actualizează lasă proiectul într-o poziție din care următoarea sesiune reconstruiește contextul
> ghicind.

## Faza curentă

> **F2 — Primul produs vandabil, pornită 2026-08-30** prin declarația proprietarului.
> Descompunerea: `_bootstrap/09-f2-backlog.md`. Cele opt întrebări ale fazei sunt răspunse (ADR-060 …
> ADR-064 plus `DNB-05` varianta C). Ce urmează dedesubt e starea F1, păstrată.
>
> **Ordinea F2 s-a schimbat prin instrucțiune (2026-08-30), și numai ordinea:** scopul rămâne un sistem
> contabil **complet** pentru Moldova, toate regimurile intră. Secvența urmează **calendarul
> clientului**, nu structura legii — lunarul înaintea anualului: (1) salarizare regim general,
> (2) scutiri, (3) calcul lunar și fluturaș, (4) IPC, (5) documente comerciale, (6) TVA,
> (7) concedii, (8) celelalte regimuri, (9) mijloace fixe, (10) IALS21 și anualul, (11) import 1C și
> e-Factura. **Ecranele merg în paralel cu fiecare pas: un pas fără ecran nu e livrat.** Deblocările
> stau în `_bootstrap/13-lista-de-deblocare.md`, fiecare cu implicitul ei.
>
> **Livrate din secvență:** `F2.B0` (ADR-065), `C1(b)` (ADR-071, ADR-072), **pasul 1** — persoană,
> contract, act adițional, ordin, pontaj —, **pașii 2, 3 și 4** (scutiri, calcul lunar și fluturaș,
> IPC), fiecare cu ecranul lui, **pasul 5 complet** (factura emisă, factura primită, încasarea și plata,
> nota de credit — ADR-073 —, decontarea — ADR-087, 31.08) și **pasul 6 început** (02.09,
> [ADR-089](decisions/089-tva-pe-documentele-comerciale.md)): TVA pe document ajunge în registru —
> 5344 / 2252, cota din nomenclator, înregistrarea companiei cu ușă și ecran; cotele rămân `draft`
> (`OD-22`), deci pe baza de dezvoltare calculul refuză numind cheia. **A doua felie, tot 02.09
> ([ADR-090](decisions/090-registrele-tva-pe-perioada-fiscala.md)):** perioadele TVA au ușă și cer
> înregistrare; registrele de livrări și procurări se citesc pe `VatPeriod`, egale cu 5344 / 2252 —
> măsurat —, cu ecran și export. **Tot 02.09, în afara secvenței, prin instrucțiunea proprietarului
> („mă aștept ca partea asta să fie setată în setările sistemului"):** consola platformei din ADR-076
> există — gazda `admin.`, `platform_staff`, prima pagină: **parametrii fiscali** ca setări de
> sistem, cu versiune nouă datată și activare de către operator
> ([ADR-091](decisions/091-consola-scrie-referinta-din-procesul-web.md)). Cotele rămân `draft` până
> când proprietarul le dă marginea — acum dintr-un ecran, nu dintr-un TOML. **03.09:** restul
> consolei — spații, angajați, jurnalul căilor privilegiate, capabilități, ringuri și flaguri, planuri
> de conturi — prin funcții de citire enumerate și `P-12`
> ([ADR-092](decisions/092-consola-citeste-metadate-si-administreaza-personalul.md)); abonamentele,
> granturile de suport și incidentele n-au server și nu se desenează. **Urmează, tot din pasul
> 6:** declarația, când textul Ordinului IFPS 1164/2012 e citit; proratarea; radierea cu ușă. *Antetul acesta a rămas în urmă de două ori — spunea
> „urmează pasul 2" până la 31.08 și „urmează trezoreria" până la 02.09, cu ambele livrate între timp.
> Se rescrie la fiecare sesiune, nu doar „Ultima sesiune".*

**Felia verticală merge cap-coadă: companie → plan de conturi → notă manuală → balanță echilibrată.**
Un test de integrare o parcurge prin HTTP, sub rolul aplicației
(`backend/tests/integration/test_vertical_slice.py`). Suita: **1.275 trec, 1 sărit** (2026-09-02, consola; frontend 59).

- **A1** — planul SNC ca date: `accounting/coa/data/snc_2020.csv`, 476 de conturi (156 gradul I,
  320 gradul II), transcrise din extragerea proprie a actului; încărcător idempotent
  `manage.py load_coa_template`, rulat ca owner, a doua rulare nu schimbă nimic
- **A2** — `P-9` scris: `rls.provision_company` (`infra/migrations/0045`), serviciu
  `tenancy.services.provisioning`, `POST /api/v1/companies`. Creatorul primește acces în aceeași
  tranzacție, altfel compania e invizibilă chiar creatorului ei
- **A3** — inițializarea planului: endpointul exista din F1.1, e acum conectat la ecran și acoperit
  de testul feliei (al doilea plan refuzat, `coa.chart_already_instantiated`)
- **A4** — `manual.journal_entry` avea motorul, nu avea ușă: `POST /api/v1/accounting/entries/manual`,
  cu `Idempotency-Key` obligatoriu; aceeași cheie de două ori postează o dată
- **A5** — balanța: agregare pe `journal_line` (sold inițial, rulaje, sold final), totaluri pe server
  (`C19`), `GET /api/v1/accounting/ledger/companies/<id>/trial-balance`
- **A6** — `OD-57` **măsurată, nu închisă**: cu parametrul absent, `app.current_company_id()` e NULL
  și clauza cade **permisiv**, nu fail-closed. Nu e breșă — ceilalți trei conjuncți (tenant,
  `has_tenant_access`, `has_company_access`) rămân în picioare, deci absența înseamnă „toate
  companiile la care ai deja acces". Amânată, ca toate OD-urile care nu sunt breșe
- **Derivă reparată în baza de dezvoltare:** `document`, `document_event`, `numbering_template`,
  `numbering_counter` aveau RLS dezactivat și zero politici — `0024` fusese derulat înapoi și nu
  reaplicat. Codul era corect (baza de test le avea); reaplicat sub owner
- **Două corecții de migrare:** `0044` — `FORCE RLS` blochează și proprietarul, deci încărcătorul de
  date de referință n-avea cum să scrie; `0046` — `0045` emisese REVOKE/GRANT după `RESET ROLE`,
  adică de la un rol care nu deține funcția, deci nu retrăsese nimic. Gardianul de privilegii a
  prins-o, `C31` respectat: fișier nou, nu editare
- **Trei violări `D6` prinse de gardian și reparate prin servicii publice**, nu prin import de
  modele: `coa.names_for`, `tenancy.functional_currency`, `numbering.create_general_template`
- **Gardianul de model rulează acum și pe baza vie:** `audit()` lua dintotdeauna un cursor, deci putea
  răspunde pentru orice conexiune — lipsea doar apelantul. Mutat din `tests/schema_guard/` în
  `platform/rls/schema_audit.py` (produs, nu suită), plus `manage.py check_schema_drift` și
  `make drift-check`. Suita își construiește baza din migrații la fiecare rulare, deci **prin
  construcție nu poate vedea deriva** — două sesiuni au dat peste ea de două ori, la zile distanță
- **Prima rulare a găsit una:** `evidenta_app` avea `INSERT, UPDATE, DELETE` pe
  `fiscal_parameter_confidence_event`, declarată `global_read_only`. **Nu e breșă, măsurat:** sub
  rolul aplicației `INSERT` e refuzat de RLS, iar `UPDATE`/`DELETE` n-au politică și au și trigger
  append-only. Retras oricum prin `0047`, ca declarația și baza să spună același lucru și ca apărarea
  să nu depindă de absența unei politici
- **Inventar: fiecare rută a serverului are un apelant în client.** 25 de rute, toate acoperite —
  clasa „serviciu complet fără ușă", care a produs patru cazuri într-o zi, e goală acum. Verificarea
  a rămas măsurătoare, nu unealtă: scrisă naiv, dă **fals negativ** pe propriul meu cod, fiindcă
  `templates.ts` compune adresa dintr-un `base()` și calea literală nu apare niciodată întreagă. Un
  gardian care strigă lupul se ignoră, ca euristica pe triggere de append-only
- **Ecranul de parteneri**, la nivel de spațiu de lucru — fără segment de companie, fiindcă aceeași
  entitate juridică e aceeași pentru toate companiile firmei. Formularul de solduri putea **alege** un
  partener și nimic nu putea **crea** unul: același gol care ținea stornoul, soldurile și șabloanele
  inaccesibile. Parcurs live: creare, IDNO duplicat refuzat (`partners.idno_taken`), retragere care
  scoate din lista implicită și păstrează rândul, filtrele `role` și `include_inactive` combinate
- **`make check-committed`**, fiindcă defectul de mai jos a trecut de `tsc`, ESLint, Vitest și build:
  toate patru citesc discul, unde fișierul uitat există. Verificarea rulează același typecheck peste
  `git archive HEAD`, deci peste un arbore în care fișierul lipsă chiar lipsește. Are `--self-test`
  care scoate un fișier și cere ca typecheck-ul **să cadă** — un gardian pe care nimeni nu l-a văzut
  căzând e un gardian despre care nimeni nu știe că e legat
- **Creanțe, datorii și lista de loturi pe ecranul de solduri**, imediat ce directorul de parteneri a
  aterizat: partenerul se **caută** după denumire sau IDNO, nu se tastează ca identificator. Lista de
  loturi era golul real — un lot nu se șterge niciodată, deci unul abandonat ieri rămâne acolo, iar
  fără drum înapoi la el următorul import începe de la zero lângă el. Parcurs live: detaliul analitic
  potrivit cu contul de control trece validarea, descompunerea vine de la server
- **O regulă de lucru în checkout partajat, plătită o dată:** `git commit -- <căi>`, niciodată `add`
  urmat de `commit`. Indexul e stare comună, iar un commit al meu a înghițit nouă fișiere ale
  sesiunii paralele, în lucru la ei. Reparat prin `reset --soft` și re-comis pe căi; fișierele lor au
  rămas stagiate și neatinse, verificat de amândoi
- **Ecranul de șabloane de operațiuni**: definire (sumă fixă sau cerută la postare — casetă, nu
  convenție de șir), listă care ascunde retrasele, folosire. Parcurs pe serverul viu: postarea din
  șablon produce o înregistrare `standard`, **nedistinsă de una tastată linie cu linie**, exact cum e
  proiectat; după retragere, postarea e refuzată și lista implicită nu-l mai arată
- **O ciocnire de nume prinsă de typecheck, nu de citire:** `accounting.templates` era deja al
  versiunilor publicate ale planului de conturi. Blocul nou e `operationTemplates` — două lucruri
  diferite nu se prescurtează la fel
- **Ecranul de solduri inițiale** peste API-ul sesiunii paralele: lot → rânduri GL → validare →
  postare, cei patru pași ai serverului, nu un wizard inventat. Doar rânduri GL: creanțele și
  datoriile cer `partner_id`, iar `masterdata/partners` n-are nicio cale HTTP — scris pe ecran, nu
  doar în cod. Parcurs pe serverul viu: contul de contrapartidă iese **0.0000** după postare, adică
  proba de completitudine din Spec B §8.3, citită din balanță
- **Un defect prins de propriul test de fum:** parserul de sume era cel de la nota manuală, cu două
  zecimale, iar serverul trimite patru (`"5000.0000"`) — deci totalurile ieșeau zero și avertismentul
  de set dezechilibrat nu apărea niciodată. Sumele se adună acum la scara serverului
- **Măsurat pe server, scris pe ecran:** data lotului trebuie să cadă într-un exercițiu deschis
  (`periods.period_not_found` la `2025-12-31`), deci „ziua dinaintea primului exercițiu" nu merge
- **Un checkout curat nu putea ajunge la ecranul de autentificare, și acum poate:**
  `manage.py create_tenant` (`make create-tenant`) creează tenantul, utilizatorul, rolurile de
  sistem, membership-ul și **înrolează al doilea factor**, fiindcă `authenticate()` refuză un cont
  fără el (`ADR-021`) — o comandă care s-ar fi oprit la utilizator ar fi produs un cont care nu poate
  intra, iar eșecul s-ar fi citit ca parolă greșită. Comandă de operator, nu endpoint: `DN-26` rămâne
  exact la fel de deschisă
- **Rulează sub rolul de instalare, măsurat, nu ales din comoditate:** politicile pe `tenant`,
  `user`, `membership` și `role` sunt scrise `TO evidenta_app`, deci sub `FORCE RLS` proprietarul
  n-are nicio politică aplicabilă și e refuzat la fiecare inserare. Alternativele erau lărgirea
  politicilor spre owner sau `rls.provision_tenant`, care ar fi trebuit să creeze un utilizator —
  ceea ce ADR-040 spune că `P-9` nu face
- **Felia parcursă cap-coadă pe baza de dezvoltare, nu doar în teste:** tenant nou → login cu TOTP →
  companie → exercițiu (12 perioade) → planul real de 476 de conturi → notă postată (a doua oară cu
  aceeași cheie: `posted_now = false`) → registru → balanță echilibrată → storno → balanță la zero
- **Registrul înregistrărilor** — `GET .../ledger/companies/<id>/entries`, antete cu rândurile lor,
  ambele sensuri ale `R14` pe sârmă, plus ecranul. Exista un gol de fond: după postare nu se vedea
  ce s-a postat, deci nici nu se putea alege ce se corectează
- **Stornoul e complet cap-coadă:** serviciul de motor e al sesiunii paralele (`a49db20`),
  endpointul `POST .../entries/<id>/reversal` și butonul din registru sunt aici. Data corecției e
  obligatorie și fără implicit — `ADR-007` e deschisă, iar un default în HTTP ar fi închis-o din
  stratul cel mai puțin îndreptățit. Testul feliei acoperă acum și corecția: al doilea storno refuzat,
  ambele legături vizibile, balanța revenită la zero
- **Bazele de test se ciocneau între sesiuni:** două suite pe `test_evidenta` au produs 594 de erori
  `AdminShutdown` — una recreează baza sub conexiunile celeilalte, și nu arată ca o coliziune, arată
  ca un defect. `TEST_DB_NAME` face numele configurabil; implicitul rămâne neschimbat
- **`make test` rulează și frontendul** (`web-test`), altfel Vitest era un runner pe care nu-l pornea
  nimic. `make seed-coa` pentru încărcătorul de plan de conturi
- **Nu am extins `drift-check` la append-only, și motivul e măsurat:** un trigger pe UPDATE/DELETE nu
  distinge „append-only" de „mașină de stări cu gardă" — 19 tabele au un astfel de trigger, iar 15 au
  legitim `UPDATE` (engagement, period, role, solduri inițiale în lucru). Verificarea ar fi produs 15
  false pozitive, adică un gardian care se ignoră. Golul real — o tabelă append-only care poartă FK
  n-are unde să se declare — cere un contract, deci ADR, deci e amânat
- **B1–B5** — creare companie (formular pe `/companii`, cu deschiderea exercițiului ca al doilea
  apel, fiindcă `platform` nu importă `accounting`), ecran de notă manuală (tabel simplu, nu
  `EntryGrid` — `OD-36` e deschisă), ecran de balanță, plus **Vitest**: 7 teste de fum, câte unul
  per ecran, peste `fetch` stubuit — nu peste modulul API, ca ecranul și clientul să nu poată devia
  împreună


**F1 — Accounting Core. Firul de implementare s-a oprit pe decizii, iar deciziile au venit
(2026-08-29, instrucțiune scrisă).** `F1.4.2` e deblocată — [ADR-036](decisions/036-forma-postarii.md)
e `Acceptat` cu `C1`–`C5` clasificate, `OD-55` închisă prin [ADR-051](decisions/051-chei-de-context-enumerate.md)
(chei enumerate în cod). La fel `F1.4.4`, `F1.5.4` ([ADR-050](decisions/050-lantul-de-inchidere-ca-roluri.md)),
`F1.8` ([ADR-053](decisions/053-tinta-de-performanta.md)) și `F1.G2` ([ADR-052](decisions/052-contractul-de-tastatura.md)).
Calea de scriere a datelor de referință există ([ADR-049](decisions/049-rolul-de-date-de-referinta.md)).
**Blocaje externe: niciunul** ([ADR-054](decisions/054-importul-e-distributie-corpusul-e-intern.md)):
importatorul 1C a plecat la F3 cu `OD-28`/`OD-30`, criteriul de ieșire se validează pe un corpus
intern, două puncte ale lui sunt deja bifate din teste, iar F1.10 e sarcină, nu blocaj. **`V1` e
citită** (formularul tace asupra zecimalelor), cele două convenții sunt **aprobate și active**, `OD-70`
e închisă ([ADR-055](decisions/055-precizia-cantitatii-e-a-unitatii.md)), direcția e `half_up`,
activă. **F1.6 e livrată; F1.5.4 e livrată** ([ADR-056](decisions/056-inchiderea-lunii-si-a-exercitiului.md)).
**F1 nu mai așteaptă pe nimeni — nici din afară, nici pe proprietar.** Rămân F1.4.4 și F1.10, în
ordinea fixată. **F1.4.4 e mai multe sesiuni, în ordinea decisă de proprietar: C4 la decontare, C5,
C2, C1** — motivele în `08-f1-backlog.md`. `OD-73` (reformarea bilanțului) rămâne deschisă până când
blochează ceva: tăcerea actului nu se rezolvă aici prin structură, e alegere de proces.
**C4 la decontare e livrat** (2026-08-30, [ADR-057](decisions/057-diferentele-realizate-la-decontare.md)):
termenul pe antet cu implicitul actului, handlerul diferențelor realizate cu discriminatorul refuzat,
trei perechi ca roluri, prima ștampilă de parametru. **C5 e livrat** (2026-08-30,
[ADR-058](decisions/058-repartizarea-costurilor-indirecte.md)): formula pct. 30 ca logică versionată,
baza pct. 31 ca date deschise, restul la 714, o lună cu producție devine închidibilă. Urmează **C2**,
apoi C1, apoi F1.10.

**F1 — Accounting Core.** F0 este închisă (criteriul de ieșire îndeplinit, mai jos). Livrate:
**F1.1** (planul de conturi, structura fără conținut) cu API-ul lui, **F1.3** (evenimentele),
**F1.5** (perioadele) și **F1.2** (registrul). Trei sesiuni lucrează în paralel în același checkout.

Descompunerea completă: `_bootstrap/08-f1-backlog.md` — patru fire care pot merge în paralel, cu
`F1.2.1` ca singur punct de sincronizare timpuriu, și tabelul de blocaje la final.

**F2 — descompusă, cu lectura și datele făcute; cod de modul: niciunul** (2026-08-30):
`_bootstrap/09-f2-backlog.md` — două fluxuri paralele (Commercial/Tax, Payroll) care converg în raportarea
statutară, 29 de sarcini, verificarea a ce a fost „modelat" făcută pe `HEAD`, tabelul de blocaje cu patru
instituții și șase decizii ale proprietarului. **A doua instrucțiune, aceeași zi:** `F2.X2` — nouă acte
cercetate (șase fișiere în `_input/cercetare/`, 17 din 21 de identități MO), `F2.X1` — 22 de parametri
`draft` pe baza de dezvoltare, neactivați, criteriul de ieșire raportat punct cu punct, întrebările pentru
proprietar grupate (`OD-71` primul). **F1.10 e livrată (`f8773ea`) și cele cinci puncte ale criteriului F1
sunt bifate în `08`** — închiderea F1 e declarația proprietarului, ca la F0; până la ea, `CLAUDE.md` §4
ține modulele F2 pe loc.

## Ultima sesiune

**2026-09-02 — Consola platformei există, și prima ei pagină sunt parametrii fiscali ca setări de sistem (`evidenta-82`).**

**De unde a pornit:** proprietarul a întrebat unde înregistrează TVA standard și a primit un TOML și două
comenzi de shell. Reacția, verbatim: *„i expect this part be setted in settings of the system… if vat
get changed? what is wrong with you?"*, apoi alegerea explicită a locului: planul de control al
platformei ([ADR-076](decisions/076-planul-de-control-al-platformei.md), acceptat la 31.08, neconstruit).

**Livrat, în ordinea în care se poate deschide în browser** (`admin.evidenta.localhost:5173`, utilizatorul
`dev@example.md` are rol `operator` pe baza de dezvoltare — acordat cu `grant_platform_staff`):

- **Gazda `admin.`** — `is_console_host` în `tenancy/subdomain.py`, ramura de consolă în
  `SubdomainTenantResolver`: fără context de tenant (`PlatformContext`, nou în `rls/context.py`),
  servește doar `/api/v1/auth/` și `/api/v1/platform/` (`CONSOLE_PATH_PREFIXES`), restul `404
  console.not_found` cu sau fără sesiune. O sesiune de consolă e refuzată pe gazdele de tenant și
  reciproc. `whoami` întoarce `tenant_id: null` pe consolă.
- **`platform_staff`** — `identity/0009` + `infra/migrations/0075`, declarată în `exceptions.toml`
  (`self_row`, scriitor `evidenta_refdata`, fără DELETE; clasa (a) din ADR-072, confirmată prin ADR-076).
  Trei roluri în `CHECK`. Autentificarea pe `admin.` emite sesiune doar unui rând viu, **după** ce
  parola și al doilea factor au trecut (`401 auth.no_access_to_console`). `grant_platform_staff`
  scrie primul rând sub rolul de instalare, ca `create_tenant`; acordarea din consolă e `OD-133`.
- **Ușa fiscală** — `GET/POST /api/v1/platform/fiscal-parameters/`, `POST …/<id>/activate`
  (`fiscal/parameters/console_views.py`): `IsPlatformOperator` pentru scriere, orice angajat pentru
  citire; scrierea sub `privileged_run(P-4)` pe conexiunea `refdata`, cu `actor = "console:operator"`
  și `actor_user_id` al persoanei. Regulile s-au mutat din comanda de încărcare în
  `services/authoring.py` (`write_parameter`, `activate_row`) și le apelează **și** cele două comenzi,
  **și** consola — o singură ușă. Câmpurile necunoscute se refuză și în serializatoarele imbricate.
- **Ecranul** — `frontend/src/app/console/`: `ConsoleLayout` (o singură intrare în bara laterală,
  fiindcă o singură pagină există; celelalte șapte din ADR-076 §4.3 nu se desenează),
  `FiscalParametersScreen` (lista cu valoare, margine sau „fără margine", act, încredere, stare;
  „Versiune nouă" cu actul în întregime și poziția din MO; „Activează" pe ciorne, doar operatorului).
  `App.tsx` ramifică pe gazdă **deasupra** rutelor; `LoginScreen` primește `console` pentru textul de
  deasupra formularului.
- **[ADR-091](decisions/091-consola-scrie-referinta-din-procesul-web.md)** — de ce scrierea se face din
  procesul web pe conexiunea de referință și nu prin funcție `SECURITY DEFINER` sau job: criteriul
  „cine apelează" din Spec A §6.2 se precizează (utilizator al unui tenant vs. angajat al platformei),
  iar propoziția din §6.1 despre proces e măsurată ca neadevărată deja (`DATABASES["refdata"]`
  necondiționat) și primește declanșator de revenire. Spec A capătă §14 (consola) și nota de sub §6.2;
  `OD-113` își pierde partea „nimic din cod nu refuză" și păstrează catalogul; `OD-133` deschisă.

**Măsurat, și a schimbat codul:** testul de graniță (ADR-076 §5 b) a răspuns la prima rulare „zero
rânduri" pe `tenant` și **niciun refuz** din `app.current_tenant_id()` sub contextul de consolă. Cauza nu
era politica: `SET LOCAL` supraviețuiește savepoint-ului, iar `_apply` **sărea** cheile nesetate, deci un
context deschis după altul în aceeași tranzacție moștenea `app.tenant_id` (și `actor_firm_id`,
`company_id`) de la precedentul. Acum le **golește** (`set_config(cheie, '', true)`), iar sub contextul
de consolă orice politică de tenant ridică `lipseste contextul de tenant` — ramura „eroare" a lui R4,
nu ramura „zero rânduri". Secvența „membru, apoi consolă" e păstrată în test ca regresie.

**Suita:** **1.275 trec, 1 sărit** (2026-09-02, poarta completă `GATE: PASS`, cu munca necomisă a sesiunilor vecine în arbore); frontend 59, dintre care 4 ale consolei.

**A doua parte, 03.09 — restul paginilor** (întrebarea proprietarului: *„consola platformei va fi și
backofisul administratorului?"* — da, și a cerut restul; [ADR-092](decisions/092-consola-citeste-metadate-si-administreaza-personalul.md)):

- **Măsurat înainte:** din cele nouă obiecte din ADR-076 §4.3, trei n-au server — `plan`,
  `subscription`, `billing_account` nu există ca modele (facturarea e decizie, nu cod), grantul de
  suport (ADR-077) n-are tabelă, incidentele n-au stare de citit. Nu se desenează; interfața spune de ce.
- **Funcțiile de citire ale consolei** (`infra/migrations/0076`, `identity/0010`): șapte funcții
  `rls.console_*`, `SECURITY DEFINER`, deținute de `evidenta_rls`, cu paznicul `rls.console_caller_role()`
  care refuză sub context de tenant și refuză un apelant fără rând viu în `platform_staff`. Sunt căile
  enumerate pe care `R7` le cere pentru interogări cross-tenant; lista stă în Spec A §14 și în
  `test_function_privileges.py`.
- **`P-12`** — administrarea personalului din consolă: `admin` acordă și retrage prin
  `privileged_run` pe conexiunea de referință; o persoană poartă un rol; un admin nu se retrage pe
  sine; primul admin rămâne al shell-ului. `PrivilegedPath` primește `P-11` (ADR-081, fără apelant) și
  `P-12`; `audit/0004` lărgește CHECK-ul jurnalului. Închide `OD-133`, deschide `OD-134` (o persoană
  cu două roluri — proprietarul e singurul om al platformei).
- **Paginile:** Spații (rândul din `tenant`, numărul de companii și de membri, marcaj „nerevendicat";
  fără acțiuni, cu motivul scris), Angajații platformei (listă cu istoric, acordare, retragere),
  Jurnalul căilor privilegiate (filtru pe cale și spațiu; citit prin aplicație pentru prima dată),
  Capabilități, Ringuri și flaguri, Planuri de conturi — toate doar citire. Bara laterală are trei
  grupe: Platformă, Date de referință, Audit. Rutele stau în `App.tsx`, sub ramura gazdei.
- **Verificat:** `tests/isolation/test_console_pages.py` — refuzul funcțiilor sub context de tenant și
  pentru ne-angajați, numărătorile fără conținut, `P-12` cu rândul lui de jurnal, un rol per persoană,
  auto-retragerea refuzată, 403 pe gazda unui tenant; patru teste de ecran în `console.test.tsx`.

- **A treia felie, tot 03.09 — paginile fără server se desenează** ([ADR-093](decisions/093-paginile-fara-server-se-deseneaza.md),
  decizia proprietarului: *„creează paginile să se știe că trebuie implementat"*): trei rute noi pe
  consolă — Abonamente și planuri, Granturi de suport, Incidente — servite de `PlannedScreen`, fără
  server, marcate „de implementat" în bara laterală și în antet; fiecare spune ce va face, ce lipsește,
  ce decizie o guvernează și când se construiește, cu textul ridicat din ADR-076/077/082/086 și Spec A.
  Restrânge ADR-092 §4 (teza „nu se desenează").

**Suita:** backend neschimbat de la poarta precedentă (**1.286 trec, 1 sărit**; gardienii de arhitectură rerulați: 118); frontend **64**, dintre care 9 ale consolei.

**Rămân:** marginile celor 22 de parametri `draft` — acum se scriu din ecran, dar tot proprietarul
citește articolele finale; `OD-134` (două roluri pentru o persoană — azi două conturi); paginile fără
server (abonamente, granturi de suport, incidente), fiecare cu modulul ei; scrierile de platformă care
lipsesc (creare de spații prin `P-9`+`P-11`, atribuire de ringuri, suprascrieri de flaguri), fiecare
cu calea ei; declanșatorul din ADR-091 §6 (credențiale separate web / worker). Nerezolvat din sesiunea
precedentă: ADR-085 §4 vs. cod (derivarea companiei titularului), fără răspuns de la proprietar.

**2026-09-02 — Pasul 6, a doua felie: registrele TVA pe perioada fiscală, egale cu registrul contabil
([ADR-090](decisions/090-registrele-tva-pe-perioada-fiscala.md)).**

**Măsurat înainte de a construi:** `VatPeriod` și cele trei servicii ale lui (deschidere, radiere cu
perioada finală, căutare pe zi) existau din F1.5.3 **fără ușă** și fără să poată verifica
înregistrarea — docstring-ul o spunea, fiindcă `tenancy` nu publica niciun accesor de TVA la vremea aceea;
`accounting.events` nu expunea payload-ul niciunui eveniment; `sales`/`purchases` expuneau doar
`residence_of`, câte un document; scriitorul CSV stătea în `accounting/ledger`, unde `operations/tax`
nu ajunge (`D3`). Din nou mai mult legare decât construcție.

**Livrat:**
- **Perioadele TVA cer înregistrare și au ușă:** `open_vat_periods` refuză luna pe care nicio
  înregistrare n-o **atinge** (suprapunere, nu includere — luna cu o zi ca plătitor se declară),
  `periods.vat_period_without_registration`; `GET/POST .../periods/companies/<id>/vat-periods`, ambele
  margini numite de apelant. Fișa companiei deschide lunile unui an, de la luna înregistrării.
- **Registrele TVA** (`operations/tax/services/vat_register.py`, `GET /api/v1/tax/vat/companies/<id>/
  registers/<side>?on=`): documentele **postate** ale familiei, plasate după **data documentului** în
  perioada fiscală găsită din zi; nota de credit **cu semn negativ**; feliile pe `(regim, cheie,
  cotă)`; la procurări, numărul și data furnizorului și **deductibilitatea din evenimentul postat**
  (`vat_deductible`, ADR-089), nu re-derivată; totaluri pe regim, total, TVA nedeductibilă, și
  **numărul documentelor validate-nepostate** din perioadă. Export CSV, o linie per document și cotă.
- **Criteriul `F2.A6`, bifat în test pentru ambele părți:** total TVA livrări = rulaj net 5344; total
  TVA procurări − nedeductibil = rulaj 2252 — cu notă de credit și cu o achiziție de dinaintea
  înregistrării în același registru.
- **Patru servicii publice noi, fiindcă registrul nu citește tabela nimănui:** `confirmed_of_types` și
  `vat_breakdown_of_many` în nucleul documentelor, `details_of` în vânzări și în achiziții,
  `posted_payloads_of` în `accounting.events`, `registered_for_vat_over` în `tenancy`.
- **Scriitorul CSV a coborât** în `platform/documents/services/csv.py`; `ledger/services/export.py`
  păstrează doar forma rapoartelor. O singură implementare pentru ambele straturi (`C20`).
- **Ecranul *Registrele TVA*** (`registre-tva`, în grupul comercial — intrarea din `sections.ts` e și ce
  ține adresa la schimbarea companiei, cum a explicat sesiunea paralelă): partea, luna, perioada
  găsită, rândurile cu semn, totalurile pe regim, avertismentul cu nepostatele, subtitlul care spune că
  **nu e forma prescrisă** a registrului de livrări / procurări (art. 118, necitit).
- **6 teste de izolare** noi + 1 în `test_vat_period.py` (refuzul fără înregistrare) + 1 de frontend.
  `test_vat_period.py` primește înregistrarea în fixture: testele lui deschideau perioade pentru o
  companie care n-a fost niciodată plătitor, ceea ce de azi e refuz.

**Ce a prins rularea:** exportul din `ledger` pierduse două importuri la mutare (`date_ro`, `Sequence`)
— prinse de ruff și mypy, nu de teste, fiindcă adnotarea locală nu se evaluează la rulare; mypy a
refuzat o variabilă refolosită între cele două ramuri ale registrului cu tipuri diferite, corect.
Rularea completă pe arborele viu a căzut o dată pe gardianul de dependențe — `D6`, în
`sales/views.py`, o editare **necomisă a sesiunii paralele** (`evidenta-85`), nu a acestui commit;
i s-a spus. Tot din arborele partajat: două hunk-uri ale ei din `ro.ts` intraseră în index prin
`git add` pe fișier; indexul s-a reconstruit din HEAD plus cele trei blocuri ale mele, verificat cu
`tsc` înainte de `update-index` — regula din memorie, plătită încă o dată.

**Rămân, cu rând scris:** `OD-132` — data pe care un document intră în perioada fiscală (aleasă: data
documentului; art. 108 necitit). Declarația, proratarea, forma prescrisă — la textele lor. Radierea are
serviciu și n-are ușă: consumatorul ei e declarația finală.

**2026-09-02 — Pasul 6 a început: TVA pe document ajunge în registru
([ADR-089](decisions/089-tva-pe-documentele-comerciale.md)).**

**Măsurat înainte de a construi:** `document_line` purta deja `vat_regime_code`, `vat_rate_key`,
`vat_rate`, `vat_amount` și CHECK-ul `total = net + vat`; `line_amounts` (rotunjirea pe linie, decisă
de proprietar) exista și **nu avea apelant** — `service_line` înmulțea și rotunjea pe cont propriu, cu
cota zero; `TVA_COLECTATA` → 5344 și `TVA_DEDUCTIBILA` → 2252 erau în catalog și nelegate de niciun
handler; `journal_formula.vat_rate` exista și nimic nu-l scria; `company_vat_registration` exista din
F0 **fără ușă** — nicio companie creată prin produs n-a putut fi vreodată plătitor; `vat.*` toate
`draft`; `fiscal.assert_regime` scris și nechemat de nimeni. Deci felia a fost mai mult **legare** decât
construcție, și asta e ce spune ADR-089.

**Livrat:**
- **Forma postării cu TVA**, un singur `HandlerVersion` per eveniment, ca înainte: faptul poartă
  `net`, `vat`, `total` și `vat_by_rate`; handlerul verifică trei identități și emite **o formulă pe
  cotă** contra 5344 (vânzare: creanța debitată de fiecare; retur: 5344 debitat) sau 2252 (achiziție
  deductibilă), cu `vat_rate` și `vat_rate_key` pe formulă (ADR-048). Cumpărătorul neînregistrat duce
  TVA-ul **în cost**, o formulă pe total.
- **Statutul decide în amonte, nu în motor** — `OD-130` rămâne deschisă, deliberat: stratul documentar
  refuză regimul după statutul **la data documentului** (neînregistrat → doar `fara_tva`; înregistrat →
  `fara_tva` refuzat, fiindcă e statut, nu tratament); emiterea verifică din nou, la validare;
  achizițiile pun `vat_deductible` pe fapt din statutul **la data contabilă**, iar motorul îl confruntă
  cu ștampila lui `emit()` (ADR-088) — dezacordul e refuz, `purchases.vat_status_mismatch`.
- **Cota vine din nomenclator:** `vat.regimes` primește `rates` (regim → cheia parametrului), `fiscal.
  regime_rate(code, on)` rezolvă în doi pași și refuză numind cheia; **prima ușă HTTP a lui `fiscal`**,
  `GET /api/v1/fiscal/vat/regimes?on=`, cu `unavailable` pe cota care nu se rezolvă. `line_amounts` e
  acum singura aritmetică, pentru toate regimurile, cu cota zero pentru `fara_tva`; `vat_breakdown` în
  nucleul documentelor. Măsurat în test: trei linii de 33,33 la 20% dau **20,01**, nu 20,00.
- **Înregistrarea în scopuri de TVA:** `tenancy.services.vat_registration` (suprapunere refuzată,
  cheia `company.edit`), `POST/GET /api/v1/companies/<id>/vat-registrations`,
  `GET .../tax-status?on=`, zona *Înregistrarea în scopuri de TVA* pe fișa companiei — istoric, nu
  bifă. Radierea (art. 114 alin. (2)) nu e aici: perioada finală e a lui `accounting/periods`.
- **Ecranele:** regimul pe linie la facturi emise (coloana apare doar când compania e înregistrată la
  data facturii; fără implicit — nici standardul) și la facturi primite (întotdeauna, plus `fara_tva`:
  descrie hârtia furnizorului); coloanele *Valoare* / *TVA* / *Total* în ambele registre.
- **15 teste de izolare** + 2 de frontend. Cel principal pentru achiziții e aceeași factură datată pe
  10 și pe 20 ianuarie, peste înregistrarea din 15: 2252 într-un caz, cost 1 200 în celălalt. Cel de
  jurnal: coloana de TVA a jurnalului documentelor egală cu rulajul lui 5344 pe lună — primul punct
  din criteriul `F2.A6`.
- `seed_documents` primește a șaptesprezecea situație — vânzare cu `taxable_standard` — ca să fie
  refuzată pe nume: niciuna dintre companiile demo nu e înregistrată.

**Trei lucruri pe care le-a prins rularea, nu citirea:** `FiscalResolutionError` nu e `ApiError`,
deci o cotă `draft` ar fi ieșit ca 500 — tradusă în `sales.vat_unavailable` / `purchases.vat_unavailable`
cu codul fiscal în context; ruta liniilor e `PUT`, nu `POST` (testul a spus-o cu 405); iar fișa
companiei cere acum două rute pe care stub-ul de test le potrivea pe prefix cu fișa însăși — rutele
specifice se listează înaintea celei generale.

**Rămân, cu rând scris:** `OD-131` — data la care se citește dreptul de deducere (aleasă: data
contabilă, ziua ștampilei) și forma TVA-ului nerecuperabil la servicii (în cost, prin analogie cu SNC
„Stocuri" pct. 15), ambele fără textul art. 102. Perioadele TVA nu se deschid la înregistrare — n-au
consumator până la registre, felia următoare.

**Proces:** sesiunea paralelă `evidenta-82` a confirmat numerele libere (ADR-089, OD-131) și a cerut
alinierea celor două apeluri din seeder — făcută aici, cu regimul explicit. Antetul acestui fișier a
rămas în urmă a doua oară; șase commituri ale sesiunii `evidenta-16` din 01.09 (seederele) **nu erau
consemnate deloc** — rândul lor e mai jos, scris din mesajele de commit. `README.md` al deciziilor
lipsea 086–088, a patra recurență a lui `OD-126`; completat, împreună cu 089.

**2026-09-01 — Registrele de facturi emise și primite arată totalul pe fiecare rând.**

Ecranele randau `totals.total` și nimic altceva (`C19`), dar endpoint-urile de listă
(`/api/v1/sales/companies/{id}/invoices`, `/api/v1/purchases/companies/{id}/invoices`) trimiteau
rândul fără `totals` — doar detaliul le atașa, prin `totals_of`. Rezultatul: liniuță în coloana
*Total* pe fiecare factură din ambele registre.

**Livrat:** `totals_of_many` în `platform/documents/services/lines.py` — o singură interogare
grupată pe `document_id` (`Sum` peste `net_amount` și `vat_amount`), cu zerouri pentru documentele
fără poziții, exact cum raportează `totals_of`, ca lista și detaliul să arate aceeași cifră. Ambele
liste o folosesc, iar `_rendered` cere totalurile ca argument — un rând nu se mai poate randa fără
ele. În frontend `totals` a devenit câmp obligatoriu pe `SalesInvoice` și `PurchaseInvoice`, iar
celula nu mai are ramura „—". Test HTTP sub rolul de aplicație,
`tests/isolation/test_document_lists.py`: trei documente per registru (două cu sume diferite, o
ciornă fără poziții), fiecare rând egal cu detaliul lui.

**2026-09-01 — Panoul de control: ce poate spune registrul azi, și golurile numite pe nume.**

Macheta panoului există în canvasul de design (`Evidenta.dc.html`, artboard „Panou de control").
Nouă carduri; **patru dintre ele n-au sursă în sistem**, iar asta s-a măsurat înainte de a scrie
ecranul, nu după:

- *De depus* — calendarul de raportare e parametru fiscal cu act normativ în spate (`R15`),
  `fiscal_parameter` e goală (`OD-22`). `periods/services/vat.py` refuză deja același lucru, cu
  motivul scris; panoul nu putea face altfel.
- *TVA de plată* — nimic nu calculează o declarație. `5344 − 2252` ar fi arătat ca răspunsul și
  n-ar fi purtat niciuna dintre regulile lui.
- *Creanțe scadente* și *Vechimea creanțelor* — `document` poartă `document_date`, nu termen de
  plată. „Scadent" nu se poate spune deloc, nici ca cifră, nici ca interval.

**Alegerea proprietarului a fost „toată macheta, cu goluri marcate"**, nu „doar ce se poate".
Fiecare gol spune ce anume lipsește — o tabelă de parametri, un calcul, o coloană — fiindcă „—"
singur se citește ca defect, iar `0,00` s-ar citi ca răspuns. Aceeași alegere pe care o face deja
antetul cu clopoțelul și cu indicatorul SFS.

**Unde stă compunerea, fiindcă asta a fost întrebarea de arhitectură.** Nu în `platform/readmodels`:
Spec A §7 îl definește cross-tenant, iar panoul e al unei companii. Nu într-un modul de
`operations`: `D3` interzice `operations` → `accounting.ledger`. Deci **fiecare modul răspunde
despre datele lui, cu totalurile pe server** (`C19`), iar ecranul pune cardurile alături. Documentele
nepostate vin prin serviciu public, nu prin citirea tabelei altcuiva (`D6`).

**Livrat:**
- `accounting/ledger/services/overview.py` — rulajul lunii și al lunii precedente, seria pe șase
  luni (o singură interogare grupată, nu șase), balanța de la începutul anului, ultimele cinci
  înregistrări cu ambele legături `R14`, notele în ciornă, disponibilul din casă prin rolul
  `CASA_MDL`. Ferestrele sunt **luni întregi**: un rulaj tăiat la ziua în care s-a pus întrebarea nu
  se compară cu luna precedentă, iar panoul le pune alături.
- `GET /api/v1/accounting/ledger/companies/<id>/overview?on=YYYY-MM-DD`. Ziua e a apelantului,
  niciodată ceasul serverului — ca toate ferestrele din API-ul acesta.
- `platform.documents.unposted_work(company_id, types)` — două numere per tip, ciornă și validat,
  niciodată suma lor: cer lucruri opuse de la cititor.
- Ecranul `app/dashboard/DashboardScreen.tsx`, componenta partajată `StatTile` (care știe să n-aibă
  cifră), `month` / `monthShort` în modulul de formatare.
- **Panoul e acum secțiunea implicită**: `DEFAULT_SECTION` și `/` duc în el, nu în planul de
  conturi. Prima pagină a unei companii nu mai e o listă de coduri de cont.
- **Ziua e un câmp, nu ceasul.** Pe Alpha, al cărei ultim rulaj e din martie, panoul din septembrie
  arăta corect „0,00" lângă o listă de note din martie — corect și necitibil. Câmpul „Situația la"
  pune ziua în adresă (`?la=YYYY-MM-DD`), deci panoul pentru martie se poate trimite ca link;
  absent, e azi.
- **Lista spune ce perioadă acoperă** (2026-09-03). „Ultimele înregistrări" nu e mărginită de
  lună, iar totalul de sub ea era; alături, se citeau ca o contradicție. Acum supratitlul poartă
  intervalul celor cinci note, totalul poartă numele lunii, seria poartă lunile ei, iar coloana
  „Contragent" a devenit „Conținutul operațiunii" — o notă între două conturi n-are contraparte.
  Rândurile din *Lucrări deschise* duc la ecranul familiei lor.
- **6 teste de izolare** (5 pe panou, 1 pe numărătoarea documentelor) + 1 de frontend. Cel de
  frontier verifică ce contează: același `company_id`, citit din celălalt tenant, dă zerouri și
  nicio înregistrare.

**Rămâne întrebare deschisă, cu declanșator:** dacă *Creanțe scadente* trebuie să arate creanțele
**deschise** (`settlements` le știe, fără scadență) în loc să rămână gol — se decide împreună cu
termenul de plată pe document, fiindcă abia acela face cuvântul „scadent" adevărat.

**2026-09-01 — Datele de demonstrație trec prin reguli (sesiunea `evidenta-16`; șase commituri,
`abef0db`…`c277861`, consemnate aici la 02.09, din mesajele de commit).**

Ecranele contabile erau goale pe baza de dezvoltare: trei companii, plan complet, zero înregistrări.
`seed_demo` postează prin `post_manual_entry` și creează parteneri prin `create_partner` (`R9`: rânduri
scrise direct în `journal_entry` ar fi umplut ecranele și n-ar fi învățat nimic); `seed_documents` — în
`operations`, singurul strat care vede vânzări, achiziții și trezorerie, gardianul de dependențe a
decis plasarea — încearcă șaisprezece situații per companie, fiecare refuz prins și numit;
`seed_payroll` — patru persoane, cele trei tipuri de raport din ADR-071, o lună de pontaj și o rulare.

**Ce a găsit rulându-le, nu raționând:**
- două companii cu planul instanțiat **fără legări de roluri** (`II Tomsa Dan`, `Tominter DS`) — prima
  vânzare refuzată pe `CREANTE_COMERCIALE_TARA`, corect: postarea ar fi trebuit să aleagă un cont, iar
  unul greșit se echilibrează la fel de bine; seeder-ul instalează implicitele de la data de început;
- serii de numerotare valabile din august, deci notele din ianuarie refuzate la mijloc — luna de bază se
  caută înainte, nu se presupune ianuarie;
- avansul și vânzarea de mărfuri **refuzate prin proiect** (ADR-073 §6, §3): paisprezece din
  șaisprezece postează, iar un seeder oprit la primul refuz le-ar fi ascuns pe celelalte;
- rularea de salarii calculează patru persoane și raportează **douăsprezece componente nerezolvate**:
  `cnas.*`, `cnam.*`, `income_tax.*` sunt `draft` — starea onestă a build-ului (ADR-064), nu un defect;
  sărbătorile nu se scot din lună, calendarul fiind date fiscale pe care repository-ul nu le are;
- cifre identice pe trei companii făceau ca schimbarea companiei să arate același lucru ca o scurgere
  — verificarea pe care o face un om nu valora nimic; fiecare companie își trage un profil dintr-un hash
  stabil al id-ului; o persoană e deliberat în toate trei, contabilul, fiindcă `employee_idnp_unique` e
  `(company_id, idnp)`; numărul contractului derivă din persoană, nu dintr-un contor al reușitelor;
- **fără TVA, ca afirmație despre sistem:** `vat.standard` e `draft`, deci 20% în note ar fi pus în
  registru un număr pe care registrul refuză să-l confirme. *(Corectat parțial la 02.09, ADR-089: regimul
  e acum explicit pe fiecare linie, tot `fara_tva`, iar a șaptesprezecea situație cere TVA ca să fie
  refuzată pe nume.)*

**2026-08-31 — statutul fiscal e datat și ștampilat pe eveniment
([ADR-088](decisions/088-statutul-fiscal-e-datat-si-stampilat.md)); `OD-83` restrânsă, pasul 6
deblocat.**

**Cum s-a ajuns aici, fiindcă partea de proces contează:** sesiunea s-a oprit înaintea pasului 6
citind „decizie de motor, a proprietarului" ca pe un zid. Proprietarul a corectat-o: *exista o variantă
reversibilă și trebuia luată, cu un rând scris.* Raționamentul lui e reprodus verbatim în ADR-088 §2.

**Partea portantă nu era unde se ramifică, ci ca statutul să fie datat.** Fără margini nu funcționează
nici ștampilarea, nici rezolvarea la postare — n-ai de unde ști ce era valabil atunci. Cu ele, ambele
variante rămân recuperabile. Diferența reală: fără ștampilă, o corecție de statut schimbă **tăcut**
rapoarte deja emise.

**Măsurat înainte de a construi:** marginile pentru TVA existau deja — `company_vat_registration`,
datată, cu sursă, cu docstring-ul care spune exact de ce. Parcul IT **nu** are tabelă, deși `OD-81` o
numește; nu s-a creat, fiindcă n-are cititor și acesta e chiar ADR-ul care refuză schemele fără
consumator.

**Livrat:**
- `tenancy/services/tax_status.py` — un singur răspuns la *ce era adevărat despre această companie la
  data asta*, versionat de la primul rând.
- `accounting_event.tax_status_snapshot`, scris **în `emit()`**, nu cerut apelantului: profilul de
  capabilități e *input* (`R26`) și poate fi suprascris, statutul e *fapt* la o dată, iar un apelant
  care l-ar uita ar produce exact eșecul tăcut. `null` înseamnă un singur lucru — scris înainte ca
  această coloană să existe —, nu „fără statute".
- **4 teste de izolare.** Cel din mijloc e motivul întregii construcții: o înregistrare de TVA adăugată
  *după* postare nu atinge ștampila, iar aceeași întrebare pusă acum răspunde altfel — ambele numere
  există în test, ca diferența să fie vizibilă.

**Ce rămâne amânat, cu rând scris:** `OD-130` — forma rezolvării în handlere, la al treilea caz.
Ștampila nu prejudecă răspunsul, nici dacă statutul se dovedește diferență de *date*, nu de formă.

**2026-08-31 — jurnalul documentelor: restul lui F1.8, deblocat de propria sesiune.**

F1.8 avea un rest cu motiv scris: *„Rămân: jurnalele de vânzări/cumpărări — sunt «pe document prin
definiție» și **nu au ce lista până nu postează un document**."* Blocajul a dispărut azi: patru
familii postează.

**Ce este, și ce spune că nu este.** Listează documentele contabilizate ale unei familii într-o
fereastră, cu totalurile pe server (`C19`) și export CSV (`C20`). **Nu** e registrul de livrări sau de
procurări: acela are formă prescrisă într-un act pe care nimeni de aici nu l-a citit, iar coloanele
lui nu se pot completa cât timp niciun document nu poartă TVA (`OD-83`). Ecranul o spune în subtitlu,
ca să nu fie depus ca altceva — `C33` e despre exact acest fel de artefact.

**Nu citește nicio tabelă din `operations`.** Familia se numește după **modulul care o deține**, iar
`platform.documents.registry` răspunde ce coduri de tip înseamnă asta — deci `accounting` nu află
niciodată că `sales` își numește documentul `sales.document`. Primitiva nouă: `types_owned_by(owner)`.

**Livrat:**
- `accounting/ledger/services/document_journal.py` + `document_journal_csv` lângă celelalte exporturi.
- `GET /api/v1/accounting/ledger/companies/<id>/journals/<owner>`, cu `?export=csv`.
- **`legal_names_for` în `masterdata.partners`** — serviciul public care lipsea. Un registru fără
  denumirea contrapărții nu e registru, iar `C39` cere **denumirea legală**, nu cea internă.
- Ecranul *Jurnalul documentelor*, cu selector de familie și fereastră.
- **4 teste de izolare** + 1 de frontend. Fixture-ul e o capcană: partenerul are ambele denumiri și
  ele diferă, deci un export care ar tipări denumirea internă trece toate celelalte aserțiuni și cade
  doar acolo.

**O aserțiune a mea era greșită, nu exportul:** căutam denumirea legală ca substring, dar CSV-ul
corect dublează ghilimelele din interiorul câmpului. Am corectat testul spre ce emite un scriitor
corect — un test care ar fi cerut forma neescapată ar fi cerut exportului să fie greșit.

## Sesiuni mai vechi

**2026-08-31 — nota de credit: pasul 5 e complet
([ADR-073](decisions/073-forma-postarii-documentelor-comerciale.md) §7).**

A patra din serie, și cea mai mică — fiindcă decizia era deja luată și măsurată: `F2.X2 (j)` a
constatat că **Instrucțiunea OMF 118/2017 anexa nr. 2 tace** asupra returului, deci actul nu alege în
locul nostru, iar înclinația proprietarului e document de vânzare cu natură retur, nu `ReversalDocument`.

**Livrat:**
- `SaleNature` primește a treia valoare, `return` (migrarea `sales/0003`, aditivă).
- **Handler propriu**, `sales.return_issued`: debit **7128 „Returnări și reduceri"**, credit creanțe.
  Nu un venit cu minus — asertiunea din test e despre *care cont*, nu despre semn: un retur creditat pe
  venit ar echilibra, ar trece `R11`, iar cifra de afaceri ar ieși mai mică exact cu returnările, fără
  ca vreun total din balanță să contrazică.
- **Orchestrarea vânzărilor alege evenimentul după natură**, cu vocabular enumerat: două fapte, două
  chei de idempotență. O cheie comună ar face nota de credit să pară o reluare a facturii pe care o
  răspunde.
- **Avansul e refuzat pe nume**, în serviciu, cu motivul din ADR-073 §6 în mesaj: postarea doar a
  primei jumătăți ar crește un sold de avansuri pe care nimic din produs nu-l poate stinge. Ecranul
  nu-l oferă deloc — un document pe care nimeni nu-l poate contabiliza n-are ce căuta într-un select.
- `nature` devine **obligatoriu pe API**, deși serviciul are implicit: uitat într-un body HTTP, ar
  face dintr-o notă de credit o factură, adică ar recunoaște venit în loc de retur.
- 3 teste de izolare noi, 1 de frontend extins.

**Ce rămâne din ADR-073:** nimic. Cele patru familii — factura emisă, factura primită, încasarea și
plata, nota de credit — merg toate cap-coadă.

## Sesiuni mai vechi

**2026-08-31 — decontarea: care factură a stins banii
([ADR-087](decisions/087-decontarea-e-o-alocare.md), `F2.A3` parțial).**

A treia din seria *„începe una după alta"*. Handlerul de diferențe exista din F1.4.4 și **n-avea
apelant**: `SettlementFact` poartă un `settlement_id`, iar nimic din produs nu scria vreodată rândul
cu acel id. Deci soldul partenerului scădea și nimic nu spunea *care factură*.

**Ce a schimbat proiectarea, și motorul m-a corectat:** prima formă emitea evenimentul contabil la
fiecare potrivire. Motorul l-a refuzat — `contract_denomination` are exact două valori, cele două
noțiuni ale standardului, și **niciuna nu înseamnă „contractul e în lei"**. Nu e o scăpare de
vocabular: **evenimentul aparține diferenței, nu alocării**. Spec B §10.1 o spune din celălalt capăt.
Forma finală: o alocare în moneda funcțională se înregistrează și se auditează, și nu emite nimic.

**Livrat:**
- **Modul nou `operations/settlements`** — o tabelă, coloana `side`, `INSERT` și `SELECT` fără
  `DELETE`: o decontare ștearsă ar face soldul unei facturi să crească înapoi fără urmă că cineva a
  decis asta.
- **Două plafoane, refuzate, nu tăiate**: nu mai mult decât a rămas pe document, nici decât a rămas pe
  mișcare. Tăierea la cel mai mic ar posta un număr pe care nu l-a tastat nimeni.
- **Discriminatorii vin de pe documentul stins** — rezidența a fost cerută o dată, de la omul care
  știa (ADR-073 §2). Testul e o capcană: factura spune „nerezident", încasarea spune „rezident", iar
  faptul trebuie să urmeze factura.
- **Solduri deschise** — două liste (documente cu sold, mișcări nealocate), API și ecran de potrivire.
- **7 teste de izolare** + 1 de frontend. Cel principal e **negativ**: balanța, la ban, și numărul de
  înregistrări sunt identice înainte și după alocare.

**Un gardian m-a prins din nou, și avea dreptate:** `balances.py` citea `platform.documents.models`
direct. Listarea documentelor e treaba nucleului care ține tabela, nu a modulului care le compune —
așa că primitiva a intrat în `documents.services.lifecycle`, unde o schimbare de filtru se face
într-un loc, nu în trei.

**Al doilea gardian, pe care nu-l întâlnisem:** `test_reservations_are_tracked` a refuzat ADR-087
fiindcă se sprijină pe ADR-073 și **scăpase rezerva `OD-83`** — statutul TVA n-are pe ce selecta un
tratament. E purtată mai departe acum, și nu ca formalitate: o decontare stinge soldul unei facturi
**fără TVA**, fiindcă acela e singurul fel pe care produsul îl emite; când pasul 6 aduce TVA-ul,
decontarea nu se schimbă, dar ajustarea bazei din `OD-128` se declanșează tot de aici.

**Coliziune de numerotare, a doua oară azi:** sesiunea paralelă luase `OD-125` și `OD-126` între timp;
ale mele au devenit `OD-127` (decontarea în valută) și `OD-128` (art. 98 alin. (2) — handler propriu,
nu diferență de curs).

## Sesiuni mai vechi

**2026-08-31 — trezoreria: încasarea și plata merg cap-coadă
([ADR-073](decisions/073-forma-postarii-documentelor-comerciale.md) §5).**

A doua din seria *„începe una după alta"*. Bucla se închide: până acum o factură se contabiliza și
**nimic nu o stingea** — creanțele și datoriile creșteau fără să aibă cum să scadă.

**Livrat:**
- **Modul nou `operations/treasury`** — două tipuri de document (`treasury.receipt`,
  `treasury.payment`), **primele din produs care nu poartă poziții**. Suma e o coloană, nu o sumă de
  linii: o încasare de 3.000 lei e un număr. Steagul `carries_lines` exista dinainte, deci nimic n-a
  trebuit lărgit pentru ele — registrul îl anticipa pe nume.
- **Tabela cu politica ei**, `infra/migrations/0073`, în aceeași tranzacție (`C30`), cu triggerul care
  ține conținutul legat de starea documentului părinte.
- **Două handlere** în familia comercială: contul de trezorerie e al **instrumentului** (casă / cont
  curent), nu al documentului; sensul decide pe ce parte stă. `CASA_MDL` și `CONT_CURENT_MDL` erau
  deja în catalog; conturile în valută rămân neatinse, fiindcă o încasare în valută deschide
  diferențele de curs, care au handlerul lor.
- **`treasury` în vocabularul lui `source_module`** (`accounting_events/0004`), a treia adăugire pe
  tiparul lui `periods` și `production`: valoarea numește **sursa faptului**, nu un app. Nu `banking` —
  acela numește extrasul, altă sursă a aceluiași fel de fapt, și o încasare în numerar n-a fost
  niciodată pe la bancă.
- **API** `/api/v1/treasury/…` și ecranul **Încasări și plăți**, o singură listă pentru ambele sensuri.
- **8 teste de izolare** + 1 de frontend.

**Ce nu face, și e decizia ADR-ului, nu o scăpare:** nu leagă banii de factura pe care o sting.
Postarea n-are nevoie — debit trezorerie, credit creanțe, oricare creanță — iar legarea e
**decontarea**, `F2.A3`, cu handlerul de diferențe deja livrat. O coloană nulă acum ar fi o legătură pe
jumătate, pe care rapoartele ar începe s-o citească. Ecranul o **spune**, în loc s-o lase descoperită.

**Arborele e partajat, și s-a văzut:** o a doua sesiune implementează `ADR-085` în paralel (spațiul
aparține unui utilizator; `own_company_id` iese). La 20:35 `make web-check` a picat pe fișierele ei,
nu pe ale mele; la 20:37 trecea. Lucrul meu din `tenancy/views.py` a supraviețuit — verificat, nu
presupus. Cele trei teste de frontend roșii la sfârșitul sesiunii mele sunt ale ei, în zbor.

## Sesiuni mai vechi

**2026-08-31 — `OD-124` închisă: rolul scris la provizionare e de nivel companie
([ADR-084](decisions/084-rolul-la-provizionare.md)).**

Prima din seria cerută prin *„începe una după alta"*, pe varianta (a) — cea recomandată de două ori.
**Dacă intenția era (b), ADR-084 se înlocuiește; e o schimbare diferită, nu o corecție a acesteia.**

**Ce era, măsurat:** `rls.provision_company` copia în `company_access.role_id` rolul de `membership`,
care e de nivel tenant. `role_permission` leagă scopul permisiunii de nivelul rolului, deci pe acele
rânduri nu se putea ține nicio cheie de companie. Toate cele patru rânduri vii din dezvoltare purtau
`owner`. Consecința nu era doar a lui ADR-083: **`company.revoke_access` e în catalog de la F0.3.3 și
n-a putut fi ținută de nimeni, niciodată** — fixture-urile scriau `company_admin`, adică forma pe care
modelul o documentează, deci fiecare test era de acord cu modelul și în dezacord cu producția.

**Livrat:**
- `infra/migrations/0072` + `tenancy/0011` — funcția **caută** rolul de sistem de nivel companie în loc
  să copieze unul. Obiecția din `0045` (*o funcție privilegiată care și-ar alege rolul ar fi o cale de
  escaladare*) rămâne valabilă și nu e încălcată: nu există alegere, interogarea are un singur rezultat
  posibil. Fișierul vechi nu s-a atins (`C31`); reversul restaurează corpul lui verbatim, defect inclus.
- **Refuz dacă rolul lipsește**, cu mesaj care numește `repair_system_roles`. Căderea înapoi pe rolul de
  membership ar fi restaurat defectul tăcut și numai la tenanții stricați.
- `repair_company_access` — comandă de operator, nu migrare (`OD-94`). Rulată: **alpha 3, proba 1,
  proba2 0**; verificat după, toate rândurile vii poartă acum `company_admin`.
- **Rândurile de engagement nu s-au atins**, deliberat: le-ar fi dat firmei `company.close` peste
  compania clientului. Cine sunt oamenii firmei pe registrele clientului rămâne `OD-42`.
- Testul care ieri afirma defectul îl afirmă acum reparat, cu povestea în docstring; plus refuzul pe un
  tenant construit ca cei stricați — **cu `owner` și fără `company_admin`**, fiindcă starea nu se poate
  atinge ștergând rolul: un rol de sistem refuză ștergerea, prin trigger.

**Efectul vizibil:** *Fișa companiei* funcționează de acum pe `alpha` — formularul și închiderea nu mai
sunt dezactivate.

## Sesiuni mai vechi

**2026-08-31 — pasul 5, latura achizițiilor: factura primită merge cap-coadă
([ADR-073](decisions/073-forma-postarii-documentelor-comerciale.md) §4).**

Sesiune de secvență, aleasă după ce am măsurat unde s-a oprit pasul 5: `sales` avea model, serviciu,
API și ecran; `purchases` avea model și un serviciu de deschidere, **și nicio ușă** — fără `views.py`,
fără `urls.py`, fără ecran. Regula fazei o spune singură: *„un pas fără ecran nu e livrat"*.

**Livrat:**
- **Cei doi discriminatori pe `purchase_document`** — `cost_destination` (vocabular închis de patru
  valori) și `partner_resident`. Migrarea `purchases/0002`, **scrisă de mână**: `makemigrations` cere
  valorile implicite la un prompt interactiv, iar un prompt răspuns într-un terminal nu lasă urmă
  despre ce s-a răspuns și de ce. *Măsurat înainte: tabela are zero rânduri, deci implicitele
  de-o-singură-dată nu etichetează nimic.*
- **Handlerul de postare** `purchases.invoice_recorded`, în `accounting/posting/services/commercial.py`,
  lângă cel de vânzări. Destinația alege **rolul** (7135 / 7129 / 811 / 821), rezidența alege
  **datoria** (5211 / 5212). Toate cele șase roluri existau deja în catalog de la ADR-073.
- **Serviciul de înregistrare** (`record_and_post`) — validează, apoi postează, în ordinea pe care o
  impun actele. Cuvântul e *înregistrare*, nu *emitere*: facturile noastre le emitem, pe ale lor le
  înregistrăm.
- **API**: `/api/v1/purchases/…` — listă, detaliu, linii, `recording`.
- **Ecranul „Facturi primite"**, pe primitivele din `shared/ui` (nu pe constantele locale `FIELD`/
  `BUTTON` de dinainte de ADR-074). **Ambele numere pe același rând**: al furnizorului, care e pe
  hârtie, și al nostru, alocat la validare.
- **5 teste de izolare** sub rolul aplicației + **1 de frontend**.

**Ce nu se poate exprima, și e structural, nu un refuz cu cod:** niciuna dintre cele patru destinații
nu numește un activ. Marfa și materialele intră în bilanț, iar a doua jumătate a acelei înregistrări
e F4 — deci nu există valoare sub care să călătorească. Latura de vânzări refuză același lucru cu un
cod, fiindcă acolo `revenue_kind` are valorile care ar fi trebuit să meargă în stoc.

**Un gol găsit prin construcție:** ecranul **facturilor emise** exista din pasul 5 și **n-avea nicio
intrare în bara laterală** — accesibil doar tastându-i adresa, exact ce comentariul din lista de
companii numește „un ecran pe care nu-l atinge nimeni". Gruparea nouă *Documente comerciale* îi dă
prima intrare, odată cu a facturilor primite.

**Verificat:** `make lint`, `make typecheck`, `make deps-check` (fără violări — `accounting` citește
`platform`, niciodată invers), `make web-check`, `make web-test` (45 verzi), suita backend.

**Al doilea gol, ridicat de proprietar privind cele două ecrane alăturate:** *„de ce arată diferit?"*
Măsurat — `SalesScreen` era **singurul fișier din tot frontendul** care mai purta constantele locale
`FIELD`/`BUTTON`, cele pe care ADR-074 le-a scos din șaisprezece ecrane. S-a scris în paralel cu
sesiunea de design și a ratat parcurgerea, apoi a stat lângă propriul corespondent arătând ca alt
produs. Trecută pe `shared/ui` și pe `PageHeader`. *Restul ecranelor își păstrează antetul simplu —
acela e opritul deliberat din ADR-074 §5, nu o scăpare.*

**Ce rămâne din pasul 5:** încasarea și plata — modul nou `operations/treasury`, ADR-073 §5 — și nota
de credit (§7). `OD-124` rămâne deschisă și nu s-a atins: „continuă" nu e un răspuns la o alegere
care lărgește sau nu accesul.

## Sesiuni mai vechi

**2026-08-31 — editarea și închiderea unei companii
([ADR-083](decisions/083-editarea-companiei.md)), plus trei constatări măsurate care au schimbat
lucrarea pe parcurs.**

Pornită din întrebarea proprietarului privind lista de companii: *cum șterg sau editez o companie?*
Răspunsul măsurat: niciuna dintre cele două nu exista — API-ul avea `GET` și `POST`, iar funcția
privilegiată spune singură *„cannot touch an existing company"*. Clicul pe rând nu schimba
selectorul: naviga la planul de conturi, iar antetul își ia compania din cale.

**Deciziile proprietarului:** două chei, `company.edit` și `company.close`, ambele la nivel de
companie; clicul pe rând trece pe ecranul companiei.

**Trei lucruri măsurate, fiecare schimbând ce însemna „adaugă cheile":**

1. **Catalogul de permisiuni nu e impus nicăieri.** `require_permission` are zero apelanți în
   producție, nu există `permission_classes` în niciun view. Cele opt chei existente au `enforced_in`
   completat spre cod care nu le verifică — exact ce interzice regula 1 din ADR-020. `company.edit` și
   `company.close` sunt **primele două chei impuse efectiv**. Restul: `OD-121`.
2. **`has_permission` nu putea vedea o cheie de nivel companie** — citește prin `role__membership`, iar
   un rol de companie stă pe `company_access`. S-a adăugat `has_company_permission`, cu condițiile de
   viață **copiate din `rls.has_company_access`**, nu inventate: o verificare mai largă decât predicatul
   ar spune „da" despre o companie din care baza nu întoarce niciun rând.
3. **`company.status` nu era citit de nimic.** `closed` nu însemna nimic — aceeași formă de defect ca
   `covers_all_companies` înainte de F0.3.3. Punctul de impunere e `assert_postable`, unde stă deja
   `R12`: motorul refuză, nu interfața.

**Livrat:**
- `company.edit` / `company.close` în catalog + migrarea `identity/0008`; `repair_system_roles --all`
  rulat pe dezvoltare (`company_admin`: 1 → 3 permisiuni).
- `has_company_permission` / `require_company_permission` în `identity.services.roles`.
- `update_company` și `close_company` în `tenancy.services.companies`, cu audit, și cu **vizibilitatea
  verificată înaintea permisiunii**: un 403 pe un rând invizibil ar confirma că id-ul există (`IZ-04`).
- `is_open_for_posting` (fapt, în `platform`) citit de `assert_postable` (refuz, în `accounting`) —
  singura direcție pe care graful o permite.
- `GET`/`PATCH /api/v1/companies/<id>` și `POST .../close`, cu coduri stabile noi.
- Ecranul **Fișa companiei**: trei zone — ce se corectează, ce nu se corectează *și de ce*, închiderea
  cu motiv. Drepturile se **citesc** din `/workspace`, deci controalele sunt dezactivate cu explicație
  în loc să eșueze la salvare.
- 8 teste de izolare sub rolul aplicației.

**Ce blochează ecranul, și e a treia constatare — `OD-124`:** `rls.provision_company` copiază în
`company_access.role_id` rolul de **membership**, care e de nivel tenant. Măsurat: toate cele patru
rânduri vii din dezvoltare poartă `owner`. Consecința e că nicio cheie de nivel companie nu se poate
ține pe rândurile reale — deci pe `alpha`, azi, formularul se vede dezactivat. Motivul din
`0045_provision_company.up.sql` e corect (*o funcție privilegiată care și-ar alege rolul ar fi o cale
de escaladare*), deci reparația e o decizie, nu o corectură: rolul de sistem de nivel companie la
provizionare, sau un rol de tenant care acoperă implicit toate companiile — **a doua lărgește accesul**.
Consemnat ca test, nu ca afirmație.

**Ce nu s-a făcut, deliberat:** ștergerea companiei (`OD-122` — „fără nimic postat" e o măsurătoare
peste tabele neenumerate) și editarea câmpurilor cu consecințe (`OD-123` — `platform` nu poate citi un
fapt din `accounting`, deci regula „nu după prima postare" n-are unde sta; refuzate în întregime, nu
condiționat).

**Verificat:** `make lint`, `make typecheck`, `make deps-check`, `make web-check`, `make web-test`
(40 verzi), suita backend, migrarea aplicată pe dezvoltare.

## Sesiuni mai vechi

**2026-08-31 — schema mandatului declarat ([ADR-081](decisions/081-revendicarea-optionala.md)
§3.1 și §3.3). Prima din cele patru sesiuni ale ADR-ului: numai schema, fără căi privilegiate și
fără interfață.**

**Proprietatea centrală a sesiunii e una negativă: predicatul de acces nu s-a atins.**
`infra/migrations/0003_access_predicates.sql` are zero modificări. Un angajament pe mandat declarat
e `active` ca oricare altul și trece prin calea 2 existentă a lui `rls.has_tenant_access` — fără
ramură, fără stare nouă, fără cost pe calea fierbinte. Verificat din două părți, fiindcă o afirmație
negativă nu se vede într-un test de funcționalitate: accesul măsurat al celor două temeiuri, comparat
între ele, **și** textul funcției, citit din `pg_get_functiondef`.

**Livrat:**
- `tenant.claimed_at` — `tenancy/0010`. Fapt cu dată, **nu** status: un tenant nerevendicat e perfect
  `active`, iar cele două axe răspund la întrebări diferite. Fără SQL pereche — n-are ce exprima
  Django aici (nu e cod, nu e politică, nu e grant).
- `engagement.acceptance_basis`, `mandate_ref`, `claim_contact_email` — `engagement/0004`, cu perechea
  `infra/migrations/0071`: `COLLATE "C"` pe referința contractului (număr de document, deci cod — `C34`)
  și `citext` pe contact, ca `user.email` din `0011` și din același motiv.
- **Trei CHECK-uri**, adăugate după scriere (regula (c) din `OD-94`): acceptarea își spune temeiul,
  temeiul stă în vocabular, mandatul declarat poartă contactul de revendicare.
- `lifecycle.accept()` și acceptarea din transfer scriu `acceptance_basis = 'client'` — singurul temei
  la care ajung, fiindcă acolo ajunge doar partea care n-a invitat.
- Fixture-ul `engage` primește `acceptance_basis`, ca să semene cu ce scrie producția.
- `backend/tests/isolation/test_declared_mandate.py` — **7 teste, `IZ-79`**, sub rolul aplicației (`T1`).

**Măsurat, nu presupus:** `engagement` are **0 rânduri** în baza de dezvoltare, deci nu s-a scris niciun
backfill. Dacă vreo bază ajunge la migrare cu un angajament acceptat, `engagement_acceptance_states_its_basis`
o refuză zgomotos, iar reparația e un backfill cu `'client'` — adevărat pentru orice rând acceptat înainte
de azi, fiindcă al doilea temei nu exista ca să fie ales.

**Ce am adăugat peste lista din instrucțiune, și de ce se semnalează:** al treilea CHECK
(`engagement_declared_mandate_has_claim_contact`). Instrucțiunea enumera coloana; §3.3 și §3.5 o numesc
**obligatorie**, iar §3.5 o numește și veriga slabă. Un câmp obligatoriu pe care nu-l impune nimic e gol
exact pe rândurile unde cineva are nevoie de el.

**Ce a rămas neimplementat din ADR-081, deliberat, fiindcă nu era în sesiune:** `billing_payer_assignment`
din §5 — atribuirea plătitorului cu dată, cu neîntrepătrundere pe `daterange`. E schemă, e aditivă și e
listată în §8; nu e în această migrare și nu e programată. Restul (`P-11`, `P-8`, poarta de firmă din
ADR-080, consola) sunt sesiunile 2–4.

**Verificat:** `make lint`, `make typecheck` (413 fișiere), `make drift-check` („fără derivă față de
contracte"), migrarea aplicată pe baza de dezvoltare, suita completă rulată.

**Nicio decizie deschisă nu s-a închis.** `OD-118` (standardul de probă la revendicare) rămâne unde
l-a lăsat ADR-081, iar `OD-37` rămâne motivul pentru care nimeni nu poate număra membrii altcuiva —
de aceea `claimed_at` e coloană și nu deducție.

## Sesiuni mai vechi

**2026-08-31 — frontend: identitatea vizuală și stratul de componente, din macheta proprietarului
([ADR-074](decisions/074-sistemul-de-design-evidenta.md)).**

Sesiune de interfață, pornită de la trei simptome de mediu și terminată cu o schimbare de identitate
vizuală.

**Întâi, două defecte de mediu, amândouă măsurate, nu ghicite.** Ecranul roșu *„A apărut o eroare
neașteptată"* era proxy-ul Vite care trimitea `/api` la portul 8000, unde rulează **alt proiect**:
`.env` avea `BACKEND_PORT=8000`, backendul Evidenta rula pe 8001. Mesajul era tocmai fallback-ul
`C10` — 404-ul HTML al celuilalt Django nu are cod, deci `ApiError('unknown')`. Reparat în `.env`;
Vite citește fișierul o singură dată, la pornire, deci a cerut repornire. Apoi: *„nu apare nimic
nou"* — nu lipsea nimic, cele 17 rute erau toate accesibile, dar **doar prin rândul companiei**.
S-a adăugat navigarea companiei (întâi bandă, apoi bară laterală).

**Ce era, măsurat:** `shared/ui/` gol deși ADR-009 spunea că acolo stau componentele; **27 de
constante locale** `FIELD`/`BUTTON`, același șir de buton copiat în **16 fișiere**; titlul de pagină
la o treaptă peste rândurile de sub el.

**Direcția a ales-o proprietarul** dintre trei propuse *(„Primitive + bară laterală")*, apoi a livrat
macheta: pachet de predare Claude Design, cu sistem de design complet (stemă cu bufniță, navy/aur pe
pergament, 23 de primitive, 14 ecrane recreate).

**Livrat:**
- **Tokenii sistemului** în `index.css`, ca valori, cu maparea către utilitarele Tailwind sub numele
  pe care codul le folosea deja — deci schimbarea de identitate n-a cerut o parcurgere a ecranelor.
  Scurtăturile compuse de font stau în afara lui `@theme` (altfel Tailwind v4 le-ar face `font-size`
  invalid) și se consumă prin utilitare `type-*`.
- **`shared/ui/`**: `Button`, `IconButton`, `Icon`, `Input`, `Select`, `Field`, `Card`, `Badge`,
  `Figure`, `EmptyState`, `PageHeader`. `Figure` **nu** formatează — cheamă `@/shared/format` (`C18`).
- **Cochilia**: bară laterală pe gradientul stemei cu secțiunile companiei deschise, antet cu
  comutator de companie (păstrează secțiunea, aruncă identificatorii de rând — un cont nu trece
  dintr-o companie în alta).
- **Grila**: cap de coloană în majuscule condensate pe fond scufundat, la înălțime de rând, și linie
  de aur peste totaluri.
- **Autentificarea**: panoul stâng cu stema și citatul care se schimbă.
- **Ecranele**: 16 fișiere trecute pe primitive; antetul cu supratitlu adoptat pe *Companii* și
  *Parteneri* ca tipar.
- **Scara de densitate trece la 52 / 44 / 36** (ADR-074 §4 revizuiește ADR-042). Numele tokenilor
  rămân, deci `C21` și gardianul ESLint nu se ating. **Rezerva de accesibilitate a lui ADR-042
  dispare cu cauza ei**: la 36px treapta strânsă poate purta butoane în rând.
- **`lucide-react` 0.544.0**, pinuită. Motivul distincției față de `C23` e în ADR-074 §6: shadcn e
  opinie de design, o pictogramă e geometrie.

**Ce s-a refuzat deliberat, deși e în machetă** (ADR-074 §5): **Panoul de control** cu cele patru
dale KPI — niciuna dintre cifre n-are endpoint, iar un tablou de bord cu numere plauzibile într-o
aplicație contabilă se citește ca un raport; căutarea din antet, clopoțelul, numele utilizatorului,
perioada din subsol, ceasul de pe autentificare (ar fi cerut un al doilea format de dată, contra
`C18`).

**Verificat:** `make web-check` (tsc, eslint, build) și `make web-test` — 35 de teste verzi, inclusiv
unul nou pentru navigarea companiei. Backendul nu s-a atins.

**Unde s-a oprit:** restul ecranelor își păstrează antetul simplu (fără supratitlu); `StatTile`,
`Tabs`, `Dialog`, `Toast`, `Tooltip`, `Breadcrumbs` din sistem nu s-au construit, fiindcă niciun
ecran nu le cere azi.

**Ce rămâne întrebare deschisă:** fonturile sunt substituție Google Fonts, cu declanșator scris în
ADR-074 §7 — se auto-găzduiesc când există fișiere licențiate.

**A doua jumătate a aceleiași sesiuni — titularul contului
([ADR-075](decisions/075-identitatea-titularului.md)).**

Pornită din întrebarea proprietarului privind lista de companii: *a cui e pagina asta?*, apoi
*Alpha SRL nu are contabilitatea proprie?* Răspunsul măsurat: `tenant` purta doar abonamentul —
subdomeniu, denumire, stare — fără IDNO și fără formă juridică, iar contabilitatea e legată de
`company` fără excepție. Deci titularul își ține registrele proprii doar dacă există **și** ca
companie, iar produsul nu putea spune care dintre companii este el: n-avea cu ce compara.

**Deciziile proprietarului, ambele alese explicit dintre trei variante:** titularul poartă `idno` +
`legal_form`; compania proprie **se propune, nu se creează automat** (data de început a evidenței e
decizie contabilă, iar un implicit ar fi o dată greșită pe care nimeni n-a observat că o alege).

**Livrat:**
- `tenant.idno` + `tenant.legal_form` — migrarea `tenancy/0009`, SQL pereche `infra/migrations/0070`
  pentru `COLLATE "C"`. Nullable, fără `UNIQUE` (regula „o firmă, un abonament" nu e decisă), fără
  `CHECK` pe formă (clasificatorul nu e în repo).
- `GET /api/v1/workspace` — titularul cu identitatea lui și **compania proprie derivată prin IDNO**,
  drepturile cititorului în cuvinte, rolurile spațiului cu ce poate fiecare, firmele cu mandat.
- Ecranul **Spațiul de lucru** + oferta care deschide formularul de companie completat din titular.
- Comenzile de operator `set_tenant_identity` și `repair_system_roles`.
- 7 teste de izolare sub rolul aplicației + 2 de frontend. Testul de potrivire e o **capcană**:
  tenantul și două companii poartă aceeași denumire cu IDNO-uri diferite, deci o implementare pe nume
  trece prin toate celelalte și cade aici.

**Defect găsit pe drum, nu căutat:** pe `alpha`, rolul de sistem `owner` avea **zero** permisiuni și
`company_admin` lipsea cu totul; `proba` și `proba2` aveau 7 și 1. Tenantul fusese creat înainte ca
`create_system_roles` să însămânțeze permisiunile. Nimic n-a semnalat — un rol fără permisiuni e un
rând valid — iar primul simptom ar fi fost proprietarul spațiului incapabil să-și editeze rolurile.
Reparat cu `repair_system_roles --all`, idempotent fiindcă serviciul era deja idempotent.

**Două violări `D6` prinse de gardian, reparate ca atare, nu prin lărgirea contractului:** vederea
citea `identity.models` (acum întreabă serviciul), iar comanda de reparare citea `tenancy.models`
(acum stă în `tenancy` și cheamă serviciul public din `identity`).

**Deschise, consemnate:** `OD-107` (facturarea abonamentului — latura clientului e o factură de la
furnizor obișnuită, latura vendorului nu există), `OD-108` (identitatea titularului nu se poate edita
din produs: ar cere o cheie de permisiune nedecisă). `OD-37` rămâne motivul pentru care lista
persoanelor din spațiu nu se poate afișa, și ecranul o spune.

**A treia parte, în aceeași sesiune — modelul s-a răsturnat, și bine că devreme
([ADR-085](decisions/085-spatiul-apartine-unui-utilizator.md), scris de sesiunea paralelă;
[ADR-086](decisions/086-facturarea-pe-companie.md), al meu).**

Proprietarul a numit cazul care rupe forma dată cu două ore înainte: **un antreprenor cu mai multe
companii e mai frecvent decât un holding**, iar el nu are companie-mamă. Concluzia lui, verbatim:
*„m-am grăbit să oblig orice tenant să fie companie… titularul contului să fie un user, cu acces și
permisiuni pe companiile create de el."*

Ce s-a schimbat în cod, pe ecran: titularul e **persoana** — nume, e-mail, rol, drepturi —, companiile
sunt egale între ele, iar „compania titularului" a dispărut cu derivare, marcaj și ofertă cu tot.
`tenant.idno` rămâne, cu alt înțeles: identitatea abonatului. Selectorul a recăpătat **starea goală**
(„Alege compania"), fiindcă un antreprenor deschide aplicația fără să fie în vreuna, iar alegerea în
locul lui ar fi o presupunere despre ce registre a venit să vadă.

**Facturarea, decisă pe fondul contabil** (ADR-086): câte o factură pe companie, fiindcă o factură
emisă pe o persoană juridică nu intră în registrele alteia; excepția e plata indirectă, unde firma de
contabilitate primește una singură pentru companiile pe care le plătește. `OD-107` restrânsă la
emitere.

**Două ecrane de editare, cu granițele scrise pe ele:**
- **Partenerul** — `PATCH` parțial pe denumiri, roluri, monedă și termen. IDNO/IDNP și TVA rămân
  afară: primul e cum numesc documentele emise partenerul și ce împiedică două fișe să împartă un
  sold (`R20`), a doua e stare cu dată. Găsit scriind testul: **DRF aruncă tăcut cheile nedeclarate**,
  deci un `PATCH` cu `idno` întorcea `200` cu vechea valoare — o corecție care arăta că a mers. Acum
  se refuză pe nume.
- **Titularul** — numele, atât. E-mailul e credențialul și cere dovada noii adrese; parola și al
  doilea factor pornesc de la cele actuale; limba n-are consumator (ADR-014). Formularul o spune,
  în loc să lase omul să caute.

**Un defect de tipografie prins tot de proprietar, cu efect larg:** utilitarele `type-*` erau scrise
prin scurtătura CSS `font:`, care **resetează** `font-style`, `font-weight` și `font-variant`. Măsurat
în artefactul construit: `.type-body-lg` apărea după `.italic`, deci `class="type-body-lg italic"`
ieșea drept — clasa era acolo, italicul nu. Aceeași capcană aștepta orice `font-bold` sau `tabular`
lipit de un `type-*`, inclusiv pe coloanele de sume, unde `C27` cere cifre tabulare. Rescrise pe
proprietăți separate.

**Unde s-a oprit:** tot ce e mai sus a intrat în `3d6291f`, comis de sesiunea paralelă la
instrucțiunea proprietarului *„comite tot"* — 180 de fișiere, ambele fluxuri, `GATE: PASS` pe
1217 teste backend și 49 frontend, `make check-committed` verde pe arborele comis.

**Ce rămâne întrebare deschisă din partea mea:** `OD-129` (cum ajunge un om la spațiile lui, când are
mai multe — directorul pe gazdă neutră, fără sesiune comună, fiindcă cookie-ul e host-only prin
construcție) și divergența semnalată de trei ori și nerezolvată: **ADR-085 §4 spune că derivarea
„companiei titularului" se păstrează pentru holdinguri, iar codul nu o mai are.** Ori se amendează
§4, ori se pune derivarea la loc; azi ADR-ul descrie un cod care face altceva — chiar tiparul din
`OD-86`.

## Sesiuni mai vechi

**2026-08-30 — instrucțiune nouă: scop și metodă schimbate. Lista de deblocare, `R1` îngustată,
ADR-071 acceptat și construit, și pasul 1 al secvenței livrat cap-coadă.**

**Ce s-a schimbat ca metodă, verbatim din instrucțiune:** *nimic nu așteaptă o sursă juridică*
(structura se construiește, valorile intră ca date, o sursă lipsă e **un rând**, nu un blocaj);
*reversibil implicit* (proprietarul decide doar ce nu se poate desface); *fiecare bucată aterizează
utilizabilă*; *ordinea urmează calendarul clientului*. Se opresc: reguli noi de proces, gardieni noi,
extinderea disciplinei de margini.

**Livrabilul zero — [`13-lista-de-deblocare.md`](_bootstrap/13-lista-de-deblocare.md).** Patru
categorii, **35 de intrări, fiecare cu implicitul ei**: §A șapte decizii ireversibile (compania-pilot,
IDNP-ul stocat, fluturașul ca document legal, ADR-007, `OD-84`, numerotarea, `DN-18`); §B opt reguli
care blochează, fiecare cu îngustarea propusă; §C unsprezece surse neobținute, cu răspunsul la
*„rândul gol cu motiv ajunge?"* pe fiecare; §D zece alegeri de produs care se scriu în schemă, cu
costul schimbării de după. **Regula fișierului:** o intrare fără implicit e incompletă — altfel lista
devine chiar blocajul pe care îl elimină.

**`R1` s-a îngustat — [ADR-072](decisions/072-exceptia-care-nu-largeste.md), `Acceptat`, decizia
proprietarului.** Confirmarea se cere doar pentru excepțiile care **lărgesc accesul la date**. Un
catalog global doar-citire, cu `writer_role = "evidenta_owner"`, însămânțat din migrarea care îl
definește, e commit obișnuit — `permission` era precedentul, în același fișier. **Costul măsurat al
formei largi:** `C1(b)` s-a oprit **trei sesiuni la rând**, fiecare raportând *„singura oprire
legitimă"*, pentru un catalog de trei valori impuse de lege.

**[ADR-071](decisions/071-tipurile-de-raport-ca-tabela.md) `Acceptat` cu cele trei corecții cerute, și
una contează:** pct. 1.1 prima liniuță numește **trei** forme, nu două. `service_relationship` —
raporturi de serviciu în baza actului administrativ — lipsea. **Nu e caz marginal:** funcționarul numit
prin act administrativ *este* salariat pentru art. 22, deci un model cu două valori l-ar fi împins în
`civil_contract`, unde invariantul nu se aplică — contribuție sub minim, perfect echilibrată, `R11`
trece, niciun test de sold n-o vede. **Simetricul exact al defectului măsurat de ADR-069.** Cum s-a
pierdut, scris în §1.1: ADR-ul a fost redactat din **întrebarea** care îl produsese (*unde se oprește
art. 22*), iar acea întrebare opune „salariat" lui „prestator civil" — raportul de serviciu nu apare în
opoziție, deci n-a apărut în tabel. **Nu e operand lipsă: operandul era în repo, în aceeași propoziție.**

**`C1(b)` construit.** `employment_relationship_type` în `fiscal/registry`, trei rânduri, fiecare cu
ancora lui în coloană; însămânțare prin `backfill()` cu `expected=0` și `CHECK`-ul de vocabular închis
în **aceeași migrare** (regula (c) din `OD-94`). **O corecție găsită de un gardian, nu de citire:**
SQL-ul a plecat fără politică permanentă de scriere pentru owner — argumentul fiind că ușa suspendă
`FORCE` oricum — iar `test_reference_load_policy` a răspuns cu un fapt: sub `FORCE`, un **privilegiu
fără politică nu vede nimic**, deci `writer_role` ar fi declarat o cale de scriere inexistentă.
`permission` poartă aceeași politică, din același motiv.

**Pasul 1 al secvenței, livrat cap-coadă: `operations/payroll`.** Cinci tabele company-scoped —
`employee`, `employment_contract`, `employment_contract_amendment`, `timesheet`, `timesheet_day` —, cu
politicile în aceeași tranzacție cu tabelele (`C30`) și colațiile după `C34`. Ce poartă fiecare și de
ce, pe scurt:

- **`employee` e al companiei, nu al tenantului** (ADR-065 §4), cu identitatea impusă ca
  **constrângere**: IDNP sau act de identitate, exact una, fiindcă rândul pentru care se face excepția
  e chiar cel care altfel n-ar avea nicio cheie naturală.
- **Contractul e cap de serie** (ADR-067): ecranul nu oferă niciodată *„editează salariul"*, oferă act
  adițional. *„Ce era în vigoare la data D"* se citește parcurgând seria, iar răspunsul spune **prin ce
  document** s-a stabilit fiecare câmp — *„9000 în martie"* nu se apără fără asta.
- **Ordinul angajatorului e câmp, nu entitate** — exact linia trasă de ADR-067 §2. Angajarea și actul
  adițional poartă numărul și data ordinului; încetarea fără ordin e refuzată **de bază**, nu doar de
  serviciu, fiindcă termenul IRM19 curge din data ordinului.
- **`relationship_type` e `NOT NULL`**, cheia străină pe care ADR-071 o argumentează. **Verificat în
  ambele feluri:** serviciul refuză cu cod stabil, iar tabela refuză structural — testul forțează
  `SET CONSTRAINTS ALL IMMEDIATE`, altfel cheia deferată a lui Django n-ar cădea niciodată într-un test
  care nu comite.
- **Pontajul e pe ore, nu pe zile**, fiindcă art. 22 alin. (1) cere proporția timpului lucrat: zilele se
  deduc din ore, invers nu. Orele de noapte și de sărbătoare sunt **parte din** ziua lucrată, impus prin
  `CHECK`. Luna închisă e înghețată **printr-un trigger**, nu de serviciu.

**Trei ecrane**, în același commit cu serverul: angajați, contracte (cu seria de acte adiționale și
întrebarea „la data D"), pontaj cu totalurile **de la server** (`C19`). Legate din lista de companii,
fiindcă un ecran la care se ajunge doar tastând adresa e un ecran la care nu ajunge nimeni — clasa care
a produs patru cazuri într-o zi.

**Măsurători și eșecuri consemnate:**

- **Un `GRANT` lipsă găsit de suită, nu de citire:** triggerul de îngheț e `SECURITY DEFINER`, deci
  rulează ca `evidenta_rls` — rol care n-avea nimic pe tabelele noi. Fără `GRANT SELECT ON timesheet TO
  evidenta_rls`, orice scriere de zi murea cu *„permission denied for table timesheet"* **din interiorul
  triggerului**, adică cu un mesaj care arată a defect de permisiuni al aplicației.
- **Cheile străine ale lui Django sunt `DEFERRABLE INITIALLY DEFERRED`**, deci un tip inexistent n-ar fi
  căzut la `INSERT`, ci la commit — la capătul cererii, departe de apelant, fără cod stabil (`C10`).
  Verificarea din serviciu nu e cosmetică: transformă un 500 la commit într-un 422 la locul faptei.
- **`OD-100` s-a manifestat din nou, în invocarea mea:** `make gate | tail` a întors 0 peste un lint
  căzut. Reţeta e corectă; conducta era a mea. A doua oară aceeaşi cauză, acelaşi loc.

**Patru rânduri noi în registru:** `OD-101` (categoria CAS n-are de unde să-și ia implicitul; vocabularul
îngustat la punctele angajatorului), `OD-102` (numele `employment_contract` nu acoperă contractele
civile — de decis la pasul 8), `OD-103` (testul de plan de execuție care cade doar în suita întreagă),
`OD-104` (`R21` și contractul de dependențe au aceeași formă ca `R1` și n-au fost atinse).

**Pasul 2 livrat în aceeași sesiune: scutirile.** Trei tabele — `exemption_dependent`,
`exemption_application`, `exemption_entitlement` — plus ecranul per persoană.

- **Pct. 18 e `CHECK`, nu obicei:** `effective_from = prima zi a lunii următoare lui `filed_on``,
  impus în bază. De asta se stochează `filed_on`, nu doar data efectivă: cu numai una, regula ar trăi
  în aplicație, iar un import în masă o ocolește. **Verificat în ambele feluri** — serviciul o derivă,
  baza refuză o pereche construită de mână.
- **Nu e stare, e istorie.** Cererea deschide o îndreptățire datată; retragerea o **închide** cu
  `valid_to` din luna următoare, nu o șterge — și `evidenta_app` **nu are `DELETE`** pe îndreptățiri.
  Interval semideschis: în vigoare până în iunie, dispărută din iulie.
- **Nu există `S`.** Art. 34 alin. (2) dă doar scutirea majorată pentru soț/soție. Vocabularul e
  `P`, `M`, `Sm`, `N`, `H`, închis în model, în bază și în lista din ecran.
- **`EXCLUDE` peste `(angajat, cod, persoană întreținută, perioadă)`** — același copil de două ori la
  același angajat e refuzat; **doi angajați pentru aceeași persoană rămâne permis**, fiindcă legea îl
  permite și un `UNIQUE` acolo ar fi invenția noastră. `COALESCE(dependent_id, uuid_nil)` fiindcă
  altfel exact scutirile personale ar scăpa de constrângere.
- **Pct. 9 e declarație, nu verificare:** `declared_sole_workplace` e ce a semnat angajatul. Sistemul
  nu poate vedea celălalt angajator; ce se păstrează e dovada pe care angajatorul a acționat.

**Al doilea `REVOKE` uitat, aceeași cauză ca `OD-47`, prins de test:** `GRANT SELECT, INSERT, UPDATE`
**nu retrage** `DELETE` — privilegiile implicite din `0001_roles.sql` îl acordaseră deja. Testul care
cerea refuzul ștergerii a trecut prin el fără să clipească. A doua oară în aceeași sesiune când un
`GRANT` incomplet arată ca o interdicție.

**Pasul 3 livrat: calculul lunar, statul de plată, fluturașul.** `payroll_run` și `payroll_line`,
motorul, documentul, ecranul.

- **Constatarea proprietarului, consemnată înainte de a fi folosită, apoi folosită** (`OD-106`,
  ADR-071 §7.1): **domeniul unui invariant e o mulțime, nu un tip.** Art. 22 prinde `employment_contract`
  **și** `service_relationship`, nu unul. O cheie străină unică nu poate spune „X și Y", iar scrisă așa,
  un tip ar fi scăpat tăcut. Închisă în aceeași zi de consumatorul ei: `calculation_invariant_domain`,
  un rând per tip, citită ca mulțime. **Testul care o dovedește:** cu brutul sub minim, primele două se
  încarcă pe minim, contractul civil pe brut.
- **Suma poate fi nulă, și e proiectare, nu gol.** Cele 22 de valori încărcate n-au margine (`C1(a)`),
  deci nu se rezolvă la nicio dată — iar răspunsul onest e **linia care există, n-are sumă și spune de
  ce**, nu zero și nu un refuz care ascunde ce s-a calculat. Regula 1 a metodei, aplicată exact acolo
  unde contează. **Aprobarea refuză** cât timp există o linie nerezolvată: acolo se oprește
  incompletitudinea.
- **Metoda cumulativă, nu aproximarea lunară** (HG 697/2014 pct. 38): venit cumulat, scutiri cumulate
  citite **lună cu lună** (pct. 18 le face istorie), impozit cumulat minus cât s-a reținut deja. Plus
  cumulativele de deschidere, prin serviciu public nou în `accounting.opening` — o punere în funcțiune
  la mijloc de an ar fi acordat scutirile anului a doua oară, aritmetic consistent și greșit.
- **Fluturașul e primul document legal generat**, deci momentul în care precondiția `C38` devine vie.
  Textul lui stă pe server, în română, **nu** în fișierul de resurse: `C32` face interfața traductibilă,
  `C33` interzice ca o traducere să ajungă pe un document. **Testul pe care gardianul de limbă îl ceruse
  în docstring-ul lui** — randează cu `ru` activ, cere ieșire românească — e scris acum: `martie 2026`,
  `10000,00`, cu `ru` activat.
- **`budget_funded_employer` pe contract** (`OD-107`): pct. 1.1 împarte 29% bugetar / 24% privat, iar
  sectorul nu e categoria. Fără implicit — un boolean căzut pe `false` ar fi aplicat cota privată
  oricărui angajator bugetar, echilibrat.

**Pasul 4 livrat: darea de seamă unificată (IPC).** Modul nou `operations/tax` — `D4` merge într-un
singur sens, iar o declarație care ar fi locuit în `payroll` ar fi tras acolo și pe toate cele
viitoare, inclusiv cele fără salariu în ele.

- **Un document, nu trei rapoarte.** Art. 5 alin. (1) din Legea nr. 489/1999 face evidența nominală și
  calcularea CAS **parte componentă** a dării de seamă. Deci: `ipc_declaration` (antet) +
  `ipc_total_line` + `ipc_nominal_line`, o entitate cu două secțiuni.
- **Cele două lucruri care sunt formă, făcute acum.** *(a)* **Versionare** (art. 188): a doua dare de
  seamă primară e refuzată, corectarea e versiunea următoare și numește versiunea pe care o
  înlocuiește; ambele rămân citibile. *(b)* **Rândurile se stochează, nu se recalculează** — dovedit
  din partea observabilă: cu declarația în lucru, o contribuție stocată se schimbă la o valoare pe care
  calculul n-a produs-o niciodată, iar citirea o întoarce pe cea stocată. Dacă ar recalcula, editarea
  n-ar fi avut niciun efect — exact ce s-ar întâmpla unei declarații depuse în ziua în care se schimbă
  o cotă.
- **Antetul e înghețat.** Codul fiscal, CUATM și CAEM se copiază de pe companie la generare; un CAEM
  corectat la anul nu rescrie o dare de seamă depusă anul acesta. CUATM și CAEM sunt coloane noi pe
  `company`, **nullable** — niciun clasificator nu e în repo —, iar declarația spune **care lipsește**
  în loc să inventeze.
- **Populația e „persoane asigurate", nu „angajați"** (ADR-069), de la numele funcției încolo:
  `payroll.services.insured.insured_charges`. Azi coincid; când apar contractele civile nu se schimbă
  nimic. `tax` o citește prin serviciu public — `D4` interzice sensul invers.
- **`T1`, ambele sensuri, și arătat CĂZÂND.** Fixture-ul cu doi oameni: se șterge un rând nominal
  dintr-o declarație în lucru → reconcilierea numește **exact** persoana căzută (`missing`, 2 contra 1);
  se adaugă un rând nominal fără sarcină → o numește pe cealaltă direcție (`extra`). **Cele două laturi
  se citesc din locuri diferite** — `charged_person_ids` citește liniile de salariu, nu funcția care a
  generat declarația: o comparație cu ambele laturi din aceeași sursă e ecou, nu verificare (`P1`).
  **Și vacuitatea e închisă prin construcție:** o lună fără rulare aprobată e **refuzată** la generare,
  deci nu există declarație a cărei reconciliere să fie goală; numărătorile stau pe rezultat ca să se
  vadă cât s-a comparat.
- **A treia apariție a `OD-105`, de data asta prevăzută:** `REVOKE DELETE` scris explicit pe antet — o
  dare de seamă depusă e artefact. După două apariții consemnate, a treia s-a scris singură.

**Ce a rămas în așteptarea textului** (`OD-108`): formularul tipizat (Anexa nr. 1) nu se randează, iar
ecranul **spune asta**; coloana categoriei asigurate rămâne goală, fiindcă Anexa nr. 3 nu e obținută;
codul sursei de venit e `SAL`, singurul citabil. Nimic din registrul care alimentează formularul nu
așteaptă.

**Pasul 5 început: `F2.A0` închis și factura emisă merge cap-coadă.**

- **[ADR-073](decisions/073-forma-postarii-documentelor-comerciale.md) `Acceptat`** — forma postării
  pentru cele patru familii comerciale. **§9 enumeră fiecare implicit luat**, cu declanșatorul care îl
  redeschide, ca proprietarul să răstoarne oricare citind o singură secțiune. Ce e forțat de Planul
  general de conturi nu e alegere; ce a fost alegere e în tabel.
- **Discriminatorii se cer, nu se deduc** — tiparul lui ADR-057. `partner` **n-are** câmp de rezidență
  (măsurat), iar un implicit „rezident" ar posta creanțele față de nerezidenți pe contul de țară:
  echilibrat, `R11` trece, greșit în bilanț la fiecare raportare. Testul care le desparte: două facturi
  identice, conturi de debit diferite — **2211** contra **2212**.
- **Mărfurile și produsele sunt refuzate, cu cod.** Venitul se recunoaște la fel, dar înregistrarea are
  a doua jumătate — descărcarea de gestiune — care e F4. Un handler care ar posta doar prima ar produce
  o lună în care marja e egală cu cifra de afaceri: echilibrată, plauzibilă, falsă.
- **Un gol găsit prin construcție, și e cel mai scump din sesiune:** `install_default_bindings`
  **n-avea niciun apelant în afara testelor**. Nicio companie creată prin produs n-avea o singură
  legare de rol — deci prima postare care ar fi cerut un rol ar fi căzut cu un refuz pe care nimeni
  nu-l putea repara. Nimic n-a observat fiindcă singurul lucru care posta era nota manuală, care
  numește conturi prin id și nu cere niciodată un rol. Reparat prin `set_up_chart`, care compune
  instanțierea planului cu legările — **nu** înăuntrul primitivei, fiindcă asta ar fi făcut un șablon
  parțial imposibil de instanțiat, ceea ce e altă regulă decât cea reparată.
- **Consecința pe fixture-uri, plătită și nu ocolită:** șase fișiere de test își construiau planul din
  trei conturi. Un plan din trei conturi nu e un plan cu care o companie poate ține contabilitate, iar
  refuzul spune exact asta — deci fixture-urile primesc acum conturile catalogului, **generate din
  catalog**, nu enumerate. Două aserțiuni pe mulțimi complete au devenit aserțiuni pe prezență: testele
  acelea sunt despre ce e postabil la o dată, nu despre câte conturi are planul.
- **Două nume de fixture care se ciocneau cu realitatea:** `sales.invoice_issued` era folosit ca nume
  de probă în două suite. E o înregistrare reală acum, iar vocabularul e închis — deci proba își ia
  numele ei, `fixture.sample_event`.

**Ce a rămas din pasul 5:** factura primită, încasările și plățile (modulul `operations/treasury`),
returul (`OD-110`) și avansul — toate cu forma deja fixată de ADR-073, deci fără decizie în calea lor.

**Unde s-a oprit.** Cinci pași atinși, șase ecrane, poarta verde la fiecare. Ce nu s-a atins
deliberat: **postarea salariilor** — cere rolurile de cont din ADR-065 §7, care nu sunt încă în
catalog.

**Ce nu s-a atins deliberat:** **postarea**. Rularea produce sume; transformarea lor în linii de jurnal
trece prin evenimente contabile (`R9`) și cere rolurile de cont din ADR-065 §7. E livrabil propriu, nu
o coadă a acestuia.


**2026-08-30 — răspunsul proprietarului la cele opt întrebări ale F2; F2 pornită. Nicio linie de cod
de modul.**

**Declarația, verbatim:** *„F2 pornește. Prima sarcină e `F2.B0`, cu `DNB-05` varianta C."* E
echivalentul propoziției care a închis F0. F1.10 era livrată (`f8773ea`) și cele cinci puncte ale
criteriului de ieșire din F1 bifate; ce lipsea era declarația, nu o sarcină.

**Ce s-a livrat — consemnarea, nu construcția.** Cinci ADR-uri, `Acceptat`, toate din decizia
proprietarului:

- [ADR-060](decisions/060-vocabularul-capabilitatilor.md) — `DN-10`, varianta B: `payroll`,
  `inventory`, `multi_company`, criteriul de apartenență fiind *ce cere inițializare*. `payroll` **nu**
  intră în `COMPLIANCE_CAPABILITIES`, dar ieșirile lui declarative nu se dezactivează — `R24` se ține
  pe ieșiri. **Ierarhia se amână, și ADR-ul își numește condiția de siguranță:** `SNAPSHOT_VERSION`
  există, deci despicarea unei chei nu cere rescrierea evenimentelor. Proprietarul a spus explicit că
  fără acea propoziție ar fi ales altfel.
- [ADR-061](decisions/061-cumulativele-de-salarii.md) — `OD-04`: vocabularul **metodei cumulative**
  (Hotărârea Guvernului nr. 697/2014 pct. 38), nu al unui proiect de formular. **Semnul era jumătatea
  care conta**: toate valorile pozitive, `CHECK amount >= 0`, fiindcă `amount` n-avea constrângere și
  două convenții ar fi coexistat tăcut.
- [ADR-062](decisions/062-aprobatorul-din-productie.md) — `OD-71`, jumătatea „cine semnează": o
  persoană reală cu MFA, fără nivel nou de rol. `DN-18` rămâne **separată**, cu motivul verificabil
  (raze de acțiune diferite). Termenul se reformulează: **înainte de prima activare în producție**.
- [ADR-063](decisions/063-coliziunea-se-decide-dupa-cine-garanteaza.md) — `DNB-11`: după cine
  garantează cheia. Plus o **corecție la Spec B §10.2**: `(company_id, sfs_document_uid)` e
  idempotență (`R19`), nu deduplicare (`R20`) — tabelul amesteca doi invarianți.
- [ADR-064](decisions/064-diferenta-explicata-nu-diferenta-zero.md) — punctul 3 al criteriului de
  ieșire din F2, rescris: **diferență explicată**, nu diferență zero. „Zero contra 1C" presupunea că
  1C are dreptate, deci obliga produsul să fie la fel de greșit ca incumbentul.

**`DNB-05` — decisă, varianta C, fără ADR încă.** Linii agregate pe rol, formule per angajat, cu
`employee_id` în slot de dimensiune. ADR-ul e al lui `F2.B0` și **nu s-a scris**. Argumentul măsurat:
liniile nu cresc cu numărul de angajați, formulele da (6 salariați ≈ 10 linii și 36 de formule; 200
de salariați, tot ~10 linii și ~1 200 de formule).

**`OD-79` nouă** — VEN12 și amortizarea fiscală, amânate cu declanșator (*pilotul traversează 31
decembrie*); dar **dimensiunea fiscală a registrului de active nu se amână** și intră în ADR-ul lui
`F2.A8`.

**Curățenia făcută în același commit, ca regula documentului să nu fie doar scrisă:** rândurile din
tabelul de blocaje al `09-f2-backlog.md` sunt tăiate pentru `F2.B0`, `F2.B6`, `F2.C4`, `F2.P2`,
`F2.P3`; secțiunea de întrebări are răspunsurile în capul ei, cu textul întrebărilor păstrat;
Spec A §11.10 și Spec B §4.2, §8.1, §10.2, §11 poartă deciziile.

**`F2.B0` scris, `Propus`, nu bifat** — [ADR-065](decisions/065-schema-salarizarii.md). Cei trei
revizori pe care sarcina îi cere au dat **cinci CRITICAL**, toate confirmate pe sursă şi corectate:
29% e la pct. 1.1 nu 1.2 (fişierul de parametri o avea corect, ADR-ul nu — nimic nu le compara);
rezerva de provenienţă pe anexa nr. 1 la L. 489/1999, restaurată; parcurile IT (pct. 1.4) omise, şi
sunt a doua **formă** de calcul, nu a şaptea categorie; `COSTURI_INDIRECTE_PRODUCTIE` exista deja în
catalog, iar un al doilea rând ar fi rupt provizionarea **oricărei** companii; `employee` fără nicio
cheie naturală pentru nerezidenţi.

**Şi `DNB-05` e redeschisă** (ADR-065 §8): argumentul pe care s-a luat decizia — *„liniile nu cresc cu
angajaţii, formulele da"* — nu se susţine în motorul care există. `merge()` pliază formulele doar pe
tuplul complet de sloturi, iar `lines_to_write()` scrie **exact două** linii per formulă; raportul e
fix 1:2, aşa cum `append_only.toml` îl declară deja. „10 linii şi 1 200 de formule" nu poate exista.
Alegerea reală, cu cifrele din modelul de volum, e în §8.1; `R13` nu cere ce se presupunea (§8.2).

**`F2.B0` livrată** — [ADR-065](decisions/065-schema-salarizarii.md) `Acceptat`, cu toate cele cinci
CRITICAL corectate şi cele şase puncte ale proprietarului aplicate. `DNB-05` închisă: **detaliul per
angajat stă în registru**, o formulă per angajat şi tip de sumă — pe motivele măsurate (volum
proporţional, fişa contului navigabilă direct, direcţia reversibilă), **nu pe cel fals**, care e
consemnat în §8.1 ca să nu fie recitit peste un an ca fapt.

**[ADR-066](decisions/066-rezerva-e-decizie-deschisa.md) `Acceptat`** — o rezervă cu declanşator e o
decizie deschisă şi are rând în registru, cu marcaj auto-declarat şi gardian
(`tests/architecture/test_reservations_are_tracked.py`, al patrulea din tiparul `REVERSIBILITY` /
`decizie de domeniu` / `case(cites=…)`). **Verificat în ambele direcţii:** cu marcajul pus, 108 trec;
scos, gardianul raportează exact cazul real — *065 leans on ADR-044 and drops OD-85*. Domeniul lui e
îngustat la ADR-urile scrise după regulă, fiindcă aplicat retroactiv acuza patru ADR-uri fără legătură
cu tarifele, iar un gardian care sâcâie ajunge oprit.

**`F2.X2 (k)` făcută şi `OD-87` închisă — `F2.B1` e deblocată.**

- **[`f2-x2-k-contractul-si-irm19.md`](_input/cercetare/f2-x2-k-contractul-si-irm19.md)** — art. 49
  integral (19 clauze, consolidare terţă oprită în 2019, lit. i) semnalată ca schimbată şi actul
  modificator neidentificat) şi IRM19 integral pentru 2021. **IRM19 n-are ordin propriu:** e Anexa
  nr. 3 la OMF 126/2017, rescrisă prin OMF 33/2019 — identitate MO verificată independent pe pagina
  ediţiei. **Metodă schimbată: Wayback e accesibil acum**, ceea ce a deschis `sfs.md`; de aici `F2.X3`.
- **Două constatări schimbă schema.** Ordinul angajatorului e faptul generator al raportării, nu
  contractul → câmpuri în `F2.B1`. Orice clauză schimbată cere act adiţional → **entitate nouă**, deci
  [ADR-067](decisions/067-contractul-e-cap-de-serie.md), cu regula care le desparte: *o sarcină adaugă
  câmpuri unei entităţi pe care ADR-ul o descrie; nu introduce una pe care n-o cunoaşte.*
- **`OD-87` închisă** pe măsurătoarea din
  [`_bootstrap/12-volumul-salarizarii.md`](_bootstrap/12-volumul-salarizarii.md): linia de salariu
  **nu** intră în append-only. Argumentul decisiv a fost (c) — nume comun, cerinţe diferite: lista
  impune partiţionabilitatea, `R10` e impusă separat şi e deja unde cerinţa legală o cere.
- **Patru rânduri noi:** `OD-88` (păstrarea calculelor intermediare — rezervă cu declanşator),
  `OD-89` (**starea datată ca implicit de proiectare** — a patra apariţie independentă a tiparului,
  înrudită cu `OD-83`), `OD-90` (datele IRM19 vin din chenarele consolidării).
- **Convenţia `REZERVĂ` a primit a treia formă la a doua folosire**, nu prin proiectare: `NEATINSĂ`,
  fiindcă ADR-067 avea altfel doar două ieşiri — să pretindă o rezervă pe care nu se sprijină, sau
  să-şi scoată cea mai puternică dependenţă din `Legate:`.

**Anexa nr. 1 la Legea nr. 489/1999 obţinută de proprietar (versiunea 2020, ataşată la LP257/2020) —
[ADR-068](decisions/068-anexa-citita-categoria-e-a-raportului.md), amendament la ADR-065.** Cinci
corecţii cu sursă, plus un fapt de metodă:

- **Maparea punctelor e confirmată la sursă.** Corecţia din 2026-08-30 era bună; acum nu mai stă doar
  pe actul de aplicare. Şi pct. 1.4 **e** în anexă — rezerva adăugată la `OD-81` se retrage.
- **Constatarea decisivă: categoria de plătitor CAS e a raportului, nu a companiei.** Pct. 1.1 a doua
  liniuţă include contractele civile ale rezidenţilor de parc IT, deci un rezident e **simultan** 1.4
  şi 1.1. Nu e caz marginal ca aviaţia sau zilierii — e regimul normal. Afirmaţia din ADR-065 §3.1 nu
  se susţine nici pentru profilul-ţintă; forma extinderii era deja scrisă acolo şi **se aplică acum**.
- **`OD-81` reformulată, nu inversată:** refuzul de parc IT se mută **de pe companie pe raport**, ca să
  nu blocheze contractele civile, care sunt obişnuite. Ce iese la iveală: CAS datorat pe o plată care
  **nu e salariu**, fără casă în niciun modul → `OD-91`.
- **Pct. 1.5 e o cotă împărţită, nu una diferită** — 24% evaluat, din care 18% suportat de angajator şi
  6% de la buget. Măsurat: `EmployerCharge` **nu o poate exprima**, fiind definit cu o singură sumă;
  primeşte două — evaluată şi suportată —, egale în cazul obişnuit.
- **Art. 22 alin. (1) e invariant de calcul, nu parametru:** baza nu poate fi sub salariul minim,
  proporţional timpului lucrat, iar la timp parţial contribuţia nu sub 25% din cea la salariul minim.
  Un handler care înmulţeşte baza cu cota îl ratează.
- **Anexa nr. 3** — 43 de poziţii fără CAS, nomenclator închis → `F2.X1`.
- **Faptul de metodă, cu dovadă:** LP318/2025 schimbă la pct. 1.9 trimiterea „1.1–1.8" în „1.1–1.7",
  iar versiunea 2020 n-are acolo nicio clauză de excludere — deci **există o redacţie intermediară pe
  care n-o avem.** Demonstraţia directă că un `doc_id` e o **redacţie, nu un consolidat cu istoric**:
  „am obţinut anexa" nu înseamnă „ştim ce spune azi".
- **`OD-85` restrânsă la valori**, nu închisă: structura e confirmată, valorile pct. 1.5, 1.8 şi 1.9 nu.
  Zilierii nu sunt o contradicţie — 6% e citit din Ordinul CNAS 31-A/2026, anexa 2020 dă taxă fixă, şi
  punctul s-a schimbat între timp. Rândul din cercetare care spunea „permanent" e corectat cu data.

**Addendum de surse, aceeaşi zi: trei acte în text integral** — OMF nr. 95/2020 în **două redacţii**
(OMF 103/17.09.2024 şi OMF 59/04.05.2026, în vigoare 08.05.2026) şi Legea nr. 489/1999 consolidată la
LP318/29.12.2025, **în vigoare azi**. Nouă puncte, dintre care două ating sarcina curentă:

- **[ADR-069](decisions/069-persoana-asigurata-nu-e-angajatul.md) — populaţia declaraţiei nominale nu
  e mulţimea angajaţilor.** Prestatorul pe contract civil e persoană asigurată, cu cont personal, şi
  apare **nominal** (art. 19 alin. (7) teza a doua, verbatim în ADR). Dacă declaraţia se construieşte
  din angajaţi, **el e invizibil şi declaraţia se validează, incompletă** — nu o eroare la depunere, un
  rând care lipseşte dintr-un răspuns corect la întrebarea greşită.
- **Efectul opus, şi e cel periculos:** art. 22 spune „pentru fiecare **salariat**", deci invariantul
  bazei minime **nu** se aplică pe contracte civile. ADR-068 §5 purtase cuvântul fără să spună unde se
  opreşte. Aplicat orbeşte, umflă rândurile la salariul minim — **datorie reală mărită tăcut şi perfect
  echilibrată**, deci `R11` trece şi niciun test de sold n-o vede. Test cerut la `F2.B2`.
- **Corecţie la rândul de metodă pe care îl propusesem** (ADR-068 §8.4): *„fiecare valoare poartă data
  redacţiei"* e greşit. **O redacţie dă un punct interior, nu o margine** — din „V apare în R" se
  deduce doar `valid_from ≤ data(R) ≤ valid_to`. Un `valid_from` scris din data redacţiei e **margine
  fabricată**, şi nimic n-o compară vreodată cu ceva. → `OD-92`, cu două câmpuri: observaţia şi
  marginea.
- **A doua dovadă pentru fapt de metodă, mai tare:** cele două redacţii IALS21 sunt **acelaşi act,
  deţinute amândouă** — diferenţa **se arată**, nu se deduce.
- **`OD-85` restrânsă a doua oară, şi mai mult:** pragul 70% (art. 17 alin. (3¹)) şi porţiunea 6% de la
  buget (art. 17 alin. (3²)) recuperate din **corpul legii**, fără anexă; pct. 1.8 taxi **se închide**
  pe două acte independente. **Ce lipseşte sunt MARGINILE, nu valorile.** Pasul care a mers 2/2: când
  o anexă lipseşte, verifică dacă articolele o referenţiază cu valoare explicită.
- **`OD-89`, a cincea apariţie, de altă formă:** primele patru sunt stare de **entitate**; IALS21 2026
  e stare de **regulă în interiorul unei perioade** — o declaraţie, două regimuri, iar cheia nu e
  perioada declaraţiei, e **data faptului generator al rândului**.
- **Anexa nr. 3 iese din „neobţinut"** — 43 de poziţii, dar e ea însăşi listă cu redacţii (poz. 42, 43
  sunt adăugiri). Fără margini, o poziţie lipsă **nu dă eroare, dă CAS pe un venit care trebuia
  exclus**. → `F2.X1`.
- **Zilierii:** varianta „nu sunt asiguraţi" **eliminată** (art. 4 lit. b¹), prin L22/2018, fără cotă);
  conflictul taxă fixă vs 6% rămâne. Regulă fermă la `F2.C2`: coloanele 8–15 ale IALS21 pentru un rând
  de zilier sunt **refuz la scriere, nu zero calculat**.
- **`OD-81` capătă sprijin structural neinvocat:** coloana 5 din IALS21 e codul sursei de venit **per
  rând**, iar antetul n-are categorie de plătitor. **Declaraţia n-a fost proiectată nici pe companie,
  nici pe angajat** — ceea ce mută reformularea din *corecţie juridică* în **constrângere a ieşirii**.

**Addendum §10 — gruparea sesiunii era greşită, şi greşeala e instructivă.**
[ADR-070](decisions/070-trei-feluri-nu-o-familie.md): cele patru defecte numite „aceeaşi familie" erau
grupate după **cum au fost găsite** (toate la revizie), nu după ce sunt. Testul care le desparte:
**unde e al doilea operand?**

- **marginea `valid_from`** şi **domeniul invariantului art. 22** — operandul **nu există în sistem**;
- **declaraţia construită din angajaţi** — amândoi operanzii există, **întrebarea** a lipsit;
- **ADR ↔ date** — amândoi există, întrebarea e pusă, **comparaţia** nu se face. Doar aceasta e `OD-86`.

**Trei feluri, trei răspunsuri.** Operand lipsă **nu se prinde, se face imposibil de scris** — coloană
obligatorie, fără implicit, fiindcă *un gardian care poate fi construit poate fi dezactivat, o coloană
obligatorie nu*. Argumentul e deja în cod, la `source_confidence`: *„A default would let the row arrive
without anyone deciding."* **Golul e mai precis decât părea, măsurat:** `fiscal_parameter.act` e actul
din care vine **valoarea**; marginea poate veni din **alt act** — un singur slot de citare acolo unde
sunt necesare două.

**Plafonul, scris ca atare:** structura **nu** ia decizia. Un `domeniu = orice_bază_CAS` pune defectul
înapoi. Ce face structura e că mută decizia **din tăcere într-un diff** — un domeniu greşit se citeşte
şi apare la revizie, unul inexistent nu apare nicăieri. Reziduul rămâne al reviziei, dar e *„a ales
greşit"*, nu *„n-a ales"*. Şi: **„mecanizabil" are două înţelesuri** — detectabil automat (3 din 4) şi
imposibil de greşit (niciunul); sesiunea le confundase.

**Reconcilierea, scrisă acum ca al patrulea test al lui `F2.B1`:** *orice persoană cu sarcină CAS în
perioada `P` apare ca rând nominal în `P` — şi invers.* Reciproca contează la fel. **Singurul dintre
cele patru defecte care se prinde fără să se construiască nimic**, şi n-a fost scris fiindcă populaţia
se numea „angajaţi" şi părea evident completă — **forma a zecea** pentru taxonomia din
`CONTEXT-evidenta.md` §6: *un gardian care n-a fost pus fiindcă domeniul lui părea trivial*, distinctă
de „un verificator care nu poate cădea".

**Predicţie datată, ca să poată fi infirmată:** a cincea instanţă trebuie să se descompună la fel —
operand lipsă, întrebare nepusă, sau comparaţie nefăcută. **Dacă apare una care nu intră în niciuna,
reformularea e greşită, nu incompletă.**

**Sursa unică e repo-ul, nu proiectul** — hotărât 2026-08-30. `CONTEXT-evidenta.md` trăieşte în
proiectul Claude, e comoditate de predare între sesiuni, şi **e singurul dintre cele două care nu poate
fi păzit**: repo-ul e versionat, diffabil, are CI. Documentul devine **pointer, nu copie**. *De notat
că există şi o a treia copie: memoria sesiunii (`evidenta-machine-properties-pass-every-test`) poartă
familia „nimic nu strigă" cu numărătoarea ei — deci şi ea devine pointer.*

**Testul de enumerare, cerut înainte de orice renumerotare, a fost rulat şi nu se poate încheia —
motivul fiind el însuşi constatarea** (ADR-070 §8bis): **niciuna dintre familii nu are listă, toate au
numărător.** Şi sunt **trei**, nu două: „proprietate presupusă în amonte…" (a zecea), „legat şi
nepornit" (a şasea, nenumită de niciunul dintre noi în discuţie), „trece fiindcă nimic nu strigă" (a
noua, în memorie, nu în repo). Una dintre apariţii spune literal *„a opta apariţie a familiei, numită
de proprietar"* **fără să numească familia**.

> **Aceeaşi formă cu tot restul zilei:** un numărător afirmă *„a N-a de acest fel"*, iar **primele
> N−1 n-au fost niciodată scrise.** Nimic nu poate contrazice numărul — operand lipsă, §1 rândul întâi.

**Relaţia, dedusă din definiţii şi marcată ca inferenţă:** fusul orar, starea divergentă, calea
neatinsă şi semantica lui `git commit -- <căi>` sunt în „nimic nu strigă" şi **nu sunt proprietăţi
impozabile în schemă** — deci probabil **două familii cu incluziune, nu una cu două nume**. **Nu se
unifică numerele; se scrie relaţia.** Enumerarea retroactivă rămâne muncă de scris, nu decizie — fără
rând în registru.

**Două rafinări pe ordine, ale proprietarului:** coloanele obligatorii se scriu **în primul commit al
lui `F2.B1`**, nu ca fază separată — proiectate în vid ar fi o schemă validată de nimic —, iar
următorul lucru scris le exercită pe amândouă; şi **domeniul invariantului e cheie străină** spre
tipurile de raport existente, nu enumerare liberă, ca un domeniu inexistent să fie violare de cheie
străină, nu o valoare acceptată.

**Unde s-a oprit.** Niciun cod de modul. `F2.B1` poate începe: are entitatea, câmpurile, clasificarea,
categoria pe raport, populaţia largă a declaraţiei şi **patru** teste numite — reconcilierea în ambele
sensuri, izolarea, lista negativă de excepţii la suspendare, şi domeniul invariantului art. 22. Ce îi trebuie, în ordine: rolurile de
cont pentru salarii din Planul general de conturi (`od-22-planul-de-conturi.md`,
`od-23-nomenclatorul-planului-de-conturi.md`), asimetria CAS/CNAM din `od-22-cnas-cnam.md`, linia cu
două date (ADR-039 §9, ADR-044 §6), și ADR-ul care fixează toate acestea **înaintea** codului.

**Ce rămâne deschis, cu locul lui:**

- ~~`CHECK amount >= 0` pe `opening_balance_payroll_cumulative`~~ — **făcut în aceeași sesiune**,
  migrare proprie `opening/0002`, la instrucțiunea proprietarului: *o constrângere care așteaptă
  sarcina care atinge tabela e o constrângere care poate să nu ajungă acolo.* Măsurat înainte ca
  superuser, dincolo de `FORCE RLS`: 0 rânduri, 0 negative. Două teste noi sub rolul aplicației
  (`T1`) — negativul refuzat **de bază**, zero permis fiindcă „categorie fără scutire acordată" e
  alt fapt decât absența rândului.
- `F2.X2 (j)` — recitirea Instrucțiunii OMF 118/2017 anexa nr. 2, **înaintea** lui `F2.A0`. `V1` tace
  pe retur și corectare, re-verificat 2026-08-30 (zero potriviri în fișier). Înclinația
  proprietarului e consemnată în `F2.A0`: document de vânzare cu natură retur, nu `ReversalDocument`
  — nefinală, fiindcă schema e-Factura poate decide în locul nostru.
- **`OD-80` nouă**, din `schema-reviewer` pe migrarea de mai sus: o violare de CHECK pe soldurile
  inițiale n-are cod stabil (`C10`) — `IntegrityError` nu e în `BUILTIN_CODES`, iar fall-through-ul e
  documentat ca deliberat, deci întrebarea e unde trece linia. **Mai îngustă decât a raportat
  revizorul, verificat:** endpointul expune doar `gl`, `receivables`, `payables`; constrângerea
  adăugată azi e pe un set pe care niciun apelant HTTP nu-l atinge, deci nu extinde golul.
- Punctele 1 și 2 ale criteriului de ieșire din F2 — amânate, declanșator: alegerea companiei-pilot.
- `DN-18` — nivelul de rol de platformă, cu accesul de suport. Nu s-a strecurat în `OD-71`.
- **`OD-81` nouă** — forma substitutivă (parcuri IT): (i) intră în F2? — măsurătoarea costului e în
  ADR-065 §3.2.1 şi e asimetrică; (ii) decis oricum — o companie rezidentă nu rulează salarii tăcut.
- **`OD-82` nouă** — o rezervă declarată într-un ADR nu se propagă în cel care se sprijină pe el, şi
  pierderea n-are semnal. Cauza verificabilă: rezerva trăia doar în proză, fără rând în registru.
  Propunerea sesiunii: marcaj auto-declarat plus gardian, în tiparul lui `REVERSIBILITY`.

**Ce nu s-a atins deliberat:** nicio linie de cod. `F2.B0` e ADR înaintea codului, iar consemnarea
trebuia să fie completă întâi — o decizie a proprietarului care rămâne doar în transcript e exact ce
putrezește.

**C1(a) livrat, C1(b) oprit la ADR, disciplina de backfill impusă.**

- **`b4f471c` — C1(a):** `valid_from` pe `fiscal_parameter` e **margine** şi nu se scrie fără ce o
  stabileşte (`OD-92`). **Măsurătoarea e rezultatul: 22 din 24 de parametri încărcaţi n-aveau margine
  cu sursă** — datele lor au trecut în `observed_in`, rândurile au rămas nerezolvabile, ceea ce e
  starea onestă. Trei eşecuri tăcute pe drum, fiecare găsit de următorul: auto-deadlock pe alias
  greşit, backfill orb sub `FORCE`, despărţire pe prefix care ar fi fabricat o citare.
- **[ADR-071](decisions/071-tipurile-de-raport-ca-tabela.md) — C1(b), `Propus`, NEIMPLEMENTAT.**
  Atinge `infra/rls/exceptions.toml`, deci e ADR prin `R1`, iar `R1` face din confirmare o condiţie.
  Două valori, `employment_contract` şi `civil_contract`, ancorate în anexa nr. 1 pct. 1.1 prima
  liniuţă şi art. 19 alin. (7) teza a doua. **Fără „general"** — ar fi drumul prin care „invariant
  aplicat orb" reintră, simetricul exact al rezervei din `OD-93`. §6 declară reziduul: rămâne *„a ales
  greşit dintre două tipuri reale"*, nu *„n-a ales"*.
- **`platform/rls/backfill.py` — `OD-94` (a) şi (b) impuse.** O singură uşă pentru scrierea de date
  dintr-o migrare. Cardinalitatea e argument obligatoriu şi se verifică **înainte** de scriere. **Rolul
  nu se declară, se detectează** — corecţia proprietarului, şi e cea care contează: *o declaraţie e o
  valoare în care ai încredere*; sonda numără de două ori şi compară. **Dovedit că poate cădea** pe
  Postgres real: rolul vede 0, tabela are 3.
- **Gardianul de inventar** (`test_cited_acts_are_inventoried.py`): un act citat şi absent de pe ambele
  liste e invizibil. Prima rulare — **trei găuri reale**, între care Legea nr. 419/2023, care ancorează
  `cnas.employer_rate`. `OD-97`.

**Unde s-a oprit.** `C1(b)` aşteaptă `Acceptat` pe ADR-071 — **singura oprire legitimă**, şi e pe
decizia proprietarului, nu pe ambiguitate. `C2` şi restul `F2.B1` sunt neîncepute prin consecinţă:
`C2` e definit ca *„exercită amândouă coloanele"*, iar a doua nu există încă. Cele patru teste ale
`F2.B1` — nescrise.

**Regula (c) din `OD-94`** — scrierea şi constrângerea în aceeaşi migrare — **rămâne neimpusă**: e
disciplină de ordonare, iar un gardian peste ea ar fi euristic.

**Uşa unică, regula (c), starea nedovedită — şi C1(b) oprit la ADR.**

- **`P0` era întrebarea corectă, şi răspunsul e da: helper-ul se putea ocoli.** *(a)* şi *(b)* erau
  impuse **în** helper, dar nimic nu obliga o migrare să treacă prin el — iar **un helper opţional e
  sfat cu paşi în plus**, aceeaşi formă cu memoria scrisă ca sfat care n-a oprit nimic de trei ori.
  Acum scrierile brute de date în migrări sunt respinse, cu detecţie prin **`ast`, nu prin grep**:
  numai şirurile date efectiv lui `RunSQL` se citesc ca SQL, deci docstring-urile lungi ale acestui
  repo rămân proză.
- **Uşa a găsit imediat o a doua migrare pre-regulă** — `platform/identity/0003_roles`, pe care
  scanarea mea manuală o ratase pe un regex. Categoria are **doi membri de la început**.
- **Regula (c) nu mai e euristică**, şi motivul merită numit: **estimarea care spunea că e euristică
  expirase înainte de a fi scrisă** — era adevărată despre lumea de dinaintea helper-ului, iar
  helper-ul a intrat în **acelaşi commit** cu estimarea. După uşa unică, *„migrarea scrie date"* e
  fapt despre graful de apeluri.
- **`OD-98` — „stare nedovedită", nu „migrări care preced regula".** Numele decide ce se face: prima
  formulare creşte cu fiecare migrare şi invită retrofitul; a doua **se micşorează pe măsură ce
  adaugi aserţiuni**. Decizia: **nicio migrare aplicată nu se rescrie**; în schimb o aserţiune
  permanentă asupra **stării**, care e lucrul care contează, şi care se verifică la fiecare rulare —
  pe când o migrare rescrisă se verifică o dată, în ziua rescrierii.
- **ADR-071 amendat cât e `Propus`.** Motivarea globalităţii era **prea largă**: tabela e globală
  fiindcă **produsul deserveşte o singură jurisdicţie**, nu fiindcă distincţia ar fi transcendentă —
  iar dimensiunea care apare la a doua jurisdicţie **nu e tenantul, e jurisdicţia**. Plus: FK-ul e
  `NOT NULL` (altfel *„fără domeniu"* redevine exprimabil şi s-ar citi ca *„oriunde"*); tabela **nu**
  poartă margini, cu motivul scris şi cu falsificatorul lui; rândul din `exceptions.toml` îşi poartă
  justificarea mărginită (`OD-95`).
- **`T2`** — sonda de rol validată din partea cealaltă: pe aceeaşi tabelă, **owner-ul e orb şi rolul
  aplicaţiei nu e**. Fără jumătatea asta, o sondă care ar răspunde mereu „orb" ar trece.

**Unde s-a oprit.** **`C1(b)` NU s-a construit: ADR-071 e `Propus`.** `R1` face din confirmare o
condiţie, nu o preferinţă. `C2` şi restul `F2.B1` rămân blocate în consecinţă; `T1`, `T3` şi `T4`
depind de entităţi care nu există.

**Predicţia de cost are primul punct, şi e confirmare parţială:** `P1`+`P2` au intrat într-un commit,
o încercare — dar nu e aceeaşi formă cu `C1(a)`, care atingea date existente. Notat ca atare, nu ca
validare.

**Poarta, lista generată, ancora estimărilor — şi `C1(b)` tot oprit.**

- **`P0`: diagnosticul meu era greşit, şi remediul pe care mi-l propusesem era fals.** Raportasem că
  „`make test` a rulat după ce typecheck a căzut" — imposibil, `&&` face scurtcircuit. **Măsurat:**
  `make typecheck` singur, pe o eroare de tip, întoarce **2**; acelaşi prin `| tail`, **0**. Conducta
  era în **invocarea mea**, nu în reţetă. Iar *„rulez poarta pe bucăţi"* **n-ar fi reparat nimic**:
  `make typecheck | tail` întoarce 0 şi singur. Aş fi înlocuit un mecanism corect cu vigilenţă,
  împotriva unei cauze pe care mecanismul n-o avea. → `OD-100`.
- **Remediu impus, nu detectat:** `SHELL := bash` şi `.SHELLFLAGS := -eu -o pipefail -c` fac
  înghiţirea **nescriabilă în reţete**; ţinta **`gate`** rulează cele patru verificări fără
  înlănţuire de mână şi tipăreşte `GATE: PASS`, deci **absenţa marcajului din coadă e semnalul chiar
  când statusul s-a pierdut**. Dovedit căzând: cu o eroare de tip, iese cu 2 şi nu tipăreşte nimic.
- **`OD-99` — mulţimea se enumeră de mecanismul care impune regula, niciodată de mână.** A patra oară
  în două zile când o enumerare manuală iese incompletă. Lista „stare nedovedită" e acum **generată**,
  iar cerinţa nu mai e un nume într-o listă, ci **o aserţiune permanentă asupra stării**: allowlist-ul
  tace alarma, aserţiunea rulează la fiecare build.
- **`P3`: diferenţa e zero** — generatorul dă doi membri, exact cei acoperiţi. **Informaţie despre
  generator, nu despre inventarul meu:** îl conţineam pe al doilea doar fiindcă gardianul îl găsise.
- **`OD-92` extins, nu dublat.** Aceeaşi formă se aplică estimărilor: *„ar fi euristic" fără starea
  contra căreia s-a evaluat* e **concluzie fabricată**, exact ca o margine fără citare. **Două verdicte
  reale găsite şi ancorate** — regula (c) din `OD-94` şi comparatorul din raportul `OD-86`; restul
  potrivirilor erau opţiuni sau descrieri.

**Unde s-a oprit.** **`C1(b)` NU s-a construit: ADR-071 e `Propus`.** `T1`, `T3`, `T4` depind de
entităţi inexistente şi nu s-au forţat.

**Sesiune scurtă, sub disciplina de scop. `C1(b)` tot neconstruit: ADR-071 e `Propus`.**

- **`P1` — „zero diferenţă" nu era informaţia care părea, şi o spusesem singur fără să trag
  concluzia.** Lista manuală îl conţinea pe al doilea membru **doar fiindcă gardianul îl găsise cu o
  zi înainte**, deci comparaţia a fost între generator şi o listă **deja corectată de mecanismul cu
  care o compar**. **O comparaţie între două surse dintre care una derivă din cealaltă nu e o
  verificare** — arată exact ca un acord independent. Falsificat separat: o migrare-sondă care scrie
  date în afara uşii **apare** în lista generată (3 membri cu ea, 2 fără), ştearsă după.
- **`P2` — domeniul regulii lărgit, nu un rând nou** (ADR-070 §4.1): *orice mecanism care produce
  încredere trebuie dovedit căzând — gardian, remediu, aserţiune, generator.* Motivul, scris ca motiv:
  **orice lucru care creează senzaţia că problema e tratată opreşte măsurarea**, deci cerinţa de dovadă
  e cea mai mare **acolo unde se produce încrederea**, nu acolo unde riscul tehnic pare mai mare.
- **`P3` — verificare, nu refacere.** Nimic nu caută `GATE: PASS` cu `grep`; la o rulare reuşită e
  ultima linie. Citirea e prin **absenţă la poziţie fixă**. Limitarea — *„e ultima linie" nu e impusă
  de nimic* — **consemnată, nefixată**.

**Constatări de meta-nivel consemnate fără reparaţie, conform `P0`:** una — limitarea de poziţie a
marcajului porţii. Lista e scurtă fiindcă sesiunea a fost scurtă şi n-a atins cod nou, nu fiindcă am
reparat pe măsură.

**Notă de reţinut, fără reparaţie:** `pipefail` în reţete **nu** apără împotriva unei conducte din
**apelant** — cauza reală a porţii era în invocare, nu în Makefile. Lista de cauze nimerise mecanismul
şi ratase locul.

## Sesiuni mai vechi

**2026-08-30, F1.10 — corpusul de regresie (instrucțiune scrisă: „singura sarcină care deblochează
cod de modul … ~20 de cazuri, fiecare cu citarea lui … un caz care nu poate cita nu intră"; sesiunea
`evidenta-04`):**

- **Ce s-a livrat:** `backend/tests/corpus/` — **33 de cazuri** în șase module, fiecare intrat prin
  `case(*seturi, cites=(…))`, singura ușă; markerul `fiscal_regression`, declarat și nefolosit până
  azi, selectează exact corpusul. Cazurile stau pe **exemplele numerice ale actelor**, nu pe cifre
  inventate: SNC „Stocuri" **Anexa 1** (120 000 constante, 80 000 variabile, trei produse — cele
  două postări ale actului, 183 764,71 și 16 235,29, ies exact), SNC „Diferenţe de curs" **Exemplele
  1, 2, 5** (2 147 favorabil pe 5212/6226; 2 127 nefavorabil pe 7224/2212; 1 016 diferență de sumă
  pe 2211/6227 și 7225/5211), SNC „Capital propriu" **Exemplul 7** (190 000 / 110 000 → 351 fără
  sold, 80 000 pe 333, în ordinea ADR-050 §3.2, cu 731 separat), SNC „Venituri" **Exemplul 8**
  (vânzarea de 36 000 / 25 000 și returul de 10 800 / 7 500 în aceeași perioadă), normele de sold ale
  Planului pentru soldurile inițiale, SNC „Politici contabile" pct. 33 pentru storno. Citările —
  numai SNC, Planul general de conturi și secțiuni de ADR — sunt transcrise verbatim în
  `_input/cercetare/f1-10-corpus-citari.md`, iar `test_corpus_integrity.py` verifică mecanic că
  fiecare citare are un pasaj, că fiecare `regression_case_set` din fișierele de parametri livrate
  numește un set cu cazuri (cele două valori arătau spre nimic) și că fiecare caz se termină cu
  `agree(book)`.
- **`agree` e criteriul de ieșire, executat:** pe aceleași linii, balanța, fișa contului, Cartea
  Mare și șahul dau un răspuns — rând cu rând, sold inițial, rulaje, sold final, plus lunile Cărții
  Mari contra propriilor totaluri. Rulat la sfârșitul fiecărui caz, nu o dată pe suită.
- **Corpusul stă pe fișierele livrate, prin calea livrată:** `book.py::load_shipped_conventions`
  rulează `load_fiscal_parameters` și `activate_fiscal_parameters --approver` pe
  `platform_conventions.toml` și `snc_stocuri.toml`, sub rolul de date de referință, la fiecare caz
  — o schimbare de `valid_from`, `value`, `implementation_ref`, a încărcătorului sau a porții de
  activare ajunge în corpus (`C14`); `snc_stocuri.toml` trece astfel prin încărcătorul real pentru
  prima dată (revizorul fiscal a găsit că nu trecea nicăieri). Prima versiune însămânța rândurile cu
  SQL propriu, cu `act_id` gol și a doua publicare a OMF 118/2013 pierdută — corectat la review.
  Codurile Planului apar în fixture-uri **doar aici**, fiindcă aici sunt obiectul; planul produsului
  (`OD-23`) nu e atins.
- **O ancoră primară pentru `half_up`:** în Anexa 1, `42 352,94 × 6000/8000 = 31 764,705` — exact
  la echidistanță — și tabelul scrie **31 764,71**. `corpus/accounting.money_rounding/1` stă pe
  acest rând; `half_even` ar da 59 999,99 pe „C" în loc de 60 000,00. ADR-037 §3.3 rămâne
  convenție provizorie; are acum un exemplu al actului care o confirmă.
- **Cinci lucruri raportate, nu decise** (`tests/corpus/README.md`, întrebările 24–27 de mai
  jos): Anexa 1 aplică cota din pct. 30 **pe produs**, handlerul pe fapt — corpusul postează un fapt
  per produs; banul rămas din coloana 4 stă pe „B" în tabel și pe cota cea mai mare la noi
  (ADR-058 §2.5, decizia proprietarului — totalurile ies exact); Exemplul 2 înregistrează 783 lei
  diferență de curs pe partea achitată în avans, unde handlerul nu postează nimic; golul 2014–2017
  rămâne refuz — și are acum un caz datat 30.06.2016 pe datele livrate, nu pe date de fixture
  (revizorul fiscal: cazul din `test_overhead_allocation.py` folosea o direcție din 2020, deci o
  mutare a lui `valid_from` înapoi n-ar fi fost văzută de nimeni).
- **Ce nu e în corpus, spus:** reevaluarea la data raportării (handler neconstruit), reformarea
  bilanțului (`OD-73`), orice sumă calculată dintr-o cotă (TVA și impozitul pe venit intră ca sume
  ale documentului, `R15`).
- **F1 iese.** Criteriul din `08-f1-backlog.md` are toate cele cinci puncte bifate; `CLAUDE.md` §4
  nu mai blochează codul de modul. Ce nu prinde corpusul — divergența dintre înțelegerea noastră și
  practică — e a primului client real (F3, ADR-054 §3).
- **Review, ambii revizori, cu urmări:** `fiscal-reviewer` — un CRITICAL: cazul „înainte de act"
  era datat 2013, deci golul 2014–2017 nu avea niciun caz pe datele livrate (cel din
  `test_overhead_allocation.py` folosește o direcție de fixture din 2020); adăugat cazul din
  30.06.2016, care afirmă refuzul cu cheia și data în mesaj (ADR-058 §6). Două MAJOR, ambele
  despre însămânțarea convențiilor cu SQL propriu în locul încărcătorului — rezolvate prin calea
  livrată, în subproces (pytest-django înfășoară aliasul `refdata` într-o tranzacție invizibilă
  conexiunii aplicației), cu rândurile luate înapoi după rollback printr-un wrapper de
  `pytest_runtest_teardown`; `clean_seeded_tables()` extras din `seed()` în harness-ul de izolare,
  singura atingere a lui. `accounting-reviewer` — niciun CRITICAL; Exemplul 5 e „exprimată în euro",
  deci `FOREIGN_CURRENCY` între rezidenți, nu unități convenționale (corectat; perechea de conturi
  o alege rezidența, pct. 17); ecartul băncii testat acum pe ambele părți; și întrebarea 27.
- **A doua instrucțiune (2026-08-30), consemnările corpusului înainte de orice cod nou:**
  (1) [ADR-037](decisions/037-conventii-de-platforma.md) §3.3 — statutul lui `half_up` rămâne
  provizoriu, dar motivul nu mai e „formularul tace": **actul o demonstrează fără s-o prescrie**
  (Anexa 1 din SNC „Stocuri", 31 764,705 → 31 764,71); același motiv în antetul
  `platform_conventions.toml`. (2) Banul pe cota cea mai mare e **abatere cunoscută și motivată**, nu
  eșec tolerat — `tests/corpus/README.md` §„Abateri cunoscute", docstring-ul cazului, transcrierea;
  întrebarea 26 de mai jos e închisă. (3) **Exemplul 2, datat:** textul din 2013, fără notă de
  modificare, pe când pct. 11 și 12 sunt „în redacţia OMF 48/2019" (01.01.2020) și mută avansurile
  pe partea nemonetară — handlerul care nu postează nimic pe avans e redacția în vigoare; cazul e
  marcat ca ilustrând o redacție abrogată (README §„Explicate", docstring, transcriere cu pct. 11 și
  12 adăugate); întrebarea 25 **dizolvată**. (4) `C1`, `C2` și reevaluarea `C4` consemnate în
  `08-f1-backlog.md` ca **reportate, nu făcute** (C2 → F2.A8, C1 → F4, reevaluarea → F2.A9), în
  rândul F1.4.4, în tabel și în criteriul de ieșire. (5) Două decizii **deschise**, neaplicate:
  `OD-77` — capacitatea normală e a producției, `AllocationFact` ar purta-o per produs (Anexa 1 ca
  dovadă, 102 000 / 18 000 ca demonstrație; ADR peste ADR-058), și `OD-78` — stornoul parțial iese
  din `R14`, de închis înainte de F2.A1. (6) Cele opt întrebări din `09` §„Întrebările pentru
  proprietar" trimise grupat, cu recomandări, `OD-71` prima. **Codul de modul F2 nu începe** până la
  răspunsul pe `OD-71` și `DN-18`. `evidenta-87` nu mai apare în `ListAgents` după commitul lor
  `c65b79f`; rândul de blocaje „F1.10 vine după C5 → C2 → C1" din `09` e depășit și rămâne al cui
  reia `09`.
- Suita: **1.072 trec, 1 sărit** (+41 față de sesiunea anterioară: 34 de teste ale corpusului — 33
  de cazuri, unul parametrizat — și 7 ale gardianului); `mypy` și `ruff` curate pe tot backend-ul;
  corpusul singur, cu încărcătorul în subproces la fiecare caz, ~25 s. **Un eșec de rulare, al
  meu din F1.8:** `tests/volume/test_account_ledger.py` a picat o dată în suita întreagă — planul
  nu mai trecea prin `journal_line_account_idx` fiindcă `ANALYZE`-ul autovacuum-ului, care vede o
  tabelă goală (liniile testului se derulează înapoi), a căzut între `ANALYZE`-ul testului și
  `EXPLAIN`; corpusul, cu postările lui derulate înapoi, îl face să viziteze tabela mai des.
  Autovacuum oprit pe cele două tabele pe durata măsurătorii, repornit după. Trecut singur, cu
  corpusul și în suita întreagă. Aceeași expunere există în `test_volume_model.py` (`audit_event`),
  neatinsă.

**2026-08-30, F2 — descompunerea (instrucțiune: „start F2 după ce termină celelalte sesiuni";
sesiunea `evidenta-87`):**

- **Ce înseamnă „start F2" când criteriul de ieșire din F1 nu e închis:** trei din cinci puncte stau
  pe F1.10, corpusul, care vine după C2 și C1 în ordinea proprietarului — iar `CLAUDE.md` §4
  interzice modulele F2+ înainte de criteriu. Ce a fost F1 la început — `08-f1-backlog.md`, primul
  commit al fazei — e ce e F2 acum: **`_bootstrap/09-f2-backlog.md`**, descompunerea. Niciun cod de
  modul. Dacă proprietarul vrea altfel, e ADR pe o regulă din §4, nu excepție tăcută.
- **Celelalte sesiuni, întrebate, nu deduse:** `evidenta-77` (`evidenta-49` în `ListAgents`) (C5 → C2 → C1 → F1.10; `posting`, `slots`,
  datele fiscale), `evidenta-2d` (F1.8 + F1.G2; căile de citire ale registrului, formatarea, tot
  `frontend/src`), `avaboss` nu e în acest checkout. Numerele: ADR-058 al lui 49, 059 al lui 2d,
  **060+ și `OD-75`+ aici**. Acest document a așteptat commiturile lor înainte să atingă orice fișier
  comun.
- **O regulă de checkout partajat, primită de la cine a plătit-o (f2c210c):** `git commit -- <căi>` ia
  conținutul **din arborele de lucru**, nu din index — deci `git diff --cached` nu dovedește nimic
  pentru un fișier pe care îl editează două sesiuni, și un commit pe căi înghite hunk-urile celuilalt.
  Fișierele comune se comit doar când `git diff -- <fișier>` arată exclusiv liniile proprii; altfel,
  blob construit din `HEAD` plus hunk-urile proprii, `update-index --cacheinfo`, commit fără pathspec
  și fără altceva stagiat.
- **F2.0, măsurat pe `HEAD`, nu presupus** — ce a fost „modelat" pentru F2 (ADR-028: obligație
  negativă, se verifică). **Verde:** statutul TVA cu dată efectivă pe companie și pe partener; antetul
  documentului cu `rate_term`; `employee_id` / `asset_id` pe linie; toate cele șase seturi de solduri
  (setul de salarii poartă forma lui `OD-04` și refuză conținutul); `VatPeriod`; `exchange_rate`
  global; `SettlementFact`; 46 de roluri; `source_module` cu toate modulele F2. **Goluri, fiecare cu
  sarcină:** `DocumentState.POSTED` declarată și de neatins; `sales` / `purchases` sunt cochilii —
  fără rută, fără `emit()`; nicio entitate de decontare; `Partner` fără rezidență și `Document` fără
  denominarea contractului (discriminatorul din ADR-057 vine azi de la apelant); rezolvatorul TVA
  există și **niciun rând `vat.*`** în date; roluri de salarii și de imobilizări corporale absente;
  `payroll` nu e capabilitate nicăieri (`DN-10`); `HandlerVersion.requires` neexersat; niciun pipeline
  de tipar (`C22`); utilizatorii de sistem inexistenți; **corpusul F1.10 nu există** — niciun
  `corpus/`, markerul `fiscal_regression` declarat și nefolosit, `regression_case_set` obligatoriu cu
  două valori care arată spre nimic.
- **Metoda F2, șapte puncte, în `09`:** F2 n-are spec — fiecare flux își fixează schema prin ADR
  înaintea codului (`F2.A0`, `F2.B0`); două fluxuri paralele (Amd §C.2); **blocajele externe se despart
  de construcție de la început**, nu la sfârșit ca la F1 — cititorii și transportul sunt adaptoare
  (`OD-24`, `OD-25`, `OD-27`, `OD-75`); valorile intră `draft`/`provisional` (`OD-22`); actele
  neobținute se citesc înainte de cod (`F2.X2` — nouă acte numite); tăcerea actului e convenție pe
  rând; layout `operations/<modul>`.
- **Două decizii noi, de arhitectură, nu de scop:** `OD-75` — canalul de depunere al declarațiilor
  SFS (IPC21, TVA, VEN12): `OD-24` e strict e-Factura, iar criteriul de ieșire spune „depuse din
  Evidenta". `OD-76` — unde locuiește `integrations/` (BNM, SFS, bănci): pe hartă e la nivelul întâi,
  în `dependencies.toml` nu e nicăieri, deci `D0`; nu e `platform` (ar importa `operations`), nu e
  `operations` (e canal); ADR înainte de primul conector, care e BNM și e cazul ușor.
- **Ce s-a raportat, nu decis** — cinci întrebări de scop pentru proprietar, în `09` §„Întrebări":
  VEN12 în F2 (cere ajustările fiscale și HG 704/2019, neobținută); ce document se emite la retur;
  `DNB-05` (granularitatea salariilor); `DNB-11` (refuz sau „suspectat duplicat" la extras și
  e-Factura); `OD-04` / `OD-71` / `DN-10`, marcate „înainte de F2" din Amendament încoace.
- **O corecție primită înainte de commit:** scrisesem că C5 atinge declanșatorul `OD-72`; nu — a
  adăugat a doua *cheie*, cu o versiune, iar declanșatorul e a doua *versiune* a aceleiași chei
  (ADR-058 §4). Autorul ADR-ului a citit backlogul înainte de commit: exact verificarea pe care „două
  semnături" n-o mai dă (ADR-010), venită de la a doua sesiune.
- **Descompunerea, verificată contra `HEAD` înainte de commit** — un agent de citire a controlat
  fiecare afirmație care numește ceva din repo (~150): **21 de neconcordanțe**, toate corectate.
  Cele care contau: `resolve_parameter` întoarce doar `status = active`, deci „valorile intră
  `draft`/`provisional`" era o descriere greșită a mecanismului — rândurile se încarcă `draft`,
  testele le activează în baza de test, producția așteaptă aprobarea; `line_amounts` primește cota
  ca argument și nu citește `vat.*` (refuzul e al lui `vat_rate()`); `OD-74` exista deja și acoperă
  întrebarea pipeline-ului PDF din `F2.P1`; registrul numerotează `OD-75`, nu `OD-075`; F1.G1 e
  nebifată în `PROGRESS.md` (golurile `DataGrid` sunt numite), F1.G2 e livrată. Un backlog scris din
  lectură are cam o eroare la șapte afirmații verificabile; verificarea costă o oră și le scoate
  înainte să devină sarcini.
- **Criteriul de ieșire din F2 rămâne al proprietarului, neschimbat:** toate trei punctele sunt
  externe — pilot, instituții, un trimestru. Ce s-a adăugat e ce F1 a primit abia prin ADR-054:
  lista a ce se poate verifica intern înainte de pilot, ca eroarea de motor să nu se afle de la client.
- Suita: **neschimbată** — nimic de cod în această sesiune.

**A doua instrucțiune a zilei (2026-08-30, sesiunea `evidenta-87`, cinci puncte și o interdicție):**

- **`F2.X2` — cele nouă acte, în paralel, prioritate mare.** Șase agenți de cercetare, un fișier fiecare
  în `_input/cercetare/`: `f2-x2-formularele-sfs.md`, `f2-x2-numerar-si-ordinul-de-plata.md`,
  `f2-x2-concedii-indemnizatii-fluturas.md`, `f2-x2-snc-situatii-financiare-si-diferente-de-curs.md`,
  `f2-x2-prorata-tva-si-amortizarea-fiscala.md`, plus **`f2-x1-identitatile-actelor.md`** — numerele
  MO ale actelor deja citate, golul care ținea orice parametru la `provisional`. Fiecare cu statutul
  sursei, proveniența pe cifră, filtrul România aplicat, tăcerea datată, „ce nu s-a putut verifica" cu
  ce s-a încercat. Rezultatul pe act e în `09-f2-backlog.md`, `F2.X2`, tabel. **Ce a mers și ce nu, ca
  metodă:** cuprinsurile edițiilor `monitorul.gov.md` (`/ro/monitor/<id>`) sunt publice — de acolo vin
  **17 din 21 de identități MO**; `legis.md` întoarce 403 **și nu e arhivat de Wayback** (cochilii JS,
  zero capturi), deci textul consolidat curent al niciunei legi nu s-a citit — codurile s-au citit în
  consolidări până în 2019, marcate; textele primare integrale sunt cele publicate de autor: PDF-ul MF al
  SNC, regulamentul BNM, textele `.doc` ale MF, proiectele `gov.md`.
- **Cinci lucruri de greutate din cercetare, raportate, nu decise:** (1) **`OD-73` — actul NU tace:**
  SNC „Prezentarea situațiilor financiare" pct. 18 pune reformarea bilanțului ca etapa 5, *după*
  aprobare, semnare și prezentare, iar pct. 228 o spune verbatim; tace doar asupra datei contabile —
  premisa rândului din registru e corectată, decizia rămâne a proprietarului. (2) **Formularele
  situațiilor financiare sunt transcrise integral** (bilanț 116 rânduri, prescurtat 23, profit și
  pierdere 44/14, capital propriu 19, fluxuri 26, cu formulele de control) — `F2.C1` nu mai așteaptă
  actul. (3) **Anexa 1 „Diferențe de curs" e integrală**, cu un caz `R17`/`R18`: avansurile au trecut
  din monetare în nemonetare la 01.01.2020 (OMF 48/2019). (4) **Codul fiscal are clauza de intrare în
  vigoare citată** — Titlurile I–II 01.01.1998, Titlul III 01.07.1998 — deci TVA are ancoră. (5) O
  **corecție** în cercetarea CNAS: „HG 966/2024" era poziția în MO; actul e HG 845/2024.
- **Ce rămâne neobținut, numit:** normele operațiunilor de casă (HG 764/1992 — text și statut incert),
  art. 11 alin. (7) din Legea 287/2017, structura adoptată a declarației TVA (boxele — reconstituire
  contradictorie, nu se folosește), Catalogul duratelor HG 941/2020, modificările post-2019 ale
  Codului muncii și ale legilor indemnizațiilor, textul adoptat al Legii 34/2024 (plafoanele de
  numerar — valorile sunt din comunicatul MF). **Tăceri datate:** nicio formă prescrisă pentru
  fluturaș (art. 142 alin. (3) cere trei elemente în scris); niciun ordin SFS nu numește canalul de
  depunere (toate trimit la art. 187 alin. (2¹)) — `OD-75` rămâne externă; ordinul de plată e set de
  date, nu formular (BNM HCE 108/2023, 13 elemente).
- **`F2.X1` — parametrii ca `draft`, neactivați.** Trei fișiere noi în `fiscal/parameters/data/`:
  `cnas_cnam.toml`, `impozit_pe_venit.toml`, `tva.toml` — **22 de rânduri, toate `draft`,
  `provisional` cu motivul pe rând**, măsurat pe baza vie; rânduri `P-4` în jurnal; a treia rulare a
  fiecărui fișier: 0 noi, 0 actualizați. TVA a intrat la a doua încărcare, când identitățile au adus
  ancora Codului. **Ancorarea e spusă în fișier, nu ascunsă:** cotele CAS/CNAM stau în anexele la
  L. 489/1999 și L. 1593/2002, ale căror pagini de ediție nu s-au găsit; rândurile sunt ancorate în legea
  anuală care le aplică, cu inferența marcată, și se re-ancorează la reîncărcare (un rând `draft` se
  actualizează, unul `active` nu). Ferestrele `valid_from` ale cotelor TVA încep la 2024, fereastra
  cercetată — nu la 1998. Un rând cu valoarea **0** pentru scutirea de soț/soție (art. 34 alin. (1), care
  nu se acordă) și unul pentru contribuția individuală CAS (anulată din 2021) există tocmai ca să nu fie
  inventate. Vocabularul cheilor e propus și se confirmă în `F2.B0`. **Măsurat înainte de a scrie:**
  `resolve_parameter` întoarce doar `status = active`, deci `draft` chiar înseamnă „nu se folosește".
- **Criteriul de ieșire, reformulat pe fiecare punct — raport, nu decizie** (`09`, §„Întrebarea
  reformulată"): niciunul nu blochează construcția; 1 și 3 au echivalent intern în CI (trei luni închise
  pe o companie sintetică; raportul de diferențe cu o diferență plantată), 2 se despică în „generat și
  validat contra formularului" (intern) și „depus și acceptat" (extern). Două observații: trimestrul nu
  se comprimă — dacă punctul 1 rămâne, F2 nu se închide mai devreme de trei luni după pilot; iar
  „diferență zero contra 1C" presupune că 1C are dreptate — raportul cere o stare „diferență explicată".
- **Întrebările pentru proprietar, într-un singur loc** (`09`, §„Întrebările"): opt, `OD-71` primul —
  utilizatorii de sistem se construiesc după Spec A §3.4 fără decizie; aprobatorul e o persoană cu rol
  de nivel platformă, care nu există, de decis împreună cu `DN-18`. Apoi `OD-04` (vocabularul
  cumulativelor = coloanele per angajat ale IALS21; metoda cumulativă e HG 697/2014 pct. 38), `DN-10`
  (varianta B), `DNB-05` ((C): linii agregate, formule per angajat — ADR-048/053), `DNB-11` (refuz pentru
  cheile pe care le garantăm noi, „suspectat duplicat" pentru cele din afară), VEN12 (în F2, ultimul),
  returul (V1 tace — `F2.X2 (j)`), criteriul.
- **Coordonare:** evidenta-04/2d a pornit F1.10 și și-a fixat convenția corpusului — preluată în
  `F2.C5`; fișierele mele de date n-au rânduri `[[logic]]`, deci gardianul lor de integritate nu le
  atinge. Rularea corpusului lor pe o bază de test privată a picat pe `accounting.money_rounding` fără
  implementare activă — **identic cu fișierele mele scoase din arbore**, deci nu e de la ele; raportat
  lor, și confirmat: era starea lor în lucru — însămânțarea prin calea livrată, apelată în proces pe
  aliasul `refdata`, rămânea în tranzacția per-alias a pytest-django, invizibilă conexiunii aplicației;
  reparat de ei prin subproces contra bazei de test. Pe drum, un experiment prost făcut: am mutat cele trei fișiere din arbore ca să izolez
  cauza, iar restaurarea din `trap` a picat pe o cale relativă după `cd` — prinsă și reparată în
  același minut, dar regula e: nu se scot fișiere din arborele partajat pentru un experiment.
- **Punctul 6, respectat:** niciun cod de modul F2; nicio sarcină n-a cerut vreunul.


## Sesiuni mai vechi

**2026-08-30, F1.8 + F1.G2 — rapoartele contabile și grila de introducere (instrucțiune scrisă:
„două sarcini reale din F1, izolate de motor, una frontend curat"; sesiunea `evidenta-04`, listată
de `ListAgents` ca `evidenta-2d` după o repornire de socket):**

- **F1.8, ce s-a livrat:** fișa contului — **un rând per document** (ADR-053 §3.1), corespondența
  citită din `journal_formula` (ADR-048), soldul curent calculat pe server peste toată fereastra chiar
  când rândurile sunt tăiate (`C19`); Cartea Mare — pe **lunile companiei** (prin `period`, nu luni
  calendaristice tăiate din date: exercițiul aprilie–martie își închide lunile unde le închide),
  rulaje în corespondență cu conturile, iar **ce nu explică nicio formulă se numește** (`unassigned`),
  nu se împarte; rulajele pe corespondențe (șahul) cu `lines_total − total` ca rest declarat;
  drill-down-ul înregistrării — ștampile ADR-048, formule, linii, sursa (`R13`, ultimul salt se
  oprește la identificatorul documentului, `D2`); export **CSV** pe server, din același dataclass ca
  ecranul (`C20`). O notă manuală rămâne rând fără corespondență, `has_formulas = false` — nu se
  inventează perechi din linii.
- **`C38` are primul pipeline, deci primul gardian real.** `platform/documents/formatting.py`:
  virgulă zecimală, `zz.ll.aaaa`, fără `django.utils.formats` — nu consultă limba activă. Exportul
  deschide `translation.override("ro")` la intrare; testul din `test_document_language.py` randează
  același raport sub `ro`, `ru` și `en` și cere aceiași octeți. `ROUND_HALF_UP` la două zecimale e
  strat de afișare (ADR-037 §4 rămâne: suma stocată nu se atinge), ales ca CSV-ul și `Intl` din client
  să arate aceeași cifră.
- **Măsurat, și a schimbat codul:** `?format=csv` răspunde **404** — DRF rezervă `format` pentru
  negocierea proprie de renderer. Parametrul e `?export=csv`, iar `xlsx` refuză cu
  `ledger.unknown_format` în loc să mintă în numele fișierului. Excel/PDF → **`OD-74`**.
- **ADR-053 §3.3, prima măsurătoare** (`tests/volume/test_account_ledger.py`, sub rolul aplicației,
  2.000 de documente generate prin `generate_series` cu politicile evaluate pe rând): o lună a
  contului celui mai încărcat, 170 de documente, **22,7 ms** prin serviciu, planul prin
  `journal_line_account_idx`. Pragul de 1 s se asertează doar la scara opt-in
  (`EVIDENTA_VOLUME_ROWS`).
- **F1.G2, `EntryGrid`** (`frontend/src/shared/EntryGrid/`): contractul ADR-052 §3 rând cu rând, cu
  un test Vitest per tastă peste componentă; punct și virgulă la aceeași formă canonică; indicatorul
  de echilibru în aritmetică întreagă la scara serverului; nomenclatorul pe `F4` cu potrivire pe cod.
  **Nota manuală și rândurile GL ale soldurilor inițiale** stau pe ea — două suprafețe, una nu e linii
  de document (criteriul 3), niciun `onKeyDown` în ecrane (`C40`). Cele trei implicite din ADR-052
  §3.1 (`Tab`, `F4`/`F2`, `Ctrl+Delete`) sunt implementate cum sunt propuse și **rămân de confirmat**.
- **Defect prins de testul de cinci rânduri, nu de cele unitare:** confirmarea celulei și deschiderea
  rândului următor porneau amândouă din rândurile randării curente, iar al doilea `onChange` îl
  ștergea pe primul — creditul dispărea exact când `Enter` deschidea linia. Testul unitar pe tastă
  nu-l vedea fiindcă niciun test nu confirma o valoare **și** deschidea un rând în același eveniment.
- **`DataGrid` n-a crescut**: primește rânduri de document și drill-down pe rând (ADR-053 §4);
  virtualizarea, coloanele înghețate, configurația per utilizator rămân goluri numite în
  `07-f1-grile.md`, fiindcă niciun ecran de azi nu le cere.
- **Ce rămâne din F1.8, numit:** jurnalele de vânzări/cumpărări — pe document prin definiție, deci
  fără conținut până la primul document postat (F1.4.4 / Etapa 8); **reconcilierea la leu contra 1C**,
  criteriul de ieșire, așteaptă extrasul real (F3, ADR-054).
- **Revizuirea contabilă a găsit trei avertismente cu o singură rădăcină, și proprietarul a pus
  întrebarea de model înaintea oricărei reparații:** are divergența de dată pe liniile unei
  înregistrări un motiv contabil? **Nu** — ADR-039 §9 definește `accounting_date` ca data postării,
  una per înregistrare; linia o poartă fiindcă e tabela partiționată, iar data economică are coloana
  ei, `document_date`. Permisiunea era un rest al proiectării linie-cu-linie. **[ADR-059](decisions/059-linia-poarta-data-inregistrarii.md)**:
  invariantul 3 devine egalitate (`posting.line_date_differs`), nota manuală refuză la payload o
  linie cu altă zi, triggerul `journal_line_carries_the_entry_date` (`0062`) e a doua barieră pentru
  importul și migrările care nu trec prin motor. Trei rapoarte spun acum aceeași zi prin construcție;
  fișa poartă și legăturile `R14`, ca registrul.
- **Scara sumei, impusă structural:** `journal_line_amount_scale` și `journal_formula_amount_scale`
  — `debit = round(debit, 2)` — CHECK în bază, la scara aprobată în ADR-037 §3.2. A zecea apariție a
  familiei „proprietate presupusă în amonte, neimpusă în schemă, consumator în aval care se sparge
  tăcut": exporturile rotunjesc rândurile și totalurile independent, deci o sumă cu patru zecimale ar
  fi făcut coloana să nu mai dea totalul, fără niciun semnal. Nota manuală refuză a treia zecimală
  cu cod (`SCALE = 2`, era 4) înaintea bazei. Când `accounting.amount_scale` se schimbă, se schimbă
  și constrângerea — în migrarea care se uită la rânduri. Stornoul și închiderea au acum test prin
  toate cele patru rapoarte.
- **C5, cele trei puncte ale proprietarului, executate în ordine.** (1) Cei patru pași confirmați în
  cod — variabilele integral (pct. 30(1)), constantele × min(1, efectiv/normal) cu o rotunjire
  `half_up` la 2, restul la 714, ce intră în cost pe produse proporțional cu baza, fiecare cotă
  rotunjită o dată — și `production.overhead_absorption` **activată** pe baza de dezvoltare cu
  `--approver 22222222-…`, rând în `privileged_access_log`. (2) **Restul pe cota cea mai mare**, la
  egalitate pe **codul produsului** (`ProductShare.code`, purtat pe fapt; identificatorul când codul
  lipsește) — nu pe ultimul produs, care e o proprietate a ordinii, nu a datelor; ADR-058 §2.5
  rescris cu motivul determinismului față de date; testul repartizează aceeași listă în două ordini
  și cere aceleași cote pe aceleași produse. (3) **Golul 2014–2017 rămâne**: regula din 2014, direcția
  din 28.10.2017, o repartizare între ele e refuzată de registru — consemnat în ADR-058 §6 și păzit
  de un test, ca nimeni să nu-l „repare".
- **Punctul 4 — gardienii, întrebați „ce afișezi dacă lucrul păzit se produce?"** (raport, nimic
  reparat):

  | Gardian | Cazul păzit | Ce afișează când se produce |
  |---|---|---|
  | `make drift-check` (`check_schema_drift`) | baza vie a deviat de la contracte: RLS oprit, `FORCE` lipsă, politică fără `WITH CHECK`, colație greșită, FK spre append-only, coloană de partiționare nulabilă, privilegiu de scriere pe tabelă `global_read_only` | **răspunde**: o linie per constatare, `[regulă] tabelă: detaliu`, plus `[PRIV] tabelă: evidenta_app holds …`, apoi `exit 1`. Verificat: a prins `fiscal_parameter_confidence_event` la prima rulare |
  | IZ-78 (`schema_audit._audit_writer`, `_audit_writer_sweep`) | o tabelă globală scrisă de altcineva decât rolul declarat, sau rolul de încărcare cu privilegii în afara tabelelor lui | **răspunde**: cinci mesaje distincte, fiecare cu rol, tabelă și cauza (`holds …`, `second door`, `no INSERT privilege`, `may DELETE`, `not its declared writer`); probele din `test_model_guard` le fac să cadă |
  | „gardianul de registre" din `tests/conftest.py` (`_registries_survive_the_test`) | un test lasă în urmă tipuri, handlere sau roluri în registrul în memorie, iar următorul test le moștenește | **nu răspunde**: e o *restaurare*, nu o verificare — golește și repune dicționarele după fiecare test și **nu afișează nimic** când un test a mutat registrul. Cazul păzit se produce tăcut și e reparat tăcut; un test care depinde de registrul poluat trece sau cade fără ca nimeni să afle de ce. **A unsprezecea apariție**, în forma cea mai curată: gardianul ascunde exact simptomul pe care ar trebui să-l strige. Reparația propusă (neaplicată): după test, dacă starea diferă de instantaneu, `pytest.fail` cu numele testului și cheile mutate |
  | `_assert_application_role` (`tests/conftest.py`) | suita rulează ca superuser, `BYPASSRLS` sau proprietar de tabele, deci trece prin politici fără să le exercite | **răspunde**: `pytest.exit` cu lista problemelor (rolul, `superuser`, `bypassrls`, tabelele deținute) — întreaga suită se oprește, nu un test |
  | CI `quality`: `ruff check`, `ruff format --check`, `mypy .`, `pytest tests/deps_guard tests/architecture`, `makemigrations --check` | stil, tipuri, D1–D6, app-uri goale, model schimbat fără migrare | **răspund**: fiecare unealtă tipărește fișier:linie și cauza; `makemigrations --check` tipărește migrarea pe care ar genera-o |
  | CI `tests`: bootstrap pe bază curată, `migrate` ca owner, `pytest -q`, „Confirm the suites ran as the application role" | un fișier de bootstrap care nu se aplică de la zero, o migrare care nu rulează, o suită care a rulat sub alt rol | **răspund** — cu o observație: pasul de confirmare a rolului tipărește rolul și cade pe `assert`; dar harness-ul refuză deja mai devreme, deci pasul afișează *care* rol a fost, nu *că* a fost greșit — e jurnal, nu gardian, și e scris ca atare în `ci.yml` |
  | CI `frontend`: `tsc -b`, `eslint .` (`C16`, `C21`), `vite build` | import direct de `react-table`, literal de înălțime în grile, tip rupt, bundle care nu se construiește | **răspund**: ESLint tipărește regula cu mesajul ei (`C16: …`, `C21: …`), `tsc` fișier:linie |
  | `make check-committed` | fișierul uitat din commit, invizibil pentru orice verificare care citește discul | **răspunde**, cu `--self-test` care scoate un fișier și cere ca verificarea **să cadă** — dar **nu rulează în CI**: CI verifică arborele împins, deci cazul e acoperit acolo implicit, fără să fie numit |

  Concluzie: dintre gardienii întrebați, unul singur nu poate răspunde — restaurarea registrelor din
  `conftest`. Nereparat; așteaptă aprobarea.
- Suita backend: **1.031 trec, 1 sărit**; Vitest: **27**; `mypy .` curat; ESLint, `tsc`, build
  curate. Reviewer-ii `accounting-reviewer` și `tenancy-guard` rulați înainte de commit; al doilea
  fără constatări, primul cu cele de mai sus.

## Sesiuni mai vechi

**2026-08-29 (a doua), `OD-67`/`OD-65` livrate și șase decizii consemnate — instrucțiune scrisă cu
nouă puncte (sesiunea `evidenta-77`):**

- **Al patrulea rol de bază de date, `evidenta_refdata`** ([ADR-049](decisions/049-rolul-de-date-de-referinta.md)):
  `LOGIN`, `NOINHERIT`, fără `BYPASSRLS`, nu deține nimic, fără privilegii implicite. Scrie exclusiv
  tabelele globale de referință declarate cu `writer_role` în `infra/rls/exceptions.toml` — cele opt
  existente (`0060`) plus trei noi — fără `DELETE` nicăieri. Politica proprietarului din `0044`
  retrasă: **o singură ușă**. Bootstrap `0004`, Makefile, CI și harness-ul de test îl cunosc;
  `.env` are `REFDATA_DB_USER/PASSWORD` (`.env.example` actualizat).
- **`privileged_access_log` construită** (`0058`), după ce a stat declarată în contract din F0 fără
  să existe în nicio bază. Singura ușă spre conexiune e `privileged_run`, care scrie rândul **ultimul,
  în aceeași tranzacție**: o rulare eșuată nu lasă nici scrieri, nici rând. Aplicația nu o citește
  deloc (forma nouă `platform_log`): conține tenanți străini. `P-10` nouă în Spec A §6.2 pentru
  planul de conturi. **Măsurat, nu presupus:** sub rol, `SELECT count(*) FROM company` e
  `InsufficientPrivilege`, nu `0` — nu există politică de trecut, fiindcă nu există privilegiu.
- **`IZ-78` în gardianul de model**, în ambele sensuri: aplicația fără privilegii de scriere pe
  tabelele globale (ce a găsit `0047` de mână), nicio politică de scriere pentru alt rol decât cel
  declarat, scriitorul fără `DELETE`, iar scriitorul fără nimic pe tabele nedeclarate. **Prima rulare
  a găsit** politica `permission_platform_write` a proprietarului din `0019` — corectă, catalogul e
  cod (ADR-020) — declarată acum, nu tolerată; și `tenant_id` pe jurnal citit ca derivă (`IZ-76`):
  redenumit `subject_tenant_id`, cu motivul în model. Cinci autoteste, ca regula să fie văzută căzând.
- **`OD-65` — registru de acte și publicări în `platform/legislation`**, M:N: identitatea publicării e
  a citării (an, număr, articol; ziua opțională), fiindcă *o poziție acoperă două acte*. La `make
  seed-coa` pe baza de dezvoltare, OMF 119/2013 stă cu ambele publicări, iar rândul de jurnal spune
  `P-10 | os:dts | 476 neschimbate`.
- **`manage.py load_fiscal_parameters`** — calea `P-4` reală: TOML cu actul lângă valoare; `draft`
  obligatoriu (o aprobare nu vine dintr-un fișier, D.1); un rând `active` nu se editează; act fără
  `effective_from` refuzat. **`platform_conventions.toml` livrează actul OMF 118/2017 și zero
  valori**: precizia e ipoteza de lucru a proprietarului (ADR-037 §0), iar nici valorile, nici data
  intrării în vigoare n-au fost citite din act — `V1`, o oră. O dată inventată e același defect ca o
  cotă inventată, în altă coloană.
- **Șase decizii închise prin instrucțiune, fiecare cu ADR:** `OD-55` — chei de context enumerate
  în cod ([ADR-051](decisions/051-chei-de-context-enumerate.md)); `C1`–`C5` clasificate, `C3`
  ștearsă cu motiv, [ADR-036](decisions/036-forma-postarii.md) **`Acceptat`**, `R28` în `CLAUDE.md`;
  `OD-36` — contractul de tastatură ([ADR-052](decisions/052-contractul-de-tastatura.md), `C40`);
  `OD-29` — fișa contului agregă pe document ([ADR-053](decisions/053-tinta-de-performanta.md),
  pragurile propuse, nu decise); `OD-22` **despicată** — lanțul de închidere e roluri din Planul
  general de conturi, nu parametri fiscali ([ADR-050](decisions/050-lantul-de-inchidere-ca-roluri.md));
  cele patru roluri sunt în catalog (41), ordinea lanțului e în ADR, **731 nu se închide cu clasa 7**.
- **`DNB-08`, corectată a treia oară** — nu în trei locuri, în **opt**: `PROGRESS.md` ×3, Spec B ×2,
  ADR-010, registrul, backlogul F0. Ce rămâne e `V1`, document public; `V2` condiționează testul de
  acceptanță, nu codul.
- **`OD-28`, reformulată după măsurare:** blochează **cititorul** formatului real și **validarea la
  leu**, nu construcția — zona de aterizare (`opening`, `source = onec_import`), maparea și
  punctarea se construiesc pe un extras sintetic în formatul intern. F1.9 iese de pe drumul critic;
  rămâne bifa finală.
- **Harta, recalculată:** din nouă blocaje de sarcini F1, **rămân trei** — F1.6 (`OD-22` strict
  cote/praguri, plus `V1`), F1.9/F1.G0 (`OD-28`, doar cititorul), F1.10 (cazuri reale). Decizii
  deschise care blochează F1: `OD-22` restrânsă, `OD-28` restrânsă, `OD-58`, `OD-60`, `OD-61`,
  `OD-62`, `DNB-08`/`V1`, `DNB-10`. **Externe reale: două** — extrasul 1C și contabilul practicant,
  exact așteptarea proprietarului.
- **Ce s-a raportat, nu decis:** `P-9` nu scrie încă în jurnal (tabela nu exista când s-a scris
  funcția); utilizatorii de sistem din Spec A §3.4 nu există; `Tab`, tasta `F` și ștergerea rândului
  din contractul de tastatură sunt implicite propuse; pragurile din ADR-053 la fel.
- Suita: **969 trec, 1 sărit** (de la 745 la începutul zilei; 46 noi aici — rol, încărcătoare, gardian). `make lint`, `make typecheck`, `make drift-check` pe baza vie: curate.

**A doua instrucțiune a zilei, după raport** ([ADR-054](decisions/054-importul-e-distributie-corpusul-e-intern.md)):

- **Importatorul 1C e instrument de distribuție, nu fundație** — mutat la F3, lângă Migration
  Center, unde spec-ul pusese de la început maparea (F2) și reconcilierea (F3). `OD-28` și `OD-30`
  au plecat cu el; cererea de extras rămâne trimisă, dar nu mai condiționează F1.
- **Criteriul de ieșire, rescris:** cele trei puncte care numeau 1C validau registrul, nu
  cititorul. Balanța și reconcilierea se validează pe corpusul intern; **două puncte bifate din
  teste existente** — storno cu lineage (`test_vertical_slice`), refuzul în perioadă închisă
  (`test_posting_invariants`, `test_periods`) — citite, nu presupuse.
- **F1.10 reclasificată:** „cazurile cu rezultat verificat nu se pot fabrica" era o definiție —
  *verificat* însemna *de altcineva*, iar ADR-010 spusese deja că a doua semnătură nu e verificare
  independentă. E sarcină: ~20 de cazuri, fiecare cu citarea lui; unul care nu poate cita nu intră.
- **Întrebarea de treizeci de secunde, răspunsă cu actul din repo:** închiderea lunii **nu**
  postează lanțul 351, și e corect — Planul general de conturi decontează clasele 6 și 7 la 351
  „la finele perioadei de gestiune", iar Legea 287/2017 art. 24 alin. (1) face perioada de gestiune
  anul. Lunar, 6 și 7 acumulează; rezultatul intermediar se citește din rulaje. Ce e inferență e
  marcat ca atare în ADR-054 §4.
- **F1.G0 sintetic, ales explicit** — nu prin omisiune, cum cerea `07-f1-grile.md`.
- **Harta, a doua recalculare:** F1 nu mai are **niciun** blocaj extern. Rămâne `V1`. Atât.
- **Ordinea următoarei sesiuni, decisă de proprietar: F1.5.4 (închiderea) întâi, apoi F1.4.4.**
  Motivele stau în `08-f1-backlog.md`, sub „Ce nu poate începe". Un lucru de verificat la `V1`, adăugat
  de proprietar: dacă formularul prescrie zecimale și pentru **cantitate** — a treia axă, omisă din
  instrucțiune; cheia `accounting.quantity_scale` are rezolvator și loc în `platform_conventions.toml`.
- **`OD-70`, deschisă la predare, condiționată:** dacă `V1` tace pe cantitate, decizia care rămâne nu e
  „câte zecimale", ci **cine** le alege — platformă, tenant sau unitate de măsură. Înclinația
  proprietarului e unitatea de măsură (bucățile se numără altfel decât kilogramele), consemnată ca
  înclinație. Implicația structurală — `fiscal_parameter` n-are `scope` per unitate — e scrisă în
  rând, ca să nu fie descoperită la implementare. *Tăcerea înregistrată e un fapt; tăcerea
  neînregistrată devine, peste șase luni, o presupunere pe care nimeni nu o mai poate data.*
- **`V1`, făcută în aceeași zi** ([cercetare](_input/cercetare/v1-factura-fiscala-omf-118-2017.md)):
  `sfs.md` și `legis.md` întorc 403 (Cloudflare) la orice preluare automată, `monitorul.fisc.md` e cu
  plată — PDF-ul SFS al ordinului a venit **prin arhiva Wayback** (captura din 17.05.2024; text din
  19.02.2021), cu pagina SFS arhivată ca a doua copie. **Rezultat: formularul și Instrucțiunea tac
  asupra zecimalelor** — preț, sume, cantitate; `zecimal`/`rotunj`/`bani`: zero apariții; „lei" e
  moneda, nu precizia. Anexele sunt **nr. 1 și nr. 2**, nu „1 și 1a". Ce prescrie e structura: produs
  pe linie, sumă pe linie, totalul = totalul coloanelor — **linia e autoritativă prin construcția
  formularului**, ceea ce confirmă regula din 28.08. Data intrării în vigoare (28.10.2017) și a
  publicării (22.09.2017) intră în registrul de acte.
- **Consecințe, făcute:** cele două convenții ale proprietarului (2 la sume, 4 la preț) sunt
  încărcate în baza de dezvoltare ca `draft`, `provisional`, cu motivul „formularul tace"; activarea e
  actul lui — `manage.py activate_fiscal_parameters platform_conventions.toml --approver <id>`,
  comandă nouă, care pune identitatea aprobatorului pe rând și în jurnalul `P-4`. **Cantitatea nu
  primește valoare**: `OD-70` e acum necondiționată, iar `line_amounts` refuză orice linie până se
  decide — mecanismul e complet și așteaptă o decizie, nu o valoare strecurată.
- **Aprobarea și `OD-70`, în aceeași zi, la instrucțiunea proprietarului.** Cele două convenții sunt
  **active** pe baza de dezvoltare, aprobate cu identitatea `dev@example.md` (singurul cont care nu e
  „proba"; presupunere spusă), rând `P-4` cu `actor_user_id`. Proprietarul a cerut să fie spus
  explicit: **convenții de platformă, nu prescripții legale** — `provisional` rămâne. `OD-70` e
  închisă prin [ADR-055](decisions/055-precizia-cantitatii-e-a-unitatii.md): precizia cantității e a
  **unității de măsură** — coloana exista din F0.7 cu `default=0`; acum e obligatorie, fără implicit,
  și **înghețată** la prima cantitate purtată (trigger `0061`, peste document, jurnal, formulă,
  solduri). `accounting.quantity_scale` a stat câteva ore în rezolvatorul fiscal și a ieșit: nu vine
  dintr-un act, n-are `valid_from`. Întrebarea „vreun motiv să fie totuși parametru?" — verificată pe
  cod, nu (ADR-055 §2).
- **Măsurat, nu presupus, ce mai lipsește pentru F1.6:** `fiscal_logic_version` e **goală** pe baza
  de dezvoltare — direcția la echidistanță n-are rând, deci `line_amounts` refuză orice linie și după
  aprobare. Nu se alege din cod: `load_fiscal_parameters` încarcă acum și `[[logic]]`, șablonul e
  comentat în `platform_conventions.toml`, alegerea (`half_up` / `half_even`) e a proprietarului.
- **`half_up`, decis de proprietar și activat** în aceeași zi (`accounting.money_rounding` v1, de la
  28.10.2017, aprobat cu identitatea lui). Motivele stau în ADR-037 §3.3; statutul rămâne provizoriu,
  cu același motiv ca celelalte două. **[ADR-037](decisions/037-conventii-de-platforma.md) e
  `Acceptat`, `DNB-08` închisă**: regula linie-autoritativă nu mai e alegere de inginerie — e
  structura formularului, pct. 15 → 17 → 18 → 23 → 24, cu MO 340-351 art. 1750 din 22.09.2017 și
  intrare în vigoare 28.10.2017; corectată și în Spec B §7.4, care spunea că regula „se citește din
  schema XML". „Convenție de platformă, nu prescripție legală" stă acum **pe rând**, în
  `provisional_reason`, unde e citit — nu doar în ADR.
- **`default=0` pe `decimal_places` — a opta apariție a familiei**, numită de proprietar: o coloană
  `NOT NULL` cu un implicit care pare rezonabil e cea mai bună deghizare a unei alegeri netăcute —
  nu strigă niciodată, iar rezultatul e o cantitate acceptată la precizie greșită pentru orice
  unitate care nu e bucata. Și distincția de păstrat de la `R18`: aici nu cere istoric de valori, ci
  ca valoarea să nu se miște sub liniile care o poartă — un trigger, nu un `valid_from`.
- **`OD-71`, nouă, înainte de F2:** aprobatorul din producție trebuie să fie o identitate reală —
  legat de utilizatorii de sistem din Spec A §3.4, care nu există. Nu blochează nimic acum.
- **F1.5.4 — închiderea, livrată** ([ADR-056](decisions/056-inchiderea-lunii-si-a-exercitiului.md)),
  prima din cele trei sarcini rămase, în ordinea fixată. Luna: `close_period` validează invariantul
  clasei 8 pe primitivă (sold zero la data raportării, prin `trial_balance` — aceeași agregare ca
  raportul), refuză cu `periods.class8_not_settled`; ușa motorului `close_month` înregistrează
  `period.month_closed`, `posted` fără înregistrare. Exercițiul: `close_year` cere toate lunile
  închise și **ultima deschisă** (lanțul e o postare, `R12` nu admite excepție), refuză conturile de
  rezultat cu sold la intrare, rezolvă cele trei roluri, scrie soldurile și conturile în payload
  (handler pur, R18), postează pașii 1, 3, 4 într-o înregistrare `closing` — 731 corespondență
  proprie, 351 la zero — apoi închide ultima lună și blochează exercițiul, într-o tranzacție. **Numele
  evenimentelor:** registrul a refuzat `period.month.closed` (trei segmente; Spec B §1.4 cere două) —
  înregistrate `period.month_closed`, `period.year_closed`; `source_module = "periods"` nou (migrarea
  `accounting_events/0002`). Zece teste, ordinea corespondențelor verificată cu sume (1000 / 600 / 80
  / 320). **Nu s-a decis în cod:** pasul 5, reformarea bilanțului — `OD-73`; impozitul (pasul 2) e
  precondiție, postarea contabilului. Fără rută HTTP încă: ecranul vine cu F1.8/F2. Pe drum, ADR-039
  §10.2 („conturile concrete sunt parametri fiscali") a primit nota de reconciliere pe care ADR-050 o
  cerea și nimeni n-o scrisese.
- **Ce a subliniat proprietarul la F1.5.4:** tranzacția unică — o lună incorectă derulează înapoi și
  închiderea exercițiului — *impune structural* ce altfel s-ar verifica; handlerul pur cu soldurile
  în payload e ce face din `R18` o proprietate, nu o promisiune; iar numele `period.month.closed`,
  dat greșit de el în trei instrucțiuni consecutive, l-a prins **mecanismul**, nu un cititor.
- **Verificat la cererea proprietarului, pentru sesiunea C4:** `Document` are `currency` și
  `exchange_rate` (ADR-039, `DN-04`; input explicit, „care zi" încă deschis — întrebarea 9 de mai jos),
  dar **nu are termenul contractual** privind cursul (pct. 19). Precondiția lui C4 **n-a intrat**;
  se adaugă întâi, în sesiunea C4, ca migrare aditivă pe antet. Proprietarul a răspuns pe loc care e
  implicitul: **la data achitării** — regula normei, nu o alegere a platformei; celelalte două
  variante sunt stipulații care se înscriu.
- **Două nume pentru aceeași sesiune:** `ListAgents` a numit conversația aceasta `evidenta-77` dimineața
  și `evidenta-49` după o repornire de socket la prânz. Toate commiturile zilei poartă
  `Session: evidenta-77` — o conversație, un trailer (ADR-002).
- **`OD-72`, amânată cu declanșator:** încrederea în sursă e pe rând la parametri (ADR-046) și nu e
  nicăieri pe rând la versiunile de logică — asimetrie raportată, nu reparată nechemat. Decizia
  proprietarului: se face la **a doua** intrare în `fiscal_logic_version`; cu una, migrarea nu
  câștigă nimic.
- **Închiderea zilei, spusă de proprietar:** F1 fără niciun blocaj — nici extern, nici la el — prima
  dată în toată sesiunea. Corecția din Spec B §7.4 a fost numită cea mai importantă din raport: regula
  de rotunjire „se citea din schema XML a e-Facturii" — o proprietate a domeniului atribuită
  **canalului de transmitere**, aceeași eroare ca e-Factura declarată blocantă cu luni în urmă. Ea a
  supraviețuit într-un spec deși principiul fusese tras: *un principiu învățat nu curăță retroactiv
  locurile unde fusese aplicat greșit — le curăță doar cine le caută.* Căutat, în aceeași zi, în
  specificații și backloguri: vezi rândul următor.
- **Căutarea, făcută:** `grep` peste specificații, backloguri și ADR-uri după „schema XML",
  „validatorul SFS", „ghidul SFS", „se citește din". Un loc viu mai purta eroarea — Spec B §7.4,
  tabelul „Ce rămâne deschis până la ghidul SFS", cu trei întrebări toate decise azi de formular și
  de proprietar, nu de SFS; rescris cu răspunsurile. Restul aparițiilor sunt fie corectate deja, fie
  note de reconciliere care spun ce era greșit.

## Sesiuni mai vechi

**2026-08-30, F1.4.4 / C5 — repartizarea costurilor indirecte de producție
([ADR-058](decisions/058-repartizarea-costurilor-indirecte.md)):**

- **Ce validează al doilea handler:** o regulă **cu calcul propriu** peste **date deschise**. Formula
  pct. 30 e a actului și stă ca logică versionată în registrul fiscal
  (`production.overhead_absorption` → `normal_capacity_v1`, `valid_from 2014-01-01`, sursa OMF
  118/2013 cu ambele publicări), selectată la ultima zi a perioadei (R17); **fără rând, refuzul e al
  registrului**, nu un implicit al handlerului — test. Baza pct. 31 e a entității („de exemplu") și
  vine pe fapt ca nume plus valoare per produs, nevalidată contra unei liste; **bază goală refuzată**,
  nu împărțită egal. Prima confirmare practică a graniței din ADR-036 §10.1: metoda se enumeră,
  baza nu.
- **Conturile din normele planului, nu deduse** (`c5-costuri-indirecte-conturi.md`): creditul lui
  821 „în corespondenţă cu debitul conturilor: 714, 811, 812" — o formulă `Dt 811[item] / Ct 821`
  per produs, restul constant nerepartizat `Dt 714 / Ct 821`; rol nou
  `COSTURI_INDIRECTE_NEREPARTIZATE` → 714 gradul I (catalogul la 46); subcontul nu-l numește niciun
  text citit. Produsul e dimensiune pe partea care o declară (ADR-048): verificat pe debit, absent pe
  credit.
- **Ultimul ban:** fiecare cotă rotunjită o dată, ultima ia restul — alegere de inginerie, scrisă ca
  atare: pct. 31 fixează baza, nu banii rămași. 100 peste trei baze egale → 33,33 / 33,33 / 33,34.
- **Verificat cu sume:** 1000 + 500 la capacitate, baza 3:1 → 1125 / 375; volum 800 din 1000 →
  1050 / 350 și **100 la 714**; variabilul integral la volum 10 din 1000; aceeași repartizare de două
  ori → o înregistrare; zero de repartizat → eveniment `posted` fără înregistrare. Opt teste sub
  rolul aplicației.
- **Sursa evenimentului spune adevărul:** `manual` ar fi însemnat că cineva a tastat repartizarea;
  `SourceModule.PRODUCTION` prin migrarea aditivă `0003`, forma lui `0002`/`periods` — valoare de
  vocabular, nu app. Aplicată pe baza de dezvoltare, `drift-check` curat.
- **Ce face adevărat pentru închidere:** după repartizare 821 e la zero — invariantul clasei 8
  (ADR-056) devine **satisfiabil**, nu doar verificabil; o lună cu producție se poate închide.
- **Raportat, nu decis:** rândul de logică e `draft` pe baza de dezvoltare (activarea e a
  proprietarului); Indicațiile metodice privind costurile de producție, necitite; 812 activități
  auxiliare neexprimabile azi (refuz prin lipsa rolului, nu aproximare); capacitatea normală e a
  politicii entității și vine pe fapt — unde stă stabil e întrebarea modulului de producție din F2;
  Anexa 1 din SNC „Stocuri" (exemplul numeric) e candidatul primului caz citat al corpusului (F1.10).
  `OD-72` nu s-a declanșat: al doilea rând de logică e pe **altă cheie**, nu a doua versiune.
- **Un rest din C4, curățat:** rândul F1.4 din lista de sarcini spunea încă „niciun handler concret".
- Suita: **1022 trec, 1 sărit** (de la 1001 la C4; 21 noi — opt C5, restul ale sesiunii paralele,
  care rulează în același arbore). `ruff`, `mypy` pe pachet, `drift-check` pe baza vie: curate.

**2026-08-30, F1.4.4 / C4 — diferențele de curs și de sumă realizate la decontare (instrucțiune
scrisă; [ADR-057](decisions/057-diferentele-realizate-la-decontare.md)):**

- **Precondiția, măsurată apoi construită:** `Document.rate_term` — vocabular închis din pct. 19
  (`payment_date`, `delivery_date`, `fixed`), `CHECK` în bază, trecut prin `open_draft` și prin cele
  cinci deschideri din vânzări și achiziții, înghețat la validare odată cu antetul (triggerul compară
  rândul întreg). **Implicitul `payment_date` e sigur și ADR-ul spune de ce**, ca peste un an să nu
  fie citit ca `default=0`: acolo implicitul acoperea o alegere nefăcută; aici e **regula supletivă a
  actului** (pct. 6, 8) — un document fără stipulație chiar cade sub normă.
- **Handlerul `settlement.differences.v1`**, pe `receivables.settlement_created` și
  `payables.settlement_created`, pur de registru, citind registrul fiscal (scara și direcția în
  vigoare la data decontării) fiindcă diferența e prima sumă **derivată** a motorului — și **prima
  ștampilă de parametru** scrisă de un handler (ADR-047, în sfârșit nevidă). Discriminatorul
  (rezident + denominarea contractului, pct. 4 și 17) e **refuzat, nu presupus**, înainte să existe
  eveniment. Trei perechi ca roluri: 6226/7224 curs, 6227/7225 sumă, **6127/7147 ecartul BNM–bancă
  contra contului în lei, rezultat operațional** — patru roluri noi, catalogul la 45.
- **Ramurile fără postare sunt cazuri, nu omisiuni:** `delivery_date` și `fixed` (pct. 21), avansul
  (pct. 23), diferența care se rotunjește la zero — toate `posted` fără înregistrare.
- **Verificat cu sume:** 1000 × (19,6234 − 19,5000) = 123,40 o singură dată; ambele sensuri pe
  creanță și datorie; ecartul −23,40 / +76,60; aceeași decontare de două ori → o înregistrare.
  Douăsprezece teste C4, două pe antet.
- **Nu intră:** reevaluarea la raportare (Anexa 1 neextrasă); `DN-04` rămâne deschisă și nu
  blochează. **Sesiunea paralelă `evidenta-04`/`2d` a pornit F1.8 + F1.G2**; zonele sunt separate,
  numerele împărțite (ADR-058+ ale lor).

**2026-08-29, baza motorului — etapa 1+2, formula ca unitate de postare și sloturile tipizate
(instrucțiune scrisă; [ADR-048](decisions/048-formula-si-sloturile-tipizate.md)):**

- **Ce s-a construit, gol, fiindcă cerea altă structură:** `journal_formula` — corespondența
  debit/credit din care se derivă exact două linii, cu sumă în lei și în valută, curs, cotă TVA ca
  **atribut**, patru sloturi tipizate (`slot_n_dimension` + `slot_n_value_id`), append-only în
  `append_only.toml`; trei versiuni pe `journal_entry` — `rule_ref`, `chart_template_id`,
  `fiscal_effective_date` — imutabile după postare prin trigger propriu, fiindcă lista din `0036` e
  append-only (`C31`); patru sloturi de declarație pe `coa_template_account` și `company_account`,
  cu `required ⊆ declarat` ca CHECK în bază. **Nicio declarație în CSV-ul planului** — un test o
  asertează; care conturi poartă ce e decizia proprietarului.
- **Ce s-a exprimat peste structura existentă, deci nu s-a construit:** tabela de agregate (sold per
  cont × tuplu × perioadă) — derivabilă din `journal_formula` fără migrare pe registru; cele 15
  coloane ale liniei rămân neatinse, slotul spune doar în care aterizează o valoare pentru contul
  acela.
- **Motorul, în ordine:** `bind_roles` (rol → cont la data postării, refuz pe rol nelegat) →
  `place` (fiecare parte primește ce declară contul ei, formula stochează reuniunea; o dimensiune pe
  care n-o declară nimeni **nu e purtată** — stratul 2 din ADR-036 făcându-și treaba, nu o pierdere)
  → `merge` (cheia de contopire, aceeași pe care baza o impune ca `UNIQUE … NULLS NOT DISTINCT`) →
  `verify` (cei șase invarianți, **o singură implementare**, peste expansiunea în linii) →
  obligativitatea per parte → `post_entry` cu linii **și** formule. Un constraint trigger amânat
  refuză la COMMIT o înregistrare ale cărei formule nu însumează liniile; una **fără** formule trece
  — nota manuală și soldurile rămân forme legitime.
- **Stornoul oglindește formulele** (conturi schimbate, restul purtat) și **copiază** planul și data
  fiscală ale originalului, cu propria `rule_ref` — nu recalculează (R18). Registrul primește
  `resolve_version` ca antetul să știe *care* tratament l-a produs; un callable nu se scrie pe rând.
- **Măsurat înainte de CHECK, ca superuser, nu ca owner** (regula din 28.08: sub `FORCE RLS` un
  `count(*)` ca owner e o politică): 0 din 1428 `company_account` și 0 din 476 `coa_template_account`
  cu `required_dimensions` nevid, deci `*_required_within_slots` nu cade pe baza de dezvoltare.
- **Ce se raportează, nu se decide** (ADR-048 §7): **`OD-69`** — „versiunea setului fiscal" n-are
  identitate aici (parametrii și logica sunt versionate rând cu rând; data pentru care s-au rezolvat
  e singura identitate, deci antetul poartă o dată, nu un id); **referința „ADR-018 §3 / §7" din
  instrucțiune nu se rezolvă** — ADR-018 de aici e despre engagementuri, iar `docs/` nu conține
  „contopire" nicăieri; s-a construit după intenția enunțată; **sloturile sunt comune celor două
  părți**, nu per parte ca în 1C — litera instrucțiunii, cu limita scrisă: Dt 221/A — Ct 221/B nu
  încape într-o formulă, iar peste patru axe distincte între cele două conturi se refuză.
- **Etapa 4 era deja livrată** de sesiunea din 28.08 (`d9a116f`): linia autoritativă, precizia ca
  parametru, direcția ca rând, backlogul corectat (nicio mențiune a „ghidului SFS" nu mai leagă
  `DNB-08`). **`V1` — Ordinul MF nr. 118/2017, anexele 1 și 1a — s-a reîncercat și de aici, cu
  același rezultat:** `sfs.md/ro/document/ordin-mf-nr118-din-28082017` și
  `legis.md/cautare/downloadpdf/153885` răspund **403**; `mf.gov.md` găzduiește doar proiectul unui
  ordin de **modificare** din 2019 (`.docx`, citit integral: 52 de paragrafe, niciunul despre
  zecimale sau rotunjire), nu textul anexelor. Precizia rămâne ipoteză de lucru — patru la preț,
  două la sume — și intră ca parametru cu `provisional` când `OD-67` deschide calea de scriere.
- **Etapele 3, 5, 6, 7 nu s-au atins**, deliberat: `CLAUDE.md` §5, o sesiune = o capabilitate, iar
  instrucțiunea le declară independente și de dat pe sesiuni separate. Etapa 8 nu începe înaintea lor.
- Suita: **927 trec, 1 sărit** (de la 863 — 64 de teste noi, plus 4 seedere care cereau o dimensiune fără s-o declare, prinse de CHECK-ul nou în 190 de erori de setup pe două rulări). `mypy` curat. `makemigrations --check`: fără derivă. Migrațiile
  `0056`/`0057` rotite în `test_reverse_sql`; `journal_formula` sub gardianul de model ca append-only.

## Sesiuni mai vechi

**2026-08-28, `DNB-08` deblocată pe structură, plus atribuirea între sesiuni (instrucțiune scrisă):**

- **Regula, decisă de proprietar și scrisă în cod:** *TVA se calculează și se rotunjește pe fiecare
  linie; totalul documentului e suma liniilor, niciodată o recalculare pe bază de total.* Cu asta,
  divergența din ADR-037 §3.1 **nu mai poate exista** — nu există două calcule concurente. Testul care
  o apără construiește chiar cazul care doare: trei linii de `0,33 × 20%` dau `0,21` prin sumare și
  `0,20` prin recalculare pe bază; sistemul răspunde `0,21` fiindcă nu execută al doilea calcul.
- **Ce a rămas date și ce a rămas cod, ținute separat deliberat.** Numărul de zecimale e **parametru
  fiscal** (`accounting.amount_scale`, `accounting.unit_price_scale`), rezolvat după dată — o
  instrucțiune care prescrie altceva e un INSERT, nu un deployment. Direcția la echidistanță e **rând
  în `fiscal_logic_version`**: `IMPLEMENTATIONS` conține acum **ambele** direcții, iar prezența
  amândurora nu e o alegere între ele. Probat: același input, două rânduri, două răspunsuri.
- **`DNB-08` nu era blocată pe ghidul SFS, iar backlogul spunea că da.** ADR-037 §5 constata deja
  contrariul — doar `V2` depinde de `OD-24`. Corectat în backlog, în două locuri.
- **Al doilea blocaj, găsit la implementare: `OD-67`.** `fiscal_parameter` are politică doar de
  **citire**, deci precizia nu se poate încărca pe nicio cale în afară de superuser. Mecanismul e
  complet și **inert** — a șasea apariție a familiei „legat și nepornit" în aceeași zi.
- **`OD-65` era greșită ca premisă, și corectarea schimbă răspunsul.** Din PDF-urile MF ale textelor
  consolidate: OMF **118**/2013 poartă `MO 177-181 art.1224` **și** `MO 233-237 art.1534`; OMF
  **119**/2013 poartă `MO 177-181 art.1225` **și același** `art.1534`. Deci art. 1534 **nu e anexa
  planului de conturi** — e o publicare care acoperă **ambele acte**. Sunt două fapte, nu unul, iar al
  doilea face varianta „încă un set de coloane" imposibilă: o coloană nu se împarte între două rânduri
  de act. Citarea din `load_coa_template` e greșită azi.
- **LIFO confirmat din act, nu din sursă secundară:** SNC „Stocuri" pct. 33 subpct. 4), *[Pct.33
  modificat prin Ordinul Min.Fin. nr.48 din 12.03.2019, în vigoare 01.01.2020]*.
- **Atribuirea între sesiuni**, cerută prin instrucțiune: cârlig `commit-msg` care cere trailerul
  `Session:`, `make hooks`, și un gardian în `tests/architecture` care verifică **commiturile de după
  cârlig**, nu instalarea lui — fiindcă un cârlig neinstalat nu refuză nimic și nu spune nimic despre
  asta. `fetch-depth: 0` în CI, iar gardianul **cade** pe un checkout superficial în loc să treacă
  peste un istoric trunchiat. Ce impune: **prezența** trailerului, adică uitarea. Nu adevărul lui.
- **Cine a comis `ee1b599` a rămas nestabilit** — nu `evidenta-34` (are reflog și cronologie), nu
  `evidenta-2a`. `ListAgents` arată `evidenta-18`, pornită la ora potrivită. Ipoteză, nu fapt; exact
  golul pe care trailerul îl închide de acum înainte.

## Sesiuni mai vechi

**2026-08-28, stratul documentar — structura documentelor și ciclul lor de viață, până la validat:**

- **Nucleul exista pe jumătate și a fost completat, nu dublat.** `platform/documents` avea antetul și
  istoricul de stări din F0.6; îi lipseau **liniile**, a doua dată (contabilă), cursul, referința la
  documentul sursă și regimul de numerotare. Un al doilea nucleu ar fi fost a doua grilă de date.
- **Documentul validat e imutabil în bază, nu în servicii.** Cerința spune „la nivel de model, nu
  prin convenție în views" — iar un serviciu nu e nivelul de model: importul în masă, migrările de
  date și orice `UPDATE` din psql îl ocolesc, și exact acolo se editează tăcut un document deja emis.
  Triggerul compară **rândul întreg minus coloanele ciclului de viață**: listă de permise, nu de
  interzise, ca o coloană adăugată peste doi ani să fie înghețată din oficiu.
- **`confirmed → draft` a fost scoasă din mașina de stări.** Era acolo din F0.6. Dezvalidarea ori
  eliberează un număr — ceea ce un registru n-are voie — ori arde unul tăcut. Refuzată și de trigger.
- **Două regimuri de numerotare, paralele.** Seria capătă `regime` (`own` / `external`) și
  **valabilitate**; cele două unicități parțiale au devenit o constrângere de neîntrepătrundere,
  fiindcă unicitatea peste tot timpul ar fi făcut imposibilă schimbarea seriei. Sub regim extern
  `allocate` **refuză**, iar documentul se validează fără număr — identificatorul e al schimbului
  e-Factura sau al unui diapazon `art. 118²`, nu al nostru.
- **Nicio sumă nu se calculează aici, și motivul e scris în cod.** Linia primește `net`, `TVA` și
  `total` gata calculate; baza verifică doar identitatea care nu cere rotunjire — `total = net + TVA`.
  Reducerea lui `cantitate × preț` sau a lui `net × cotă` la scara stocată **este** pasul de
  rotunjire, iar regula lui e logică fiscală versionată, deschisă pe trei axe deodată (ADR-037 §3.1–3.3,
  `DNB-08`). Un `CHECK` scris înainte ar fi codificat unul dintre răspunsuri ca lege.
- **Cota vine din nomenclator, la dată; regimul TVA e cod stocat, nu enumerare.** `fiscal.parameters`
  primește `vat_rate(key, on)` și `vat_regimes(on)`. Vocabularul de regimuri **nu e în cod** — vine
  din Codul fiscal și se schimbă prin act, deci e parametru; modulul stochează codul primit, ca
  `strictforms.form_type_code`.
- **Contrapartea: `partner.vat_code` a devenit `partner_vat_registration`**, cu perioadă de
  valabilitate, aceeași formă pe care `company_vat_registration` o are deja. Nu duplicat: codul
  aparține înregistrării, iar un partener radiat și reînregistrat primește altul — o singură coloană
  l-ar fi suprascris tăcut pe cel pe care facturile deja emise îl poartă. `internal_name` (ADR-034)
  aterizează pe `partner` și pe `item`, cu căutarea extinsă peste el.
- **Articolul:** `item_unit` (unități alternative cu coeficient **per articol**, distinct de
  `unit_conversion`, care e general), `item_barcode` (tabelă, nu coloană — un articol are mai multe
  coduri), `tariff_code`, plus felurile `material` și `low_value_short_lived` (OMVSD).
- **Tipurile concrete stau în `operations/{sales,purchases}`**, tabele una-la-unu cu antetul: document
  de vânzare cu natură (livrare/avans, **un** tip), document de cumpărare cu numărul și data
  furnizorului (ale lui, deduplicate pe cheie naturală — `R20`), proformă, comandă client, comandă
  furnizor cu conversie declarată în registru. Stornoul e al nucleului: e același document pentru
  vânzare și pentru cumpărare, iar `reversal_document` există ca legătura să fie `NOT NULL`.
- **Peste cusătura dintre module trec identificatori, nu rânduri.** Serviciile publice ale nucleului
  iau `uuid`; `operations` întoarce `uuid`; `items.services.catalogue` întoarce un dataclass înghețat,
  nu instanța `Item`. Prins de gardianul de dependențe (`D6`) în lucru, nu la citire — patru violări,
  reparate prin structură: vocabularul regimurilor a ieșit din stratul de model în
  `platform/numbering/regimes.py`.
- **Scara sumelor are un singur loc: `platform/amounts.py`.** `accounting.currency.money` o
  reexportă, ca nimic care o importa deja să nu se schimbe. `platform` nu poate importa `accounting`,
  iar o constantă pe care tabela de linii n-o poate citi nu e un singur loc, e un comentariu.
- **Măsurat, nu presupus:** triggerul `SECURITY DEFINER` a murit cu „permission denied for table
  document" la prima linie inserată — `evidenta_rls` are `BYPASSRLS` dar **niciun** privilegiu de
  tabelă implicit. Grant punctual, ca la `journal_entry` în `0036`.
- **Un defect prins scriind raportul, nu rulând suita:** cheia de deduplicare a documentului de
  cumpărare era `(companie, număr, dată)` — fără furnizor. Doi furnizori care emit „001" în aceeași
  zi e ordinar, iar constrângerea l-ar fi refuzat pe al doilea *arătând ca deduplicarea care
  funcționează*. `partner_id` e denormalizat pe `purchase_document` tocmai fiindcă o cheie pe două
  tabele nu poate fi constrângere. Testul care o apără verifică acceptarea, nu refuzul.

- **Capcana pe care o descrie chiar fișierul care a căzut în ea.** `make migrate` a murit la
  proprietar: `column "valid_from" contains null values`. Politica lui `numbering_template` e scrisă
  `TO evidenta_app`, iar `FORCE RLS` se aplică **și** proprietarului — deci `UPDATE ... WHERE
  valid_from IS NULL` rulat ca owner atinge zero rânduri **și reușește**, iar `SET NOT NULL` de după
  scanează tabela *fizic* și găsește cele trei rânduri pe care UPDATE-ul nu le-a văzut. Verificasem
  înainte cu `select count(*)` — **rulat tot ca owner**, care a răspuns `0` din exact același motiv.
  Măsurătoarea menită să prevină greșeala a confirmat-o. **Regula de aici: pe o tabelă cu `FORCE RLS`,
  un `count(*)` rulat ca owner nu e o măsurătoare, e o politică.** Confirmată independent de sesiunea
  paralelă pe `company` — `3` ca superuser, `0` ca owner, în aceeași bază, în aceeași clipă — și
  ascuțită de ea: citirea oarbă produce **două zgomote diferite**. Un `INSERT` care se sprijină pe ea
  cade pe loc, la constrângerea de unicitate; un `UPDATE` care se sprijină pe ea **reușește**, iar
  eșecul apare mai târziu și vorbește despre o coloană, nu despre un rol. Disciplina e cerută de al
  doilea caz. Reparat cu `NO FORCE` → `UPDATE` →
  `FORCE` în tranzacția migrării, nu cu o politică de scriere ca în `0044`: aceea rămâne în bază după
  ce nevoia a trecut, iar aici nevoia e o singură instrucțiune.

Suita: **863 trec, 1 sărit.** `mypy .` **curat, 314 fișiere** — ultima eroare rămasă era a mea și e
reparată printr-un refuz explicit, nu printr-un `cast`: `document.partner_id` e nullable fiindcă o
ciornă are voie să fie incompletă, iar `purchase_document.partner_id` nu e, fiindcă e jumătate din
cheia pe care `R20` deduplica. `make drift-check`: fără derivă față de contracte.

## Sesiuni mai vechi

**2026-08-28, modulul 2 din briefing — registrul formularelor cu regim special (`art. 118²`):**

- **Entitatea nu își alege seria.** Asta e faptul pe care stă tot modulul, și e **opusul** regimului
  românesc, unde entitatea își definește seriile și le resetează anual. SFS asigură sistemul unitar
  de înseriere; o entitate care imprimă de sine stătător primește o serie și un diapazon pentru toată
  perioada de activitate. Deci nu e generator de numere, e **registru de alocări din care se consumă.**
- **Modul separat de `numbering` (ADR-022), deliberat.** Contorul *generează* — corect pentru
  documentele fără regim special, care se numerotează liber. A-l îndoi să facă și una și alta ar
  produce numerotare liberă oriunde cineva a uitat ce fel de document are în față.
- **Numerele nu se materializează.** Un diapazon poate fi mare, iar un rând pe număr ar face tabela
  proporțională cu ce s-a alocat, nu cu ce s-a întâmplat. Alocarea poartă un cursor; un număr iese o
  singură dată, și acea ieșire e un rând. „Alocat" se **deduce**; restul stărilor se scriu — fiindcă
  anularea e stare evidențiată, nu absență.
- **Consumul se face la postare, sub lock, în tranzacția documentului** — niciodată la crearea
  ciornei. O ciornă care rezervă un număr și e abandonată arde un număr emis de SFS, iar registrul
  rămâne cu un gol pe care nu-l explică niciun document. Nu există endpoint care dă un număr: ar fi
  exact defectul respectiv, expus ca funcționalitate.
- **Identitatea pe care o reconstituie un control** — emis = consumat + anulat + rămas — e asertată
  ca aritmetică, nu descrisă. Un formular deteriorat neînregistrat o rupe tăcut.
- Paisprezece teste de izolare sub rolul aplicației, plus append-only prin trigger pe rândurile de
  număr, probat pe rânduri semănate.

**ÎNTREBARE CONTABILĂ — nomenclatorul formularelor cu regim special.** Structura e construită; **lista
nu e seedată și nu o ghicesc.** Briefingul semnalează HG 496/2025 (în vigoare 14.08.2025) ca
neverificată; căutarea a scos la iveală și **HG 901/2024**, încă o modificare la HG 294/1998 pe care
briefingul n-o menționează. `legis.md` refuză preluarea (HTTP 403), deci redacția curentă nu se poate
citi de aici. Lista e parametru fiscal — briefingul o numește explicit așa — deci intră prin seed
versionat cu temei normativ, nu prin cod. **Blochează:** ce coduri de formular acceptă registrul.
**Nu blochează:** nimic din structura de mai sus.

Suita: **787 trec, 1 sărit.**

## Sesiuni mai vechi

**2026-08-27, două servicii complete care n-aveau cale de intrare — stornoul și soldurile inițiale:**

- **Stornoul prin motor** (`accounting/posting/services/reversal.py`). `ledger/services/reversal.py`
  știa să oglindească o înregistrare postată din F1.2 și **nimic nu-l apela**. Tipul evenimentului e
  derivat din al originalului — [ADR-038 §7.2](decisions/038-vocabularul-de-evenimente.md), fiecare tip
  stornabil are perechea lui — deci merge pentru factura de vânzare și pentru salarii când apar.
- **Coliziune de notație, rezolvată prin măsurare.** §7.2 scrie `*.reversed`, ceea ce se citește ca al
  treilea segment. Nu poate fi: Spec B §1.4 fixează tipul ca `<domain>.<action>`, iar `NAME` din
  registru e un tipar de două segmente. Scris întâi `manual.journal_entry.reversed` și văzut
  `register()` refuzându-l. Singura citire care satisface ambele formează perechea **în acțiune**:
  `manual.journal_entry_reversed`.
- **Handlerul e `reverse_entry` însuși**, deci semnele se inversează într-un singur loc. Consecința:
  o oglindă **nu poate deriva** cu capabilitățile, fiindcă nu recalculează nimic (`R18`).
- **API-ul soldurilor inițiale** (`accounting/opening/`) — cinci endpointuri peste servicii complete
  din F1.7.2 care nu erau apelate de nimic. Consecința practică a lipsei: produsul era utilizabil
  doar de o companie fondată azi, fiindcă o firmă venită din alt sistem nu-și putea aduce soldurile,
  iar balanța ei pornea de la zero.
- **Expuse doar rândurile GL, creanțe și datorii**, din cele șase pe care le acceptă serviciul.
  Celelalte trei referă `item_id` (F4), `asset_id` și `employee_id` (F2) — entități care nu există.
  Un endpoint pentru un id fără tabelă în spate arată ca funcționalitate livrată și nu poate fi apelat
  corect de nimeni.
- **Un defect găsit de propriul `REVOKE`:** prima versiune a testului era `transaction=True`, iar
  golirea bazei la teardown rulează **sub rolul aplicației** — care n-are `DELETE` pe
  `entry_parameter_stamp`, prin ADR-047. Cade cu „permission denied" în teardown, ceea ce se citește
  ca fixture stricat și e de fapt garanția append-only funcționând. Motivul e scris în fișier.
- **`TEST_DB_NAME` adoptat.** Două rulări ale mele, cu 273 și 530 de erori urmate de verde la
  reluare, se explică fără rest: `AdminShutdown` — sesiunea vecină recrea `test_evidenta` sub
  conexiunile mele. Nu în `.env`, care e partajat; pe linia de comandă.

- **Șabloanele de operațiuni au API** (`entries/companies/<id>/templates`) — al treilea serviciu
  complet fără cale de intrare, găsit în aceeași zi. Layer 4 din [ADR-036](decisions/036-forma-postarii.md)
  §7: un șablon se expandează într-un payload `manual.journal_entry` și trece prin **același**
  motor ca o notă tastată. De-aia nu există tip de eveniment `template.posted`: registrul
  consemnează ce s-a întâmplat, iar ce s-a întâmplat a fost o notă manuală. Cum a completat
  omul formularul e proprietate a interfeței, nu a faptului contabil — asertat prin registru.
- **Citirea vede șabloanele retrase, expandarea nu.** `_template` filtrează pe `is_active` fiindcă
  un șablon retras nu mai are voie să producă înregistrări. Dar o înregistrare postată anul trecut
  îl numește, deci o definiție devenită necitibilă ar lăsa acea înregistrare explicându-se cu un
  id. `definition_of` are acum propria căutare, cu motivul lângă ea.

- **Lista de loturi de solduri inițiale** (`GET .../opening-balances/companies/<id>`) — gol
  găsit de sesiunea vecină citind suprafața. Un lot nu se șterge niciodată și trei din cele
  patru stări supraviețuiesc sesiunii care le-a creat, deci un `draft` abandonat ieri rămâne
  acolo. Fără drum înapoi la el, următorul import începe de la zero lângă el, iar compania
  ajunge cu două tablouri parțiale ale aceleiași poziții de deschidere.
- **Directorul de parteneri** (`/api/v1/masterdata/partners/`) — modulul avea o tabelă și
  nimic altceva: niciun serviciu, nicio rută. Consecința apărea cu un strat mai încolo, într-un
  ecran care nu putea oferi creanțe, fiindcă **un formular care cere un `partner_id` e un
  formular pe care nimeni nu-l poate completa corect.** Căutarea potrivește exact ce are omul
  în față: numele de pe document și IDNO-ul de pe el.
- Partenerul e la nivel de **tenant**, nu de companie: aceeași entitate juridică e aceeași
  entitate pentru toate companiile firmei, iar o copie per companie e felul în care un holding
  ajunge cu doi furnizori identici ale căror solduri nu mai reconciliază. `CompanyPartner` —
  conturile pe care le folosește o companie anume — n-are suprafață, fiindcă nimic din F1 nu-l
  citește, iar o suprafață neapelată se depărtează de ce pretinde.

- **`make check-committed` acoperă acum și backendul.** Frontendul îl construise sesiunea
  vecină după ce un commit uitase un fișier și toate cele patru verificări locale rămăseseră
  verzi — citeau discul, unde fișierul era. Backendul are aceeași expunere **plus una proprie:**
  `manage.py check` **nu încarcă migrațiile**, deci un fișier SQL uitat trece de el. De-aia
  rulează și `makemigrations --check`, care construiește graful și acolo `run_sql_file` verifică
  existența și suma de control. Ambele măsurate prin mutație pe copia comisă:
  `ModuleNotFoundError` la modulul scos, `SqlFileMissingError` la `.up.sql` scos.
- **Fiecare jumătate își dovedește separat căderea** în `--self-test`. O probă care acoperă doar
  frontendul lasă backendul indistinct, din afară, de un script care tipărește o linie
  liniștitoare.

Suita: **773 trec, 1 sărit.**

## Sesiuni mai vechi

**2026-08-26, ștampila parametrului la postare — `OD-68` închisă prin
[ADR-047](decisions/047-stampila-parametrului-la-postare.md):**

- **Livrat: `entry_parameter_stamp`** — ce a stat sub un calcul, scris la postare, în aceeași
  tranzacție cu înregistrarea. Tabelă atârnată de `journal_entry`, nu `jsonb`, fiindcă întrebarea
  care o justifică se citește *înainte, peste toate înregistrările*: „SFS a publicat, ce am postat pe
  o deducție?". Fără FK spre `fiscal_parameter` (`D6`); FK spre antet e permis — `journal_line` e cea
  din `append_only.toml`, nu antetul.
- **Încrederea se copiază, nu se referă**, iar `resolved_at` o face re-derivabilă din istoricul lui
  ADR-046. Testul verifică ambele sensuri: la instantul ștampilei `provisional`, la instantul
  publicării `confirmed`. Opt teste de izolare, toate sub rolul aplicației.
- **Măsurat, și a schimbat migrarea:** un `GRANT SELECT, INSERT` restrâns nu *retrage* nimic —
  tabela ajunsese la `evidenta_app` cu toate patru privilegiile, din cele implicite. Comentariul din
  fișier spunea că privilegiul oprește aplicația; catalogul spunea altceva. `REVOKE` explicit.
- **[ADR-043](decisions/043-privilegiile-functiilor-rls.md) §4.1 nou, și corectează o propoziție din
  §3 al lui.** Revocarea lui PUBLIC din `0041` a scos de sub tiparul de creare a triggerelor
  suportul pe care nimeni nu observase că stă: `CREATE TRIGGER` verifică `EXECUTE` la creare și se
  emite ca `evidenta_owner`, care e `NOINHERIT`. §3 spunea „retragerea nu costă nimic" — adevărat
  pentru starea măsurată, fals pentru tranziția nemăsurată. Găsit de `evidenta-2f`, lovind-o.
- **Gardian nou, `tests/architecture/test_trigger_function_grants.py`**, cu referința la ADR **în
  mesajul de eroare**. Alegerea e a proprietarului, și raționamentul merită păstrat: *documentația
  ajunge la cine caută, mesajul de eroare ajunge la cine nu știe că trebuie să caute.* Mesajul e ușa,
  ADR-ul e camera. Restrâns la migrările de după `0041`: cele zece de dinainte au rulat cât PUBLIC
  încă avea `EXECUTE`, și rulează la fel la o reconstruire de la zero.
- **`_TRIGGER_STATE` a crescut cu trei linii** — `entry_parameter_stamp`, `journal_entry`,
  `journal_line`. Aceeași asimetrie descrisă acolo, a doua oară: modulul care deține tabela seamănă
  prin ORM, deci suita lui trece fără linie; testul care seamănă prin `seed()` cade la setup, nu la
  aserțiune.
- **Nimic nu scrie încă ștampile.** Niciun handler nu rezolvă un parametru fiscal — F1.4.4 e blocată
  pe `C1`–`C5`. Mecanismul e înaintea primului producător deliberat: ieftin acum, scump după ce
  există calcule postate, fiindcă o coloană adăugată ulterior e goală pentru toată istoria.

- **[ADR-039](decisions/039-valuta-si-perioade.md) §9.1 nou — tiparul dată economică / dată
  tehnică.** S-a redescoperit de trei ori independent: linia de registru (`document_date` /
  `accounting_date`), rezoluția regulii (ADR-044), linia de salariu (perioada de muncă / data
  de angajament, Legea nr. 489/1999 anexa 1, art. 20 alin. (5)). Regula pentru data următoare:
  cele două date se separă de la început, chiar dacă în cazul obișnuit coincid. Scris acum
  fiindcă a patra oară ar fi în salarii, unde coloana lipsă nu se mai adaugă retroactiv.

Suita: **744 trec, 1 sărit.**

## Sesiuni mai vechi

**2026-08-26, patru ecrane peste API-ul care exista — și o bază goală în spatele lor:**

- **Livrat: `/companii`, planul de conturi cu compania în cale, inițializarea planului și fișa
  contului** (redenumire, blocare, închidere, subcont). Toate peste endpointuri care existau și erau
  testate din F1.1, niciunul nou. Ecranul de formatare (`HomeScreen`) a fost înlocuit de lista de
  companii — era un substitut, iar întrebarea „care companie" e prima pe care o pune orice ecran
  contabil
- **Compania a intrat în cale, nu în starea componentei.** `/companii/:companyId/plan-de-conturi`,
  ca în rutele serverului. Înainte, planul unei companii anume nu avea adresă: nimic nu putea trimite
  un link spre el, iar o reîncărcare cădea tăcut pe prima companie din listă. Tenantul rămâne unde
  era — în subdomeniu (`C8`), niciodată în cale
- **`OD-57` a devenit scadentă azi.** Termenul ei scrie „înainte de primul ecran care alege o
  companie"; acel ecran există acum. Îngustarea pe `company_id` e construită pe o treime din politici
  și **calea de request n-o trimite deloc** — deci ecranele de mai sus se bazează pe RLS de tenant,
  nu pe îngustare de companie. Nu am atins-o: e decizie, nu implementare
- **Măsurat înainte de a promite ceva: baza de dezvoltare e goală** — 1 tenant, 32 de sesiuni,
  **0 companii, 0 versiuni de plan, 0 conturi**. Deci fiecare ecran nou își arată azi starea goală,
  iar cauza nu e în ecrane: conținutul planului nu poate fi încărcat (`OD-23` blocat de `OD-56` —
  `coa_template` e globală, scrierile retrase rolului aplicației), iar compania se creează prin `P-9`
  ([ADR-040](decisions/040-crearea-tenantului-si-a-companiei.md)), decisă și nescrisă
- **Ieșirea din cont nu funcționa, și defectul era pe server, nu în buton.** `logout` răspundea
  `JsonResponse({}, status=204)` — un 204 cu corp. RFC 9112 termină mesajul la antet pentru 204, deci
  cei doi octeți se citesc ca începutul următorului răspuns: **măsurat, parserul HTTP al lui node —
  cel pe care rulează proxy-ul de dezvoltare — respinge perechea cu `HPE_INVALID_CONSTANT`**. Sesiunea
  era deja revocată, dar browserul vedea cererea eșuată, deci ecranul rămânea pe loc. Testul de
  izolare asertează acum și corpul gol, nu doar codul 204
- **Ce nu e acoperit de niciun test: tot ce am scris în frontend.** Nu există runner de teste
  frontend în `package.json` și nu am adăugat unul — ar fi decizie de tooling luată în treacăt, iar
  `C28` fixează lanțul de backend tocmai fiindcă astfel de alegeri se iau o dată. Verificat în schimb
  ce se putea verifica fără browser: `tsc`, ESLint, build, și **fiecare cale pe care o cheamă
  clientul rezolvată prin URL-conf-ul Django** — sonda HTTP nu putea dovedi nimic, fiindcă
  autentificarea răspunde 401 înaintea rezolvării rutei, inclusiv pentru o cale inexistentă
- **`amount` și `money` au rămas fără niciun consumator** odată cu ecranul de formatare; `date` are
  trei. Primul ecran cu solduri le readuce — până atunci, dovada că formatarea e a Moldovei nu mai
  stă nicăieri, iar locul ei era oricum un test, nu o pagină

**2026-08-26, `OD-64` — opt inverse care nu rulau, și de ce clasificarea a schimbat sarcina:**

- **Proprietarul a cerut lista înainte de tratament**, și a avut dreptate: nu toate „migrările
  inverse" sunt același lucru. Clasificate pe conținut măsurat — DML **în afara** corpurilor de
  funcție, nu grep naiv: **șapte din opt sunt pur RLS/roluri**, categoria cea mai periculoasă,
  fiindcă un invers pe jumătate nu produce eroare, produce acces greșit. `0028` e singura care
  transformă date
- **Corecția e opt fișiere noi**, `0042`–`0049`, cu `run_sql_file` extins să primească `down_name`.
  Direcția de dus nu se schimbă deloc — același fișier, aceeași amprentă. Se schimbă din ce fișier se
  citește inversul, iar acel invers **nu rulase niciodată**, deci nu se falsifică niciun istoric.
  `C31` rămâne respectat: niciun fișier aplicat nu e editat
- **Patru cerințe ale proprietarului, toate intrate ca test, nu ca intenție:** ordinea triggere →
  politici → funcții, verificată; **fără `CASCADE`**, fiindcă un `CASCADE` nu se oprește la ce a
  creat migrarea și poate șterge tăcut obiecte atașate între timp de altă migrare; rotația rulată
  **sub `evidenta_owner`**, rolul real, fiindcă drept superuser ar trece întotdeauna și ar eșua în
  producție; și **rotație, nu inversare** — `down`, apoi `up`, cu catalogul comparat înainte și după
- **A doua aplicare e cea care prinde ce scapă primei verificări:** funcția rămasă, numele de
  politică ciocnit, triggerul orfan. „N-a aruncat" nu e afirmația; „baza e unde a plecat" este
- **Un test asertează că inversul ORIGINAL încă eșuează** cu „must be owner of function". Fără el,
  nimic n-ar distinge „am reparat un defect" de „am rescris un fișier care mergea"
- **Motivul reversibilității lui `0028` era greșit la mine, deși concluzia era corectă.** Scrisesem
  „șterge doar datele pe care el le-a creat" — adevărat azi, **se rupe tăcut** din clipa în care
  producția scrie token-uri reale. Motivul real e **regenerabilitatea**: o amprentă de token e
  efemeră, deci nu se pierde informație, se pierd sesiuni. Scris în fișier ca atare, cu consecința
  operațională: **cine derulează înapoi deloghează pe toată lumea**
- **Gardianul de recidivă acceptă ambele declarații**, și asta e cerința, nu o slăbiciune:
  ireversibilitatea forțată acolo unde ceva e reversibil de drept e o minciună la fel de dăunătoare
  ca `noop`-ul pe ceva ireversibil. Iar `"reversible-tested"` nu e etichetă — gardianul cere ca
  fișierul să fie în lista rotită efectiv
- **`OD-64` închisă.** 41 de teste noi (27 de rotație, 14 de convenție); `0036_ledger` declară
  „reversibil, cu invers testat"

**2026-08-26, primul ecran real — și trei lucruri corectate de o cercetare care a ajuns la timp:**

- **Întrebarea proprietarului a fost dreaptă:** 687 de teste în spate, iar pe ecran o demonstrație de
  formatare. Interfața era la **o singură decizie** distanță — `OD-35` —, iar eu tot alesesem muncă
  de backend fără să ofer vreodată să mișc decizia. `ADR-042` a scris-o ca propunere cu valori, nu ca
  întrebare, iar proprietarul a cerut implementarea
- **Livrat:** `shared/DataGrid` — singura intrare pentru grile de citire (`C16`, `C17`) —, regula
  ESLint pentru `C21` **cu probă că refuză**, `GET /api/v1/companies`, și **planul de conturi ca
  ecran**, peste API-ul care exista din F1.1 fără niciun consumator
- **Un gol care nu se vedea din backend:** clientul n-avea cum să afle un `company_id`. `whoami`
  întoarce tenantul și utilizatorul, iar rutele contabile cer o companie. Endpointul nu filtrează
  nimic — politica de pe tabelă o face; un `.filter()` acolo ar fi creat impresia de siguranță pe
  care `C3` o scoate din ecuație. Două teste: trei companii, doar cea cu acces e vizibilă
- **`ADR-042` a fost revizuit în aceeași zi, după cercetarea sesiunii paralele — și revizuirea e
  vizibilă tocmai fiindcă acceptarea fusese dată pe alte cifre.** Trei corecții, fiecare verificată
  de mine înainte de a fi acceptată:
  1. **`--density-*` nu generează niciun utilitar în Tailwind v4.** Construit CSS-ul: variabila e
     emisă, utilitarul nu. Cu `--spacing-*`, build-ul produce
     `.h-row-compact{height:var(--spacing-row-compact)}`. Cu numele greșit, §5 cerea ESLint-ului să
     interzică ceva ce nimeni n-ar fi putut scrie
  2. **Valorile sunt acum 40/32/24, implicit 32** — prior art, nu aritmetica mea. Carbon, Sage și SAP
     livrează fiecare exact aceste trepte; **28 e orfan**, doar AG Grid Balham îl are. Treapta de 40
     lipsea complet din propunerea mea, iar ea e modul de citire
  3. **Motivarea antetului era greșită, deși valoarea era corectă.** Scrisesem că „o ancoră își pierde
     rolul la aceeași înălțime cu conținutul"; Carbon spune explicit contrariul. Cea mai utilă dintre
     cele trei: o valoare corectă cu o motivare greșită supraviețuiește până când cineva schimbă
     valoarea urmând motivarea
- **`WCAG 2.2 SC 2.5.8`, scris în ADR ca să nu vină de la un audit:** la 24px, minus 1px bordură,
  rămân 23 — sub minimul de 24×24. Deci `dense` nu poartă butoane-iconiță în rând
- **`DataGrid` nu virtualizează, și golul e numit în docstring.** Randează tot ce primește, ceea ce e
  corect pentru un plan de conturi și greșit pentru o Carte Mare la volum. `ADR-001` rezervă CSS-ul
  de mână exact pentru asta, exact în fișierul acela (`C25`); cusătura e `rows` și nimic deasupra ei
  nu se schimbă când vine virtualizarea

**2026-08-26, privilegiile funcțiilor `rls` — o apărare scrisă, crezută în vigoare, inexistentă:**

- **Reparat defectul de securitate găsit ieri.** `0041_rls_function_privileges` retrage `EXECUTE`
  de la PUBLIC pe toate cele 25 de funcții din schema `rls` — de data asta **sub rolul care le
  deține**, deci cu efect — și îl acordă lui `evidenta_app` pe mulțimea măsurată: funcțiile apelate
  din Python reunite cu cele care apar în expresiile politicilor, fiindcă o politică se evaluează ca
  utilizatorul care interoghează. **Paisprezece.** [ADR-043](decisions/043-privilegiile-functiilor-rls.md)
- **Măsurat înainte și după, pe baza reală:** 22 de funcții cu `EXECUTE` pentru PUBLIC → **0**.
  `rls.journal_entry_balanced()` apelată sub rolul aplicației răspunde acum `permission denied`;
  ieri executa. Suita: **673 trec** cu privilegiile retrase, deci mulțimea acordată e exactă — n-a
  fost nevoie de nicio corecție după prima rulare
- **Prevenirea nu stă în schemă, și asta s-a măsurat, nu presupus.**
  `ALTER DEFAULT PRIVILEGES … REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` pare mecanismul evident și
  **nu funcționează**: încercat în ambele forme, în aceeași tranzacție și într-una nouă după commit,
  o funcție creată ulterior iese cu ACL implicit, deci din nou deschisă. L-am scos din migrare în loc
  să-l las acolo părând că apără ceva
- **Doi gardieni, fiindcă nimic n-ar fi prins clasa asta.** `schema_guard/test_function_privileges.py`
  interoghează catalogul pe o bază construită de la zero — prima migrare care adaugă o funcție fără
  să-i retragă PUBLIC-ul face suita roșie; lista celor paisprezece e **declarată acolo**, deci
  lărgirea ei e o editare pe care cineva o citește. `architecture/test_reverse_migrations.py` refuză
  orice `.down.sql` **nou** care șterge o funcție `rls.` fără `SET LOCAL ROLE`
- **`OD-64` înregistrată în `T0`:** cele opt fișiere `.down.sql` care nu se derulează înapoi. `C31`
  le face append-only, deci corecția e fișier nou plus migrare nouă, peste șase module — sarcină
  proprie. Sunt enumerate în gardian ca excepție care **poate doar să scadă**, cu un test care
  refuză o listă rămasă în urma fișierelor
- **Reversul migrării mele funcționează**, verificat rulând `migrate rls zero` și reaplicând — ceea
  ce e chiar diferența față de cele opt

**2026-08-26, restul neblocat din F1, orchestrat pe șase agenți — și două defecte găsite rulând:**

- **Livrat, toate verzi:** `F1.4.3` cei șase invarianți ai motorului (22 teste), `F1.5.3` perioada
  fiscală TVA ca entitate distinctă (20), `F1.7.1` nota manuală prin motor (36), `F1.7.2` soldurile
  inițiale (45), `F1.7.3` șabloanele de operațiuni (42). Suita: **673 trec**, 1 sărit — verificată
  independent, de două ori, cu rezultat identic. `ruff`, `mypy` și gardienii curați
- **`REVOKE ... FROM PUBLIC` nu revocă nimic dacă nu-l emite proprietarul funcției — și nu-l emite.**
  Măsurat pe `pg_proc.proacl`, apoi **demonstrat prin apel**: **18 funcții `SECURITY DEFINER` din
  schema `rls` sunt executabile de PUBLIC**, deși niciuna n-a fost acordată lui `evidenta_app`.
  Printre ele cele patru `auth_*` (calea de dinaintea contextului, ADR-026), `resolve_session`,
  `resolve_tenant_by_subdomain`, `provision_engagement_company_access` și
  `revoke_engagement_company_access`. Rulate sub rolul aplicației: `auth_lookup_user` **execută**;
  `provision_engagement_company_access` ajunge la linia 9 din corpul ei și e oprită doar de garda
  internă, nu de privilegii. Cauza: funcțiile se creează sub `SET LOCAL ROLE evidenta_rls`, iar
  `REVOKE`-ul e emis după `RESET ROLE`, de owner — iar un `REVOKE` de la cine nu deține funcția dă
  **WARNING, nu eroare**. Apărarea e scrisă în migrare, se crede în vigoare, și nu e
- **Opt fișiere `.down.sql` nu se pot derula înapoi.** `evidenta_owner` e `NOINHERIT`, deci
  apartenența la `evidenta_rls` nu-i dă privilegiile fără `SET ROLE`: fișierele de dus creează
  funcțiile sub `SET LOCAL ROLE`, cele de întors le șterg ca owner și cad cu „must be owner of
  function". Confirmat rulând `migrate ledger zero`. Afectate: `0014`, `0015`, `0016`, `0023`,
  `0028`, `0030`, `0032`, `0036`. `C30` spune „`reverse_sql` nu este opțional" — reversul **există
  și nu rulează**. `0036_ledger` e pe drumul de întoarcere al întregii contabilități, deci nimic
  din F1 nu se poate derula azi
- **Amândouă sunt din aceeași familie ca restul zilei:** SQL-ul a rulat, nimic n-a strigat, efectul
  n-a existat. Niciuna nu e regresie a sesiunii — sunt în fișiere din F0, comise; `0036` e singurul
  al meu. Corecția e fișier nou și migrare nouă (`C31`), peste șase module: **sarcină proprie, cu
  ADR**, nu reparație în trecere
- **Ce au refuzat agenții să decidă, fiecare cu motivul:** formulele de sumă din șabloane și nota în
  valută (`DNB-08`, rotunjirea — deschisă); cumulativele payroll modelate ca formă, fără conținut
  (`OD-04`); clauza „linie zero declarată de handler" din ADR-036 §5.2.5, care **contrazice**
  `journal_line_one_side_only` din `0036_ledger` — ori se schimbă `CHECK`-ul, ori se șterge clauza
  înainte de `Acceptat`; și niciun cod de cont nicăieri (`OD-22`/`OD-23`)
- **Backlogul numește un `event_type` pe care vocabularul îl refuză:** `opening.balance.posted` are
  trei segmente, iar `registry.NAME` impune două (Spec B §1.4, ADR-038). A doborât `check`, `mypy` și
  suita întregului arbore partajat vreo cincisprezece minute. Livrat ca `opening.balance_posted`;
  **rândul din backlog trebuie corectat**, altfel următorul îl retastează

**2026-08-25, F1.4.1 și un dezacord de o zi între aplicație și bază:**

- **F1.4.1, partea care e a mea, e livrată:** `accounting/posting/resolution.py` — transformă un
  eveniment stocat în cele trei argumente de care are nevoie selecția, iar selecția însăși rămâne
  unde e, în `events.registry`. **Nu ia niciodată un `AccountingEvent`**: `D6` interzice atingerea
  modelelor altui modul, iar excepția de compunere de schemă acoperă `models`, nu servicii — deci
  apelantul, care are evenimentul, dă valorile. Semnătura *este* granița. 10 teste, fără bază de date
- **Un `{}` nu mai poate trece drept „nicio capabilitate".** Instantaneul e citit dintr-o formă
  versionată, iar lipsa versiunii sau o versiune mai nouă sunt **refuz**, nu implicit. Alternativa
  tentantă — „nu știu, deci nimic" — e cel mai prost răspuns disponibil: o companie cu TVA ar primi
  tăcut tratamentul scris pentru una fără, înregistrarea ar fi echilibrată, iar nimic din aval n-ar
  părea greșit
- **Forma pe care o ceruserăm era greșită, și sesiunea paralelă a corectat-o.** Cerusem `requires`
  ca **poartă** — refuză când lipsește o capabilitate. `R26` cere altceva: „aceeași operațiune **se
  contabilizează diferit**". Un refuz nu e „diferit". `requires` e **criteriu de selecție**: două
  tratamente ale aceluiași eveniment coexistă pe aceeași zi, unul pentru o companie plătitoare de
  TVA și unul pentru una care nu e
- **Suita a picat pe un test care nu e al meu, și defectul e de sistem, nu de test.** Măsurat **pe
  calea reală**, prin conexiunea Django: `SHOW timezone` întoarce **`UTC`**, fiindcă `USE_TZ = True`
  face Django să seteze fusul sesiunii la UTC la fiecare conexiune. `date.today()` întoarce
  **2026-08-26** (fusul `Europe/Chisinau` din settings, pus în mediu), iar `current_date` întoarce
  **2026-08-25**. Două zile calendaristice diferite, simultan, în același proces
- **Prima mea măsurătoare era pe calea greșită și am corectat-o.** Prin `psql`, `SHOW timezone` dă
  `Europe/London` — implicitul mașinii din `postgresql.conf`. Dar aplicația nu trece niciodată pe
  acolo. Diferența reală e deci **Chișinău față de UTC: trei ore în fiecare noapte**, nu două, iar
  varianta „aliniem sesiunea de bază la fusul produsului" **este** o singură linie, dar nu oricare:
  măsurat, `DATABASES['OPTIONS'] = {'options': '-c timezone=...'}` e **suprascris** cu UTC în
  `init_connection_state`, în timp ce `DATABASES['TIME_ZONE'] = 'Europe/Chisinau'` **ține**. Nu
  lupți cu framework-ul, îi spui — afirmația mea anterioară era prea tare
- **Cele două precauții pe care le ridicasem sunt măsurate, și amândouă cad.** (1) `manage.py check`
  cu `DATABASES['TIME_ZONE'] = 'Europe/Chisinau'` și `USE_TZ = True`: „no issues". (2) `__date`
  **nu depinde de fusul conexiunii**: un moment stocat la `2026-08-25 22:30 UTC` iese ca
  **26 august** și cu sesiunea pe `UTC`, și cu ea pe `Europe/Chisinau` — Django trimite numele
  fusului ca **parametru** în `AT TIME ZONE %s`, luat din fusul Django activ, nu din conexiune
- **Ceea ce schimbă diagnosticul, nu doar o precauție: ORM-ul răspunde deja corect.** Fiecare
  interogare Django grupează pe **ziua de la Chișinău**. Singurele care răspund în UTC sunt cele
  care citesc `current_date` în SQL scris de mână. Deci nu e o problemă sistemică de fus — e
  **izolată exact acolo unde am găsit-o**
- **Raza de acțiune, numărată:** `current_date` apare de **7 ori, în 2 fișiere** —
  `infra/bootstrap/0003_access_predicates.sql` (4, în `has_tenant_access` și `has_company_access`)
  și `infra/migrations/0032_engagement_provisioning.up.sql` (3). Restul apariţiilor de ceas din
  `infra/` sunt `now()`, care compară **momente**, nu zile: un `timestamptz` față de `now()` e
  corect în orice fus. `OD-63` e deci o decizie despre șapte linii, nu despre sistem
  *Găsit fiindcă `evidenta-2f` a măsurat `UTC` unde eu măsurasem `Europe/London`, în aceeași oră pe
  aceeași mașină; amândouă erau adevărate, pentru căi diferite*
- **Consecință secundară:** `make bootstrap` rulează prin `psql` (London), migrațiile prin Django
  (UTC). Astăzi niciuna nu conține logică de dată, deci nu produce nimic — dar cele două jumătăți
  ale schemei se aplică sub fusuri diferite
- **Consecința nu e testul.** `rls.has_tenant_access` decide dacă un engagement e viu prin
  `valid_to >= current_date` — **ziua bazei** —, iar serviciile calculează datele în Python — **ziua
  aplicației**. În fiecare noapte, timp de **trei ore** (00:00–03:00 la Chișinău), un engagement pe
  care aplicația îl consideră
  expirat e încă viu pentru predicat. Și nu doar engagement-ul: fiecare fereastră de valabilitate din
  produs e interogată cu o dată din Python, iar predicatul citește ceasul bazei. Într-un sistem
  contabil, ziua decide în ce perioadă cade o postare
- **Testul a prins-o din întâmplare** — e singurul care compară o dată calculată în Python cu un
  `current_date` din SQL. A trecut toată ziua fiindcă până la 22:00 BST cele două zile coincid, și
  **va redeveni verde singur după 01:00**, ceea ce e partea neplăcută. **Nu l-am adaptat ca să
  treacă**: `CLAUDE.md` §4 interzice exact asta, iar aici testul are dreptate și codul nu
- **Fusul serverului nu e ales de nimeni, e nimerit** — `pg_settings` dă `TimeZone = Europe/London`
  cu `source = configuration file`, fișier **din afara repository-ului**, iar nimic din `infra/`,
  `.env.example`, `infra/docker/` sau `DATABASES.OPTIONS` nu-l setează. Pentru aplicație asta e însă
  **irelevant**, fiindcă Django îl suprascrie cu UTC; rămâne relevant pentru tot ce trece prin
  `psql`, adică pentru bootstrap
- **Proiectul are deja tiparul reparației.** `0000_locale_guard.sql` există fiindcă *colația* e o
  proprietate de mașină care „funcționează perfect și sortează greșit pentru totdeauna", iar antetul
  lui spune exact ce se aplică și fusului: „fail-closed nu ajunge, trebuie și fail-loud". Un gardian
  de fus la bootstrap costă cincisprezece linii. Nu înlocuiește direcția de mai jos, o completează:
  una scoate ceasul din predicat, cealaltă verifică faptul că baza e configurată cum crede produsul
- **Direcția pe care o propun, nu o iau:** predicatele să nu mai citească `current_date`, ci să
  primească data ca parametru. Proiectul a decis deja de mai multe ori că un rezolvator care poate
  citi ceasul e un defect — `R18`, `postable_accounts`, `resolve_parameter`, `active_profile` iau
  toate data ca parametru. Predicatul de acces e singurul loc care și-o ia singur

**2026-08-25, profilul de capabilități — coloana pe care nimeni n-o putea completa:**

- **Pornit ca F1.4.1 și prima constatare a schimbat sarcina:** jumătate din ea era deja scrisă.
  `events.registry.resolve_handler(name, accounting_date)` face exact selecția „`event_type` + dată
  efectivă, zero sau două e eroare", livrată la F1.3.2 de sesiunea paralelă. Nu am rescris-o — ar fi
  fost a doua copie a aceleiași reguli. Ce lipsea din criteriu e filtrarea pe **profilul de
  capabilități**, pe care `R26` o cere ca input **explicit**
- **`capability_snapshot` era un argument obligatoriu pe care nimic din produs nu-l putea produce.**
  `platform/capabilities` avea doar modele, **niciun serviciu** — deci fiecare apelant al lui
  `emit(...)` își inventa valoarea, iar unul care trimitea `{}` obținea o companie fără nicio
  capabilitate: tăcut, plauzibil, și exact opusul a ce cere `R26`
- **Livrat `platform.capabilities.services.profile`.** Trei alegeri, fiecare derivată, nu preferată:
  (1) **două mulțimi, nu una** — `activated` și `usable`; `R25` face din activare o entitate cu
  stare de inițializare, iar o capabilitate `in_progress` e pornită și **nefolosibilă**, fiindcă
  postarea sub ea produce chiar înregistrările pe care inițializarea urmează să le pună la punct;
  (2) **uniune între nivelul de tenant și cel de companie, nu precedență** — modelul n-are cum să
  exprime o negare, deci „oricare rând în vigoare" e singura citire pe care schema o suportă, iar
  Spec A §1.8 nu spune nimic despre precedență, deci n-am ales, am derivat; (3) `as_snapshot()` cu
  `version` și liste sortate, fiindcă ajunge în `jsonb` și e citit peste ani — două profiluri
  identice nu trebuie să arate diferit
- **Fereastra e half-open, rescrisă, nu împrumutată.** `platform` nu importă niciun alt strat, deci
  `fiscal.parameters.in_force` nu se poate refolosi; patru linii de query duplicate sunt mai ieftine
  decât o inversare a grafului de dependențe, iar testul fixează ziua de graniță
- **Restanță scadentă, semnalată, neluată:** Spec A §1.8 cere ca `effective_from` să coincidă cu
  începutul unei perioade contabile — „în F0 în serviciu, **mutată în bază la F1.5**". Nu există
  nici serviciul (modulul n-avea niciunul până azi), nici constrângerea. F1.5 tocmai a aterizat,
  deci partea a doua e scadentă acum
- **O gaură a mea, găsită și reparată în aceeași sesiune:** profilul unei companii **invizibile**
  întorcea capabilitățile de tenant ale apelantului. RLS nu acoperă cazul — rândurile de nivel
  tenant sunt chiar ale apelantului, deci supraviețuiesc politicii oricare ar fi identificatorul de
  companie cerut. Un motor care citea profilul ar fi postat ca și cum acele capabilități se aplicau.
  Acum se verifică vizibilitatea întâi, cu refuz `api.not_found` — absent, nu interzis (IZ-04)
- **6 teste noi** (18 în fișier); suita completă **481 trece**, 1 sărit — numărul crește și de la
  celelalte două sesiuni, care lucrează în același arbore. `ruff`, `mypy` și gardienii curați

**2026-08-25, F1.2.4 — stornoul, plus suprafața publică pe care o uitasem:**

- **Stornoul e livrat** (`ledger/services/reversal.py`): mirror image al înregistrării postate, cu
  **cele două legături** ale lui `R14` — spre evenimentul care a cerut corecția și spre
  înregistrarea anulată. Refuzuri cu cod stabil: ciornă (nu s-a înregistrat nimic, deci n-are ce
  anula), al doilea storno al aceleiași înregistrări (aproape mereu aceeași corecție cerută de două
  ori, iar rezultatul e un registru care anulează de două ori). Stornoul unui storno e permis, cu
  lanțul navigabil în ambele sensuri. **9 teste noi**
- **Liniile se inversează, nu se neagă.** O linie negativă strică rulajele: rulajul debitor al lunii
  ar *scădea* cu corecția în loc să crească, iar balanța ar înceta să arate activitatea reală. Spec
  B §9.2 o cere, iar `journal_line_one_side_only` o face oricum imposibil de scris
- **Cursul stornoului este cel original, nu cel de azi**, și e cazul cel mai ușor de greșit: un curs
  proaspăt ar lăsa diferența în urmă ca derivă tăcută de sold — iar aceea e diferență de curs,
  eveniment economic propriu cu tratament propriu, nu artefact de rotunjire al unei corecții. Test
  pe o linie în EUR
- **Perioada stornoului rămâne a apelantului.** `ADR-007` e `Propus`, cu trei întrebări de tratament
  contabil nerăspunse, iar Spec B §9.3 spune explicit că F1.2 se poate construi pe structura din
  `ADR-006` cât timp serviciul care *alege* perioada rămâne nescris. Un implicit aici ar fi răspuns
  tăcut la o decizie deschisă
- **`ledger` n-avea nicio suprafață publică — lipsă reală, semnalată de `evidenta-2f`.** Avea
  modele, migrare și teste, dar niciun mod prin care alt modul să facă saltul `linie → înregistrare`
  fără să importe modelele mele, ceea ce `D6` interzice (excepția de compunere de schemă acoperă
  doar `models`, nu `services`). Adăugat `services/lineage.py`: `origin_of_line` face **două
  salturi într-o citire**, fiindcă întrebarea următoare e mereu „și ce eveniment a produs
  înregistrarea". **Întoarce date, niciodată modele** — un `JournalEntry` predat peste granița de
  modul e chiar cuplajul pe care `D6` îl oprește, ajuns printr-un serviciu în loc de un import
- **26 de teste de registru**, suita completă **469 trece**, 1 sărit; `ruff`, `mypy` și gardienii
  curați. **Nimic nu e comis:** `origin/main` e la `cac570f`, iar `coa/`, `ledger/`, `periods/` și
  `platform/api/authentication.py` sunt toate netrackate. „Verde local" și „verde pe main" arată
  identic din interiorul unei sesiuni, iar `git status` nu spune nimic despre ce e împins — de aceea
  se scrie aici

**2026-08-25, F1.2 — registrul, și un trigger amânat care nu face ce pare că face:**

- **Livrat ca o singură migrare: F1.2.1, F1.2.2 și F1.2.3.** Nu comasare de comoditate — toate trei
  sunt *forma lui `journal_line`*, iar aceea e tabelă append-only de volum mare: cele trei date
  (ADR-039 §9), cele patru câmpuri de valută (ADR-039 §3) și cele cincisprezece coloane de
  dimensiuni (ADR-029) există de la primul rând tocmai fiindcă adăugarea lor ulterioară e migrarea
  pe care nimeni n-o vrea. Trei migrări succesive peste aceeași tabelă ar fi fost exact ce regulile
  există să prevină. **458 de teste trec** (15 proprii); `ruff`, `mypy` și gardienii curați
- **Trei mecanisme în bază, niciunul exprimabil în Django:** echilibrul verificat la commit,
  imutabilitatea după postare, refuzul de a posta într-o perioadă închisă. Plus lipsa `DELETE`
  pentru rolul aplicației pe ambele tabele — corecția e storno, nu ștergere
- **Constatarea care contează, găsită rulând, nu citind:** un `CONSTRAINT TRIGGER` amânat **nu
  rulează o dată la commit — rulează pentru fiecare eveniment din coadă**, cu `NEW` înghețat la
  momentul lui. Liniile se inserează una câte una, deci coada conține și starea de după prima linie,
  dezechilibrată prin construcție. Scris cu `NEW`, mecanismul din Spec B §1.6 respinge la commit
  exact înregistrările **corecte**, iar amânarea nu rezolvă nimic. Funcția **recitește rândul**;
  atunci toate evenimentele din coadă văd starea finală. A picat pe prima linie a primului test
- **Spec B se contrazice, și §1.6 câștigă.** §1.2 listează `CHECK (total_debit = total_credit)` pe
  `journal_entry`. Un `CHECK` imediat se declanșează la prima actualizare a totalurilor și face
  imposibil de scris o înregistrare corectă — măsurat, nu dedus. Constrângerea **nu s-a construit**;
  triggerul amânat este mecanismul, iar `CHECK`-ul ar fi fost o a doua copie a lui, care nu poate
  funcționa
- **Clauza de îngustare din ADR-004 e pe toate trei tabelele noi**, cu test care arată că îngustează
  în fapt: două companii ale aceluiași apelant, context îngustat pe una, liniile celeilalte pur și
  simplu nu sunt acolo. Pe tabele **noi** nu există motiv de abatere — costul azi e zero, iar
  adăugarea ei mai târziu pe `journal_line` ar fi migrare pe cea mai mare tabelă din sistem.
  `OD-57` rămâne, pentru cele vechi
- **Am rupt arborele pentru trei sesiuni, cu o linie.** `models.Index(fields=["company", ...])` pe
  `JournalLine`, care are `company_id` fiindcă `R21` îi interzice cheile străine — registrul de
  aplicații Django cădea la import, deci **fiecare** test din arbore, nu doar ale mele. Cauza nu e
  linia, e cum a ajuns acolo: convertisem patru indecși cu înlocuiri de șir, **trei aveau `assert`
  că șirul căutat există și a patra nu**, iar între timp `ruff format` reflowase exact acea
  declarație pe o singură linie. Înlocuirea a trecut tăcut. Aceeași clasă cu
  `{entry["name"]: entry}` din gardieni: pierde tăcut și raportează succes
- **Și a doua jumătate a aceleiași greșeli:** reparat modelul, `manage.py check` a spus „no issues"
  — fiindcă **`check` nu încarcă migrările**, iar copia greșită rămăsese în migrarea generată din
  model. Proprietatea e deja scrisă în `platform/rls/sql.py`, notată acolo pentru checksum-uri. Ca
  poartă după o editare de model, `check` nu e suficientă; `makemigrations --check` sau o rulare de
  teste este
- **Funcțiile din schema `rls` se creează prin `SET LOCAL ROLE evidenta_rls`**, tiparul din `0014`
  și `0032`: schema aparține acelui rol, iar owner-ul are doar `USAGE`. Le crease ca owner, iar
  migrarea pica cu „permission denied for schema rls". Și `evidenta_rls` n-are niciun privilegiu de
  tabelă implicit — se acordă punctual, altfel triggerele cad la prima linie inserată
- **`_TRIGGER_STATE` din `tests/isolation/conftest.py` acoperă acum și `accounting_event_no_delete`**
  — și regula generală, pe care o scrisesem greșit prima dată, e acum lângă listă. Nu „tabela era
  goală": modulul care deține `accounting_event` **inserează** evenimente în testele lui, dar prin
  ORM, în tranzacția testului, care se derulează înapoi — deci rândurile nu se comit niciodată,
  curățenia următoare nu potrivește nimic și un trigger `FOR EACH ROW` nu se declanșează pe zero
  rânduri. `seed()` scrie pe conexiunea de administrare cu `autocommit`, deci rândurile lui
  supraviețuiesc. **Regula utilă: o tabelă are nevoie de intrare în `_TRIGGER_STATE` dacă are
  trigger care refuză `DELETE` *și* e seedată prin `seed()`.** Cine scrie doar teste prin ORM n-o
  descoperă niciodată — motiv pentru care tabela și triggerul au putut intra în același commit fără
  ca nimic să se plângă. Măsurat de `evidenta-2f`, care a scos linia și a rulat cele 27 de teste ale
  lui, verzi în ambele feluri

**2026-08-25, F1.5 — perioadele și exercițiul, plus jumătatea de criteriu care nu se putea închide:**

- **Ce s-a livrat:** `accounting/periods` — `fiscal_year` și `period`, `0035_periods.{up,down}.sql`,
  serviciile de deschidere, închidere, redeschidere și blocare, plus primitiva pe care o va apela
  motorul. **25 de teste sub rolul de aplicație**; suita completă **427 trec**, `ruff` și `mypy`
  curate
- **De ce F1.5 și nu F1.2.1, deși backlogul o numea „singurul punct de sincronizare":** `journal_entry`
  are `period_id` **și** `accounting_event_id` `NOT NULL REFERENCES`, iar `journal_entry` **nu** e în
  `infra/schema/append_only.toml` — deci FK-urile lui sunt reale, spre deosebire de cele ale liniei.
  Ordinea e inversă față de diagramă: `period` + `accounting_event` → `journal_entry`. Trei sesiuni au
  ajuns la aceeași concluzie independent, iar backlogul a fost corectat în `f070e32`
- **Exercițiul aprilie–martie e testul implicit, nu cazul exotic.** O suită scrisă pe
  ianuarie–decembrie ar trece cu presupunerea calendaristică intactă, ceea ce e chiar defectul pe care
  ADR-039 §6 îl evită. Periodele sunt **generate** din exercițiu, deci nimeni nu tastează o lună;
  `period_no` numără în interiorul exercițiului, deci perioada 1 e aprilie, nu luna a patra
- **Ce s-a impus în bază, nu doar în serviciu:** perioada e **exact o lună calendaristică** (`CHECK`);
  exercițiul nu depășește douăsprezece luni; exercițiile și perioadele nu se suprapun (`EXCLUDE USING
  gist`); `locked` e **terminală prin trigger**; iar rolul aplicației **nu are `DELETE`**. Motivul e
  unul singur, scris în migrare: importatorul 1C și migrările de date ocolesc serviciul, iar acelea
  sunt exact căile pe care un exercițiu depus s-ar redeschide tăcut
- **Criteriul F1.5.1 se închide pe jumătate, și partea lipsă e numită.** „Postarea într-o perioadă
  închisă e refuzată **de motor**" nu se poate demonstra fără motor. S-a livrat în schimb
  `assert_postable(company_id, accounting_date)`, cu **două** coduri de refuz — `period_not_open` și
  `period_locked` — fiindcă una se poate redeschide și cealaltă niciodată. Triggerul `BEFORE INSERT`
  din Spec B §6.3 aparține lui F1.2.1, unde există tabela pe care stă
- **`OD-58` nouă:** Spec B §6.1 listează patru stări, ADR-039 §8 listează trei. Implementate trei, cum
  cere regula din backlog („ADR-ul câștigă"); a inventa semantica lui `closing` ar fi fost o decizie de
  flux de lucru luată în cod. Adăugarea unei stări rămâne migrare aditivă
- **`OD-57` nouă, măsurată peste toate migrările:** șablonul din ADR-004 are **patru** clauze, iar a
  patra — îngustarea pe `app.current_company_id()` — apare în **patru politici din unsprezece**;
  `capability_activation` e singura care scrie de ce nu o are. Cealaltă jumătate: `middleware.py:95`
  construiește contextul **fără** `company_id`, deci un task Celery poate îngusta și o cerere HTTP nu.
  Semnalată de sesiunea paralelă, verificată aici. `period` și `fiscal_year` o poartă — costul e zero
  azi și o migrare peste o tabelă citită de motor mâine
- **`DNB-07` rămâne deschisă și se vede în ce lipsește:** niciun `period_module_lock`, nicio coloană de
  modul. Comportamentul de azi *este* varianta (A), iar asta e scris în modul, nu lăsat să fie
  descoperit la F1.5.4
- **Două corecturi în backlog, găsite de sesiunea care a livrat F1.1:** conținutul planului de conturi
  e `OD-23`, nu `OD-22`; iar „scriere doar prin `P-4`" nu se putea îndeplini — `P-4` inserează
  parametri fiscali, iar planul de conturi nu e parametru fiscal. Exact `OD-56`
- **Ce nu s-a rulat:** lanțul de review cu agenți (`schema-reviewer`, `tenancy-guard`) — sesiunea are
  agenții dezactivați. Ce a rulat: gardianul de model, gardianul de dependențe, suita de izolare și
  cea de penetrare, toate verzi
- **Nu s-a construit F1.5.3** (perioada fiscală TVA). Are entitate proprie prin ADR-039 §7 și rămâne
  sarcină proprie: în F1 n-are încă niciun cititor, iar o tabelă fără cititor e chiar tiparul prins de
  două ori aici

**Continuarea aceleiași sesiuni, după livrare — cinci decizii deschise, niciuna găsită citind
documente:**

- **`OD-59`** — baza de dezvoltare a divergeat de migrări: șapte tabele business cu RLS oprit și zero
  politici, deși toate cele 33 de migrări sunt înregistrate ca aplicate. Discriminantul care arată că
  SQL-ul **n-a rulat niciodată** acolo: lipsesc și colațiile din aceleași fișiere. Cauza probabilă —
  `run_sql_file` adăugat într-o migrare **deja aplicată**, pe care Django n-o mai rulează
- **`OD-63`** — aplicația și baza nu sunt de acord ce zi este: `TIME_ZONE = Europe/Chisinau` în
  settings, iar sesiunea de bază rulează pe **UTC**, fiindcă `USE_TZ = True` o setează la fiecare
  conexiune; `rls.has_tenant_access` decide valabilitatea cu `current_date`. **Trei ore pe noapte**,
  un engagement expirat pentru aplicație e viu pentru predicat. Testul care a prins-o **se vindecă
  singur** după 03:00. *Prima măsurare, a mea, dădea `Europe/London` — corectă, dar făcută prin
  `psql`, o cale pe care aplicația n-o folosește; prinsă de `evidenta-2f`, reverificată prin
  conexiunea Django*
- **`OD-62`** — F1.5, așa cum e livrat, **refuză cazul din ADR-039 §6 lit. (d)**: exercițiul unei
  entități nou-create începe la data înregistrării de stat, iar `_validate_window` cere ziua întâi a
  lunii. Am impus în validare o regulă mai largă decât e legea. Nereparată deliberat: dacă prima
  perioadă e martie întreagă sau 12–31 martie e întrebare de tratament, nu de cod
- **`OD-61`** — obligația din Spec A §1.8 („`effective_from` coincide cu începutul unei perioade")
  n-a existat niciodată, nici în serviciu, nici în bază, și e scadentă acum. Mutarea în bază ar
  inversa graful de module tăcut, fiindcă **gardianul de dependențe nu vede SQL**. Variantă propusă:
  cerința se reduce la o regulă de dată pură, fiindcă perioada e strict lunară
- **`OD-60`** — un eveniment eșuat pe o perioadă închisă nu se repostează singur, iar coada l-ar
  plimba tăcut. Găsită la interfața dintre două sesiuni, nu în niciuna dintre ele
- **Blocajul nescris:** `F1.4.2` spunea `Blocat de: —`, deși registrul are `OD-55` cu termen „înainte
  de F1.4" și ADR-036 e `Propus`. Clasa inversă celei curățate dimineață — nu expirat, ci **nescris**
- **Ce leagă patru dintre defectele zilei:** nu mecanismul, ci semnalul. **Verde nu înseamnă
  verificat, înseamnă că nimic n-a strigat** — proprietate a mașinii, stare divergentă de la migrări,
  sau calea care ar fi eșuat n-a fost atinsă

**2026-08-25, API-ul planului de conturi — și un mecanism decis, construit pe sfert:**

- **Cerut explicit de proprietar**, după ce frontend-ul a fost respins ca următor pas: un ecran de
  plan de conturi este ecran cu grilă, iar `OD-35` (scara de densitate) e „înainte de primul ecran",
  `C16`/`C17` cer `DataGrid`/`EntryGrid`, care sunt `F1.G1`/`F1.G2` și vin după F1.2. Sarcina nu
  există în backlogul F1 — acesta nu conține nicio sarcină de API
- **Livrat:** `/api/v1/accounting/coa/` — `templates`, `companies/{id}/chart`,
  `companies/{id}/accounts` (cu `?on=` pentru conturile postabile la o dată), `accounts/{id}`
  pentru redenumire, blocare și închidere. **Nicio scriere prin serializator:** fiecare mutație
  trece prin servicii, unde stau regulile Spec B §2.4; un `ModelSerializer.save()` ar fi fost a doua
  cale pe lângă toate trei
- **Convenția DRF care lipsea, pusă unde îi e locul.** `REST_FRAMEWORK` avea `IsAuthenticated` și
  **zero clase de autentificare**, deci orice endpoint DRF ar fi răspuns 401 pentru exact cookie-ul
  cu care endpointurile Django simple răspundeau normal. `platform/api/authentication.py` adoptă
  identitatea stabilită de middleware — nu rezolvă sesiunea a doua oară, fiindcă două locuri care
  decid cine e apelantul ajung să se contrazică. Plus randare JSON: API-ul navigabil cere
  `rest_framework` în `INSTALLED_APPS` și transformă o eroare de negociere într-un 200 cu HTML
- **Compania stă în cale, tenantul niciodată** (`C8`). Iar asta a scos la iveală o gaură care nu e a
  acestei sesiuni: **corpul cererii putea muta scrierea în altă companie.** Ambele companii fiind
  ale apelantului, RLS le permite pe amândouă — deci `parent_id` din corp ar fi câștigat tăcut în
  fața căii. Refuzat acum în view, cu test care arată că subcontul nu apare nicăieri
- **`app.company_id` este decis, și construit pe sfert.** [ADR-004](decisions/004-company-context.md)
  dă șablonul cu patru clauze, ultima fiind
  `(app.current_company_id() IS NULL OR company_id = app.current_company_id())`. **Patru din
  unsprezece** tabele company-scoped o poartă — numărătoare peste `infra/migrations/*.up.sql`,
  făcută de sesiunea paralelă. *Prima mea cifră, „una din șase", era greșită și cauza contează: o
  luasem din `pg_policy` în baza de dezvoltare, care driftase de la migrări — vezi mai jos.*
  Iar calea de request **nu setează niciodată** `app.company_id`: `tenancy/middleware.py` construiește
  contextul fără el; singurul loc care îl trimite e decoratorul Celery (`rls/tasks.py`). Deci un task
  poate îngusta pe o companie, iar îngustarea se aplică la o tabelă din șase; o cerere HTTP nu poate
  îngusta deloc. **Nu am reparat două tabele din șase** — jumătate de îngustare e o capcană mai rea
  decât absența ei uniformă: cineva vede că merge pe conturi și presupune că merge peste tot.
  Aparține unei migrări proprii, peste toate șase, cu decizie în spate
- **Baza de dezvoltare nu mai corespunde migrărilor, și nimic n-ar fi spus-o.** Șapte tabele
  business în `evidenta` — `document`, `document_event`, `numbering_counter`, `numbering_template`,
  `fiscal_parameter`, `fiscal_parameter_source`, `fiscal_logic_version` — au **RLS oprit** și zero
  politici, adică exact conținutul lui `0024_documents.up.sql` și `0027_fiscal.up.sql`, deși
  migrările Django sunt marcate aplicate. Cu `relrowsecurity = f`, rolul aplicației vede acolo
  rândurile tuturor tenanților. **Gardianul nu poate vedea asta:** `tests/schema_guard/` rulează pe
  baza de test, construită de la zero la fiecare rulare, unde totul e corect prin construcție. Nimic
  nu verifică vreodată baza împotriva căreia se dezvoltă efectiv; `make rls-report` există fix
  pentru asta și nu-l rulează nimeni. **Nereparat**: `make reset-db` e distructiv și baza e
  partajată de trei sesiuni — cere cuvântul proprietarului
- **`0033_coa.up.sql` cita un ADR inexistent** — `041`, numărul pe care decisesem să nu-l iau după
  ce am găsit intrările deja în `exceptions.toml`. Citările rămăseseră. Semnalat de sesiunea
  paralelă cât fișierul era încă editabil; înlocuite cu sursa reală, verificat prin `diff` peste
  liniile non-comentariu că **nicio instrucțiune SQL nu s-a schimbat**, checksum recalculat
- **Trei sesiuni în același checkout.** `0033` al meu, `0034_accounting_events` al unei a treia
  sesiuni, `0035_periods` al celei de documentație. Baza de test **`test_evidenta` a fost ștearsă
  sub o rulare a mea** de harness-ul altei sesiuni (`DROP DATABASE ... WITH (FORCE)`); rulat mai
  departe cu `POSTGRES_DB=evidenta_s86`. Nota există deja în `tests/conftest.py`, lângă `DROP`
- **12 teste proprii**, toate prin lanțul real: gazdă → tenant, cookie → sesiune, middleware →
  context. Niciunul nu construiește un `TenantContext` de mână — serviciile fuseseră probate într-un
  context primit, iar astea probează că el chiar ajunge. Suita întreagă: **427 trec**, 1 sărit, pe
  arborele comun al celor trei sesiuni; `ruff`, `mypy` și gardienii curați
- **Eroarea de dependențe inversată în backlog, semnalată:** `F1.3.1` și `F1.5.1` declară „Depinde
  de: `F1.2.1`", iar diagrama spune că firele C și D îl așteaptă. În realitate **`F1.2.1` le
  așteaptă pe ele** — `journal_entry` **nu** e în `append_only.toml`, deci `period_id` și
  `accounting_event_id` sunt chei străine reale. Recomandasem greșit contrariul înainte de a verifica

**2026-08-25, F1.1 — planul de conturi, și o coloană care ar fi rămas necitită:**

- **Nu s-a început cu F1.2, și motivul nu e o decizie deschisă, ci o cheie străină.** `journal_entry`
  are `period_id` și `accounting_event_id` amândouă `NOT NULL REFERENCES` (Spec B §1.2), iar
  `period` este F1.5 și `accounting_event` este F1.3. Ledgerul nu poate fi prima tabelă din fază.
  F1.1 nu depinde de nimic neconstruit în afară de `company`
- **Livrat:** `accounting/coa` — `coa_template`, `coa_template_account` (globale, citire liberă),
  `company_chart`, `company_account` (la nivel de companie), `0033_coa.{up,down}.sql`, serviciile
  de instanțiere și de întreținere a planului, **26 de teste proprii**. Total **327 → 354**;
  al 27-lea vine de la gardianul ADR-028, parametrizat per app — `coa` a intrat în el fără
  să fie nevoie de nimic, fiindcă app-ul chiar declară ceva;
  `ruff`, `mypy`, gardianul de dependențe și cel de model, curate
- **Niciun cont.** Nici un cod, nici o denumire — conținutul planului este `OD-23` și cere ordinul
  citat. Aceeași disciplină ca `fiscal_parameter` la F0.8, care n-are nicio cotă. Fixture-ul de
  test folosește coduri pe care niciun plan publicat nu le are (`T1`, `T11`, `T2`), tocmai ca
  primul care îl citește să nu le ia drept SNC
- **Propagarea rămâne nescrisă** (`OD-03` = `DNB-03`). Schema poartă ce cere oricare dintre cele
  patru variante: `valid_from`/`valid_to` pe contul companiei, deci o reclasificare se poate data
  în loc să fie suprascrisă (§2.5, punctul 2)
- **`OD-56` nouă, găsită la implementare:** publicarea unei versiuni de plan de conturi **nu are
  cale privilegiată**. Enumerarea din Spec A §6.2 nu conține niciuna care s-o acopere — `P-4` este
  „inserează parametri fiscali și versiuni de logică", iar planul de conturi e act normativ
  contabil. Blochează încărcarea, nu structura. Înregistrată de sesiunea paralelă, care ține
  registrul
- **Ce nu se șterge, nu se poate șterge.** Rolul aplicației **nu are `DELETE`** pe `company_account`
  și `company_chart`. Un refuz doar în serviciu ar fi ocolit exact de căile pe care un plan de
  conturi se strică: importatorul 1C și migrările de date. Două teste îl demonstrează, sub rolul de
  aplicație
- **Gardianul de dependențe a prins ceea ce citirea n-a prins.** Serviciul de instanțiere importa
  `Company` din `platform.tenancy.models` ca să afle tenantul — `D6`, și chiar cazul pe care regula
  îl vizează („`services/` care importă modelele altui modul"). Reparat prin
  `tenancy.services.access.company_visible_in_context`, perechea lui `tenant_visible_in_context`:
  întoarce un boolean, nu rândul, fiindcă un helper care întoarce `Company` ar face cuplajul să
  reintre printr-un serviciu. Tenantul vine acum din context, unde politica îl cere oricum
- **Trei reconcilieri cu Spec B §2, scrise, nu făcute tăcut:** (1) `company_chart.template_version`
  **nu s-a construit** — `template_id` identifică deja versiunea, fiindcă `coa_template` e unic pe
  `(code, version)`; o copie a șirului dă o a doua sursă pentru aceeași întrebare, iar copia e cea
  care derivează; (2) `company_account.allows_subaccounts` **s-a adăugat** — §2.4 cere ca un subcont
  să apară „sub un cont care permite subconturi", iar pentru un cont creat de companie nu există
  rând de șablon de întrebat, deci fără coloană regula nu se putea impune deloc; (3)
  `coa_template_account.is_system` **a primit un cititor** — este sursa lui `origin` de pe contul
  companiei. §2.2 pune steagul pe șablon, §2.4 contrastează aceleași două feluri pe companie: e un
  singur fapt scris în două locuri. Necablat, ar fi fost a treia coloană pe care n-o citește nimeni
- **Ce e livrat este schema și serviciile — niciun apelant.** Măsurat, nu presupus: `instantiate_chart`
  apare de zece ori, toate în teste. O companie creată azi **nu primește niciun plan de conturi**, și
  nici nu poate: nu există cale de producție care creează o companie (`P-9`, ADR-040, nescrisă).
  Modulul n-are suprafață de API și niciun ecran; următoarele lucruri care îl ating din producție
  sunt onboarding-ul și rezoluția contului din Posting Engine (F1.4)
- **O coloană scrisă de nimic, livrată conștient și numită ca atare:** `company_chart.last_propagation_at`.
  Există fiindcă toate cele patru variante de propagare o cer și niciuna nu-i schimbă înțelesul — dar
  este exact tiparul `covers_all_companies` de la F0.2.4, deci se numește aici în loc să fie descoperită
  a doua oară. Primește cititor odată cu `OD-03`
- **ADR-036 §13.1 („versiune de șablon + strat de suprascriere, nu copie derivată") nu se poate lua
  literal**, și motivul e ledgerul, nu o preferință: `journal_line.account_id` are nevoie de un
  identificator stabil pe viața companiei. Într-un strat pur de suprascriere, un cont de sistem ar
  fi identificat de rândul **global** până la prima redenumire și de un rând de companie după — deci
  identitatea contului s-ar schimba sub o tabelă append-only care deja o referă. Ce urmărește ADR-ul
  supraviețuiește: `template_account_id` plus indexul lui fac propagarea o actualizare peste rânduri
  identificate, nu o migrare de date. ADR-036 e `Propus`, deci nu s-a construit peste el ca peste o
  decizie închisă

**2026-08-25, două decizii de F1 depuse ca ADR — și trei reconcilieri găsite la depunere:**

- **[ADR-036](decisions/036-forma-postarii.md) — forma postării stă în cod**, restul configurării
  stă în date, pe cinci straturi cu destinație diferențiată. Răspunde `DNB-04` (Spec B §3.2) cu
  opțiunea (C), dar cu granița trasată: „forma postării" = câte linii, ce semn, din ce câmp derivă
  suma. Atât. `Propus` — cazurile `C1`–`C5` (metoda de cost, amortizarea, CTA, diferențele de curs,
  repartizarea indirectelor) sunt clasificate pe **presupuneri**, iar `CLAUDE.md` §4 nu le acceptă
  fără SNC citat
- **[ADR-037](decisions/037-conventii-de-platforma.md) — convențiile de platformă** (rotunjire,
  zecimale, granularitatea postării). `Propus`, blocat pe `V1`–`V4`. Ce s-a găsit la depunere:
  **`V1` și `V3` nu depind de accesul SFS** — formularul tipizat (Ordinul MF 118/2017) și Codul
  fiscal sunt publice, deci `DNB-08` era înregistrată ca blocată pe `OD-24` mai mult decât e
- **Trei reconcilieri, consemnate în ADR-uri, nu rezolvate tăcut:** (1) „subconturi definibile de
  client, orice număr rezonabil" contrazicea [ADR-029](decisions/029-dimensiuni-analitice.md),
  `Acceptat` — sloturile *sunt* mecanismul, iar plafonul de cinci există fiindcă dimensiunile sunt
  coloane pe `journal_line`, tabelă `R21`; (2) trimiterea la „setul închis de chei de context"
  citea o versiune anterioară a deciziei — a devenit `OD-55`, fiindcă chei extensibile înseamnă
  evaluator de expresii, adică DSL-ul respins în același ADR; (3) „rămâne de fixat forma stornoului"
  e deja fixată structural de ADR-006, iar politica stă în ADR-007
- **Ce se schimbă în specificație la `Acceptat`, nu acum:** Spec B §3.2 descrie `posting_rule_line`
  cu `amount_expression jsonb` — forma opțiunii (A). Pointerul e pus; rescrierea așteaptă
- **Nimic implementat.** Sesiune de decizie, nu de cod: două ADR-uri, indexul, registrul (`OD-55`
  nouă, `T2` reordonată), patru trimiteri în Spec B

**2026-08-25, limba și delegarea: trei decizii scrise, două invariante care nu erau numite:**

- **A pornit dintr-o întrebare, nu dintr-o sarcină:** tabloul consolidat al cabinetului — „este
  actualizat deja?" Da, în specificație: Spec A §7 descrie read models aproape cuvânt cu cuvânt —
  agregate și identificatori, `firm_id` denormalizat, politică pe firmă, scriere doar prin `P-6`,
  ștergere la revocare, `IZ-63`…`IZ-67`. **Nu există cod:** `platform/readmodels` nu există,
  tabelele `rm_*` sunt F3
- **Ce lipsea din același paragraf** a intrat acum: bannerul permanent de context, în Spec A §7.1,
  cu auditul pe ambele identități; lista nominală a persoanelor care ating datele clientului este
  `OD-54`, **nouă**, și depinde de `OD-51` — azi clientul nu poate citi nici numele firmei sale
- **ADR-033 — limba la generare.** `C33` spunea *ce* nu are voie să se întâmple, nimic nu spunea
  *cine împiedică*. Măsurat înainte de a scrie regula: `formats.date_format` dă `7 Martie 2026` cu
  `ro` activ și forma rusă cu `ru`; iar limba activată **rămâne activă pe firul respectiv după
  unitatea de lucru care a setat-o** — un worker refolosit o duce în următoarea sarcină. Riscul nu
  e activ azi (serverul nu activează nicio limbă, implicitul e `ro`), și exact de asta regula costă
  zero acum. → `C38` plus gardă în `tests/architecture/test_document_language.py`, cu probă că poate
  eșua
- **ADR-034 — denumire legală și denumire internă** pe `item` și `partner`. `OD-40` **rămâne
  deschisă**: e întrebare juridică, nu de produs. Ce se schimbă e că răspunsul ei nu mai poate cere
  retastarea nomenclatoarelor. Respins explicit: `CHECK` pe alfabet — denumirea juridică a unui
  furnizor ucrainean chiar este în chirilice, iar art. 11 alin. (11) o acceptă. → `C39`; migrarea
  este `F0.7.7`, **nescrisă**: cere lanțul de review de migrare, deci sesiune proprie
- **ADR-035 — delegarea nu este tranzitivă.** Proprietatea era adevărată **din forma predicatului**,
  pe care nimic n-o numea și niciun test n-o acoperea — exact genul de cod care se „extinde" pentru
  un motiv plauzibil. Acum e `R27`, cu `IZ-68` și `IZ-69`, fiecare cu aserțiune de control care
  demonstrează că primul salt chiar există
- **`IZ-22`, angajatul care pleacă din cabinet:** aserțiunea care contează este ultima — rândul
  `company_access` derivat din engagement rămâne pe loc și nu mai dă nimic, fiindcă politica
  company-scoped cere și acces la tenant, iar acela se reevaluează la fiecare interogare
- **323 de teste trec** (fără `tests/volume/`, care aparține sesiunii paralele); `ruff` și `mypy`
  curate
- **Două ciocniri din lucru în paralel, ambele consemnate:** `032` fusese luat de cheia de
  partiționare, deci ADR-urile de aici sunt `033`–`035`; iar harness-ul de test face
  `DROP DATABASE ... WITH (FORCE)` la pornire, deci două rulări simultane se distrug reciproc —
  75 de erori care nu aveau nicio legătură cu codul. Rulat cu `POSTGRES_DB=evidenta_s2`, bază
  separată. Nota e acum în `tests/conftest.py`, lângă `DROP`

**2026-08-25, F0.11 — și un index găsit prin măsurătoare, nu prin citire:**

- **`OD-30` nu cerea ce părea că cere.** Blocajul spunea „firma de contabilitate colaboratoare nu
  este identificată", dar criteriul lui F0.11 cere ca scenariile să fie **cuantificate**, nu ca
  datele să fie reale — datele le generează scriptul. Cuantificarea stă în statistică publică (BNS,
  BNM) plus cifrele deja scrise în Amendament, pe care nimeni nu le citise ca sursă
- `docs/_bootstrap/11-volume-model.md`: trei scenarii, fiecare număr cu sursa lui, **cinci ipoteze
  marcate ca ipoteze** și testate la sensibilitate. Trei capcane din sursele publice semnalate ca să
  nu se propage — comunicatele IMM 2024 și 2025 **nu sunt comparabile**, ponderea sare de la 46,1% la
  73,4% printr-o schimbare de metodologie
- calculul confirmă independent două afirmații din Amendament: „sute de milioane de linii cumulat,
  nu pe an" (515 mln la 5 ani, 103 mln pe an) și că **`audit_event` este primul candidat**, nu
  `journal_lines` (172 față de 103 mln pe an)
- **Benchmark-ul a găsit altceva înainte să răspundă la întrebare.** Enumerarea Spec A §9.3 — „ce s-a
  întâmplat în tenantul ăsta, cel mai recent întâi" — citea **un milion de rânduri ca să întoarcă
  cincizeci**, în 6.749 ms. Nu scan secvențial: *index scan* peste tot, fiindcă
  `audit_event_scope_idx` are `company_id` între tenant și timp, deci rândurile unui tenant nu sunt
  ordonate după timp. Reparat prin `audit_event_recent_idx`: **1,05 ms, 50 de rânduri citite**
- verificarea pe care o scrisesem căuta absența cuvântului „Seq Scan" și **trecea mulțumită la 6,7
  secunde**. Acum verifică rândurile citite. Dacă am fi partiționat fără să măsurăm, am fi făcut o
  operațiune scumpă care nu repara nimic
- **constatare care depășește tabela:** planificatorul nu poate estima selectivitatea prin
  `app.current_tenant_id()` — presupune `rows=1` acolo unde realitatea e un milion. Valabil pentru
  **orice** interogare din sistem, fiindcă toate filtrează prin ea. Forma planului se schimbă cu
  dimensiunea reală în feluri pe care un fixture mic nu le arată niciodată
- `OD-01` închisă prin **ADR-032**: chei desemnate, aplicate la prag (~100 mln de rânduri **și**
  interogări elagabile), niciodată `tenant_id` — distribuția BNS dă un raport de 50:1 între tenanți
- **326 de teste trec** pe o bază construită de la zero; `mypy` și gardienii curați

## F0 — criteriul de ieșire este îndeplinit

**Toate cele cinci rânduri sunt bifate.** Suitele rulează verde în CI sub rolul de aplicație; cele
patru combinații de acces se comportă corect; un task Celery fără context eșuează în loc să
returneze zero rânduri; gardianul de model eșuează la o tabelă fără `tenant_id`; modelul de volum
este livrat, cu măsurători rulate cu RLS activ.

Ce rămâne livrat **parțial**, marcat ca atare și nu ca terminat: `F0.0.3` (imagini scrise, nerulate —
docker nu e instalat pe mașina de lucru), `F0.6.3` (fără provider S3 — `OD-52`), `IZ-28` și `IZ-29`
amânate la F2 fiindcă n-au ce refuza fără module de business.

Faza următoare nu se deschide aici. F0 merită privită întreagă de proprietar înainte.

**2026-08-25, F0.2.4 — și coloana care nu era citită de nimeni:**

- **Constatarea, înainte de orice cod:** `covers_all_companies` apărea de **zero ori** în tot
  `infra/`. Era scrisă de serviciul de ciclu de viață și citită de nimic, deci un engagement
  declarat ca acoperind toate companiile acoperea, în fapt, exact companiile pentru care cineva
  inserase manual un rând `company_access`. Coloana promitea o regulă pe care n-o impunea nimeni.
  La fel `engagement_company_scope` — politică pe ea însăși, niciun predicat care s-o consulte — și
  `permission_level`, cu `CHECK` și fără cititor
- **Livrat:** `0032_engagement_provisioning`, oglinda revocării din `0014`. O cale privilegiată
  îngustă care întinde accesele derivate dintr-un engagement asupra unei companii apărute după
  semnare — dar numai când engagementul chiar acoperă toate companiile. Aceeași condiție de
  siguranță ca la revocare: fără ea, un uuid ar fi fost de ajuns ca să întinzi accesele altui tenant
- **Ce nu face, și de ce contează:** nu acordă accesul inițial. Cine servește un client este
  `OD-42`, deschisă — iar o provizionare „la acceptare, tuturor membrilor firmei" ar fi răspuns
  tacit la ea și ar fi dat unei firme cu 40 de contabili acces la fiecare companie a fiecărui client
- două defecte găsite rulând, niciunul vizibil la citire: `evidenta_rls` n-avea `SELECT` pe
  `company`, deci funcția nu-și putea rezolva tenantul; iar refuzul abortează tranzacția, deci
  testul care îl aștepta avea nevoie de savepoint, altfel ieșirea din context devenea o eroare
  fără legătură
- **`IZ-28` și `IZ-29` amânate la F2, cu motiv scris:** scope-ul de modul și `permission_level` n-au
  ce refuza cât nu există niciun modul de business. `IZ-28` cere „se cere un modul din afara
  scope-ului"; nu există modul de cerut
- **`OD-53` înregistrată:** nicio cale de producție nu creează o companie — politica pe `company`
  cere `has_company_access(id)` și în `WITH CHECK`, deci `INSERT`-ul prin rolul aplicației e
  imposibil. Azi companiile apar doar din fixture-uri, ca superuser. Când calea se scrie, trebuie să
  apeleze provizionarea în aceeași tranzacție
- **306 teste trec** pe o bază construită de la zero; `ruff`, `mypy` și gardianul de dependențe
  curate. Jobul rapid de CI rulează acum ambele suite statice

### Unde stătea F0 la momentul acelei sesiuni

**Patru din cinci criterii de ieșire îndeplinite.** Al cincilea — modelul de volum — era considerat
imposibil de închis în cod, fiindcă `OD-30` cerea „date reale de la o firmă colaboratoare".
**Premisa era greșită**, și s-a corectat în sesiunea următoare: criteriul cere scenarii
*cuantificate*, iar ordinele de mărime sunt publice. Vezi intrarea de sus.

Rămâneau, în afara criteriului: `F0.0.3` livrat **scris, nerulat** (docker nu e instalat pe mașina de
lucru), `F0.6.3` parțial (`OD-52` — fără provider S3, deci fără cale de încărcare), `F0.7.5` și
`F0.7.6` (`OD-11` închisă prin ADR-028; `DNB-02`), și `IZ-28`/`IZ-29` amânate la F2.

**2026-08-25, F0.2.5 și două reparații de gardian** — continuarea sesiunii de F0.0.5:

- **F0.2.5 livrat.** Cele 12 teste care existau probau mecanismul contextului — se setează, se
  curăță, refuză înainte de orice interogare — dar rulau toate pe UUID-uri inventate. Corect pentru
  un refuz: niciun rând nu trebuie să existe ca un refuz să fie refuz. Insuficient pentru `IZ-41` și
  `IZ-45`, unde întrebarea e ce **răspunde baza**. Trei teste noi pe date reale, 15 în total
- cel mai informativ dintre ele: un task pornit cu id-ul tenantului B și utilizatorul lui A
  **chiar primește contextul B** — și tot nu vede rândul. A numi un tenant nu înseamnă a avea acces
  la el; politica întreabă dacă utilizatorul poate ajunge acolo
- fiecare test poartă acum identificatorul scenariului. „Acoperă `IZ-40`…`IZ-45`" era criteriul, iar
  fără identificatori acoperirea nu se putea **arăta**, doar susține
- **ambele gardiene refuzau tăcut un contract cu două răspunsuri.** `{entry["name"]: entry for ...}`
  păstrează ultima intrare și nu spune nimic — deci două declarații pentru aceeași tabelă, ultima în
  vigoare, iar gardianul raportează conformitate față de o declarație pe care nimeni n-o știa
  câștigătoare. Ajunsese în fișierul real o dată, ca un al doilea set de tabele fiscale. Reparat în
  ambele, cu test fiecare
- ADR-024 completat cu golul concret al analizei statice, găsit la F0.8: `implementation_ref` e un
  șir cu puncte scris pe cale privilegiată. Rezolvat prin import, un singur `INSERT` privilegiat
  devine execuție de cod arbitrar, **fără niciun import de citit în sursă**. Registrul selectează
  dintr-un dicționar declarat în cod; unde un șir devine cod, granița o ține refuzul de la locul
  rezolvării, nu gardianul
- **291 de teste trec** pe o bază construită de la zero; `ruff` și `mypy` curate

**F0.2.4 nu s-a scris, deliberat, și motivul este o constatare.** Modelul de scope există în schemă
și nu e impus nicăieri: `covers_all_companies` apare de **zero ori** în tot `infra/`;
`engagement_company_scope` are politică pe ea însăși, dar niciun predicat nu o consultă;
`permission_level` are `CHECK` și nu e citit de nicio politică. Din cele cinci scenarii, `IZ-25` și
`IZ-26` ar fi trecut **din motivul greșit** — nu fiindcă scope-ul e impus, ci fiindcă accesul cere un
rând `company_access` explicit — iar `IZ-27`, `IZ-28` și `IZ-29` descriu comportament care nu există.
Decizia proprietarului: **impunerea stă la provizionare, în servicii**, nu în predicate. Serviciul
care acceptă un engagement creează `company_access` doar pentru companiile din scope, iar cu
`covers_all_companies = true` crearea unei companii noi provizionează accesul. Aceea e sarcina
următoare, și abia după ea `IZ-25`…`IZ-27` au ce demonstra.

Criteriul de ieșire din F0 are acum trei rânduri bifate din cinci. Al patrulea — cele patru
combinații de acces — pare acoperit de `IZ-10`…`IZ-18`, dar **nu l-am bifat** cât F0.2.4 e deschisă:
bifa ar spune că sarcina e terminată, iar ea nu e.

**2026-08-25, F0.10.1 — convenții API:**

- **codurile stabile se randează prin middleware, nu prin handlerul DRF.** `C10` e o garanție despre
  API, nu despre un framework, iar endpointurile de autentificare sunt Django simplu — o garanție
  care ar sta doar în DRF ar ține pentru o parte din API și pentru restul nu. Handlerul DRF există
  și el, fiindcă mapează și excepțiile proprii ale frameworkului
- **cârligul e `process_exception`, nu `try/except` în jurul lui `get_response`.** A doua formă e cea
  evidentă și e greșită: Django transformă excepția unui view în răspuns **înainte** să ajungă la
  `except`-ul unui strat exterior. Varianta evidentă trece testele dacă testele folosesc view-uri
  DRF, apoi cade tăcut pe cele Django simple — adică exact jumătatea pentru care există middleware-ul
- **middleware-ul stă în interiorul contextului de tenant**, ca tranzacția să fie încă deschisă: o
  eroare ridicată de un serviciu trebuie să deruleze înapoi, iar prinderea ei în afara contextului ar
  transforma o scriere parțială într-un 400 curat
- **`Idempotency-Key` se cere și se validează; replay-ul nu se implementează, deliberat.** `R19` pune
  cheia pe evenimentul contabil, care vine la F1.2. Un cache de replay la nivel de endpoint ar fi
  chiar lucrul despre care `R19` spune că nu ajunge, și ar trebui scos. `DNB-10` rămâne deschisă —
  fereastra de 24h e convenția din industrie și ar fi fost plauzibil de scris
- **endpointul de probă stă în teste**, nu în `config/urls.py`: o rută care există doar ca să fie
  testată ajunge în producție și e găsită de cineva, iar una cu „efect financiar" în nume e un lucru
  prost de lăsat într-o hartă de URL-uri
- **F0.10.2, în aceeași sesiune:** blocajul `DN-09` era expirat — decizia „obligatoriu pentru toți"
  fusese luată și implementată prin ADR-021, dar intrarea rămăsese în listă. Din cele patru cazuri
  cerute, trei erau deja acoperite de F0.3.7c; `IZ-04` lipsea. Adăugat ca **convenție**, nu ca
  verificare într-un endpoint: **404, niciodată 403.** Un 403 spune „există și nu e al tău", iar
  repetat peste un interval de identificatori e oracol de enumerare — un concurent cu o listă de
  clienți află care dintre ei își țin evidența aici. RLS dă răspunsul corect fără să fie întrebat,
  iar testul verifică și controlul: un rând existent și un identificator niciodată emis trebuie să
  fie **indistinctibile**
- **288 de teste trec**

## Sesiuni mai vechi

**2026-08-25, ADR-028 — ce înseamnă „modelat în F0". `OD-11` închisă, `F0.7.5` retrasă:**

- **decizia era deja luată** și stătea într-o regulă cu prioritate declarată. `CLAUDE.md` §4:
  „Nu se creează app-uri Django goale pentru module din faze viitoare. «Modelat în F0» înseamnă că
  structura din faza curentă nu face imposibil modulul viitor, nu că app-ul există acum." Prima
  variantă din `OD-11` e exclusă direct; a doua — model găzduit într-un app părinte — e aceeași
  lucrare sub alt nume, și e chiar acumularea pe care `C1` o interzice
- **„modelat în F0" este obligație negativă.** Nu cere să scrii ceva, cere ca nimic din ce scrii să
  nu facă modulul viitor imposibil. Se verifică. Verificarea, făcută: nicio tabelă din F0 nu referă
  un depozit, `journal_line` nu există încă, iar când va exista `warehouse_id` e cheie **ieșind**,
  deci `R21` nu se opune
- **`X-5` se rezolvă în favoarea hărții:** `warehouses` rămâne F4, `dimensions` F1
- **regula §4 n-avea gardian** și un app gol ar fi trecut de toate suitele — gardianul de dependențe
  raportează `D0` doar pentru un pachet cu strat nedeclarat, iar `masterdata/warehouses` **ar fi**
  într-un strat declarat. Acum are: `tests/architecture/test_no_empty_apps.py`, fără bază de date,
  cu probă care cade
- **273 de teste trec**

## Sesiuni mai vechi

**2026-08-25, F0.6.5 — notificări.** Închide conflictul X-9: modulul era marcat F0 în hartă și în
V2 §10, dar n-avea sarcină în §6.1.

- **notificările sunt personale, nu la nivel de tenant.** Politica îngustează la destinatar. Un
  utilizator al firmei cu engagement viu ajunge la datele clientului — pentru asta există
  engagementul — dar căsuța administratorului clientului nu face parte din ele. E granița pe care o
  politică mai largă ar fi trecut-o fără să observe nimeni; are test propriu
- **expedierea către altcineva e cale privilegiată**, iar judecata stă în SQL: destinatarul trebuie
  să fie membru activ al tenantului, iar cel care notifică trebuie să aibă el însuși acces. Prin
  `rls.has_tenant_access`, **nu** prin `app.current_tenant_id() = p_tenant_id` — a doua variantă
  compară două lucruri pe care le controlează același server de aplicație, prima verifică un fapt de
  bază de date
- **lista destinatarilor se calculează în SQL**, nu în Python: `membership` aparține lui `identity`,
  iar un serviciu care importă modelele altui modul e chiar ce interzice `D6`
- **rândul păstrează cheie + parametri, nu o propoziție randată.** Corectarea unei formulări devine
  deployment, nu migrare peste rânduri; și `ADR-014` ține rusa ca strat de prezentare — un corp
  înghețat în română la scriere ar fi transformat tăcut „amânăm rusa" în „refuzăm rusa"
- **`OD-51`, găsită prin măsurare, nu prin citit:** comentariul politicii pe `firm` spune că firma
  se vede clientului cu engagement viu; predicatul e `rls.has_tenant_access` peste tenantul
  **firmei**, iar un administrator al clientului întoarce fals. Deci clientul nu poate citi numele
  contabilului său. Notificările nu numesc cealaltă parte — ceea ce e oricum corect, numele aparține
  altui tenant — dar costul e vizibil: un client cu doi contabili nu poate spune care a plecat
- **`OD-50`:** canalul de e-mail e modelat și n-are transport. Expeditorul rulează fără identitate
  de utilizator, deci cere o cale privilegiată proprie, și nu e ales niciun furnizor. Rândurile stau
  pe `unavailable`, nu pe `pending`: numărabile, spre deosebire de o notificare pierdută tăcut
- **253 de teste trec**

## Sesiuni mai vechi

**2026-08-25, F0.0.3 — imagini de container.** Livrată **scrisă, nerulată**, și asta e o stare
declarată, nu o bifă:

- **docker nu e instalat pe mașina de dezvoltare.** `docker compose --profile app up` n-a fost
  executat niciodată, deci criteriul de terminare al sarcinii — healthcheck-uri verzi — **nu e
  demonstrat**. Dockerfile-ul și compose-ul sunt scrise cu grijă și marcate ca atare, în ambele
  fișiere. Ce e verificat sunt cele două sonde HTTP, care au acum teste proprii
- **defect real găsit în compose, nu în ce am scris eu:** `POSTGRES_USER: evidenta_owner` face
  imaginea de Postgres să creeze rolul de owner ca **superuser** — iar un owner superuser ocolește
  RLS în întregime. Contrazicea `R5` fix acolo unde contează. Acum `postgres` creează baza, iar
  cele trei roluri vin din `0001_roles.sql`, cu atributele lor
- **al doilea defect:** `DATABASE_URL` era trimis către backend și worker și **nu-l citea nimic** —
  `base.py` citește `POSTGRES_HOST`, `APP_DB_USER` etc. Containerul ar fi căzut înapoi pe
  `localhost`, adică pe el însuși, cu o eroare de conexiune care nu arată nicăieri lângă cauză
- **bootstrap și migrare sunt servicii proprii**, nu entrypoint. Rulează sub roluri diferite:
  bootstrap ca superuser și ca owner, migrarea ca owner, aplicația ca `evidenta_app` (R5). Un
  entrypoint care ar migra la pornire ar cere containerului de aplicație acreditările owner-ului și
  ar face separarea rolurilor decorativă
- **`frontend` a ieșit din profilul `app`** în profilul `web`: Dockerfile-ul lui vine la F0.10, iar
  cât timp lipsește făcea profilul întreg să cadă la build. Un profil care nu poate porni nu e
  pregătit, e stricat
- **`/healthz` și `/readyz`**, exact două căi noi exceptate de context, cu patru teste — inclusiv
  controlul care arată că o cale obișnuită pe aceeași gazdă tot refuză. Liveness nu atinge baza,
  deliberat: o sondă care interoghează baza repornește o aplicație sănătoasă când baza clipește
- **`OD-49`**: gunicorn cu workeri sincroni e alegere, nu neutralitate — `R3` ține contextul într-un
  `ContextVar` pe durata tranzacției, iar nimic din suită n-ar observa dacă un worker asincron ar
  întreține requesturi pe același fir
- **241 de teste trec**

## Sesiuni mai vechi

**2026-08-25, F0.9 — modelul de sumă și cursurile valutare:**

- **modulul refuză să rotunjească.** `convert()` cere o regulă de rotunjire rezolvată din registrul
  fiscal pentru perioada postată, iar pentru `accounting.money_rounding` **nu e înregistrată
  niciuna**: `DNB-08` e blocată pe ghidul de integrare SFS (`OD-24`). Un test afirmă exact starea
  asta, ca să nu alunece tăcut. O regulă aleasă acum ca să facă modulul utilizabil ar produce
  numere care nu se pot apăra în fața validatorului care decide dacă factura e acceptată
- **de aceea nu există `round_money()`.** Spec B §7.4 pct. 3: rotunjirea e logică fiscală
  versionată, nu utilitar. Un ajutor de rotunjire într-un modul de utilitare e exact forma în care
  o regulă fiscală ajunge nemarcată în cod
- **rândul din registru selectează, nu importă.** `implementation_ref` e o cheie într-un tabel de
  implementări din cod, nu o cale importabilă. `fiscal_logic_version` se scrie prin calea
  privilegiată P-4; dacă referința ar ajunge la un `import`, un singur `INSERT` privilegiat ar fi
  execuție de cod arbitrar în rolul aplicației — iar gardianul de dependențe, care citește AST-ul,
  n-ar vedea un import dinamic deloc. Un test încearcă `os.system` și primește refuz
- **cele patru elemente se produc împreună**, fiindcă separat e felul în care ajung să descrie
  momente diferite, iar înregistrarea e imutabilă după postare. Nu e alegere de proiectare: Legea
  287/2017, art. 7 alin. (2) — contabilitatea faptelor în valută se ține în ambele monede
- `float` e **refuzat la construcție**, nu convertit tăcut: face aceeași balanță să dea rezultate
  diferite după ordinea de agregare
- **235 de teste trec**; `mypy` curat pe tot `backend`

## Sesiuni mai vechi

**2026-08-25, F0.8 — parametri fiscali și registrul de selecție**, scrisă în paralel cu sesiunea de
cale de request, în același arbore:

- **structura, fără nicio valoare.** `OD-22` e deschisă și legislația nu se ghicește din memorie;
  regula proiectului o spune direct. Testele folosesc `test.rate.alpha` și valorile 1 și 2 —
  nonsens vizibil, deliberat: un număr plauzibil într-un fișier de test e primul loc de unde
  cineva copiază o cotă
- **R15 și R16 sunt două tabele, nu una.** Parametrul e dată și se schimbă prin `INSERT`; logica e
  cod versionat și se schimbă prin deployment. `fiscal_logic_version` ține referința către
  implementare ca text, nu ca import — ca un algoritm retras să poată fi referit fără să fie
  încărcat, fiindcă `R18` cere ca recalcularea unei perioade din 2026 să-l găsească în 2030
- **rezolvarea nu citește niciodată ceasul.** Fiecare funcție primește data ca argument. Un
  rezolvator care ar putea cădea pe „azi" ar face recalcularea unei perioade închise să întoarcă
  răspunsul anului curent, iar greșeala ar fi tăcută și cu aspect corect. Asta e și motivul pentru
  care `if year >= X` e interzis în codul de business: registrul știe anul, implementarea nu
- **zero potriviri e eroare, nu zero.** Cea mai valoroasă aserțiune din fișier: un rezolvator care
  întoarce `0` pentru o cotă neconfigurată produce o înregistrare fără impozit, care se postează,
  se echilibrează și trece de orice altă verificare
- **baza refuză ambiguitatea înainte s-o vadă rezolvatorul.** `EXCLUDE` peste `daterange`, doar pe
  rândurile `active` — un refuz la calcul înseamnă că eroarea de configurare a ajuns la cineva care
  închide luna și n-o poate repara. `COALESCE(scope_ref, uuid_nil)` fiindcă două rânduri globale au
  amândouă `scope_ref` NULL, iar `NULL = NULL` e necunoscut: un `EXCLUDE` pe coloana nudă nu s-ar
  declanșa exact în cazul cel mai frecvent
- **ADR-027** — `fiscal` intră în lista straturilor de compunere de schemă. Nu fiindcă gardianul a
  raportat ceva, ci fiindcă `R13` cere ca o înregistrare contabilă să poată numi versiunea de
  parametru sub care s-a calculat. Alternativa — cheie străină doar în SQL, invizibilă lui Django —
  ar fi fost o capcană cu întârziere
- **două constatări ale gardianului de dependențe, reparate la cauză, nu prin excepție:**
  rezolvarea parametrilor a fost mutată lângă tabela pe care o citește (`fiscal.parameters`), iar
  verificarea de acces din autentificare trece acum prin serviciul public al lui `tenancy`, nu prin
  modelele lui
- **coliziunea de nume din gardianul de model, reparată la cauză.** Sonda `IZ-76` crea o tabelă
  numită literal `fiscal_parameter`; a mers cât timp tabela nu exista. A treia oară când apare
  forma asta (`audit_event`, `document_event`), și de fiecare dată reparația e aceeași: o sondă
  poartă nume de sondă
- **220 de teste trec**, sub `evidenta_app`, pe o bază construită de la zero

## Sesiuni mai vechi

**2026-08-25, F0.3.7c — calea de request: rezolvator cablat, autentificare din sesiune**, scrisă în
paralel cu sesiunea de gardian de dependențe și masterdata, în același arbore:

- punctul de plecare a fost un traceback: `http://localhost:8000/` → `TenantResolutionError`. Nu era
  defect, era regula aplicată — dar în spatele ei erau **trei** lipsuri, nu una. `RLS_CONTEXT_RESOLVER`
  nu era cablat; `localhost` n-are subdomeniu; și nimic din codul de producție nu punea vreodată
  `request.authenticated_user_id` — atributul era scris în exact un loc din tot repo-ul, în teste
- **de ce F0.3.7b nu putea fi apelat de pe nicio cerere:** `app.current_user_id()` e fail-closed.
  Fără context ridică excepție, nu întoarce `NULL`, deci nicio politică `self_row` — `user`,
  `mfa_method`, `mfa_backup_code`, `user_session` — nu poate răspunde înainte de autentificare. Nici
  pentru rândul propriu: „propriu" e tocmai ce nu se știe încă. Testele existente ascundeau asta
  deschizând manual un context, adică presupunând rezolvat exact ce autentificarea trebuie să producă
- **ADR-026**: patru funcții privilegiate pentru ce precede identitatea verificată, și o graniță
  explicită pentru ce **nu** trece pe acolo — emiterea sesiunii, `last_login_at` și revocarea proprie
  se fac prin ORM, sub context, fiindcă după al doilea factor identitatea e cunoscută. Varianta cu un
  context deschis după parolă ar fi redus totul la o funcție; ar fi fost `ADR-021` încălcat cu un
  strat mai jos, unde nu se mai vede
- **ADR-025** închide `OD-20`: `*.evidenta.localhost`, `TENANT_BASE_DOMAIN` implicit doar în `dev.py`
- `user_session` a primit `token_hash`. Până acum sesiunea era identificată doar prin cheia primară —
  iar o cheie primară nu e secret: apare în loguri, în mesaje de eroare, în referințe. Tokenul e
  `secrets.token_urlsafe(32)`, stocat ca SHA-256 nesărat (256 de biți n-au dicționar de rezistat, iar
  o sare per rând ar face căutarea după token o parcurgere a tuturor sesiunilor)
- **verificarea accesului la emitere întreabă baza, nu Python:** vizibilitatea rândului din `tenant`
  trece prin aceeași `rls.has_tenant_access` pe care o folosește orice interogare ulterioară. O
  reimplementare ar fi fost a doua copie a regulii de acces. Fără ea, parolă corectă + factor corect
  pe subdomeniul greșit ar fi produs o sesiune validă în care fiecare interogare întoarce zero rânduri
  — sigur, și imposibil de distins de un produs stricat
- cookie **host-only** (fără `Domain`): granița de tenant și granița de cookie devin aceeași linie.
  `SameSite=Lax` e deocamdată **toată** protecția CSRF — nu există middleware CSRF în lanț
- trei endpoint-uri, Django simplu, nu DRF: convențiile API sunt F0.10.1 și n-aveau de ce să se
  închidă din greșeală aici. `/api/v1/auth/login` e singura cale exemptată de context — exact, nu ca
  prefix — iar ce face exceptarea sigură e garda de interogări: fără context, o viziune exemptată nu
  poate atinge date de business deloc
- **11 teste noi de cale de request**, plus unul la nivel de rezolvator. Suita de izolare: **184 de
  teste trec**; `mypy` curat pe `platform` și `config`
- **rămas deschis, `OD-48`:** înrolarea MFA n-are cale de request. Cine n-are al doilea factor nu
  poate obține sesiune, deci nu poate ajunge la ecranul de înrolare. Circular și cunoscut
- **defect găsit, nereparat, în afara scopului:** `invalidate_sessions_for_engagement` scrie prin ORM
  peste sesiunile *altor* utilizatori, dar politica e `user_id = app.current_user_id()` — deci
  actualizează zero rânduri când o cere administratorul clientului, adică în singurul caz real.
  Testul trece fiindcă revocă sesiunea propriului utilizator. Aceeași clasă cu `OD-37`; are nevoie de
  o cale privilegiată, ca `company_access` în `0014`
- **suita completă e roșie dintr-un motiv care nu ține de aici:** `tests/schema_guard/test_model_guard.py`
  creează o tabelă-probă numită literal `fiscal_parameter`, nume care acum aparține modulului fiscal
  în lucru în paralel. 219 trec, 1 cade, pe o bază de test privată

**2026-08-25, F0.0.5 — gardianul de dependențe (ADR-024)**, scris în paralel cu sesiunea de
masterdata, în același arbore:

- `D1`–`D6` erau declarate în `CLAUDE.md` §3 și **citite de nimic**. Acum: parcurgere AST peste
  `backend/evidenta`, contract într-un singur fișier (`infra/modules/dependencies.toml`), 19 teste,
  fiecare regulă cu probă că poate eșua. ~0,1 s, fără bază de date, deci stă în jobul rapid de CI
- **`import-linter` respins, cu motiv măsurat, nu de gust:** un contract de straturi nu poate
  exprima `D6`, nu distinge `accounting.events` de `accounting.ledger` (`D3`), și **tace** despre
  pachetul pe care nimeni n-a știut să-l declare. Gardianul îl raportează — `D0` — și vede pe
  deasupra importurile relative și pe cele din interiorul funcțiilor, a doua formă fiind exact cum
  se face un ciclu să funcționeze la rulare
- **`D6` a fost decis pe măsurătoare, nu pe citire.** Aplicat literal, declara defecte zece
  importuri existente, toate ținte de `ForeignKey` în `models.py`. Excepția are două condiții,
  ambele impuse: numai un modul `models` poate compune schemă, și numai către `platform` și
  `masterdata`. Lista a fost `["platform"]` singur câteva minute — a căzut când `Articol → Unitate
  de măsură` a ieșit ca încălcare
- gardianul a prins în prima oră două chei străine scrise în aceeași oră, în `masterdata`. Ambele
  au devenit referințe prin șir. Una dintre ele a scos la iveală un al doilea defect, care nu era
  ținta lui: mutarea cheilor străine în altă migrare a lăsat `CREATE POLICY ... USING (tenant_id =
  ...)` să ruleze înaintea coloanei — eșua pe bază curată, trecea pe una migrată
- **gardianul a prins o eroare în propriul lui contract**, nu în cod: `fiscal.may_import` era gol,
  dar graful spune „totul poate depinde de platform", iar `D1` vorbește despre module **business**.
  Nimic nu o prinsese cât `evidenta/fiscal/` nu exista; primul fișier pus acolo a fost o migrare
  care importă `run_sql_file` — mecanismul cerut de C30 — și verificarea a căzut. Contractul e
  greșit acolo, nu codul
- **190 de teste trec** pe o bază construită de la zero; `ruff`, `mypy` curate; `make deps-check` și
  pasul de CI cablate

**Lucrul în paralel a costat, și costul e de consemnat.** Două sesiuni în același arbore au
implementat F0.0.5 **de două ori**, simultan, fiindcă decizia care alegea unealta a fost pusă într-o
sesiune și nu în cealaltă. S-a rezolvat prin mesaj între sesiuni, dar numai fiindcă niciuna nu
comisese. Registrul de decizii a suferit aceeași coliziune a doua oară în aceeași zi: `OD-44` și
`OD-45` primiseră fiecare o a doua decizie, iar una era înregistrată de două ori — devenite acum
`OD-46` (gardianul pe `*_key`) și `OD-47` (privilegiile implicite). **Regula care lipsește: cine ia
o sarcină o spune înainte, iar numerele de `OD`, de ADR și de migrare se rezervă, nu se aleg la
scriere.**

**2026-08-25, corecții pe stratul de rezoluție** — mesaje care trimiteau la o fază terminată:

- `refuse_all` și comentariul din `settings/base.py` spuneau amândouă „la F0.3.5", dar F0.3.5 e
  livrat. Spun acum ce lipsește de fapt: `RLS_CONTEXT_RESOLVER` e un dotted path către un callable,
  iar `SubdomainTenantResolver` cere `base_domain` în constructor — deci cablarea cere o setare și o
  factory, nu o linie de settings. Plus utilizatorul autentificat, fără de care rezolvatorul refuză
  oricum (F0.3.7b)
- **de urmărit**: F0.3.5 e bifat, dar rezolvatorul nu e pe calea de request a niciunui mediu. Se
  exercită doar prin suita de izolare, care îl instanțiază direct. Bifa nu spune asta
- `resolver_for_testing` șters din `platform/rls/middleware.py`: zero referințe în repo, iar ce
  făcea era să deducă tenantul din anteturi `X-Test-*` — calea pe care `C8` o interzice. Cod mort
  care citește identitatea dintr-un antet este exact ce se cablează din greșeală mai târziu
- **`makemigrations` nu rulează** sub gardă: `check_consistent_history()` citește
  `django_migrations` pe conexiunea aplicației și garda refuză — aceeași clasă de problemă ca la
  `runserver`, dar fără exemptare declarată. Spre deosebire de `runserver`, verificarea e apelată
  inline în `handle()`, deci un `makemigrations` propriu ar trebui să declare `unguarded()` peste
  toată comanda, nu peste o singură interogare. Nedecis; până atunci comanda cade
- suita completă verde la măsurătoare: **121 de teste**, `ruff` și `mypy` curate

**2026-08-25, F0.3.7a** — modelul de roluri, ADR-020 aplicat:

- `permission` (catalog global, cheie primară naturală, alimentat din cod prin migrare), `role` și
  `role_permission` per tenant; `membership.role` și `company_access.role` au devenit chei străine
- **cheile străine compuse** sunt ce nu se putea exprima în Django: `(tenant_id, role_id)` pe
  membership și company_access, iar pe `role_permission` una singură — `(tenant_id, role_id, scope)`
  → `role (tenant_id, id, level)` — care ține două invariante deodată: același tenant și același
  nivel. Un rol de tenant nu poate primi o permisiune de companie, iar baza o refuză
- **triggere** pentru cele două ștergeri care ar bloca un tenant în afara lui însuși: rolul de
  sistem nu se șterge, și nu poate pierde `tenant.manage_roles`
- **serviciul** a intrat direct în `OD-37` — găsit de `tenancy-guard` la review, nu de mine la
  scris: `membership` are politica `user_id = app.current_user_id()`, deci o sesiune își vede un
  singur rând. Două consecințe, ambele acum refuzate cu cod stabil în loc să pară că funcționează:
  `assign_role` nu poate muta rolul altui membru (rândul e invizibil, iar ORM-ul ar fi raportat
  „nu există", ceea ce e alt fapt), iar regula anti-blocare din ADR-020 nu poate fi **verificată**,
  fiindcă a demonstra că mai există un administrator înseamnă a citi alte membership-uri. Garda
  scrisă inițial ar fi găsit mereu zero și ar fi trecut testele exact ca una care funcționează
- catalogul are 8 chei, fiecare cu calea de cod care o impune scrisă lângă ea — o permisiune fără
  punct de impunere ar citi ca protecție într-un ecran și n-ar bloca nimic
- două defecte găsite rulând, nu citind: `RunPython` scria pe conexiunea implicită (tabela nici nu
  era vizibilă, iar aplicația n-are grant de scriere pe catalog), iar triggerul de protecție
  bloca chiar curățarea fixture-urilor — harness-ul îl dezactivează acum explicit, pentru curățare
- **121 de teste trec**; `ruff` și `mypy` curate; migrarea aplicată și pe baza de dezvoltare
- `tenancy-guard` a dat două CRITICAL, ambele reale și ambele reparate. Peste ele, un test care
  arată că refuzul este o **limită**, nu regula cerută: cu doi administratori activi în tenant,
  răspunsul e același. Fără el, testul anterior trecea din motivul greșit
- `schema-reviewer` a dat un CRITICAL, tot real: protecția rolurilor de sistem se declanșa **doar
  pe DELETE**, iar aplicația are `UPDATE`. Două instrucțiuni obișnuite o ocoleau complet —
  `UPDATE role SET is_system = false` urmat de `DELETE`, sau rescrierea lui `permission_key` fără
  ca vreun rând să dispară. Testele probau ștergerea, adică fix calea acoperită. Închis prin
  `0020_roles_hardening` (fișier nou, nu editarea lui `0019`, care e aplicat — C31), cu probă
  pentru fiecare dintre cele două căi
- două corecții mai mici din același review: `role_permission.permission_key` nu avea `COLLATE "C"`
  deși e cod (C34) — cu efect vizibil, un index în plus creat de Django ca să compenseze; și
  `GRANT SELECT ON permission` era fără efect, fiindcă privilegiile implicite din bootstrap dau deja
  CRUD. Comentariul promitea două straturi acolo unde exista unul; `0021` adaugă `REVOKE`-ul
- **123 de teste trec.** Rămase de decis, nu tăcute: `module_key` (F0.3.3) are aceeași lipsă de
  colație; gardianul de model nu poate prinde niciuna, fiindcă `CODE_COLUMN_SUFFIXES` nu conține
  `key`; cheile străine cu o singură coloană generate de Django dublează inutil cele compuse

**2026-08-25, poziție consemnată** — răspunderea pentru un asistent automat (`OD-43`):

- registrul avea `OD-41` și `OD-42` folosite fiecare pentru **două** decizii diferite, din lucru
  în paralel. Numerele vechi rămân la deciziile vechi — `OD-42` e citat în ADR-017, care e
  `Acceptat` și nu se editează. Perechea apărută la F0.3.3 a devenit `OD-44` (listarea tenanților)
  și `OD-45` (corecțiile din contractul RLS); `infra/rls/exceptions.toml` actualizat. SQL-ul aplicat
  `0012_tenant_context_binding.up.sql` păstrează numărul vechi: `C31` îl face append-only, iar
  maparea stă în rândul `OD-44`

- asistentul este **instrument, nu actor**: răspunde tenantul, iar cel care l-a activat verifică ce
  a făcut. Aceeași poziție ca pentru un contabil angajat sau o firmă cu engagement — execută unul,
  răspunde altul
- consecință care simplifică modelul: **nu** e nevoie de identitate non-umană.
  `audit_event.actor_user_id` rămâne `NOT NULL`, iar `ADR-020` nu are de acoperit un actor în plus
- „cine a pornit asistentul" **este** activarea capabilității (R25), nu un câmp nou
- rămâne o singură coloană de decis, la `OD-43`: legătură nulabilă din `audit_event` către activare,
  de aceeași formă cu `actor_firm_id`. Ieftină cât tabela e goală în producție

**2026-08-25, decizii** — `DN-06` și `DN-07` închise, prin ADR-018 și ADR-019:

- **DN-06 → opțiunea B:** un tenant poate avea engagementuri vii cu mai multe firme, separate prin
  scope de module. `engagement_live_unique` rămâne cum e — opțiunea A ar fi adăugat o constrângere
  peste ea, B nu adaugă. Regula de arbitraj este *fără suprapunere*: un `module_key` aparține unui
  singur engagement viu per tenant, impus **în bază** — o verificare doar în servicii cade la primul
  import în masă sau la prima scriere concurentă
- **DN-07 → opțiunea A:** `module_key` = numele modulului de business din harta §4.1; `read`/`write`,
  `write` include `read`; `platform/*` nu primește chei de scope; lista într-un singur loc, impusă prin
  `CHECK`. Aleasă fiindcă se extinde spre catalogul fin fără migrare de date, iar B ar fi cerut și
  `DN-08` închisă. Limita acceptată, scrisă în ADR: o firmă cu `payroll` vede salariile individuale
- **`DN-15` rămâne deschisă și atinge direct regula de suprapunere:** dacă transferul între firme lasă
  firmei vechi acces numai-citire pe durata predării, aceea este prin definiție o suprapunere. Excepția
  se scrie atunci, explicit — până atunci transferul se modelează ca succesiune
- F0.3.3 fusese livrat **fără** cele două: modelele lăsau `module_key` fără `CHECK` și numeau decizia
  deschisă în comentariu, în loc să inventeze un răspuns. Acum se poate completa (F0.3.3b), iar F0.2.4
  — cazurile de engagement, IZ-25…IZ-29 — nu mai are nimic în față

**2026-08-25, tooling** — dezvoltarea locală trece pe nativ, fără docker:

- `Makefile` nu mai trece prin `docker compose exec`: `psql` merge direct la clusterul local, iar
  variabilele poartă exact numele citite de settings și de harness-ul de test — un singur vocabular,
  suprascris din `.env` (model în `.env.example`)
- **`make migrate` era defect:** rula `manage.py migrate` fără `--database=migration`, deci pe
  conexiunea `default`, adică `evidenta_app` — rolul care nu deține nimic. Ar fi eșuat cu
  *permission denied* la prima rulare reală. Harness-ul de test o făcea corect, de aceea nu s-a văzut
- ținte noi: `doctor` (uv, psql, PostgreSQL, Redis, baza), `setup`, `psql-app`, `run`, `worker`.
  `reset-db` cere `CONFIRM=yes`: acum șterge o bază reală, nu un volum docker
- docker rămâne pentru producție și CI. `docker-compose.yml` și criteriul F0.0.3 o spun explicit,
  ca sesiunea următoare să nu reintroducă compose în bucla de dezvoltare
- `make schema-dump` și `make rls-report` **există acum**: `schema-reviewer` le declara ca singurele
  două comenzi permise, dar niciuna nu fusese scrisă vreodată. Raportul stă în `infra/rls/report.sql`
- **Verificat pe un cluster de probă construit de la zero:** `make setup` creează baza cu colația
  ICU, aplică bootstrap-ul și cele patru migrații, apoi `make test` trece — 43 de teste, sub
  `evidenta_app`. Nu este raționament despre Makefile, ci rularea lui
- rulat apoi pe mașina de lucru, unde a ieșit un defect real de harness: `PGPASSWORD` și
  `password=` **setate pe gol** sunt tratate de libpq ca parolă validă, deci `~/.pgpass` nu mai era
  citit niciodată. `conftest.py` distinge acum „absent" de „gol" (`_admin_password`), iar Makefile-ul
  pune `PGPASSWORD` doar când are valoare. Pe un cluster cu credențialul în `.pgpass`, suita nu
  putea porni deloc
- `make check-roles`: numele rolurilor nu sunt configurabile — apar literal în fiecare politică și
  fiecare GRANT. Configurate greșit în `.env`, bootstrap-ul eșua abia la `0002`, după ce `0001`
  crease deja rolurile corecte. Acum refuză înainte, cu numele așteptate
- `backend/Makefile` redirecționează către rădăcină, ca `make test` să meargă și din `backend/`
- **43 de teste trec pe baza reală**, sub `evidenta_app`; `ruff` curat, `mypy` fără erori
- **`runserver` nu pornea deloc**, descoperit rulându-l: Django citește `django_migrations` pe
  conexiunea aplicației înainte să lege portul, iar garda refuză — corect, fiindcă nu poate deosebi
  o verificare de pornire de o cerere care a uitat contextul. Excepția e declarată acum îngust, într-un
  `runserver` propriu (`platform/rls/management/commands/`), nu lărgită în gardă: lărgită acolo, ar fi
  scutit citirea pentru toți apelanții, inclusiv cei care sunt defecte
- serverul pornește și răspunde 500 la orice cerere, cu `TenantResolutionError` — starea corectă
  până la F0.3.5: nu există rezolvator de subdomeniu, deci nicio cale de request către date
- `make manage ARGS="..."` — poarta pentru comenzile `manage.py`, care altfel rulează cu parolele
  implicite din settings, nu cu cele din `.env`

**2026-08-25, sesiunea a șasea** — F0.3 aproape complet, F0.4 livrat, trei blocaje închise:

- F0.3.3b, F0.3.5, F0.3.6, F0.4 livrate; 106 teste trec
- **ADR-020** închide DN-08: roluri ca date compozabile, dar peste un **catalog fix de permisiuni**
  în cod — clientul compune roluri, nu inventează drepturi
- **ADR-021** închide DN-09: MFA obligatoriu pentru toți, cu cerințele de recuperare scrise ca
  parte din decizie, nu ca detaliu ulterior
- **ADR-022** închide OD-02: numerotarea e șablon configurabil; filiala **nu** se modelează, iar
  dacă devine cerință reală e decizie nouă cu entitate proprie

**2026-08-24, sesiunea a cincea** — F0.1 completă, F0.2.1 livrat:

- F0.1.4 și F0.1.5: middleware, gardă de interogare și decorator Celery, în forma tare
- F0.0.2: proiect Django, fără `django.contrib.auth` (ar fi închis tacit DN-08)
- F0.2.1: harness cu trei privilegii separate — admin creează baza, owner aplică bootstrap și
  migrații, app rulează testele. Verificat că refuză ca owner și ca superuser
- cele 20 de verificări din probele Python au devenit 22 de teste pytest; probele au fost șterse în
  aceeași schimbare
- F0.2.2: gardianul de model, cu probă că fiecare regulă poate eșua. Două găuri reale găsite rulând:
  `citext` nu era instalat nicăieri, iar `evidenta_owner` nu avea `CREATE` pe bază — o acoperisem
  manual în fiecare probă în loc s-o remediez. Ambele reparate în `0001_roles.sql`

**2026-08-24, sesiunea a patra** — cinci ADR-uri, dintre care trei din corectarea unor premise:

- **ADR-016** — limba contabilității are **temei legal**, nu de piață: Legea nr. 287/2017, art. 7
  alin. (1), „Contabilitatea se ţine în limba română şi în monedă naţională". Am extras textul
  autentic al legii, nu un rezumat. Consecințe: rusa e strat de prezentare exclusiv; `OD-38`
  (ieșire bilingvă) se închide ca **nu se face**; denumirile din planul de conturi rămân valoare
  unică; `DN-01` se închide complet. Art. 7 alin. (2) dă temei legal modelului de sumă multi-valută
- **ADR-015** — `Acceptat`: colația bazei este `ro-x-icu`, decizie „la creare". Coloanele de cod
  primesc `COLLATE "C"` explicit. Parametrii verificați pe PostgreSQL 18.6: `ICU_LOCALE 'ro'`, nu
  `'ro-x-icu'` — al doilea e numele obiectului de colație
- F0.1.4 și F0.1.5 au acum criterii în **forma tare**, cu forma slabă numită explicit: un test care
  arată că *funcționează cu* context nu demonstrează că *nu funcționează fără*; iar un decorator
  fail-closed dar tăcut trece toate testele și raportează succes pe zero rânduri

- **ADR-013** — motivul consemnat pentru Python 3.13 se învechise în 24 de ore: Django 5.2.8,
  psycopg 3.3 și Celery 5.6 suportă 3.14. Pinul rămâne, dar cu motivul real (dependențele din F1–F2
  cu extensii C) și cu o condiție de ieșire verificabilă — corpusul de regresie verde pe versiunea
  nouă, nu citirea unui changelog
- **ADR-014** — `DN-01` restrânsă: „tenantul lucrează în rusă" nu cere schimbare de schemă, deci
  **nu blochează F0.7**. Rămâne deschisă doar forma denumirilor pentru datele de referință livrate
  de noi, cu termen F1.1. `OD-38` nou pentru ieșirea bilingvă, ținut separat deliberat
- **ADR-015** — `Propus`. Premisa („chirilicul se sortează imprevizibil") a căzut la măsurare:
  chirilicul se așază consecvent după latină sub orice colație lingvistică. Ce se rupe e `COLLATE
  "C"`, care sortează greșit **româna**, azi. Al doilea motiv, mai grav: colațiile glibc se schimbă
  între versiuni de SO și corup tăcut indecșii

**2026-08-24, sesiunea a treia** — tooling, mecanismul de migrare, regula de retragere a probei:

- ADR-012 închide OD-18: SQL-ul de politici se aplică din migrațiile Django. **F0.1 este completă
  ca decizii**; rămâne doar execuția, care cere `uv.lock`
- granița bootstrap/migrații este acum o **locație**, nu o convenție: `infra/bootstrap/` (roluri,
  scheme, predicate — idempotente, în afara ciclului) vs. `infra/migrations/` (per tabelă, referite
  din migrări). `schema-reviewer` o verifică mecanic

- ADR-011 închide OD-15: uv, ruff, pytest, mypy strict doar pe `platform` și `accounting`
- `backend/pyproject.toml` + `.python-version`; țintele reale `sync`, `lint`, `format`,
  `typecheck`, `test`. **`uv.lock` lipsește** — `uv` nu e instalat pe mașina de lucru
- ADR-008 a trecut la `Acceptat` (ADR-010 a închis OD-32); ADR-007 rămâne `Propus`, dar pentru trei
  întrebări de tratament contabil, nu din lipsă de semnătură
- proba SQL are acum opt scenarii, cu IZ-11 inclus, reverificate de la zero; **F0.2 nu e terminată
  până când toate au echivalent Python care trece**, iar SQL-ul se șterge în același commit

**2026-08-24, sesiunea a doua** — șase ADR-uri și primele trei migrări SQL:

- ADR-003 … ADR-008. Patru `Acceptat` (RLS pe tenancy, context de companie, versiuni de stack,
  cele două date ale stornoului), două `Propus` în așteptarea contabilului (perioada stornoului,
  retenția)
- lista excepțiilor RLS unificată în `infra/rls/exceptions.toml`, sursă unică pentru gardianul de model
- `infra/bootstrap/0001_roles.sql`, `0002_app_context.sql`, `0003_access_predicates.sql` — scrise
  **și rulate** pe PostgreSQL 18.6, idempotente
- `infra/rls/smoke_fixture.sql` + `smoke_test.sql` — șapte scenarii de izolare, toate cu rezultatul
  așteptat, sub rolul de aplicație
- `schema-reviewer` a primit înapoi `Bash`, restrâns la două comenzi read-only pre-aprobate

**2026-08-24, sesiunea întâi** — inițializare completă, etapele 0–6 din `BOOTSTRAP.md`:

- Etapa 0: citite integral cele trei documente de intrare; produs `_bootstrap/00-inventory.md`
  (invarianți, module, decizii, conflicte, goluri)
- Etapa 1: schelet de repo, `CLAUDE.md`, `README.md`, `.gitignore`, `docker-compose.yml`, `Makefile`
- Etapa 2: șase definiții de agenți în `.claude/agents/`, trei comenzi în `.claude/commands/`
- Etapa 3: structura `docs/`, formatul ADR, registrul deciziilor deschise, acest fișier
- Etapa 4: `specs/spec-a-tenancy.md` — 1625 linii, 25 de puncte „DECIZIE NECESARĂ"
- Etapa 5: `specs/spec-b-accounting.md` — 1018 linii, 11 puncte „DECIZIE NECESARĂ"
- Etapa 6: `_bootstrap/06-f0-backlog.md` — 49 de sarcini de dimensiunea unei sesiuni
- În afara etapelor, sesiune de decizii frontend:
  - **ADR-002** — guvernanța (`Acceptat`): proprietarul aprobă; conținutul contabil, fiscal sau
    juridic cere co-semnătura contabilului practicant și rămâne `Propus` până există unul.
    Regulile obligatorii intră în `CLAUDE.md` **doar** din ADR-uri `Acceptat`. Închide `OD-33`
  - **ADR-001** — grila de date (`Acceptat`): TanStack Table, consumat exclusiv prin `DataGrid`
    (citire) și `EntryGrid` (introducere)
  - `CLAUDE.md` §2.6 „Frontend" — `C16`–`C22`, plus patru intrări în §4
  - `OD-19` restrânsă; adăugate `OD-34` (biblioteca de componente — shadcn/Tailwind recomandat,
    **nedecis**), `OD-35` (scara de densitate), `OD-36` (contractul de tastatură)
  - **ADR-009** — shadcn/ui + Tailwind (`Acceptat`): componente copiate în `shared/`, tokeni ca
    sursă unică, `tabular-nums` pe coloanele numerice. Închide `OD-34`, deblochează `OD-35`
  - **ADR-010** — contabilul practicant (`Acceptat`): rolul e acoperit de proprietar. Închide
    `OD-32`. Măsura de risc trece de la „ADR-uri în `Propus`" la acoperirea corpusului de regresie
  - `CLAUDE.md` §2.6 crește la `C16`–`C27`
  - `_bootstrap/07-f1-grile.md` — cele două sarcini de grilă, extras parțial din backlogul F1
  - `OD-41` — Glide Data Grid evaluat și **păstrat ca variantă de rezervă**, mărginit la
    suprafețele de reconciliere. **Fără declanșator** — un prag măsurabil cere `OD-30`, care nu
    există; se reevaluează la F1.9. Cartea Mare și balanța rămân pe TanStack în orice variantă
  - **ADR-017** — terminologia (`Acceptat`): două straturi independente, cu hartă fixă între ele.
    `CLAUDE.md` §2.7 primește `C35`–`C37` (doar partea scurtă; tabelele stau în ADR). Deschide
    `OD-42` — `assignment` are cuvânt, nu are entitate în Spec A
  - `F1.G2` rescrisă: `EntryGrid` este **primitiva generală de introducere cu tastatura**, nu
    grila de linii de document. Acoperă și maparea conturilor la import și potrivirea extrasului.
    Dacă e proiectată îngust, a doua bibliotecă devine inevitabilă — singurul element din
    discuția despre grile cu cost dacă întârzie

## Sarcini

### Inițializare

- [x] Etapa 0 — Inventar și raport de goluri
- [x] Etapa 1 — Schelet de repo și `CLAUDE.md`
- [x] Etapa 2 — Agenți și comenzi
- [x] Etapa 3 — Infrastructură de documentație și stare
- [x] Etapa 4 — Draft Spec A (tenancy) — **necesită review uman**
- [x] Etapa 5 — Draft Spec B (accounting) — **necesită review uman și validare contabilă**
- [x] Etapa 6 — Backlog F0

Inițializarea este completă. Nimic nu mai poate avansa fără răspunsuri umane — vezi „Întrebări
deschise" mai jos.

### F0 — Fundament (nu a început)

Ordinea este obligatorie și nu se rearanjează. Rolurile de bază de date și suitele de verificare
preced orice model.

- [x] F0.1 — Roluri de bază de date și infrastructură RLS
  - [x] F0.1.0 — baza cu provider ICU + `0000_locale_guard.sql`, verificat pe toate trei variantele
  - [x] F0.1.1 — roluri (`0001_roles.sql`), cu verificări care refuză configurarea greșită
  - [x] F0.1.2 — schemele `app` și `rls`, funcțiile de context fail-closed (`0002_app_context.sql`)
  - [x] F0.1.3 — predicatele de acces (`0003_access_predicates.sql`), cu probă de fum
  - [x] F0.1.4 — middleware, gardă de interogare, context fail-closed; 8 verificări PASS
  - [x] F0.1.5 — decorator Celery fail-loud; 11 verificări PASS, inclusiv calea de retry
  - [x] F0.1.6 — mecanismul de aplicare a SQL-ului manual (`sql.py`, `make bootstrap`, `make migrate`)
- [ ] F0.0 — schelet de proiect
  - [x] F0.0.1 — dependențe și tooling; `uv.lock` comis, `ruff` curat
  - [x] F0.0.3 — imagini de container: backend/worker, bootstrap și migrare ca servicii
        proprii sub roluri diferite. **Scrisă, nerulată** — docker nu e instalat aici
  - [x] F0.0.2 — proiect Django și Celery; `check`, `ruff`, `mypy`, `pytest` toate verzi
  - [ ] F0.0.3 — imagini de container
  - [x] F0.0.4 — CI pe GitHub Actions; jobul `quality` și jobul `tests`
  - [x] F0.0.5 — gardianul de dependențe (ADR-024): `D0`, `DG`, `D1`–`D6`, contract într-un
        singur fișier; 19 teste, fără bază de date
- [ ] F0.2 — Suitele de verificare (penetrare + gardian de model)    ← ÎN CURS
  - [x] F0.2.1 — harness sub rolul de aplicație; refuză ca owner și ca superuser
  - [x] F0.2.2 — gardianul de model; 11 teste, fiecare regulă cu probă că poate eșua
  - [x] F0.2.3 — penetrare: toate cele opt scenarii SQL au echivalent pytest care trece
  - [x] F0.2.6 — suitele în CI, sub rolul de aplicație; proba SQL retrasă
  - [x] F0.2.5 — task-uri Celery: IZ-40…IZ-45, cu trei scenarii pe date reale
  - [x] F0.2.4 — cazurile de scope: IZ-25…IZ-27 pe provizionare; IZ-28 și IZ-29
        amânate la F2, fiindcă n-au ce refuza fără module de business
- [x] F0.3 — Tenancy și identitate
  - [x] F0.3.1 — `Tenant`, `Company`, `CompanyVatRegistration` + politici, într-o migrare
  - [x] F0.3.2 — `User`, `Membership`; `tenant` interogabil pe calea de membru
  - [x] F0.3.3 — `Firm`, `Engagement`, scope-uri; a doua cale de acces, 9 teste
  - [x] F0.3.4 — `CompanyAccess`, `company` interogabilă, revocare în cascadă; 6 teste
  - [x] F0.3.5 — rezoluția subdomeniului, cale privilegiată îngustă; 15 teste
  - [x] F0.3.6 — ciclul de viață: matrice de tranziții ca date, coduri stabile; 12 teste
  - [x] F0.3.7a — modelul de roluri (ADR-020): catalog fix în cod, roluri ca date per tenant,
        chei străine compuse, triggere pe rolurile de sistem; 12 teste
  - [x] F0.3.7b — autentificare și MFA obligatoriu, coduri de rezervă, sesiuni; 13 teste
  - [x] F0.3.7c — calea de request (ADR-025, ADR-026): `token_hash` pe sesiune, funcțiile
        privilegiate de dinainte de context, middleware de sesiune, rezolvatorul cablat prin
        factory, `/api/v1/auth/{login,logout,whoami}`; 12 teste
  - [x] F0.3.3b — ADR-018 și ADR-019 aplicate: vocabular `module_key` cu `CHECK`, regula de
        nesuprapunere impusă prin index unic parțial + triggere de sincronizare; 4 teste
        (`CHECK`, listă într-un singur loc) și regula de arbitraj *fără suprapunere*, în bază
- [x] F0.4 — Audit
  - [x] F0.4.1 — `audit_event` append-only, fără chei străine, `occurred_at NOT NULL`
  - [x] F0.4.2 — captare explicită din servicii, fără signals; engagement cablat
  - [x] F0.4.3 — corelatorul `request_id` și enumerarea efectelor (Spec A §9.3)
- [x] F0.5 — Capabilități și feature flags
  - [x] F0.5.1 — `CapabilityActivation` cu dată efectivă și stare de inițializare;
        nesuprapunere pe `COALESCE(company_id, tenant_id)`; R24 impus prin `CHECK`
  - [x] F0.5.2 — feature flags și release rings; override cu motiv și expirare
        obligatorii; flagurile de conformitate refuzate la suprascriere, prin trigger
- [ ] F0.6 — Document core, numerotare, atașamente    ← ÎN CURS
  - [x] F0.6.1 — `Document` cu tip discriminator, stări generice și matrice de tranziții
  - [x] F0.6.2 — numerotare pe șabloane (ADR-022): contor blocat, unicitate în bază
  - [x] F0.6.4 — `document_event`, append-only, disciplina R21/R22
  - [~] F0.6.3 — atașamente: metadate la nivel de companie, politici, contract de stocare.
        **Parțial** — providerul, semnarea și limitele reale sunt `OD-52`
  - [x] F0.6.5 — notificări: in-app complet, canalul de e-mail modelat fără transport (OD-50);
        închide conflictul X-9
- [ ] F0.7 — Master data    ← ÎN CURS
  - [x] F0.7.1 — `CounterpartyRegistry` global, doar citire la ambele straturi
  - [x] F0.7.2 — `Partner`, nivel tenant, unic pe IDNO
  - [x] F0.7.3 — `CompanyPartner`, configurare per companie
  - [x] F0.7.4 — `Item`, `ItemCategory`, `UnitOfMeasure`, `UnitConversion`
  - [x] ~~F0.7.5~~ — `Warehouse` **retrasă** prin ADR-028: „modelat în F0" e obligație negativă,
        verificată, nu construită. `masterdata/warehouses` rămâne F4; `OD-11` închisă
  - [x] F0.7.6 — dimensiuni: ADR-029, listă închisă plus cinci sloturi generice. Niciun cod,
        cum cere sarcina — `journal_line` se creează la F1.2
- [x] F0.8 — Parametri fiscali și registru
  - [x] F0.8.1 — `fiscal_parameter` și proveniența: sursa obligatorie, aprobarea obligatorie
        pentru `active`, nesuprapunere impusă în bază. **Nicio valoare fiscală** (OD-22)
  - [x] F0.8.2 — registrul de selecție după dată efectivă: rezolvare cu dată obligatorie,
        zero și două potriviri sunt erori cu cod stabil
- [x] F0.9 — Multi-valută *(modelul; conectorul BNM e F1, reevaluarea F2 — OD-10)*
  - [x] F0.9.1 — modelul de sumă: `Decimal` peste tot, valutele nu se amestecă,
        rotunjirea vine din registrul fiscal după data perioadei — nu există `round_money()`
  - [x] F0.9.2 — `exchange_rate` global, `UNIQUE (currency, rate_date, rate_type)`,
        scriere doar prin calea privilegiată P-3
- [x] F0.10 — Convenții API și schelet frontend
- [x] F0.11 — modelul de volum: trei scenarii din surse publice, măsurători cu RLS
      activ; `OD-01` închisă prin ADR-032
  - [x] F0.10.1 — convenții API: coduri de eroare stabile prin middleware, `Idempotency-Key`
        cerut și validat (replay-ul stă pe evenimentul contabil, F1.2)
  - [x] F0.10.2 — autentificare la nivel de API: IZ-04 adăugat ca **convenție** (404, niciodată
        403); IZ-05/36/37 erau acoperite de F0.3.7c. `DN-09` era blocaj expirat — ADR-021
  - [x] F0.10.3 — schelet frontend: React 19 + Vite pe Node 24, autentificare prin proxy,
        formatare `ro-MD`, `C16` impus prin ESLint. Verificat pe lanțul real

Descompunerea în 49 de sarcini de dimensiunea unei sesiuni, cu dependențe, agenți de review și
criterii de terminare: `_bootstrap/06-f0-backlog.md`.

**Nicio sarcină F0 nu poate începe încă.** Prima, F0.0.1, cere versiunile stack-ului și tooling-ul
Python (OD-14, OD-15).

**F0.1 este completă, iar F0.2 a început.** Izolarea are ambele straturi: baza refuză prin RLS și
funcții fail-closed, aplicația refuză mai devreme și cu mesaj lizibil — pe request, task, comandă și
shell. Harness-ul de test rulează sub rolul de aplicație și **refuză să pornească altfel**.

**106 de teste pytest trec**, sub `evidenta_app`. Probele manuale Python au fost retrase în aceeași
schimbare care le-a înlocuit; a rămas doar cea SQL, care așteaptă tabelele de tenancy din F0.3.

### F1 — Accounting Core (în curs)

Ordinea din `_input/evidenta-implementation-spec.md` nu este ordinea în care se poate construi:
`journal_entry` are chei străine `NOT NULL` către `period` (F1.5) și `accounting_event` (F1.3), deci
F1.2 nu poate fi prima. Ordinea reală se notează aici, pe măsură ce se stabilește.

- [x] F1.1 — Plan de conturi SNC: **structura**, patru tabele, politici, granturi fără `DELETE`,
      instanțiere în două treceri, subconturi, blocare, închidere; 26 de teste.
      **Fără conținut** (`OD-23`) și **fără propagare** (`OD-03`)
- [x] F1.5 — Perioade și exercițiu fiscal: stări, tranziții, exercițiu cu date explicite, perioada
      TVA distinctă *(forma: [ADR-039](decisions/039-valuta-si-perioade.md) partea II; `OD-58`,
      `OD-62` deschise pe drum)*
      — **F1.5.4 închiderea, 29.08** ([ADR-056](decisions/056-inchiderea-lunii-si-a-exercitiului.md)):
      `period.month_closed` validează clasa 8 și nu postează; `period.year_closed` postează lanțul
      ADR-050 (pașii 1, 3, 4) într-o înregistrare `closing`; pasul 5 e `OD-73`
- [x] F1.3 — Accounting Events: eveniment idempotent, registru de tipuri, ciclu de viață și coadă
      *(vocabularul: [ADR-038](decisions/038-vocabularul-de-evenimente.md))*
- [x] F1.2 — Ledger: `journal_entry`, `journal_line`, `company_dimension`, echilibrul verificat în
      bază, storno *(structura stornoului: [ADR-006](decisions/006-reversal-two-dates.md); cele trei
      date ale liniei și câmpurile de valută: [ADR-039](decisions/039-valuta-si-perioade.md))*
- [ ] F1.4 — Posting Engine: **rezoluția, cei șase invarianți, rolurile cu legarea necondiționată și
      formula ca unitate** ([ADR-048](decisions/048-formula-si-sloturile-tipizate.md)) livrate;
      **primele două handlere livrate, 30.08** — C4 ([ADR-057](decisions/057-diferentele-realizate-la-decontare.md)),
      C5 ([ADR-058](decisions/058-repartizarea-costurilor-indirecte.md)); rămân C2, C1 —
      *deblocat 29.08: `C1`–`C5` clasificate (ADR-036 `Acceptat`),
      legarea condiționată decisă ([ADR-051](decisions/051-chei-de-context-enumerate.md)); rolurile
      lanțului de închidere în catalog ([ADR-050](decisions/050-lantul-de-inchidere-ca-roluri.md))*
- [x] F1.6 — Logică fiscală, primul strat: rotunjirea în registru, selectată după dată; `half_up`,
      2 la sume, 4 la preț — **active**, aprobate de proprietar, `provisional` fiindcă formularul tace
      (`V1` citită 29.08); calea de scriere [ADR-049](decisions/049-rolul-de-date-de-referinta.md);
      precizia cantității pe unitate ([ADR-055](decisions/055-precizia-cantitatii-e-a-unitatii.md)).
      *Criteriul „trece corpusul" se închide cu F1.10*
- [x] F1.7 — Note contabile manuale, solduri inițiale, șabloane de operațiuni — toate prin motor,
      cu API și ecran
- [ ] F1.8 — Rapoarte contabile: **fișa contului, Cartea Mare, rulajele pe corespondențe,
      drill-down la sursă, export CSV** livrate 30.08 (ADR-053 pentru granularitate); rămân jurnalele
      pe document (fără documente postate) și **reconcilierea la leu contra 1C** — criteriul de ieșire,
      care așteaptă extrasul (F3); Excel/PDF `OD-74`
- ~~F1.9 — Importator 1C~~ → **F3, Migration Center** ([ADR-054](decisions/054-importul-e-distributie-corpusul-e-intern.md))
- [ ] F1.10 — Corpus de regresie, **intern**: ~20 de cazuri cu citare, construite de sesiune (ADR-054)
- [x] F1.G2 (`EntryGrid`) — livrată 30.08 pe contractul [ADR-052](decisions/052-contractul-de-tastatura.md);
      nota manuală și soldurile inițiale pe ea
- [ ] F1.G0, F1.G1 (`DataGrid`) — `_bootstrap/07-f1-grile.md`; `DataGrid` servește F1.8, fără
      virtualizare și fără configurație per utilizator (goluri numite); F1.G0 pe `OD-28` → F3

## Blocaje active

| Ce blochează | Ce nu se poate face | Referință |
|---|---|---|
| ~~Corpusul de regresie fiscală nu are cazuri reale cu rezultat verificat~~ | **Reclasificat 2026-08-29** ([ADR-054](decisions/054-importul-e-distributie-corpusul-e-intern.md)): corpusul e intern, construit de sesiunea de implementare cu citare — sarcină (F1.10), nu blocaj. Ce nu prinde — divergența față de practică — se prinde la primul client, F3 | ADR-010, ADR-054, C14, F1.10 |
| ~~Nu există extras real dintr-o bază 1C~~ | **Mutat la F3** cu importatorul (ADR-054). Grilele se validează pe fixture-ul sintetic F1.G0, cu ce se sacrifică scris în `07-f1-grile.md` | OD-28, OD-30 — F3 |
| Nu există semnătură electronică, entitate de test și acces în e-Factura | Formatele declarațiilor și `V2` din ADR-037 (schema XML — condiționează **testul de acceptanță** al rotunjirii, nu codul). **`DNB-08` nu e aici**: ce-i rămâne e `V1`, un document public. *Corectat 2026-08-29, a treia oară* | ADR-010, ADR-037 §5, OD-24, OD-25 |

Primele trei rânduri se rezolvă în câteva ore: o instalare și două decizii. Ultimele trei nu se
rezolvă în cod — cer date reale și acces instituțional, iar de aceea sunt cele care contează.

## Decizii luate în această fază

Zece ADR-uri — opt `Acceptat`, două `Propus`. Index complet: `decisions/README.md`.

| ADR | Ce închide | Status |
|---|---|---|
| 001 — grila de date | restrânge `OD-19`; TanStack Table prin `DataGrid` + `EntryGrid` | Acceptat |
| 002 — guvernanța | `OD-33` | Acceptat |
| 003 — politica RLS pentru tabelele de tenancy | `DN-12`, `OD-07` | Acceptat |
| 004 — contextul de companie | `DN-11`, `OD-08` | Acceptat |
| 005 — versiunile stack-ului | `OD-14` *(nu și `OD-15`)* | Acceptat |
| 006 — stornoul are două date | `DNB-09`, partea structurală | Acceptat |
| 007 — perioada stornoului | `DNB-09`, politica | **Propus** |
| 008 — retenția | `DN-22`, mecanismul | **Propus** |
| 009 — componente și stil | `OD-34`; deblochează `OD-35` | Acceptat |
| 010 — contabilul practicant | `OD-32` | Acceptat |
| 018 — engagementuri multiple | `DN-06` | Acceptat |
| 019 — vocabularul de scope | `DN-07` | Acceptat |

**ADR-007 și ADR-008 sunt deblocate de ADR-010**, dar rămân `Propus`: trec în `Acceptat` la
confirmarea proprietarului, nu automat.

Registrul deciziilor deschise: `decisions/000-open-decisions.md` — 42 de intrări
închise, plus 25 de puncte în Spec A §11 și 11 în Spec B §11.

Deciziile închise anterior, prin documentele de intrare, sunt inventariate în
`_bootstrap/00-inventory.md` §3.1. Trei dintre ele au nevoie de ADR retroactiv.

## Întrebări deschise către om

Ordonate după cât de devreme blochează. Lista de mai jos e reconciliată cu ADR-urile 003–011:
`OD-07`, `OD-08`, `OD-10`, `OD-14`, `OD-15`, `OD-18` și `OD-32` sunt **închise** și au ieșit de aici.

1. **OD-16** — platforma CI și cum rulează suitele **sub rolul de aplicație** într-un runner efemer.
   Blochează F0.0.4 și F0.2.6.
2. **ADR-007** — cele trei întrebări de tratament contabil despre perioada stornoului:
   redeschiderea unei perioade închise înainte de depunere; dacă o corecție după depunere impune
   obligatoriu declarație rectificativă; stornoul unei perioade `locked`. Deblocate de `ADR-010`,
   dar nerăspunse.
3. **OD-37** — cum se listează membrii unui tenant, dat fiind că politica pe `membership` este
   `user_id = current_user_id()`. Blochează ecranele de administrare a echipei (F0.3.2).
4. **OD-11** — unde locuiesc modelele „modelate în F0, implementate mai târziu", dat fiind că
   app-urile Django goale sunt interzise.
5. **OD-40** — acoperă art. 7 și conținutul documentelor primare emise? Art. 11 nu prescrie limba
   pentru ele; singura prevedere, alin. (11), privește documentele primite din străinătate și
   acceptă și rusa. Până la răspuns, produsul nu restricționează nimic.
6. **OD-06, OD-22, OD-23** — deblocate de `ADR-010`, dar nerăspunse: valorile fiscale efective
   cer în continuare actul normativ citat, nu memoria. `OD-22` e **restrânsă** din 29.08 la cote și
   praguri ([ADR-050](decisions/050-lantul-de-inchidere-ca-roluri.md)); calea de scriere există.
7. **Accesul la e-Factura** — semnătură electronică, entitate de test, ghid de integrare. Blochează
   formatele declarațiilor și `V2` (testul de acceptanță al rotunjirii). **Nu** blochează `DNB-08`:
   ce-i rămâne e `V1`, Ordinul MF 118/2017, document public.

**Din stratul documentar (2026-08-28), în ordinea în care blochează.** Niciuna nu e aleasă în cod;
fiecare are un refuz sau o absență explicită în locul ei.

8. **Rotunjirea, încă o dată, dar acum cu un consumator.** `DNB-08` / ADR-037 §3.1–3.3 nu mai
   blochează doar postarea: **nimic nu poate calcula o linie de document.** `document_line` primește
   `net`, `TVA` și `total` gata calculate, iar baza verifică doar `total = net + TVA`. Până la
   deblocare, orice ecran sau import trebuie să aducă sumele de altundeva.
9. **Data cursului valutar** (`ADR-039`, `DN-04`, art. 97 alin. (6)). `document.exchange_rate` este
   **input explicit**, niciodată căutat: `currency.rate_on()` cere ziua exactă și refuză altfel, iar
   `latest_before()` există și nu e chemat de nimeni. Cine decide ziua decide și ce funcție se cheamă.
10. **Vocabularul regimurilor de TVA** — ce tratamente există și cum se numesc. E dată, nu cod:
    `fiscal.vat_regimes()` și `assert_regime()` sunt scrise și **nu sunt chemate de stratul
    documentar**, fiindcă nomenclatorul nu e încărcat (`OD-22`) și un gardian care refuză totul se
    ocolește. Se leagă în ziua în care lista aterizează.
11. **Data contabilă implicită = data documentului.** Ales ca implicit, nu ca identitate — coloana
    există tocmai ca ele să difere. Dacă implicitul e greșit pentru vreun tip, e decizie contabilă.
12. **Anul fiscal al numărului vine din `document_date`**, nu din `accounting_date` (comportamentul
    ADR-022, nemodificat). Dacă înserierea trebuie să urmeze data contabilă, se schimbă.
13. **Validarea nu verifică perioada.** Un document se validează cu dată contabilă într-o perioadă
    închisă; refuzul e al postării (`R12`). Probabil corect — validarea nu e postare — dar e o
    alegere, nu o omisiune.
14. **Conversia e totală și unică:** o proformă sau o comandă produce **un** document, cu toate
    liniile. Facturarea parțială a unei comenzi nu e modelată. La fel stornoul: unul per document.
15. **Anularea documentului produs eliberează sursa** pentru o nouă conversie. Ales; de confirmat.

**Din baza motorului, etapa 1+2 (2026-08-29; [ADR-048](decisions/048-formula-si-sloturile-tipizate.md) §7).**

16. **`OD-69` — ce e „setul fiscal" al cărui număr de versiune ar sta pe antet.** Azi antetul poartă
    data pentru care s-a rezolvat (`fiscal_effective_date`), fiindcă aceea e singura identitate pe
    care o are un set de parametri și logică versionate rând cu rând. Dacă vrei un pachet numit, e
    structură în `fiscal`, cu calea `P-4` (`OD-67`).
17. **Sloturi comune sau per parte.** Instrucțiunea spune „trei sloturi tipizate pe formulă, al
    patrulea opțional" și s-a urmat literal: formula poartă reuniunea a ce declară cele două conturi.
    Un transfer între două valori ale aceluiași cont nu încape într-o formulă, iar peste patru axe
    distincte între cele două conturi se refuză. Dacă la Etapa 8 nu ajunge, e ADR care înlocuiește
    §2.3, nu opt coloane.
18. **„ADR-018 §3 cheia de contopire / §7 cheia agregatelor"** — referința nu se rezolvă în acest
    repository. Dacă e alt document, spune care; s-a construit după intenția enunțată.
19. **Care conturi poartă ce dimensiuni** — declarațiile sunt goale, în CSV-ul planului
    (`dimension_slots`, `required_dimensions`, cu `|` între nume) și per companie prin
    `PATCH /accounts/<id>` cu `dimension_slots`. Decizia e a ta; structura o așteaptă.

**Din F1.8 + F1.G2 (2026-08-30).**

20. **`OD-74` — Excel și PDF pentru rapoarte.** CSV există pe server; Excel cere o bibliotecă
    pinuită, PDF cere pipeline-ul de tipar din `C22`. Care, și când.
21. **Cele trei implicite din ADR-052 §3.1** — `Tab` navighează fără linie nouă, `F4` nomenclator și
    `F2` editare, `Ctrl+Delete` cu a doua apăsare când rândul are conținut — sunt implementate așa;
    confirmă-le sau schimbă-le acum, cât sunt două ecrane pe ele.
22. **Pragurile ADR-053 §3.3** au prima cifră: 22,7 ms pentru fișa unui cont pe o lună la 2.000 de
    documente. Rămân propuse; măsurătoarea la scara „Mare" se rulează cu `EVIDENTA_VOLUME_ROWS`.
23. **`ROUND_HALF_UP` la două zecimale în export** — convenție de afișare, aliniată cu `Intl` din
    client, nu regulă fiscală. Dacă vrei exportul la patru zecimale (scara stocată), e un parametru.

**Din corpusul F1.10 (2026-08-30; `backend/tests/corpus/README.md`, „Divergențe raportate").**

24. **C5 — la ce nivel se aplică cota din SNC „Stocuri" pct. 30 → `OD-77`** (deschisă
    2026-08-30, prin instrucțiune). Anexa 1 a actului aplică
    raportul *efectiv / normal* pe **fiecare produs**, cu capacitatea normală a produsului, și abia
    apoi însumează (103 764,71 în cost, 16 235,29 la cheltuieli). `AllocationFact` poartă **o**
    capacitate normală și **un** volum efectiv; cu cele trei produse într-un singur fapt ar da
    102 000 / 18 000. Corpusul reproduce actul cu un fapt per produs. Dacă faptul trebuie să poarte
    capacitatea per produs e o întrebare de model pe ADR-058, nu a corpusului.
25. ~~**C4 — partea achitată în avans, la diferențe de *curs*.**~~ **Dizolvată 2026-08-30, prin
    datare:** Exemplul 2 e textul din 2013; pct. 11 și 12 în redacția OMF 48/2019 fac avansurile
    nemonetare, neînregistrate la alt curs decât cel inițial — handlerul e redacția în vigoare.
    Textul întrebării, păstrat: Exemplul 2 recunoaște creanța
    integral la cursul livrării și, la trecerea în cont a avansului primit la alt curs, înregistrează
    **783 lei** diferență de curs nefavorabilă pe partea avansată. Handlerul, cu
    `settles_advance = True`, nu postează nimic — pe pct. 23, care stă la *diferențe de sumă*.
    Răspunsul depinde de cum va recunoaște modulul de vânzări (F2) creanța pe partea avansată
    (ADR-039 §3.2, art. 97 și 108 CF); până atunci corpusul reproduce doar termenul decontării.
26. ~~**C5 — banul rămas, confirmare.**~~ **Închisă 2026-08-30:** abatere cunoscută și motivată,
    consemnată în corpus. Textul, păstrat: Tabelul Anexei 1 lasă banul din împărțire pe „B"
    (28 235,30); ADR-058 §2.5 îl pune pe cota cea mai mare, prin instrucțiunea ta. Actul tace despre
    rest, totalurile ies exact, două celule diferă cu un ban. Rămâne cum e, dacă nu spui altfel.
27. **Stornoul parțial n-are legătură navigabilă → `OD-78`** (deschisă 2026-08-30, prin
    instrucțiune; revizorul contabil, pe corpus). SNC „Politici
    contabile" pct. 33 (2) și SNC „Venituri" pct. 17 corectează o *parte* a unei înregistrări; în
    motor asta e o notă manuală cu corespondența inversă, care nu poartă nicio legătură spre
    înregistrarea corectată — cele două legături `R14` există doar la stornoul integral
    (`post_reversal`). Dacă o corecție parțială trebuie să poarte un `corrects_entry_id` pentru
    drill-down din fișa contului, sau descrierea ajunge, e decizia ta; până atunci corpusul afirmă
    rezultatul actului, nu lineage-ul.

Peste acestea, punctele „DECIZIE NECESARĂ" rămase din Spec A §11 și Spec B §11. Dintre cele care
cereau contabilul practicant, `DNB-05`, `DNB-07` și `DNB-09` sunt deblocate de `ADR-010`. `DNB-08`
(rotunjirea TVA) **nu** este blocată de contabil — și nici extern: rămâne `V1`, un document public
(vezi 7).
