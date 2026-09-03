# ADR-092 — Consola citește metadatele platformei prin funcții enumerate și își administrează personalul prin `P-12`

- **Stare:** Acceptat — tehnic (arhitectură delegată); proprietarul confirmă sau răsturnă, cu
  declanșatoarele din §6
- **Data:** 2026-09-03
- **Decis de:** sesiunea de implementare (`evidenta-82`), la instrucțiunea proprietarului: *„adaugă
  restul paginilor și funcționalității"* consolei, dată după ce a întrebat dacă consola „va fi și
  backofisul administratorului"
- **Închide:** `OD-133` (calea prin care `admin` administrează `platform_staff` din consolă)
- **Deschide:** `OD-134`
- **Atinge:** Spec A §6.2 (rândul `P-12`), §14 (lista funcțiilor de citire ale consolei, paginile),
  `infra/migrations/0076`, `platform/audit` (`PrivilegedPath`), `platform/identity/console_views.py`,
  `platform/{tenancy,audit,capabilities,flags}/console_views.py`, `accounting/coa/console_views.py`

## 1. Problema: paginile consolei sunt interogări cross-tenant prin definiție

[ADR-076](076-planul-de-control-al-platformei.md) §4.3 enumeră ce administrează consola: spațiile,
abonamentele, capabilitățile, ringurile și flagurile, parametrii fiscali, versiunile planului de
conturi, jurnalul căilor privilegiate, granturile de suport, incidentele. Prima pagină (parametrii
fiscali, [ADR-091](091-consola-scrie-referinta-din-procesul-web.md)) a costat puțin fiindcă tabelele
ei sunt globale: rolul aplicației le citește sub orice context.

Restul nu sunt globale. „Spațiile" e tabela `tenant`; „capabilitățile" e `capability_activation`,
cu `tenant_id`; „ringurile" sunt `tenant_release_ring`; jurnalul e `platform_log`, pe care rolul
aplicației n-are **niciun** privilegiu (Spec A §6.3). Sub contextul de consolă — fără tenant, prin
construcție — orice politică de tenant ridică eroare (măsurat, `test_console.py`). Deci fiecare din
aceste pagini e o interogare cross-tenant, iar `R7` le permite doar în read models și în „căile
privilegiate enumerate în Spec A".

A doua întrebare e `OD-133`: `admin` „administrează `platform_staff` însuși" (ADR-076 §4.1), dar
tabela se scria doar din shell, sub rolul de instalare, fără rând de jurnal.

## 2. Opțiuni evaluate

### 2.1 Citirile

1. **Read models (`rm_*`, `P-6`).** *Avantaje:* stratul pe care `R7` îl numește primul.
   *Dezavantaje:* read models sunt proiecții **pe firmă** (`readmodel_firm`, filtrare pe `firm_id`),
   construite de un job; consola n-are firmă și n-are job; iar o proiecție a tabelei `tenant` ar fi
   o copie a unei tabele de 60 de rânduri, actualizată de un worker care nu rulează în dezvoltare.
   *Cost:* mare, pentru o problemă pe care n-o are.
2. **Rolul de referință ca cititor.** *Dezavantaje:* `evidenta_refdata` n-are privilegii pe
   `tenant`, `membership`, `capability_activation`, și gardianul (`IZ-78`, sweep) le refuză pe drept:
   un rol de încărcare care citește tabelele tenanților e un al doilea rol de aplicație. *Cost:*
   contrazice ADR-049.
3. **Funcții `SECURITY DEFINER` înguste, în schema `rls`, deținute de `evidenta_rls`, câte una pe
   pagină, cu paznicul în interior.** Forma lui `rls.resolve_tenant_by_subdomain` și `rls.auth_*`
   (0016, 0028): citiri care preced sau depășesc contextul, expuse una câte una. Fiecare începe cu
   `rls.console_caller_role()`, care **refuză când există context de tenant** — funcția nu se
   apelează de pe gazda unui client, oricine ar fi apelantul — și **refuză când apelantul n-are rând
   viu în `platform_staff`**. Abia apoi citește, și întoarce doar coloanele din ADR-076 §4.3: nicio
   sumă, niciun document, niciun nume de partener. *Dezavantaje:* încă o listă de funcții de
   întreținut; se ține în Spec A §14. *Cost de schimbare:* mic — o funcție se înlocuiește cu alta.

