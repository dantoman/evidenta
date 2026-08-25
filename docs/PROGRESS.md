# Stare proiect

> Acest fișier este mecanismul prin care munca supraviețuiește resetării contextului între sesiuni.
> Se citește la începutul fiecărei sesiuni și se actualizează la sfârșit. O sesiune care nu îl
> actualizează lasă proiectul într-o poziție din care următoarea sesiune reconstruiește contextul
> ghicind.

## Faza curentă

**F0 — Fundament.** Inițializarea s-a terminat; implementarea a început cu **F0.1 — roluri de bază
de date și infrastructură RLS**.

## Ultima sesiune

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

## Sesiunea anterioară

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
  - [ ] F0.6.3 — atașamente *(blocat de DN-16 și de providerul S3)*
  - [x] F0.6.5 — notificări: in-app complet, canalul de e-mail modelat fără transport (OD-50);
        închide conflictul X-9
- [ ] F0.7 — Master data    ← ÎN CURS
  - [x] F0.7.1 — `CounterpartyRegistry` global, doar citire la ambele straturi
  - [x] F0.7.2 — `Partner`, nivel tenant, unic pe IDNO
  - [x] F0.7.3 — `CompanyPartner`, configurare per companie
  - [x] F0.7.4 — `Item`, `ItemCategory`, `UnitOfMeasure`, `UnitConversion`
  - [ ] F0.7.5 — `Warehouse` *(blocat de OD-11)*
  - [ ] F0.7.6 — dimensiuni: ADR, nu cod *(blocat de DNB-02)*
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
- [ ] F0.10 — Convenții API și schelet frontend

Descompunerea în 49 de sarcini de dimensiunea unei sesiuni, cu dependențe, agenți de review și
criterii de terminare: `_bootstrap/06-f0-backlog.md`.

**Nicio sarcină F0 nu poate începe încă.** Prima, F0.0.1, cere versiunile stack-ului și tooling-ul
Python (OD-14, OD-15).

**F0.1 este completă, iar F0.2 a început.** Izolarea are ambele straturi: baza refuză prin RLS și
funcții fail-closed, aplicația refuză mai devreme și cu mesaj lizibil — pe request, task, comandă și
shell. Harness-ul de test rulează sub rolul de aplicație și **refuză să pornească altfel**.

**106 de teste pytest trec**, sub `evidenta_app`. Probele manuale Python au fost retrase în aceeași
schimbare care le-a înlocuit; a rămas doar cea SQL, care așteaptă tabelele de tenancy din F0.3.

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

Peste acestea, punctele „DECIZIE NECESARĂ" rămase din Spec A §11 și Spec B §11. Dintre cele care
cereau contabilul practicant, `DNB-05`, `DNB-07` și `DNB-09` sunt deblocate de `ADR-010`. `DNB-08`
(rotunjirea TVA) **nu** este: depinde de validatorul SFS, nu de expertiză contabilă.
