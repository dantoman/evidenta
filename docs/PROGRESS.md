# Stare proiect

> Acest fișier este mecanismul prin care munca supraviețuiește resetării contextului între sesiuni.
> Se citește la începutul fiecărei sesiuni și se actualizează la sfârșit. O sesiune care nu îl
> actualizează lasă proiectul într-o poziție din care următoarea sesiune reconstruiește contextul
> ghicind.

## Faza curentă

**Felia verticală merge cap-coadă: companie → plan de conturi → notă manuală → balanță echilibrată.**
Un test de integrare o parcurge prin HTTP, sub rolul aplicației
(`backend/tests/integration/test_vertical_slice.py`). Suita: **745 trec, 1 sărit.**

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


**F1 — Accounting Core. Firul de implementare s-a oprit pe decizii, nu pe cod.** `F1.4.2` — rolurile
de cont și legarea — e blocată de două ori: [ADR-036](decisions/036-forma-postarii.md) e `Propus`
(cazurile `C1`–`C5` cer SNC citat), iar `OD-55` decide forma tabelei de legare, fiindcă chei de
context definibile de client înseamnă evaluator de expresii peste `payload` — chiar DSL-ul respins
în același ADR. *Backlogul spune pentru `F1.4.2` „Blocat de: —"; registrul spune contrariul. Cine
citește doar backlogul construiește tabela înainte să se știe ce formă are.*

**F1 — Accounting Core.** F0 este închisă (criteriul de ieșire îndeplinit, mai jos). Livrate:
**F1.1** (planul de conturi, structura fără conținut) cu API-ul lui, **F1.3** (evenimentele),
**F1.5** (perioadele) și **F1.2** (registrul). Trei sesiuni lucrează în paralel în același checkout.

Descompunerea completă: `_bootstrap/08-f1-backlog.md` — patru fire care pot merge în paralel, cu
`F1.2.1` ca singur punct de sincronizare timpuriu, și tabelul de blocaje la final.

## Ultima sesiune

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

Suita: **863 trec, 1 sărit.** `mypy` nu adaugă nicio eroare peste linia de bază de la `HEAD`
(18, în trei fișiere neatinse de sesiunea asta — măsurat într-un worktree curat, nu presupus).

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
- [ ] F1.5 — Perioade și exercițiu fiscal *(înainte de F1.2 — `journal_entry.period_id` e
      `NOT NULL`; forma e fixată de [ADR-039](decisions/039-valuta-si-perioade.md) partea II)*
- [ ] F1.3 — Accounting Events *(înainte de F1.2, din același motiv; vocabularul e închis prin
      [ADR-038](decisions/038-vocabularul-de-evenimente.md))*
- [ ] F1.2 — Ledger: `journal_entry`, `journal_line`, `company_dimension`, echilibrul verificat în
      bază *(structura stornoului: [ADR-006](decisions/006-reversal-two-dates.md); cele trei date ale
      liniei și câmpurile de valută: [ADR-039](decisions/039-valuta-si-perioade.md))*
- [ ] F1.4 — Posting Engine *(blocat pe `OD-55`, deschisă de [ADR-036](decisions/036-forma-postarii.md),
      care e `Propus`)*
- [ ] F1.6 — Logică fiscală, primul strat
- [ ] F1.7 — Note contabile manuale și solduri inițiale
- [ ] F1.8 — Rapoarte contabile
- [ ] F1.9 — Importator 1C, fundament *(`OD-28`)*
- [ ] F1.10 — Corpus de regresie fiscală
- [ ] F1.G0, F1.G1 (`DataGrid`), F1.G2 (`EntryGrid`) — `_bootstrap/07-f1-grile.md`;
      `EntryGrid` cere întâi `OD-36`

## Blocaje active

| Ce blochează | Ce nu se poate face | Referință |
|---|---|---|
| Corpusul de regresie fiscală nu are cazuri reale cu rezultat verificat | Nimic nu verifică mecanic conținutul contabil; este singura măsură de risc rămasă după ADR-010 | ADR-010, C14, F1.10 |
| Nu există extras real dintr-o bază 1C | `DataGrid` și `EntryGrid` nu pot fi validate pe structuri neanticipate; volumul se poate simula, structura nu | OD-28, OD-30, `_bootstrap/07-f1-grile.md` |
| Nu există semnătură electronică, entitate de test și acces în e-Factura | `DNB-08` (rotunjirea TVA) și formatele declarațiilor. **Singurul element extern pe drumul critic** | ADR-010, OD-24, OD-25 |

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
6. **OD-06, OD-22, OD-23** — deblocate de `ADR-010`, dar nerăspunse: valorile fiscale efective și
   planul de conturi SNC cer în continuare actul normativ citat, nu memoria.
7. **Accesul la e-Factura** — semnătură electronică, entitate de test, ghid de integrare.
   Singurul element extern pe drumul critic; de el depinde `DNB-08`.

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

Peste acestea, punctele „DECIZIE NECESARĂ" rămase din Spec A §11 și Spec B §11. Dintre cele care
cereau contabilul practicant, `DNB-05`, `DNB-07` și `DNB-09` sunt deblocate de `ADR-010`. `DNB-08`
(rotunjirea TVA) **nu** este: depinde de validatorul SFS, nu de expertiză contabilă.
