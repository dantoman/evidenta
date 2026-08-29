# ADR-049 — Datele de referință au un rol de încărcare, o cale și un jurnal; actele au publicări

- **Status:** Acceptat — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md);
  pornită prin instrucțiunea scrisă a proprietarului din 2026-08-29, punctul 1. **Nu decide nimic
  contabil sau fiscal**: niciun parametru nu primește valoare aici (§7)
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** `OD-67` (calea de scriere a datelor de referință — `P-4`, `OD-56`, istoricul de
  încredere, cursurile BNM), `OD-65` (forma tabelei de publicări), `OD-56` (pliată în `OD-67`)
- **Afectează:** `infra/bootstrap/0004_refdata_role.sql`, `infra/migrations/0058`–`0060`,
  `infra/rls/exceptions.toml` (cheia `writer_role`, forma `platform_log`),
  `infra/schema/append_only.toml`, `platform/audit` (`privileged_access_log`, `privileged_run`),
  `platform/legislation` (app nou), `platform/rls/schema_audit.py` (`IZ-78`), `fiscal/parameters`
  (`load_fiscal_parameters`, `set_confidence`), `accounting/coa` (`load_coa_template`), Spec A
  §2.2 și §6.2 (`P-10`), Makefile, CI, harness-ul de test
- **Legate:** [ADR-003](003-rls-tenancy-tables.md) (cele trei roluri), [ADR-040](040-crearea-tenantului-si-a-companiei.md)
  (`P-9`, calea privilegiată ca funcție), [ADR-043](043-privilegiile-functiilor-rls.md),
  [ADR-045](045-sursa-de-adevar-pentru-parametri.md), [ADR-046](046-istoricul-increderii-in-sursa.md),
  [ADR-037](037-conventii-de-platforma.md) §0 (mecanismul „complet și inert")

---

## 1. Context

Douăsprezece tabele sunt declarate `global_read_only` în `infra/rls/exceptions.toml`: rolul
aplicației le citește, scrierile îi sunt retrase explicit. Pentru opt dintre ele — parametrii
fiscali, sursele lor, istoricul de încredere, versiunile de logică, cursurile BNM, planul de conturi
(două tabele) și registrul de contrapărți — Spec A §6.2 enumeră câte o cale privilegiată (`P-3`,
`P-4`, `P-5`) și, până azi, **niciuna nu avea mecanism**. Singura scriere posibilă era conexiunea de
owner, și numai pentru planul de conturi, printr-o politică pe care `0044` a trebuit s-o adauge ca
încărcătorul să nu fie refuzat de propria bază.

`OD-67` a numit asta o singură gaură, nu trei: „date pe care aplicația nu are voie să le scrie, și
pentru care nu s-a definit cine are". Consecința măsurată în [ADR-037](037-conventii-de-platforma.md)
§0: mecanismul de precizie și rotunjire era complet și **inert** — `fiscal_parameter` nu putea
primi niciun rând în afară de superuser. A șasea apariție a familiei „legat și nepornit" într-o
singură zi.

Spec A §6.1 lăsa deschisă alegerea mecanismului (`DN-17`): funcții `SECURITY DEFINER` expuse
rolului aplicației — forma lui `P-9` — sau un rol separat folosit de procese dedicate, „acceptabil
dacă procesele respective rulează izolat".

Pe drum, `OD-65`: `fiscal_parameter_source` ține **o** publicare per act, iar din PDF-urile
Ministerului Finanțelor s-a verificat (2026-08-28) că OMF 118/2013 și OMF 119/2013 poartă fiecare
două citări și că a doua — *MO nr. 233-237 art. 1534 din 22.10.2013* — e **aceeași** pentru amândouă.

## 2. Opțiuni evaluate

### 2.1 Cine scrie

1. **Conexiunea de owner, generalizată** (starea de fapt, lărgită la toate tabelele). *Avantaj:*
   zero rol nou. *Dezavantaje:* rolul de migrare deține schema — un încărcător rulat ca owner poate
   face `ALTER TABLE` din greșeală; are alt ciclu de viață (rulează la deploy, nu în producție);
   și fiecare tabelă ar avea nevoie de propria politică `TO evidenta_owner`, adică de încă un
   `0044`. *Cost de schimbare ulterioară:* mic, dar crescător cu fiecare tabelă.
2. **Funcții `SECURITY DEFINER` per operațiune, ca `P-9`.** *Avantaj:* granularitate și audit per
   apel, forma pe care §6.1 o preferă. *Dezavantaje:* apelabile de rolul aplicației, deci de orice
   cerere de tenant — iar exact asta refuză `OD-67` („un tenant nu declară că o cotă e confirmată");
   ar cere o noțiune de operator de platformă în interiorul funcției, care nu există (`DN-18`,
   `P-7`); și 476 de conturi printr-o funcție per rând nu e un încărcător, e un protocol.
3. **Un al patrulea rol de bază de date, `evidenta_refdata`** — *ales*. `LOGIN`, `NOINHERIT`, fără
   `BYPASSRLS`, nu deține nimic, nu e membru al nimănui; primește `SELECT, INSERT, UPDATE` și o
   politică `FOR ALL` **doar** pe tabelele de referință, fiecare printr-un `GRANT` scris. Ciclul de
   viață e al încărcării: rulează în producție, dar nu la fiecare cerere, dintr-o comandă de
   operator — procesul izolat pe care §6.1 îl cere. *Dezavantaj:* granița de securitate e a
   procesului, nu a apelului; o greșeală de configurare dă rolului mai mult decât trebuie. *Cum se
   ține:* gardianul de model verifică în **ambele sensuri** (§3.4). *Cost de schimbare:* mic — o
   tabelă nouă de referință e o linie în contract și un `GRANT` în migrația ei.

### 2.2 Unde stă publicarea

1. **Încă un set de coloane pe act** (`official_gazette_number_2`, …). *Dezavantaj:* o coloană nu
   se împarte între două rânduri de act; faptul (b) din `OD-65` o face imposibilă, nu doar urâtă.
2. **Tabelă de publicări atârnată de `fiscal_parameter_source`.** *Dezavantaj:* planul de conturi e
   act **contabil**, nu parametru fiscal (`OD-56`), iar `CoaTemplate` refuzase deliberat o cheie
   spre `fiscal`; publicarea comună celor două ordine ar fi ajuns tot într-un singur modul.
3. **Registru de acte și publicări în `platform`, M:N** — *ales*. `normative_act` (tip, număr,
   dată — toate trei sunt identitatea), `official_publication` (an, număr de Monitor, articol —
   identitatea citării, ziua opțională), `normative_act_publication`. `fiscal_parameter_source.act`
   și `coa_template.act` sunt chei nule spre el (C5), iar coloanele vechi rămân.

## 3. Decizia

### 3.1 Rolul

`infra/bootstrap/0004_refdata_role.sql`, rulat ca superuser, idempotent, cu verificările de la
sfârșit ca la `0001`: fără `BYPASSRLS`, nu superuser, nu membru al lui `evidenta_rls` sau
`evidenta_owner`, fără `CREATE` pe schema publică. Primește `CONNECT` și `USAGE`; **niciun
privilegiu implicit** — spre deosebire de rolul aplicației, fiecare `GRANT` către el e o decizie,
ca la `evidenta_rls`. Parola vine din `REFDATA_DB_PASSWORD`; Makefile, CI și harness-ul de test o
trec la bootstrap exact ca pe celelalte două.

### 3.2 Politicile

`0060`: pe fiecare tabelă de referință, `FOR ALL TO evidenta_refdata USING (true) WITH CHECK
(true)` și `GRANT SELECT, INSERT, UPDATE`. **Fără `DELETE` nicăieri**: datele de referință se
versionează, nu se șterg — un parametru ștampilat ([ADR-047](047-stampila-parametrului-la-postare.md))
sau un cont de șablon copiat de o companie nu are voie să dispară. Istoricul de încredere primește
doar `SELECT` și `INSERT`; triggerul din `0042` rămâne a doua barieră, nu prima. Politica
proprietarului din `0044` e **retrasă**: două uși spre aceeași tabelă sunt chiar „două mecanisme
ușor diferite" pe care `OD-67` le refuză.

### 3.3 Jurnalul

`privileged_access_log` (`0058`), declarat în contract din F0 și construit acum, cu forma din Spec
A §6.3 și două abateri scrise: `actor_user_id` e nul (utilizatorii de sistem din §3.4 nu există
încă, iar o comandă din shell n-are rând de utilizator) lângă un `actor` text obligatoriu; iar
coloana tenantului atins se numește `subject_tenant_id`, fiindcă `tenant_id` pe o tabelă fără
context de tenant e citit de gardian ca derivă (`IZ-76`), iar a-l declara coloană de context ar fi
o minciună. Append-only prin trigger, `bigint`, `occurred_at NOT NULL`, în `append_only.toml`.
**Nimeni nu îl citește prin aplicație**: forma nouă `platform_log` din contract înseamnă zero
privilegii pentru `evidenta_app` — conține tenanți străini, iar „citire liberă" ar fi o interogare
cross-tenant în afara stratului de read models (R7). Cititorul e administrarea platformei, care nu
are încă rol (`DN-18`).

Singura ușă spre conexiune e `platform.audit.services.privileged.privileged_run(path_code, …)`:
deschide tranzacția pe `refdata`, dă corpului un `payload` de completat, și scrie rândul **ultimul,
în aceeași tranzacție** — o rulare care cade nu lasă nici scrieri, nici rând care să pretindă că
s-a întâmplat; una care reușește nu poate comite fără rând. Calea planului de conturi e **`P-10`**,
nouă în Spec A §6.2, fiindcă `P-4` spune „parametri fiscali și versiuni de logică" și planul nu e
niciuna.

### 3.4 Gardianul

`IZ-78`, în `schema_audit.py`, citește cheia nouă `writer_role` din contract și verifică, pe baza
vie (`make drift-check`) și pe cea de test:

- rolul aplicației **nu deține** `INSERT/UPDATE/DELETE` pe o tabelă `global_read_only` — privilegiul,
  nu politica, fiindcă privilegiile implicite din `0001` îl dau și doar un `REVOKE` explicit îl ia
  (`0047` l-a dat târziu, de mână);
- orice politică de scriere de pe tabelă numește **exact** rolul declarat; o a doua ușă e o
  constatare, nu o toleranță;
- scriitorul declarat are `INSERT` și **nu** are `DELETE` acordat;
- și în sens invers: un rol declarat scriitor care nu deține nimic nu are niciun privilegiu și
  nicio politică pe vreo tabelă care nu-l declară — altfel un rol îngust de încărcare devine tăcut
  al doilea rol de aplicație, și nimic pe partea tabelei n-ar observa.

Prima rulare a găsit ce n-ar fi găsit nimeni citind: `permission` are din `0019` o politică de
scriere pentru `evidenta_owner`. Corect — catalogul e cod (ADR-020) și se însămânțează din migrarea
care îl definește — deci declarat ca atare, nu tolerat.

### 3.5 Cine scrie ce, azi

| Cale | Ce | Prin |
|---|---|---|
| `P-4` | parametri fiscali, surse, versiuni de logică, istoricul de încredere | `manage.py load_fiscal_parameters <fișier.toml>`; `fiscal.parameters.services.confidence.set_confidence` |
| `P-10` | planul de conturi (`coa_template`, `coa_template_account`) și actul lui | `manage.py load_coa_template` (`make seed-coa`) |
| `P-3` | cursul BNM (`exchange_rate`) | politica și privilegiul există; conectorul e `OD-26` |
| `P-5` | registrul de contrapărți | idem; alimentarea e F2 |

Încărcătorul de parametri refuză la ușă ce refuză și modelul, cu mesajul potrivit: un act fără
`effective_from` nu poate purta parametri (R15), un rând `active` nu se editează — o valoare nouă e
un rând nou cu `valid_from` propriu (R15, R18) —, `provisional` cere motiv, și **nimic nu intră
altfel decât `draft`**: activarea e actul contabilului practicant (Amendament D.1), iar un fișier
nu poate purta o aprobare.

## 4. Consecințe

- **Devine posibil:** F1.6 are cale de scriere — precizia și rotunjirea nu mai sunt inerte;
  conținutul planului de conturi ajunge în producție prin aceeași cale ca în dezvoltare, cu jurnal;
  cursurile BNM au unde ateriza când vine conectorul; `set_confidence` nu mai primește conexiunea de
  la apelant. O tabelă nouă de referință costă o linie în contract și un `GRANT`.
- **Devine imposibil sau scump, asumat:** un serviciu care servește cereri nu poate atinge
  `refdata` fără să treacă prin `privileged_run`, deci fără rând de jurnal; nimeni nu șterge date de
  referință, nici prin rolul de încărcare — corecția e un rând nou; `load_coa_template` pe
  conexiunea de owner e refuzat de acum, deliberat.
- **Ce se modifică:** Spec A §2.2 (al patrulea rol) și §6.2 (`P-10`); `OD-67`, `OD-65`, `OD-56`
  închise în registru; `docs/PROGRESS.md`; `08-f1-backlog.md` F1.6 (`OD-67` iese din „Blocat de").
- **Ce se verifică automat:** `tests/isolation/test_refdata_role.py` (atributele rolului din
  `pg_roles`; scrie referință, aplicația nu; `permission denied` — nu zero rânduri — pe `company`,
  `tenant`, `journal_entry`; fără `DELETE`; un rând per rulare, niciunul la eșec; jurnalul invizibil
  aplicației și nerescriibil nici de administrator); `tests/isolation/test_reference_loaders.py`
  (planul de 476 de conturi de două ori, actul cu ambele publicări, rândul de jurnal; parametrii ca
  `draft`, idempotenți, `active` needitabil, act fără dată refuzat; fișierul livrat încarcă actul și
  zero valori); `tests/schema_guard/test_reference_load_policy.py` (fiecare scriitor declarat
  citește și inserează *prin politică*); `test_model_guard.py` (cinci autoteste `IZ-78`, ca regula
  să fie văzută căzând); `make drift-check` pe baza vie.

## 5. Ce s-a măsurat

- Pe baza de test, sub `evidenta_refdata`: `SELECT count(*) FROM company` → `InsufficientPrivilege`,
  nu `0`. Diferența contează: `0` ar fi însemnat o politică, adică o ușă închisă azi și deschisă
  de următoarea politică adăugată.
- Prima rulare a lui `IZ-78` pe schema reconstruită: politica `permission_platform_write` a
  proprietarului (§3.4), și `IZ-76` pe `tenant_id` din jurnal (§3.3). Amândouă corecte, amândouă
  invizibile la citire.
- Contractul `append_only.toml` avea deja `privileged_access_log`, din F0.1; a doua declarație,
  adăugată de sesiunea aceasta, a fost refuzată de gardian („declared twice") înainte de orice test.

## 6. Ce NU decide

Nicio valoare de parametru. `platform_conventions.toml` livrează **actul** (OMF 118/2017, cu
publicarea citată în ADR-037 §0) și **niciun parametru**: nici valorile preciziei, nici data intrării
în vigoare n-au fost citite din act (`V1`), iar o dată inventată e același defect ca o cotă inventată,
în altă coloană. Șablonul celor două intrări stă în fișier, în comentariu, pentru ziua în care
`V1` e citită. `OD-22` rămâne deschisă pentru partea ei de parametri fiscali reali.

## 7. Ce se raportează

- `P-9` (`rls.provision_company`) **nu scrie** încă în `privileged_access_log`: tabela nu exista
  când a fost scrisă funcția. Spec A §6.1 o cere; e o datorie separată, numită aici.
- Utilizatorii de sistem din Spec A §3.4 nu există; `actor_user_id` rămâne nul pe rulările din
  shell până atunci.
- `DN-17` (funcții sau rol) se închide **parțial** prin această decizie: rolul, pentru încărcarea
  datelor de referință; `P-9` rămâne funcție, fiindcă e apelată dintr-o cerere de utilizator, unde
  un rol de proces nu are ce căuta. Cele două forme coexistă pe criteriul din §6.1 — cine apelează.

## 8. Surse

- Instrucțiunea proprietarului, 2026-08-29, punctul 1; `docs/decisions/000-open-decisions.md`,
  rândurile `OD-56`, `OD-65`, `OD-67`.
- Spec A §2.2, §3.4, §6.1–6.3; `CLAUDE.md` — `R5`, `R7`, `R15`, `R18`, `R21`, `C5`, `C30`, `C31`,
  `C34`, `T1`.
- [ADR-037](037-conventii-de-platforma.md) §0 — identitatea și publicarea OMF 118/2017, citate
  dintr-un document al Ministerului Finanțelor; textele consolidate MF pentru OMF 118/2013 și
  119/2013 (verificarea din 2026-08-28 consemnată în `OD-65`).
- `infra/migrations/0044`, `0047` — cele două corecții manuale pe care `IZ-78` le face mecanice.