### 2.2 Scrierea personalului

1. **Rămâne shell-ul.** Sincer pentru primul `admin`; nesincer după: „cine a acordat cui ce" ar fi
   istoricul de bash al cuiva.
2. **Funcție `SECURITY DEFINER` apelată din cererea `admin`-ului** — criteriul literal „cine
   apelează" din Spec A §6.2. *Dezavantaje:* ADR-091 §3 a precizat criteriul: `P-9` e `SECURITY
   DEFINER` fiindcă apelantul e **utilizator al unui tenant**; angajatul platformei, pe gazdă fără
   tenant, asupra unei tabele globale, e cealaltă categorie. `platform_staff` are deja scriitor
   declarat (`evidenta_refdata`, 0075) și nicio funcție.
3. **`P-12`, pe conexiunea de referință, prin `privileged_run`, apelant `admin` verificat în cod.**
   Aceeași formă ca `P-4` din ADR-091; rândul de jurnal poartă `actor = "console:admin"`,
   `actor_user_id` și, în `payload`, cui i s-a acordat sau retras ce.

## 3. Decizia

**Citirile — opțiunea 3; scrierea — opțiunea 3.**

Funcțiile de citire ale consolei (0076): `rls.console_tenants()`, `rls.console_staff()`,
`rls.console_user_by_email(text)`, `rls.console_privileged_log(text, text, integer)`,
`rls.console_capabilities()`, `rls.console_release_rings()`, `rls.console_flag_overrides()`.
Paznicul comun `rls.console_caller_role()` e intern. Lista trăiește în Spec A §14 și în
`tests/schema_guard/test_function_privileges.py` (`GRANTED_TO_APP`), unde lărgirea e o editare pe
care cineva o citește. Nu lasă rând în `privileged_access_log`: sunt citiri de metadate ale
platformei, aceeași clasă ca 0016/0028, care nu loghează. Scrierile consolei loghează.

`P-12` — „Administrarea angajaților platformei": acordă și retrage roluri în `platform_staff`, din
consolă, de către `admin`, cu rând per operațiune. Trei reguli în serviciu, nu în ecran: o persoană
poartă un singur rol (cheia primară e persoana; schimbarea e retragere apoi acordare, ca ambele date
să existe); un `admin` nu își retrage propriul rol (ultimul admin ar închide consola pentru toți);
contul acordat trebuie să existe și să fie activ (`rls.console_user_by_email`). Primul `admin` rămâne
al shell-ului (`grant_platform_staff`), unde și repararea unei console blocate e legitimă — de aceea
comanda **nu** are paza auto-retragerii.

Cine citește ce: orice angajat viu citește toate paginile (sunt metadate ale platformei); scrie doar
rolul pe care ADR-076 §4.1 îl numește — `operator` pe `P-4`, `admin` pe `P-12`. Verificat în cod
(`platform/api/permissions.py`), nu afirmat.

## 4. Consecințe mecanice

- **Paginile construite (03.09.2026):** Spații, Capabilități, Ringuri și flaguri, Angajații
  platformei, Parametri fiscali (ADR-091), Planuri de conturi, Jurnalul căilor privilegiate.
  Toate doar citire, în afară de parametrii fiscali și de personal.
- **Paginile neconstruite, cu motivul, spus și în interfață:** *Abonamente și planuri* — tabelele
  `plan`, `subscription`, `billing_account` nu există (modulul de facturare nu e construit; ADR-082,
  ADR-086 sunt decizii, nu cod); *Granturi de suport* — ADR-077 e acceptat și neconstruit (`P-7`
  n-are tabelă); *Incidente* — nu există stare de joburi de citit, nu rulează niciun worker. Nu se
  desenează intrări pentru ele: o intrare care duce nicăieri învață oamenii să nu creadă bara laterală.
- **Ce nu face consola nici pe paginile construite:** nu creează spații (ADR-078 §3.1 o prevede;
  cere `P-11`, revendicarea, neconstruită — comanda `create_tenant` rămâne canalul), nu suspendă și
  nu arhivează (regimurile din Spec A §9.4 nu sunt servite), nu atribuie ringuri și nu suprascrie
  flaguri (nimic din produs nu scrie azi aceste tabele; o cale de scriere e un ADR), nu activează
  capabilități (actul e al clientului, în spațiul lui), nu încarcă planuri de conturi (`P-10` e din
  fișier).
- **Spec A** primește rândul `P-12` în §6.2 și, în §14, lista funcțiilor de citire și starea
  paginilor. `PrivilegedPath` primește `P-11` (declarat de ADR-081, fără apelant încă) și `P-12`;
  constrângerea CHECK a jurnalului le enumeră (migrarea `audit/0004`).
- **Ce se verifică automat:** `tests/isolation/test_console_pages.py` — o funcție de consolă refuză
  sub context de tenant și refuză un apelant care nu e angajat; spațiile vin cu numărători și fără
  conținut; un `operator` nu acordă roluri, un `admin` acordă și rândul de jurnal `P-12` îl numește;
  o persoană poartă un rol; un admin nu se retrage pe sine; paginile răspund 403 pe gazda unui tenant.
  `test_function_privileges.py` ține lista funcțiilor executabile de aplicație.

## 5. Ce devine posibil, imposibil, scump

- **Posibil:** back office-ul platformei e un ecran, nu un `psql`: cine sunt clienții și în ce stare,
  cine a rulat ce cale și când, cine e angajat și cu ce rol — fără ca vreo pagină să poată arăta o
  cifră a vreunui client.
- **Imposibil prin construcție:** ca o pagină de consolă să citească o tabelă de tenant altfel decât
  printr-o funcție din lista din Spec A §14 — sub contextul de consolă politicile ridică eroare, iar
  funcțiile refuză oricui nu e angajat și orice apel venit dintr-un context de tenant.
- **Scump, deliberat:** orice pagină nouă care ar avea nevoie de altceva decât metadate. Trebuie să
  treacă prin ADR-077 (consimțământ) sau să nu existe.

## 6. Ce rămâne deschis și când se revine

- **`OD-134` — o persoană cu două roluri.** ADR-076 fixează trei roluri și cheia primară pe
  persoană, deci un singur rol viu. Proprietarul e azi singurul om al platformei și are nevoie și de
  `operator` (parametri), și de `admin` (personal). Azi: două conturi, sau re-acordarea din shell.
  Variantele: `admin` cuprinde `operator`; roluri multiple per persoană (cheie compusă); un al
  patrulea rol `owner`. Fiecare schimbă ADR-076 §4.1, deci e ADR nou, al proprietarului. Declanșator:
  prima săptămână în care proprietarul folosește consola singur.
- **Scrierile care lipsesc** (ringuri, flaguri, spații, suspendare) primesc fiecare calea lor când
  apare modulul care le dă sens — nu preventiv.
- **Declanșatorul din ADR-091 §6** rămâne: credențiale separate web / worker mută `P-4` și `P-12`
  într-un task, cu aceleași servicii.

## Surse

- Spec A §6.1–§6.3, §9.4, §13.5, §14; `R7`, `R23`, `R24`, `R25`, `C10`.
- [ADR-049](049-rolul-de-date-de-referinta.md), [ADR-076](076-planul-de-control-al-platformei.md),
  [ADR-077](077-grantul-de-suport.md), [ADR-078](078-cine-poate-crea-un-tenant.md) §3.1,
  [ADR-081](081-revendicarea-optionala.md), [ADR-091](091-consola-scrie-referinta-din-procesul-web.md).
- `infra/migrations/0016`, `0028` (forma funcțiilor de cerere), `0075`, `0076`.
- Măsurat: `plan`, `subscription`, `billing_account`, tabelele grantului de suport — absente din
  modele; `tenant_release_ring`, `feature_flag_override` — fără scriitor în servicii.
- Conversație 2026-09-03.
