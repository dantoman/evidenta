# Spec A — Identitate, tenancy, engagement, billing, release

- **Status:** draft. **Necesită review uman atent înainte de a fi considerat valid.**
- **Data:** 2026-08-24
- **Derivă din:** `_input/evidenta-master-plan-v2.md`, `_input/evidenta-master-plan-v2-amendament-1.md`
  (prevalează), `_input/evidenta-implementation-spec.md`
- **Blochează:** F0.1–F0.7. Fără această specificație, sarcinile respective nu au destul detaliu
  pentru implementare.

## Cum se citește

Textul normal este specificație: se implementează ca atare.

Blocurile marcate **`DECIZIE NECESARĂ (DN-nn)`** sunt puncte unde documentele de intrare nu dau
suficient pentru a specifica. Conțin opțiunile identificate și implicațiile fiecăreia. **Nu au fost
alese aici.** Lista completă este în secțiunea 11. Unde restul documentului trebuie totuși să
continue, se scrie astfel încât consecința fiecărei opțiuni să fie explicită — niciodată alegând
tacit.

SQL-ul este *aproape-SQL*: sintaxă PostgreSQL reală, dar numele de tabele și coloane se validează la
implementare împotriva modelelor Django. Tipurile sunt PostgreSQL; echivalentele Django se aleg la
F0.3.

---

## 1. Entități

Convenții comune tuturor tabelelor din această specificație:

- cheie primară `UUID`, generată în aplicație (entități expuse extern — regula C6 din `CLAUDE.md`)
- `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()`
- ștergerea fizică nu există pentru nicio entitate din această specificație; ciclul de viață se
  exprimă prin `status` și prin coloane de dată
- toate datele de tip „moment" sunt `timestamptz`; toate datele calendaristice de business
  (valabilitate, dată efectivă) sunt `date`, pentru că se compară cu granițe de perioadă contabilă

### 1.1 `Tenant`

Clientul SaaS. Proprietarul datelor. Nu are `tenant_id` — este rădăcina.

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | uuid | PK | |
| `subdomain` | citext | NOT NULL, UNIQUE, CHECK `~ '^[a-z][a-z0-9-]{2,29}$'` | Singura sursă a contextului de tenant în request (C8) |
| `legal_name` | text | NOT NULL | |
| `status` | text | NOT NULL, CHECK în `('active','suspended','offboarding','archived')` | Vezi 9.4 |
| `claimed_at` | timestamptz | NULL | Faptul revendicării, nu un status: un tenant nerevendicat e perfect `active`. [ADR-081](../decisions/081-revendicarea-optionala.md) |
| `default_locale` | text | NOT NULL, DEFAULT `'ro'` | Există din F0, cu o singură valoare posibilă. Este un câmp, nu o funcționalitate — ADR-014 |
| `primary_contact_user_id` | uuid | NULL, REFERENCES `user` | Contact administrativ; nu implică drepturi |
| `suspended_at`, `offboarding_started_at`, `archived_at` | timestamptz | NULL | |
| `created_at`, `updated_at` | timestamptz | NOT NULL | |

Indici: `UNIQUE (subdomain)`; `(status)` parțial pentru joburile de offboarding.

**Nume rezervate de subdomeniu.** Lista se ține versionată în cod și include cel puțin: `www`,
`api`, `admin`, `app`, `static`, `assets`, `mail`, `status`, `docs`, `help`, `support`, `billing`,
`firm`, `partner`. Un subdomeniu rezervat nu poate fi alocat; verificarea se face la creare și la
schimbare.

**Schimbarea subdomeniului** este o operațiune administrativă cu urmă în audit. Subdomeniul vechi
nu se eliberează pentru realocare — vezi `DN-02`.

### 1.2 `Company`

Entitatea juridică cu ledger propriu. Un tenant poate avea mai multe (holding).

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | uuid | PK | |
| `tenant_id` | uuid | NOT NULL, REFERENCES `tenant` | Context RLS |
| `idno` | text | NOT NULL, CHECK lungime și formă IDNO | Vezi `DN-03` pentru unicitate globală |
| `legal_name` | text | NOT NULL | |
| `short_name` | text | NULL | Pentru interfață și rapoarte |
| `legal_form` | text | NULL | Din registrul global de contrapărți, dacă există |
| `functional_currency` | char(3) | NOT NULL, DEFAULT `'MDL'` | Vezi `DN-04` |
| `fiscal_year_start_month` | smallint | NOT NULL, DEFAULT 1, CHECK 1–12 | Vezi `DN-05` |
| `accounting_start_date` | date | NOT NULL | Data de la care compania ține contabilitatea în Evidenta. Postarea înainte de ea este refuzată |
| `status` | text | NOT NULL, CHECK în `('active','suspended','closed')` | |
| `registered_address` | jsonb | NULL | |
| `created_at`, `updated_at` | timestamptz | NOT NULL | |

Indici: `UNIQUE (tenant_id, idno)`; `(tenant_id, status)`.

Statutul de plătitor de TVA **nu** este un boolean pe companie. Este stare cu dată efectivă:

`company_vat_registration`: `id`, `tenant_id`, `company_id`, `vat_code text NOT NULL`,
`valid_from date NOT NULL`, `valid_to date NULL`, `source text`, `created_at`.
Constrângere de neîntrepătrundere pe `(company_id, daterange(valid_from, valid_to))`.

> Motivul: o companie se înregistrează și se poate radia ca plătitor de TVA în cursul anului.
> Recalcularea unei perioade trecute trebuie să folosească statutul valabil atunci (R18).

### 1.3 `Firm`

Firma de contabilitate. Este ea însăși un actor, cu propriul tenant pentru propria contabilitate.

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | uuid | PK | |
| `tenant_id` | uuid | NOT NULL, UNIQUE, REFERENCES `tenant` | Tenantul propriu al firmei. `UNIQUE` — un tenant nu poate fi două firme |
| `name` | text | NOT NULL | |
| `idno` | text | NULL | |
| `status` | text | NOT NULL, CHECK în `('active','suspended','closed')` | La `closed`, engagementele active se suspendă — vezi 4.6 |
| `created_at`, `updated_at` | timestamptz | NOT NULL | |

Indici: `UNIQUE (tenant_id)`; `(status)`.

**Distincția care nu se colapsează:** holdingul este `Tenant → Company*` (proprietate comună);
firma de contabilitate este `Firm → Engagement* → Tenant*` (acces delegat, revocabil). Dacă cele
două se modelează identic, schimbarea contabilului devine migrare de date pe un ledger imutabil,
subdomeniul aparține contabilului în loc de client, iar clienții rămân captivi dacă firma se
închide.

### 1.4 `Engagement`

Relația `Firm → Tenant`. Delegată, revocabilă, cu valabilitate, scope și stare.

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | uuid | PK | |
| `firm_id` | uuid | NOT NULL, REFERENCES `firm` | |
| `client_tenant_id` | uuid | NOT NULL, REFERENCES `tenant` | Tenantul care rămâne proprietarul datelor |
| `status` | text | NOT NULL, CHECK în `('invited','active','suspended','revoked','expired','transferred')` | Vezi 4 |
| `covers_all_companies` | boolean | NOT NULL, DEFAULT false | Dacă `true`, scope-ul acoperă companiile existente **și viitoare** ale tenantului |
| `valid_from` | date | NOT NULL | |
| `valid_to` | date | NULL | `NULL` = nedeterminat |
| `initiated_by` | text | NOT NULL, CHECK în `('firm','tenant')` | Invitația poate porni din ambele direcții |
| `invited_by_user_id` | uuid | NOT NULL, REFERENCES `user` | |
| `invited_at` | timestamptz | NOT NULL | |
| `accepted_by_user_id` | uuid | NULL, REFERENCES `user` | |
| `accepted_at` | timestamptz | NULL | |
| `suspended_at` | timestamptz | NULL | |
| `revoked_at` | timestamptz | NULL | |
| `revoked_by_user_id` | uuid | NULL, REFERENCES `user` | |
| `revocation_reason` | text | NULL | |
| `transferred_to_engagement_id` | uuid | NULL, REFERENCES `engagement` | Setat pe engagementul vechi la transfer |
| `created_at`, `updated_at` | timestamptz | NOT NULL | |

Constrângeri:

- `CHECK (valid_to IS NULL OR valid_to >= valid_from)`
- `CHECK (status <> 'active' OR accepted_at IS NOT NULL)` — activ fără acceptare este imposibil
- `CHECK (status <> 'revoked' OR revoked_at IS NOT NULL)`
- unicitate: `UNIQUE (firm_id, client_tenant_id) WHERE status IN ('invited','active','suspended')`
  — o firmă are cel mult o relație vie cu un tenant la un moment dat

Indici: `(client_tenant_id, status)`; `(firm_id, status)`;
`(client_tenant_id, valid_from, valid_to) WHERE status = 'active'`.

> **Delegarea nu se re-deleagă** — [ADR-035](../decisions/035-fara-delegare-tranzitiva.md), `R27`.
> Engagementul leagă o firmă de un tenant, iar predicatul potrivește exact o relație, niciodată un
> lanț. Direcția inversă rămâne permisă și nu e excepție: firma A poate fi clientul firmei B pentru
> propria contabilitate, iar B vede registrele lui A — inclusiv că A facturează clientul X, fiindcă
> factura aceea e documentul lui A. Din registrul lui X nu vede nimic. Cabinetul care vrea să
> subcontracteze cere clientului un al doilea engagement, posibil prin
> [ADR-018](../decisions/018-engagementuri-multiple.md) — nu o cedare de acces. `IZ-68`, `IZ-69`.

**`DN-06` — ÎNCHISĂ prin [ADR-018](../decisions/018-engagementuri-multiple.md):** da, prin opțiunea B de mai jos. Regula de arbitraj este *fără suprapunere* — un `module_key` este revendicat de cel mult un engagement viu per tenant, impus în bază.

Cazul real: o firmă ține contabilitatea, alta ține salarizarea. Documentele nu spun nimic.

- **Opțiunea A — o singură firmă activă per tenant.** Constrângere:
  `UNIQUE (client_tenant_id) WHERE status = 'active'`. Model simplu, dashboard simplu, dar
  refuză un scenariu frecvent în piață și forțează clientul să aleagă.
- **Opțiunea B — mai multe firme, separate prin scope de module.** Constrângerea de unicitate
  rămâne cea de mai sus (per pereche firmă–tenant), iar suprapunerea se controlează prin
  `engagement_module_scope`. Cere o regulă de arbitraj când două engagementuri revendică același
  modul, și complică fiecare test de izolare cu o dimensiune în plus.
- **Opțiunea C — mai multe firme, separate prin companii.** Firma X ține compania 1, firma Y ține
  compania 2. Mai simplu de verificat decât B, dar nu acoperă cazul „aceeași companie, module
  diferite".

Implicația comună: opțiunea aleasă intră direct în politica RLS (secțiunea 2.4) și în suita de
penetrare (secțiunea 8).

#### `engagement_company_scope`

Rândurile există doar când `covers_all_companies = false`.

| Câmp | Tip | Constrângeri |
|---|---|---|
| `id` | uuid | PK |
| `engagement_id` | uuid | NOT NULL, REFERENCES `engagement` |
| `client_tenant_id` | uuid | NOT NULL | Denormalizat pentru RLS; `CHECK` de coerență cu engagementul |
| `company_id` | uuid | NOT NULL, REFERENCES `company` |
| `created_at` | timestamptz | NOT NULL |

`UNIQUE (engagement_id, company_id)`. Index: `(company_id)`.

#### `engagement_module_scope`

| Câmp | Tip | Constrângeri |
|---|---|---|
| `id` | uuid | PK |
| `engagement_id` | uuid | NOT NULL, REFERENCES `engagement` |
| `module_key` | text | NOT NULL |
| `permission_level` | text | NOT NULL, CHECK în `('read','write')` |

`UNIQUE (engagement_id, module_key)`.

**`DN-07` — ÎNCHISĂ prin [ADR-019](../decisions/019-vocabular-scope.md):** opțiunea A de mai jos — numele modulului de business, cu `read`/`write`. Modulele `platform/*` nu primesc chei de scope.

V2 §9.1 descrie scope-ul ca „ce companii, ce module, ce drepturi", fără să enumere niciunul.

- **Opțiunea A — `module_key` = numele modulului din harta §4.1** (`accounting`, `payroll`,
  `sales`, …), cu două niveluri de drept. Direct verificabil, dar granularitate grosieră: „acces la
  `payroll`" înseamnă și vizualizarea salariilor individuale.
- **Opțiunea B — vocabular de permisiuni separat de module** (`payroll.view_salaries`,
  `payroll.run`, `accounting.post`). Granularitate reală, dar cere un catalog de permisiuni
  menținut și verificat, plus decizia din `DN-08` (rolurile).
- **Opțiunea C — scope pe capabilități**, reutilizând cheile din `CapabilityActivation`. Evită un
  al doilea vocabular, dar suprapune două concepte ortogonale (ce a activat tenantul vs. ce poate
  vedea firma).

Consecință: fără acest vocabular, cazul de test „engagement cu scope restrâns" (obligatoriu în
suita 1, T2 din `CLAUDE.md`) nu poate fi scris.

### 1.5 `User`

Identitate **globală**. Un contabil are un singur cont pentru toți clienții. **Nu are `tenant_id`**
— este una dintre excepțiile din secțiunea 5.

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | uuid | PK | |
| `email` | citext | NOT NULL, UNIQUE | Identificatorul de conectare |
| `email_verified_at` | timestamptz | NULL | |
| `full_name` | text | NOT NULL | |
| `password_hash` | text | NULL | `NULL` dacă autentificarea e delegată (SSO, ulterior) |
| `mfa_enabled` | boolean | NOT NULL, DEFAULT false | Vezi `DN-09` |
| `mfa_secret_encrypted` | bytea | NULL | Niciodată în clar, niciodată în loguri |
| `locale` | text | NOT NULL, DEFAULT `'ro'` | Idem `tenant.default_locale` |
| `is_active` | boolean | NOT NULL, DEFAULT true | Dezactivarea taie accesul la **toți** tenanții |
| `last_login_at` | timestamptz | NULL | |
| `created_at`, `updated_at` | timestamptz | NOT NULL | |

Indici: `UNIQUE (email)`; `(is_active)`.

> Consecința identității globale: tabela `user` este vizibilă în afara oricărui context de tenant.
> De aceea **nu conține niciun câmp de business**. Orice atribut specific unei relații
> utilizator–tenant stă pe `membership`, nu aici. Un câmp adăugat greșit pe `user` devine o scurgere
> de informație între tenanți fără să declanșeze nicio politică RLS.

### 1.6 `Membership`

Apartenența unui user la un tenant, cu rol.

| Câmp | Tip | Constrângeri |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id` | uuid | NOT NULL, REFERENCES `tenant` |
| `user_id` | uuid | NOT NULL, REFERENCES `user` |
| `role` | text | NOT NULL — vocabular în `DN-08` |
| `status` | text | NOT NULL, CHECK în `('invited','active','suspended','removed')` |
| `invited_by_user_id` | uuid | NULL, REFERENCES `user` |
| `invited_at` | timestamptz | NOT NULL |
| `accepted_at` | timestamptz | NULL |
| `suspended_at`, `removed_at` | timestamptz | NULL |
| `created_at`, `updated_at` | timestamptz | NOT NULL |

Constrângeri: `UNIQUE (tenant_id, user_id) WHERE status <> 'removed'`;
`CHECK (status <> 'active' OR accepted_at IS NOT NULL)`.

Indici: `(user_id, status)` — folosit de fiecare evaluare de politică RLS, deci obligatoriu;
`(tenant_id, status)`.

### 1.7 `CompanyAccess`

Accesul unui user la o companie, cu rol. Există **și** pentru membrii tenantului, **și** pentru
utilizatorii firmei care acționează prin engagement — coloana `granted_via` le distinge.

| Câmp | Tip | Constrângeri |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id` | uuid | NOT NULL | Denormalizat pentru RLS |
| `company_id` | uuid | NOT NULL, REFERENCES `company` |
| `user_id` | uuid | NOT NULL, REFERENCES `user` |
| `role` | text | NOT NULL — vocabular în `DN-08` |
| `granted_via` | text | NOT NULL, CHECK în `('membership','engagement')` |
| `engagement_id` | uuid | NULL, REFERENCES `engagement` |
| `valid_from` | date | NOT NULL |
| `valid_to` | date | NULL |
| `granted_by_user_id` | uuid | NOT NULL, REFERENCES `user` |
| `revoked_at` | timestamptz | NULL |
| `created_at`, `updated_at` | timestamptz | NOT NULL |

Constrângeri:

- `CHECK ((granted_via = 'engagement') = (engagement_id IS NOT NULL))`
- `UNIQUE (company_id, user_id, granted_via) WHERE revoked_at IS NULL`

Indici: `(user_id, company_id) WHERE revoked_at IS NULL` — evaluat de politica RLS pe fiecare tabelă
company-scoped; `(engagement_id) WHERE revoked_at IS NULL` — folosit la revocare în cascadă.

> **Regula de coerență la revocare:** revocarea unui engagement revocă în aceeași tranzacție toate
> rândurile `CompanyAccess` cu `granted_via='engagement'` care îl referă. Accesul nu poate
> supraviețui relației care l-a produs. Testul care demonstrează asta este obligatoriu (secțiunea 8).

> **`DECIZIE NECESARĂ (OD-54)` — vizibilitatea nominală și blocarea unei persoane.** Clientul
> revocă engagementul integral, dar azi nu poate nici să vadă nominal cine din firmă îi atinge
> datele, nici să blocheze o persoană fără să rupă relația cu firma. Întrebarea deschisă nu este
> dacă se face, ci **unde se impune**: dacă blocarea trăiește doar la provizionare (`CompanyAccess`),
> o reprovizionare ulterioară o învie — vezi §6.2 și `provision_company_access`; dacă intră în
> predicat, apare pe calea fierbinte a fiecărei interogări. Înrudite: `OD-42` (entitatea din spatele
> lui `assignment`), `OD-51` (azi clientul nu poate citi nici măcar numele firmei sale).

### 1.8 `CapabilityActivation`

Activarea unei capabilități este entitate, nu boolean (R25).

| Câmp | Tip | Constrângeri |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id` | uuid | NOT NULL, REFERENCES `tenant` |
| `company_id` | uuid | NULL, REFERENCES `company` | `NULL` = capabilitate la nivel de tenant |
| `capability_key` | text | NOT NULL, CHECK pe vocabularul închis din [ADR-060](../decisions/060-vocabularul-capabilitatilor.md) |
| `effective_from` | date | NOT NULL |
| `effective_to` | date | NULL |
| `initialization_state` | text | NOT NULL, CHECK în `('not_required','required','in_progress','complete')` |
| `initialization_ref` | text | NULL | Trimitere la procesul de inițializare (import de solduri, cumulative payroll) |
| `activated_by_user_id` | uuid | NOT NULL, REFERENCES `user` |
| `activated_at` | timestamptz | NOT NULL |
| `source` | text | NOT NULL, CHECK în `('plan','manual','migration')` |
| `created_at`, `updated_at` | timestamptz | NOT NULL |

Constrângeri:

- neîntrepătrundere pe aceeași capabilitate și același scope:
  `EXCLUDE USING gist (company_id WITH =, capability_key WITH =, daterange(effective_from, effective_to) WITH &&)`
  (pentru rândurile cu `company_id IS NULL`, exclusion pe `tenant_id` în loc de `company_id`)
- `effective_from` trebuie să coincidă cu începutul unei perioade contabile. Perioadele apar în F1,
  deci în F0 constrângerea se implementează în serviciu, cu un test care o acoperă, și se mută în
  bază la F1.5.

**Ce nu este acest tabel.** Nu este planul comercial. Capability set și plan sunt axe ortogonale
(secțiunea 10). Un client al unei firme poate avea nevoie de Inventory fără să corespundă vreunui
tier din grila directă.

**Regula care nu se încalcă:** capabilitățile de conformitate (TVA, e-Factura, raportare SNC,
payroll în măsura obligațiilor declarative) **nu apar niciodată** ca rânduri dezactivabile aici.
Ele nu sunt opționale pentru niciun tenant și nu sunt niciodată paywall (R24). Dacă o capabilitate
de conformitate ajunge în acest tabel cu `effective_to` setat, este defect critic.

---

## 2. Politicile RLS

### 2.1 Două bariere independente

Aplicația nu filtrează pe tenant (C3). Baza de date o face. Motivul nu este eleganța: un manager
care filtrează maschează absența contextului, iar bug-ul se descoperă când cineva scrie o
interogare care ocolește managerul.

Barierele:

1. **Stratul de aplicație** garantează că fiecare request și fiecare task rulează într-o tranzacție
   cu context setat (secțiunea 3). Dacă nu poate, refuză cererea.
2. **RLS** garantează că, dacă bariera 1 eșuează, interogarea nu returnează nimic.

Niciuna nu o înlocuiește pe cealaltă. Suita 1 testează bariera 2 prin ocolirea barierei 1.

### 2.2 Roluri de bază de date

**Trei roluri, nu două** — [ADR-003](../decisions/003-rls-tenancy-tables.md). *Plus un al patrulea,
în afara runtime-ului, de la [ADR-049](../decisions/049-rolul-de-date-de-referinta.md):
`evidenta_refdata` — `LOGIN`, `NOINHERIT`, fără `BYPASSRLS`, nu deține nimic, fără privilegii
implicite; primește `SELECT, INSERT, UPDATE` și o politică `FOR ALL` doar pe tabelele globale de
referință declarate cu `writer_role` în `infra/rls/exceptions.toml`. `infra/bootstrap/0004_refdata_role.sql`.*

```sql
-- rol de migrare: deține obiectele. Nu se folosește la runtime.
CREATE ROLE evidenta_owner NOINHERIT LOGIN;

-- rol de aplicație: fără BYPASSRLS, fără ownership, fără CREATE pe schema publică.
CREATE ROLE evidenta_app NOINHERIT LOGIN;

-- rol de rezolvare: deține schema `rls` și predicatele din ea (2.4). Nimic altceva.
CREATE ROLE evidenta_rls NOINHERIT NOLOGIN BYPASSRLS;

-- owner-ul face SET ROLE ca să creeze funcțiile în schema `rls`, pe care nu o deține.
-- Atributul BYPASSRLS nu se moștenește prin apartenență, ci doar prin SET ROLE.
GRANT evidenta_rls TO evidenta_owner;

GRANT USAGE ON SCHEMA public, app TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO evidenta_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evidenta_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO evidenta_app;
```

**Două scheme.** `app` — funcțiile de context, deținute de `evidenta_owner`, citesc doar GUC-uri.
`rls` — predicatele de acces, deținute de `evidenta_rls`, citesc tabele ocolind politicile.
Separarea face ca „ce rulează privilegiat" să fie o proprietate a schemei, nu o notă de subsol.

**De ce al treilea rol.** Tutorialele de `SECURITY DEFINER` presupun că proprietarul tabelei
ocolește RLS. Cu `FORCE ROW LEVEL SECURITY` — obligatoriu la noi — nu îl mai ocolește. O funcție
deținută de `evidenta_owner` ar fi deci supusă acelorași politici pe care încearcă să le rezolve, iar
recursiunea revine pe ușa din dos. `BYPASSRLS` este singurul atribut care o rupe, și trăiește pe un
rol care nu se poate autentifica și nu deține nicio tabelă.

Reguli care fac diferența între RLS efectiv și RLS decorativ:

- `evidenta_app` **nu** are `BYPASSRLS`, **nu** este superuser și **nu** este membru al lui
  `evidenta_rls`. Primește doar `EXECUTE` pe predicate.
- Fiecare tabelă business primește `ENABLE` **și** `FORCE ROW LEVEL SECURITY`. Fără `FORCE`,
  owner-ul ocolește politicile, iar orice job rulat cu rolul de migrare vede tot.
- Migrațiile rulează sub `evidenta_owner`; aplicația și testele rulează sub `evidenta_app` (T1).
- Revocarea `UPDATE` și `DELETE` pentru `evidenta_app` pe tabelele ledgerului postat este a doua
  linie de apărare pentru R10 — se stabilește la F1, nu aici, dar granturile implicite de mai sus
  trebuie ajustate atunci, nu uitate.

### 2.3 Funcțiile de context — comportament fail-closed

```sql
CREATE SCHEMA app;

CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid
LANGUAGE plpgsql STABLE AS $fn$
DECLARE v text := current_setting('app.tenant_id', true);
BEGIN
    IF v IS NULL OR v = '' THEN
        RAISE EXCEPTION 'evidenta: missing tenant context'
            USING ERRCODE = '42501';   -- insufficient_privilege
    END IF;
    RETURN v::uuid;
END $fn$;

CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE plpgsql STABLE AS $fn$
DECLARE v text := current_setting('app.user_id', true);
BEGIN
    IF v IS NULL OR v = '' THEN
        RAISE EXCEPTION 'evidenta: missing user context'
            USING ERRCODE = '42501';
    END IF;
    RETURN v::uuid;
END $fn$;

-- Poate lipsi legitim: un membru al tenantului nu acționează prin firmă.
CREATE OR REPLACE FUNCTION app.current_actor_firm_id() RETURNS uuid
LANGUAGE sql STABLE AS $fn$
    SELECT NULLIF(current_setting('app.actor_firm_id', true), '')::uuid;
$fn$;
```

**Refuz, nu tăcere.** Contextul absent produce **eroare**, nu zero rânduri. Ambele satisfac
formularea din invariantul 3, dar eroarea este de preferat: o interogare care returnează zero
rânduri arată ca un rezultat legitim și trece prin teste, în timp ce o excepție se vede imediat.

Excepția: rutele privilegiate (secțiunea 6) rulează cu un rol și un mecanism distincte, nu prin
absența contextului.

### 2.4 Predicatele de acces

Sunt inima politicii. Ambele căi de acces din V2 §4.2 — membru al tenantului, sau engagement activ
al firmei — sunt aici.

```sql
CREATE OR REPLACE FUNCTION rls.has_tenant_access(p_tenant_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS $fn$
    SELECT
    -- calea 1: membru activ al tenantului
    EXISTS (
        SELECT 1 FROM membership m
        WHERE m.tenant_id = p_tenant_id
          AND m.user_id   = app.current_user_id()
          AND m.status    = 'active'
    )
    OR
    -- calea 2: engagement activ al firmei în numele căreia acționează utilizatorul
    EXISTS (
        SELECT 1
        FROM engagement e
        JOIN firm f       ON f.id = e.firm_id
        JOIN membership fm ON fm.tenant_id = f.tenant_id
                          AND fm.user_id  = app.current_user_id()
                          AND fm.status   = 'active'
        WHERE e.client_tenant_id = p_tenant_id
          AND e.firm_id          = app.current_actor_firm_id()
          AND e.status           = 'active'
          AND e.valid_from      <= current_date
          AND (e.valid_to IS NULL OR e.valid_to >= current_date)
    );
$fn$;
```

Trei lucruri de reținut, fiecare fiind o cale prin care implementarea poate eșua silențios:

1. **`SECURITY DEFINER`, deținut de `evidenta_rls`.** `membership` și `engagement` au ele însele
   politici RLS. Fără ocolirea lor, evaluarea unei politici ar declanșa evaluarea altei politici pe
   tabelele consultate, iar PostgreSQL ridică `infinite recursion detected in policy for relation`
   — nu încetinește, eșuează. Funcția aparține rolului cu `BYPASSRLS` (2.2), **nu** lui
   `evidenta_owner`, care sub `FORCE ROW LEVEL SECURITY` nu ocolește nimic. `search_path` fixat în
   definiție, altfel funcția devine vector de escaladare de privilegii.
2. **Apartenența la firmă se verifică, nu se presupune.** Nu e suficient ca `app.actor_firm_id` să
   fie setat: utilizatorul trebuie să fie membru activ al tenantului firmei. Altfel oricine poate
   pretinde că acționează pentru orice firmă doar setând o variabilă de sesiune.
3. **Valabilitatea se evaluează la `current_date`.** Un engagement expirat nu mai dă acces fără să
   fie nevoie de un job care să-i schimbe starea. Starea `expired` (secțiunea 4) există pentru
   raportare și pentru interfață, nu ca mecanism de securitate.

```sql
CREATE OR REPLACE FUNCTION rls.has_company_access(p_company_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS $fn$
    SELECT EXISTS (
        SELECT 1 FROM company_access ca
        WHERE ca.company_id = p_company_id
          AND ca.user_id    = app.current_user_id()
          AND ca.revoked_at IS NULL
          AND ca.valid_from <= current_date
          AND (ca.valid_to IS NULL OR ca.valid_to >= current_date)
    );
$fn$;
```

### 2.5 Politica pentru tabelele tenant-scoped

Șablonul se aplică identic fiecărei tabele de nivel tenant (secțiunea 5).

```sql
ALTER TABLE partner ENABLE ROW LEVEL SECURITY;
ALTER TABLE partner FORCE  ROW LEVEL SECURITY;

CREATE POLICY partner_tenant_access ON partner
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));
```

`WITH CHECK` nu este opțional: fără el, un `INSERT` sau un `UPDATE` poate scrie un rând cu
`tenant_id` străin, care devine invizibil imediat după commit — cea mai neplăcută formă de coruperi
de date, pentru că nu produce nicio eroare.

### 2.6 Politica pentru tabelele company-scoped

Contabilitatea este obligatoriu company-scoped, fără excepții (V2 §4.3).

```sql
ALTER TABLE journal_entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entry FORCE  ROW LEVEL SECURITY;

CREATE POLICY journal_entry_access ON journal_entry
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id));
```

**`DN-11` — DECIS.** Vezi [ADR-004](../decisions/004-company-context.md).

`app.tenant_id` rămâne obligatoriu și fail-closed. `app.company_id` este **opțional** și, când e
setat, îngustează suplimentar. Izolarea între companiile aceluiași tenant rămâne în bază, exprimată
prin `has_company_access()`, nu prin variabila de sesiune. Șablonul complet devine:

```sql
USING (
    tenant_id = app.current_tenant_id()
    AND rls.has_tenant_access(tenant_id)
    AND rls.has_company_access(company_id)
    AND (app.current_company_id() IS NULL OR company_id = app.current_company_id())
)
```

`app.current_company_id()` returnează `NULL` când GUC-ul lipsește — spre deosebire de
`current_tenant_id()`, care ridică excepție. Diferența este intenționată.

**`app.company_id` nu este mecanism de securitate**, ci de scoping pentru contextul de interfață.
Codul care uită să îl seteze lărgește rezultatul la companiile la care utilizatorul are oricum
drept: bug de corectitudine, nu scurgere de date. Motivul alegerii: contabilul care ține toate cele
trei companii ale unui holding, consolidarea și dashboard-ul au nevoie legitimă de interogări peste
companii ale aceluiași tenant, iar dacă `company_id` ar fi obligatoriu fiecare astfel de caz ar
deveni cale privilegiată — iar lista aceea trebuie să rămână scurtă ca să însemne ceva.

### 2.7 Politica pentru tabelele care definesc tenancy-ul

**`DN-12` — DECIS.** Vezi [ADR-003](../decisions/003-rls-tenancy-tables.md).

Problema: `rls.has_tenant_access()` citește `membership` și `engagement`. Dacă acele tabele au
politici care apelează predicatul, evaluarea recursează și PostgreSQL ridică eroare. Dacă nu au
politici deloc, gardianul de model le raportează — corect, pentru că un utilizator ar putea citi
apartenențele altor tenanți.

Soluția: predicatele rup recursiunea rulând sub `evidenta_rls` (2.2), iar tabelele de tenancy
primesc politici **simple, neîncrucișate**.

| Tabelă | Politică |
|---|---|
| `user` | `id = app.current_user_id()` |
| `membership` | `user_id = app.current_user_id()` |
| `company_access` | `user_id = app.current_user_id()` |
| `engagement` | `rls.can_see_engagement(client_tenant_id, firm_id)` — vizibil ambelor părți |
| `tenant` | `rls.has_tenant_access(id)` |
| `firm` | membru al tenantului firmei, sau tenant cu engagement viu asupra firmei |

Apelul predicatului din ultimele două nu recursează, pentru că predicatul rulează cu `BYPASSRLS`.

**Consecință acceptată:** un membru **nu** vede ceilalți membri ai tenantului său prin ORM.
Ecranul „echipa mea" are nevoie de un serviciu dedicat, nu de un queryset. Forma acelui serviciu
este `OD-37`, deschisă.

`engagement_company_scope` și `engagement_module_scope` **nu** mai sunt excepții: poartă
`client_tenant_id` și folosesc șablonul obișnuit. Firma le vede pe calea 2 a predicatului.

### 2.7.1 Ce nu apără RLS — model de amenințare

Se confundă des, așa că se scrie explicit:

**RLS te apără de un filtru uitat în cod. Nu te apără de un server de aplicație compromis.** Acela
poate seta orice GUC — deci poate revendica orice `app.tenant_id` și orice `app.user_id`, iar
politicile îl vor servi cu conștiinciozitate.

Sunt două amenințări diferite:

| Amenințare | Acoperită de | Mecanism |
|---|---|---|
| Filtru uitat, queryset scris greșit, raport care ignoră contextul | **da**, aici | RLS + suita 1 + suita 2 |
| Server de aplicație compromis, secrete scurse, dependență otrăvită | **nu** | securizarea serverului, a secretelor, a lanțului de livrare |

Confuzia dintre ele produce fie fals confort („avem RLS, suntem în siguranță"), fie efort irosit în
a întări RLS împotriva a ceva ce nu poate opri.

### 2.8 Costul de execuție al politicilor

`has_tenant_access` și `has_company_access` sunt `STABLE`, dar PostgreSQL nu memoizează funcțiile
`STABLE` între rânduri. Pe o interogare care returnează 50.000 de linii de jurnal, predicatul se
poate evalua de 50.000 de ori.

Măsuri, în ordinea preferinței:

1. **Indicii care fac predicatul ieftin:** `membership (user_id, status)`,
   `company_access (user_id, company_id) WHERE revoked_at IS NULL`,
   `engagement (firm_id, client_tenant_id, status)`. Fără aceștia, fiecare evaluare este un seq scan.
2. **Cache în tranzacție.** La stabilirea contextului (secțiunea 3), aplicația calculează o dată
   drepturile efective și le pune într-o variabilă de sesiune; predicatul o citește și consultă
   tabelele doar dacă lipsește. Câștigul e mare, dar mută o parte din decizie în aplicație — se
   documentează ca ADR dacă se adoptă, pentru că slăbește bariera 2.
3. **Măsurare obligatorie înainte de F1.** Ținta de performanță pentru balanța pe 5 ani
   (OD-29) se măsoară **cu politicile active**. Un benchmark rulat ca owner nu spune nimic despre
   producție.

### 2.9 Ce sparge izolarea silențios

Enumerate pentru că fiecare a fost cauza unei scurgeri într-un sistem real:

- **`SET` în loc de `SET LOCAL`.** Valoarea supraviețuiește tranzacției și, cu pooling, ajunge la
  cererea altui tenant. `SET LOCAL` este singura formă permisă.
- **Cerere în afara unei tranzacții.** `SET LOCAL` nu are efect; funcțiile de context ridică
  excepție — de aceea ridică, în loc să returneze `NULL`.
- **pgbouncer în transaction pooling** fără ca tot requestul să fie într-o tranzacție. Sparge
  izolarea fără niciun semn. Cerința „tot requestul într-o tranzacție" (R3) există exact pentru asta,
  și trebuie testată *înainte* de a introduce pooling, nu după.
- **Conexiune deschisă cu rolul de migrare** de către un job, un shell de management sau un script
  de import. `FORCE ROW LEVEL SECURITY` nu ajută: owner-ul cu `FORCE` respectă politicile, dar
  rolul de migrare are și `BYPASSRLS` dacă cineva i l-a acordat „temporar".
- **Teste rulate ca superuser.** Trec întotdeauna. T1 le interzice.
- **Tabelă nouă fără politică.** Prinsă de suita 2, dar numai dacă suita rulează. De aceea intră în
  CI de la primul commit (F0.2), înaintea primului model.

---

## 3. Contextul de sesiune

### 3.1 Variabilele

| Variabilă | Tip | Obligatorie | Cine o setează | Sursă |
|---|---|---|---|---|
| `app.tenant_id` | uuid | da | middleware / decorator Celery | subdomeniul cererii, sau argumentul task-ului |
| `app.user_id` | uuid | da | middleware / decorator Celery | sesiunea autentificată, sau utilizatorul de sistem al task-ului |
| `app.actor_firm_id` | uuid | nu | middleware / decorator Celery | firma selectată de utilizator, validată contra apartenenței |
| `app.company_id` | uuid | **nu** — îngustare opțională (ADR-004) | middleware / decorator Celery | compania selectată în interfață, sau argumentul task-ului |
| `app.request_id` | text | da | middleware | corelatorul folosit de audit (secțiunea 9.3) |

Toate se setează cu `SET LOCAL`, în interiorul tranzacției, **înainte de orice interogare**.

### 3.2 În request

```
1. Rezolvă subdomeniul → tenant. Subdomeniu inexistent sau tenant nu e 'active' → 404, fără a
   dezvălui dacă tenantul există.
2. Autentifică utilizatorul. Neautentificat → 401, fără atingerea bazei de date de business.
3. Deschide tranzacția.
4. SET LOCAL app.tenant_id, app.user_id, app.request_id și, dacă utilizatorul acționează pentru o
   firmă, app.actor_firm_id — după ce apartenența la firmă a fost validată.
5. Execută viziunea.
6. Commit sau rollback. Contextul dispare odată cu tranzacția.
```

`ATOMIC_REQUESTS` acoperă pasul 3 pentru viziunile normale. Nu acoperă: middleware care
interoghează înainte de tranzacție, streaming responses care produc rânduri după commit, comenzi de
management, shell-ul Django. Fiecare dintre acestea are nevoie de context explicit sau de refuz
explicit.

**Interdicție:** contextul nu vine niciodată din payload, din query string sau dintr-un header pe
care clientul îl controlează (C8). Un `tenant_id` primit de la client este ignorat; dacă diferă de
cel din subdomeniu, cererea se respinge și se auditează.

### 3.3 În task-uri Celery

Fiecare task primește `tenant_id` explicit ca argument (R6). Un task care îl deduce din starea
globală, dintr-un obiect încărcat anterior sau din ultimul context al workerului este defect critic.

```
@tenant_task
def rebuild_vat_register(tenant_id, company_id, period, ...):
    ...
```

Decoratorul, cu comportament obligatoriu:

1. Refuză la pornire dacă `tenant_id` lipsește din argumente — **eroare, nu valoare implicită**.
2. Deschide tranzacția și setează contextul, inclusiv un `user_id` de sistem trasabil (nu `NULL`,
   nu utilizatorul care a declanșat lanțul cu trei task-uri în urmă, dacă acesta nu mai e relevant).
3. Setează `app.request_id` la identificatorul task-ului, ca efectele să fie enumerabile (9.3).
4. Curăță contextul la ieșire, inclusiv pe calea de eroare și de retry.

Se aplică la: e-Factura, curs BNM, payroll, amortizare, rapoarte, import, migrare 1C — adică la
fiecare task cu efect asupra datelor unui tenant.

Cazul „task fără context" este test obligatoriu în suita 1 (T2): trebuie să **eșueze**, nu să
returneze date.

### 3.4 Utilizatorul de sistem

Task-urile periodice și rutele privilegiate nu au utilizator uman. Au nevoie totuși de `app.user_id`
pentru audit. Se rezervă un `user` cu `is_active = false` și email nefolosibil, per tip de proces
(`system:billing`, `system:bnm`, `system:efactura`), astfel încât auditul să distingă sursa.

Un utilizator de sistem **nu** are `membership`. Prin urmare nu trece de `has_tenant_access` și nu
poate citi date de business pe calea normală — ceea ce este corect: procesele care au nevoie de așa
ceva trec prin căile privilegiate din secțiunea 6, unde sunt enumerate și auditate.

---

## 4. Ciclul de viață al Engagement-ului

### 4.1 Stările

```
                  ┌──────────┐
   invitație ────►│ invited  │
                  └────┬─────┘
                       │ acceptare
                       ▼
                  ┌──────────┐  suspendare   ┌───────────┐
                  │  active  │◄─────────────►│ suspended │
                  └────┬─────┘   reluare     └─────┬─────┘
                       │                            │
        revocare       │        valid_to trecut     │ revocare
                       ▼                            ▼
                  ┌──────────┐              ┌─────────────┐
                  │ revoked  │              │   expired   │
                  └──────────┘              └─────────────┘
                       ▲
                       │ transfer către altă firmă
                  ┌────┴───────┐
                  │transferred │
                  └────────────┘
```

### 4.2 Matricea tranzițiilor

| Din | În | Cine poate declanșa | Efect asupra accesului |
|---|---|---|---|
| — | `invited` | firma (către tenant) sau tenantul (către firmă) | niciun acces |
| `invited` | `active` | partea care **nu** a inițiat, cu drept de administrare | acces conform scope-ului, de la `valid_from` |
| — | `active` | firma, pe **mandat declarat**, la crearea tenantului — `acceptance_basis = 'declared_mandate'` ([ADR-081](../decisions/081-revendicarea-optionala.md) §3.3) | acces conform scope-ului; identic cu cel acceptat de client, iar predicatul nu se atinge |
| `invited` | `revoked` | oricare parte | niciun acces; invitația expiră și de la sine — vezi `DN-13` |
| `active` | `suspended` | tenantul, firma, sau administrarea platformei | acces tăiat instantaneu, relația se păstrează |
| `suspended` | `active` | aceeași parte care a suspendat, sau tenantul | acces restabilit, fără reacceptare |
| `active` / `suspended` | `revoked` | **tenantul, oricând și fără motivare** (INV-7); firma, cu preaviz — vezi `DN-14` | acces tăiat instantaneu și irevocabil |
| `active` | `expired` | automat, când `valid_to < current_date` | accesul încetează prin predicat, nu prin job |
| `active` | `transferred` | tenantul, prin acceptarea unei invitații de la altă firmă | vezi 4.5 |

Tranzițiile care nu apar în tabel sunt interzise și se refuză în serviciu, cu cod de eroare stabil
(C10). `revoked`, `expired` și `transferred` sunt stări terminale: nu se iese din ele. Reluarea
relației se face printr-un engagement **nou**, ca istoricul să rămână lizibil.

### 4.3 Revocarea

Revocarea taie accesul instantaneu, dar nu șterge urma.

În aceeași tranzacție:

1. `engagement.status = 'revoked'`, `revoked_at`, `revoked_by_user_id`, `revocation_reason`.
2. Toate rândurile `company_access` cu `granted_via = 'engagement'` și `engagement_id` egal primesc
   `revoked_at`.
3. Se emite un eveniment de audit per rând afectat, cu `request_id` comun, ca revocarea să fie
   enumerabilă ca un tot (9.3).
4. Sesiunile active ale utilizatorilor firmei pentru acest tenant se invalidează. Fără acest pas,
   accesul persistă până la expirarea sesiunii, iar predicatul RLS nu ajută: el se reevaluează la
   fiecare interogare, deci **tot** taie accesul — dar interfața rămâne deschisă și produce erori în
   loc de un mesaj util.

Ce **nu** se întâmplă la revocare:

- nu se șterge niciun document, nicio înregistrare contabilă, niciun atașament creat de firmă;
  datele aparțin tenantului (INV-7)
- nu se anonimizează autorii; `created_by` rămâne utilizatorul firmei, pentru că altfel lanțul de
  trasabilitate (INV-9) se rupe
- nu se retrag drepturile deja exercitate; corecția unei postări greșite se face prin storno, nu
  prin ștergere

**Documentele în lucru.** Un document `Draft` creat de firmă rămâne al tenantului, editabil de
membrii lui. Un document `Confirmed` sau `Posted` este intangibil oricum.

### 4.4 Expirarea

Un engagement cu `valid_to < current_date` nu mai dă acces, indiferent de `status`, pentru că
predicatul verifică datele (2.4). Un job periodic mută `status` în `expired` pentru claritatea
interfeței și a rapoartelor — dar **securitatea nu depinde de rularea lui**. Această separare este
deliberată: un job care nu rulează nu trebuie să lase acces deschis.

Testul corespunzător din suita 1 verifică exact asta: engagement cu `valid_to` în trecut și `status`
încă `active` → zero acces.

### 4.5 Transferul către altă firmă

„Transferul nu mută date — schimbă doar relația" (V2 §9.1).

```
1. Firma nouă trimite invitație către tenant (engagement nou, status 'invited').
2. Tenantul acceptă.
3. În aceeași tranzacție:
   - engagementul nou trece în 'active', cu valid_from = data transferului
   - engagementul vechi trece în 'transferred', cu transferred_to_engagement_id setat
   - accesele vechi se revocă la fel ca la 4.3
4. Istoricul rămâne: cine a avut acces, când, ce a făcut.
```

Nu există transfer „direct" între firme fără acceptarea tenantului. Firma care pleacă nu poate
transmite accesul mai departe — ar contrazice INV-7.

**`DECIZIE NECESARĂ (DN-15)` — suprapunerea la transfer.**
Firma nouă are nevoie de acces înainte de a se încheia perioada firmei vechi (predare, verificare,
închiderea lunii). Opțiuni: (A) fără suprapunere — tăiere netă la o dată, cu risc operațional real;
(B) suprapunere limitată, cu ambele engagementuri active o perioadă definită, ceea ce contrazice
opțiunea A din `DN-06` dacă aceasta se alege; (C) firma veche păstrează acces **numai citire** pe
durata suprapunerii, ceea ce cere ca `permission_level` să poată fi degradat la nivel de engagement,
nu doar de modul.

### 4.6 Închiderea firmei

Când `firm.status` devine `closed`, toate engagementele ei active trec în `suspended`, nu în
`revoked`. Motivul: clientul trebuie să poată alege singur ce face — să transfere, sau să continue
pe cont propriu. Datele nu se ating; ele nu au fost niciodată ale firmei.

Notificarea tenanților afectați este obligatorie, nu opțională.

### 4.7 Ce se păstrează permanent

Pentru fiecare engagement, indiferent de starea finală: părțile, intervalul, scope-ul la fiecare
modificare, cine a invitat, cine a acceptat, cine a suspendat sau revocat și de ce, plus lanțul
complet al acțiunilor efectuate de utilizatorii firmei asupra datelor tenantului (audit, secțiunea
9.3).

Această păstrare nu este o funcție de audit generic. Este ce face posibil răspunsul la întrebarea
„cine a modificat această înregistrare în martie 2027", după ce firma respectivă nu mai există.

---

## 5. Nivelurile tabelelor

Trei niveluri. Nivelul determină politica RLS și indicii.

| Nivel | Ce conține | Coloană de context | Politică |
|---|---|---|---|
| **Global** | date comune tuturor tenanților, fără proprietar | niciuna | citire pentru toți; scriere doar prin căi privilegiate (6) |
| **Tenant** | date ale clientului, partajabile între companiile lui | `tenant_id` | șablonul 2.5 |
| **Companie** | date cu ledger propriu | `tenant_id` + `company_id` | șablonul 2.6 |

### 5.1 Nivel global

| Tabelă | De ce e globală |
|---|---|
| `user` | identitate globală: un contabil are un cont pentru toți clienții (ÎNC-2) |
| `counterparty_registry` | registru public după IDNO, alimentat din surse publice |
| parametri fiscali (`fiscal_parameter`, `fiscal_parameter_source`) | aceeași lege pentru toți; versionate după dată efectivă |
| registrul de logică fiscală (`fiscal_logic_version`) | idem |
| curs BNM (`exchange_rate`) | idem |
| template plan de conturi SNC (`coa_template`, `coa_template_account`) | template legislativ, instanțiat per companie |
| tabele de sistem Django (`django_migrations`, `django_content_type`, …) | infrastructură |
| `feature_flag`, `release_ring` | tehnice, nu conțin date de tenant |

### 5.2 Nivel tenant

`membership`, `partner`, `tenant_setting`, `api_key`, `billing_account`, `subscription`,
`capability_activation` (când `company_id IS NULL`), `notification`, `attachment_metadata`
(vezi `DN-16`).

### 5.3 Nivel companie

Tot ce ține de contabilitate, fără excepții: `journal_entry`, `journal_line`, `accounting_event`,
`period`, plan de conturi instanțiat, TVA, bancă, casă, stocuri, payroll, active,
`company_partner`, `company_access`, `document`, `numbering_series`,
`capability_activation` (când `company_id IS NOT NULL`).

### 5.4 Lista limitativă a excepțiilor

**Lista trăiește într-un singur loc: [`infra/rls/exceptions.toml`](../../infra/rls/exceptions.toml).**
Gardianul de model o citește de acolo. Această specificație **nu** o reproduce — duplicarea în trei
documente este exact greșeala pe care fișierul o corectează (`00-inventory.md`, X-6).

Ce trebuie știut fără a deschide fișierul:

- Lista este **normativă**. O tabelă fără `tenant_id` care nu apare în ea face suita 2 să eșueze,
  iar remediul este decizia, nu adăugarea tabelei în listă de către cel care a scris-o.
- Fișierul declară **două lucruri distincte**: excepția de la R1 (tabela nu are coloană de context)
  și forma politicii, când diferă de șablon. O tabelă poate fi în a doua categorie fără să fie în
  prima — `membership` are `tenant_id`, dar politica ei este `self_row`.
- Gardianul **nu sare** peste tabelele listate. Verifică forma declarată. O tabelă cu politică lipsă
  eșuează chiar dacă e listată.
- Modificarea fișierului este ADR.

### 5.5 Ce nu este excepție, deși pare

- **Read models** au `tenant_id` **și** `firm_id`. Nu sunt excepție; au o politică proprie (7.3).
- **Tabelele append-only** (`audit_events`, `document_events`, arhivele) au `tenant_id` ca oricare
  alta. Volumul nu scutește de izolare.
- **Datele de configurare ale platformei** care conțin referințe la tenanți (ex. atribuirea unui
  release ring către un tenant) sunt tenant-scoped, nu globale. `release_ring` este catalogul;
  atribuirea este `tenant_release_ring`, cu `tenant_id`.

---

## 6. Căile privilegiate cross-tenant

Enumerare **limitativă**. Ce nu e aici, nu există. Adăugarea unei intrări este ADR, nu o linie de
cod.

### 6.1 Mecanism

Nu prin absența contextului — aceea produce eroare (2.3). Prin funcții `SECURITY DEFINER` deținute
de `evidenta_owner`, expuse rolului de aplicație una câte una, fiecare cu:

- un scop îngust: o singură operațiune, nu „citește orice"
- semnătură care nu acceptă SQL sau nume de tabele ca parametri
- înregistrare obligatorie în `privileged_access_log` (mai jos), în aceeași tranzacție
- un test care demonstrează că funcția nu poate fi folosită pentru altceva

Alternativa — un al treilea rol de bază de date cu `BYPASSRLS`, folosit de procese dedicate — este
acceptabilă dacă procesele respective rulează izolat (worker separat, coadă separată). Ce nu este
acceptabil: același proces care servește cereri de utilizator să poată comuta la un rol privilegiat.

**`DECIZIE NECESARĂ (DN-17)` — care dintre cele două mecanisme.** Funcțiile sunt mai granulare și
auditabile per apel; rolul separat e mai simplu, dar mută granița de securitate la nivel de proces,
iar o greșeală de configurare dă acces la tot.

### 6.2 Lista

| # | Cale | Ce face | De ce nu poate fi tenant-scoped | Audit |
|---|---|---|---|---|
| **P-1** | Facturarea abonamentelor | Citește consumul și starea abonamentelor tuturor tenanților; emite facturi | Procesul e al platformei, nu al unui tenant | rând per tenant atins |
| **P-2** | Polling SFS | Interoghează statusuri e-Factura pentru toți tenanții cu documente în așteptare | Coada e globală; SFS nu cunoaște tenanții | rând per tenant atins |
| **P-3** | Curs BNM | Scrie în tabela globală de cursuri | Scriere globală, citire liberă | rând per rulare |
| **P-4** | Aplicarea regulilor fiscale noi | Inserează parametri fiscali și versiuni de logică | Scriere globală | rând per rulare, cu trimitere la actul normativ |
| **P-5** | Alimentarea registrului de contrapărți | Actualizează `counterparty_registry` din surse publice | Scriere globală | rând per rulare |
| **P-6** | Construirea read models | Citește date operaționale ale mai multor tenanți pentru a produce agregate | Prin definiție cross-tenant (7) | rând per rulare, cu tenanții atinși |
| **P-7** | Suportul platformei | Acces temporar la datele unui tenant pentru diagnostic | Necesar operațional | vezi `DN-18` |
| **P-8** | Offboarding și export | Produce exportul complet al unui tenant, inclusiv date pe care niciun rol de utilizator nu le citește într-o singură interogare | Operațiune de platformă | rând per export, cu cine l-a cerut |
| **P-9** | Provizionarea unui tenant sau a unei companii | Creează rândul rădăcină și acordă accesul creatorului, în aceeași tranzacție | Crearea precede contextul: `tenant` e rădăcina contextului, iar politica pe `company` cere `has_company_access(id)` și în `WITH CHECK` — o companie nu poate avea acces la ea însăși înainte să existe | rând per creare, cu creatorul și subdomeniul sau IDNO-ul |
| **P-10** | Încărcarea planului de conturi | Scrie o versiune publicată a planului general de conturi (`coa_template`, `coa_template_account`) și actul ei | Scriere globală; act **contabil**, nu parametru fiscal, deci nu e `P-4` (`OD-56`) | rând per rulare, cu versiunea și numărul de conturi scrise |
| **P-11** | Revendicarea unui tenant | Acordă un `membership` de administrare celui care dovedește că reprezintă IDNO-ul tenantului, și scrie `claimed_at` | Revendicarea precede orice apartenență: cine revendică nu e încă membru al nimic | rând per revendicare, cu `justification` și referința probei |
| **P-12** | Administrarea angajaților platformei | Acordă și retrage roluri în `platform_staff`, din consolă, de către un `admin` ([ADR-092](../decisions/092-consola-citeste-metadate-si-administreaza-personalul.md)) | Tabela e globală și nu a nimănui; scriitorul ei e `evidenta_refdata`, iar apelantul e angajat al platformei, pe o gazdă fără tenant | rând per operațiune, cu cine a acordat sau retras, cui, ce rol |

*`P-3`, `P-4`, `P-5` și `P-10` rulează sub rolul `evidenta_refdata` (§2.2), prin
`platform.audit.services.privileged.privileged_run`, care scrie rândul din §6.3 în aceeași
tranzacție — [ADR-049](../decisions/049-rolul-de-date-de-referinta.md). `P-9` rămâne funcție
`SECURITY DEFINER`, fiindcă e apelată dintr-o cerere de utilizator; `DN-17` se închide astfel
parțial, pe criteriul „cine apelează".*

*Consola platformei ([ADR-076](../decisions/076-planul-de-control-al-platformei.md)) apelează `P-4`
dintr-o cerere HTTP pe gazda `admin.`, tot sub `evidenta_refdata` și tot prin `privileged_run`, cu
apelantul verificat în `platform_staff` (rol `operator`) și ștampilat ca `actor_user_id`.
[ADR-091](../decisions/091-consola-scrie-referinta-din-procesul-web.md) precizează criteriul „cine
apelează": `P-9` rămâne `SECURITY DEFINER` fiindcă apelantul e un utilizator al unui tenant; consola
apelează ca angajat al platformei, pe o gazdă fără tenant, asupra unor tabele care nu sunt ale
nimănui — două categorii de apelant, nu două transporturi. Propoziția din §6.1 despre procesul care
servește cereri rămâne neadevărată la nivel de proces, cum era și înainte (`DATABASES["refdata"]` e
declarat necondiționat), și se revine la ea când producția dă serverului web și workerului
credențiale diferite (ADR-091 §6).*

**`DN-18` — DECISĂ 2026-08-31, varianta (B)**, prin
[ADR-077](../decisions/077-grantul-de-suport.md). `P-7` nu e o ocolire, e un **grant**: cererea trece
prin calea privilegiată (angajat cu rol `support` în `platform_staff`,
[ADR-076](../decisions/076-planul-de-control-al-platformei.md)), **aprobarea trece prin politica
obișnuită a tenantului** — un membru cu `tenant.approve_support_access` — iar accesul trăiește ca o
ramură mărginită în predicat, stinsă de `expires_at > now()` fără să ruleze niciun job. Grantul e
**doar-citire**: nu există grant de scriere, fiindcă un autor din afara relației, în ledger, rupe
`INV-9`. `request_ref` e `NOT NULL` fiindcă ecranul de consimțământ din
[ADR-017](../decisions/017-terminologie.md) numește solicitarea — *„un consimțământ generic aprobă
orice, oricând"*. Ce rămâne deschis e clauza contractuală (`OD-115`), nu mecanismul.

*Formularea originală, păstrată: opțiunile erau (A) nu există — diagnosticul se face exclusiv din
loguri și metrici, ceea ce face unele incidente irezolvabile; (B) există, cu acordul explicit al
tenantului per incident și expirare automată; (C) există, fără acord, dar cu notificare către tenant
și audit vizibil clientului. Alegerea are consecințe contractuale, nu doar tehnice.*

### 6.3 `privileged_access_log`

Tabelă globală, append-only, fără chei străine intrând (R21 se aplică prin analogie: crește
nelimitat).

| Câmp | Tip | Note |
|---|---|---|
| `id` | bigint | PK |
| `occurred_at` | timestamptz | NOT NULL — coloană naturală de partiționare |
| `path_code` | text | NOT NULL, `P-1` … `P-10` |
| `actor_user_id` | uuid | NULL — utilizator uman sau de sistem (3.4); nul cât utilizatorii de sistem nu există, lângă `actor` text NOT NULL (cine sau ce a rulat calea) — ADR-049 |
| `subject_tenant_id` | uuid | NULL — tenantul atins, dacă e unul singur. Nu `tenant_id`: pe o tabelă fără context de tenant, numele acela e citit de gardian ca derivă (`IZ-76`) — ADR-049 |
| `tenant_count` | integer | NULL — pentru rulările globale |
| `request_id` | text | NOT NULL — corelator (9.3) |
| `justification` | text | NULL — obligatoriu pentru P-7 |
| `payload` | jsonb | NULL — parametrii apelului, fără date de business |

Interogarea acestei tabele face parte din raportul lunar de conformitate. O cale privilegiată care
nu apare niciodată în log este fie moartă (se șterge), fie neinstrumentată (defect).

---

## 7. Read models

### 7.1 Ce sunt și ce nu sunt

Sunt stratul — și singurul — unde interogarea cross-tenant este permisă (INV-10). Sunt conceptual un
store separat, chiar dacă azi trăiesc în același cluster.

Justificarea lor este concretă: contabilul cu 60 de clienți vrea să știe cine are declarația
nedepusă, cine are TVA de plată, cine are documente neînregistrate, cine are termen săptămâna asta.
Fără read models, acel dashboard se scrie ca un `JOIN` peste tabelele operaționale ale 60 de
tenanți — și în ziua în care se scrie, invariantul se pierde fără ca nimeni să observe.

Ce **nu** sunt: o cale de acces la date de detaliu. Un read model conține agregate și
identificatori, niciodată sume de linii de jurnal sau conținut de document. Drill-down-ul dintr-un
read model se face intrând în contextul tenantului respectiv, pe calea normală, cu politicile
active.

**Intrarea în contextul clientului este schimbare de context, nu navigare.** Trei cerințe decurg
din asta:

- interfața arată **permanent**, cât timp durează, în ce tenant se lucrează și prin ce relație —
  cu cuvintele de interfață fixate în [ADR-017](../decisions/017-terminologie.md), niciodată cu
  termenii de model (`C37`);
- fiecare acțiune se auditează cu ambele identități: persoana **și** firma prin care a obținut
  accesul. Coloana există — `audit_event.actor_firm_id`; cerința este să fie completată pe această
  cale, nu să existe;
- tabloul consolidat nu devine niciodată a doua cale către date de detaliu. Când un indicator cere
  „de ce", răspunsul este intrarea în context, nu o coloană în plus în read model.

### 7.2 Structura

Fiecare tabelă de read model are:

- `tenant_id` — proprietarul datelor
- `firm_id` — firma îndreptățită să vadă rândul, **denormalizat**
- `company_id` — unde e relevant
- `as_of` — momentul la care agregatul e valabil
- `source_version` — pentru detectarea rândurilor învechite
- agregatele propriu-zise

Exemple de tabele (structura completă a fiecăreia se fixează la F3, modelul acum):

| Tabelă | Conținut |
|---|---|
| `rm_client_compliance_status` | per tenant + companie: declarații datorate, depuse, întârziate, următorul termen |
| `rm_client_financial_snapshot` | TVA de plată, solduri AR/AP, disponibil, la o dată |
| `rm_client_document_backlog` | documente neînregistrate, neconfirmate, nepostate |
| `rm_firm_workload` | per firmă: volum pe client, termene în săptămâna curentă |

### 7.3 Politica RLS a read models

Diferă de șablon: filtrează pe `firm_id`, nu pe `tenant_id`.

```sql
CREATE POLICY rm_client_compliance_firm_access ON rm_client_compliance_status
    FOR SELECT TO evidenta_app
    USING (
        firm_id = app.current_actor_firm_id()
        AND EXISTS (
            SELECT 1 FROM firm f
            JOIN membership fm ON fm.tenant_id = f.tenant_id
                              AND fm.user_id  = app.current_user_id()
                              AND fm.status   = 'active'
            WHERE f.id = rm_client_compliance_status.firm_id
        )
    );
```

Trei consecințe de reținut:

1. **Fără politică de scriere pentru rolul de aplicație.** Read models se scriu exclusiv prin calea
   privilegiată P-6. `evidenta_app` primește doar `SELECT`.
2. **`app.tenant_id` nu apare în politică.** Este singurul loc din sistem unde asta e corect.
   Gardianul de model trebuie să știe despre acest tipar, altfel îl raportează ca încălcare.
3. **Rândul dispare când engagementul se stinge.** `firm_id` denormalizat trebuie curățat la
   revocare — vezi 7.5.

### 7.4 Actualizarea

Două mecanisme, ambele necesare:

- **La eveniment:** închiderea unui document, depunerea unei declarații, postarea unei perioade
  produc un mesaj care actualizează rândul corespunzător. Latență mică, dar poate rata evenimente.
- **Prin job periodic:** reconstrucție completă per tenant, care corectează divergențele. Latență
  mare, dar convergent.

Read model-ul este **derivabil integral** din datele operaționale. Dacă nu este, a devenit sursă de
adevăr și încalcă propriul rol.

### 7.5 Ciclul de viață față de engagement

- La **revocare** sau **expirare**: rândurile cu acel `firm_id` se șterg în aceeași tranzacție cu
  revocarea. Nu se păstrează „pentru istoric" — istoricul e în audit, nu într-un cache.
- La **transfer**: rândurile vechi se șterg, cele noi se construiesc pentru firma nouă. Nu se
  reetichetează, ca să nu apară o fereastră în care ambele firme văd rândul.
- La **suspendare**: rândurile se marchează inactive, nu se șterg — suspendarea e reversibilă.

**`DECIZIE NECESARĂ (DN-19)` — read models pentru tenantul fără firmă.** Un tenant pe canal direct
nu are `firm_id`. Ori read models sunt exclusiv pentru firme (și tenantul direct își vede starea
prin interogări normale, în propriul context), ori `firm_id` devine nullable și politica capătă o a
doua ramură. Prima variantă e mai curată; a doua evită duplicarea logicii de calcul a stării de
conformitate.

---

## 8. Cazurile de test de izolare

Listă din care testele se scriu direct. Fiecare rând este un test. Rezultatul așteptat este parte
din specificație, nu din interpretarea celui care scrie testul.

**Condiție care se aplică tuturor (T1):** rulează sub `evidenta_app`. Un test rulat ca superuser sau
ca owner trece întotdeauna și nu demonstrează nimic. Suita verifică la pornire rolul efectiv și
refuză să ruleze dacă nu e cel corect.

**Fixtura minimă comună:**

```
Tenant A  (subdomeniu a)  — Company A1, Company A2  — User UA (membru)
Tenant B  (subdomeniu b)  — Company B1              — User UB (membru)
Firm F    (tenant propriu TF)                       — User UF (membru al TF)
Engagement E: F → Tenant B, activ, covers_all_companies = true
User UX: fără nicio apartenență
```

### 8.1 Penetrare de bază — tenant A încearcă să atingă tenant B

| # | Scenariu | Rezultat așteptat |
|---|---|---|
| IZ-01 | UA, context tenant A, citește `partner` | doar partenerii lui A |
| IZ-02 | UA, context tenant A, citește `journal_entry` cu filtru pe compania B1 | zero rânduri |
| IZ-03 | UA setează `app.tenant_id` = B și interoghează | zero rânduri: `has_tenant_access` eșuează, deși `tenant_id` corespunde |
| IZ-04 | UA cere prin API o resursă a lui B, după `id` | 404, nu 403 — existența nu se dezvăluie |
| IZ-05 | UA accesează subdomeniul `b` cu sesiunea proprie | refuz la autentificare/autorizare, fără atingerea datelor |
| IZ-06 | Repetat pentru fiecare tip de resursă: facturi, înregistrări contabile, payroll, atașamente, documente, obiecte API, read models | zero acces, în toate cazurile |
| IZ-07 | UA citește `user` (tabelă globală) și încearcă să deducă apartenențele lui B | tabela e vizibilă, dar nu conține niciun câmp de business (1.5) |
| IZ-08 | UA citește `membership` filtrând pe tenantul B | zero rânduri. Politica e `user_id = app.current_user_id()`, deci UA nu vede nici măcar apartenențele colegilor lui (ADR-003) |

### 8.2 Stările engagementului

| # | Scenariu | Rezultat așteptat |
|---|---|---|
| IZ-10 | UF, `actor_firm_id = F`, context tenant B, engagement **activ** | acces conform scope-ului |
| IZ-11 | Engagement **expirat** (`valid_to` în trecut, `status` încă `active`) | zero acces — verificat prin predicat, nu prin job |
| IZ-12 | Engagement **revocat** | zero acces, imediat, în aceeași tranzacție cu revocarea |
| IZ-13 | Engagement **suspendat** | zero acces; relația se păstrează |
| IZ-14 | Engagement **invited**, neacceptat | zero acces |
| IZ-15 | Engagement cu `valid_from` în viitor | zero acces până la data respectivă |
| IZ-16 | UF setează `actor_firm_id = F` dar **nu** e membru al tenantului firmei | zero acces — apartenența la firmă se verifică (2.4, punctul 2) |
| IZ-17 | UF setează `actor_firm_id` = o firmă care nu are engagement cu B | zero acces |
| IZ-18 | UA (membru al A) setează `actor_firm_id = F` pentru a împrumuta drepturile firmei | zero acces |
| IZ-19 | După revocare, `company_access` cu `granted_via='engagement'` | toate revocate în aceeași tranzacție |
| IZ-20 | După revocare, sesiunea activă a lui UF | invalidată; cererile ulterioare eșuează |
| IZ-21 | Engagement transferat către altă firmă | firma veche: zero acces; firma nouă: acces; niciun interval în care ambele au acces (dacă `DN-15` alege A) |
| IZ-22 | Membrul firmei este suspendat sau scos din firmă | zero acces la **toți** clienții, la următoarea interogare — statutul se reevaluează, nu se copiază; rândurile `company_access` rămân și nu mai dau nimic |
| IZ-68 | UC (membru doar al firmei C), cu engagement **activ** C → tenantul firmei A, cere contextul unui client al lui A | zero acces — predicatul potrivește o relație, nu un lanț (ADR-035) |
| IZ-69 | Același, la nivel de companie: clientul lui A are `company_access` derivat din engagementul lui A | zero acces; controlul demonstrează că utilizatorul lui A **chiar** ajunge la companie |

### 8.3 Scope restrâns

| # | Scenariu | Rezultat așteptat |
|---|---|---|
| IZ-25 | Engagement cu `covers_all_companies = false` și scope doar pe B1; se cere B2 | zero acces la B2 |
| IZ-26 | Companie nouă creată la tenantul B după acceptarea engagementului cu `covers_all_companies = false` | fără acces automat |
| IZ-27 | Idem, cu `covers_all_companies = true` | acces automat |
| IZ-28 | Engagement cu scope de modul restrâns (`DN-07`), se cere un modul din afara scope-ului | zero acces |
| IZ-29 | Engagement cu `permission_level = 'read'`, se încearcă scriere | refuz la scriere, citirea funcționează |

### 8.4 Context absent sau incorect

| # | Scenariu | Rezultat așteptat |
|---|---|---|
| IZ-30 | Interogare fără `app.tenant_id` | **eroare**, nu zero rânduri (2.3) |
| IZ-31 | Interogare fără `app.user_id` | eroare |
| IZ-32 | `app.tenant_id` cu valoare inexistentă | zero rânduri |
| IZ-33 | `app.tenant_id` malformat (nu e uuid) | eroare |
| IZ-34 | Interogare în afara unei tranzacții, după `SET LOCAL` într-o tranzacție anterioară | eroare — contextul nu supraviețuiește |
| IZ-35 | `SET` în loc de `SET LOCAL`, apoi commit și o a doua tranzacție pe aceeași conexiune | testul trebuie să **eșueze la build**: un lint interzice `SET` neînsoțit de `LOCAL` |
| IZ-36 | Cerere API cu `tenant_id` în payload, diferit de subdomeniu | cerere respinsă și auditată |
| IZ-37 | Cerere pe un subdomeniu inexistent | 404, fără a dezvălui existența |
| IZ-38 | Cerere pe subdomeniul unui tenant `suspended` / `archived` | refuz conform 9.4 |

### 8.5 Task-uri Celery

| # | Scenariu | Rezultat așteptat |
|---|---|---|
| IZ-40 | Task fără `tenant_id` în argumente | **eșuează la pornire**, nu returnează date |
| IZ-41 | Task cu `tenant_id` care setează contextul corect | acces doar la tenantul respectiv |
| IZ-42 | Task care încearcă să interogheze înainte de a seta contextul | eroare |
| IZ-43 | Două task-uri consecutive pe același worker, tenanți diferiți | contextul primului nu se scurge în al doilea |
| IZ-44 | Task care eșuează și se reia | contextul se resetează pe calea de eroare și de retry |
| IZ-45 | Task cu utilizator de sistem, fără `membership` | zero acces pe calea normală (3.4) |

### 8.6 Calea de scriere

| # | Scenariu | Rezultat așteptat |
|---|---|---|
| IZ-50 | `INSERT` cu `tenant_id` diferit de contextul curent | refuzat de `WITH CHECK` |
| IZ-51 | `UPDATE` care mută un rând la alt `tenant_id` | refuzat |
| IZ-52 | `INSERT` într-o companie la care utilizatorul nu are acces | refuzat |
| IZ-53 | `DELETE` pe un rând al altui tenant | zero rânduri afectate |

### 8.7 Căi privilegiate și read models

| # | Scenariu | Rezultat așteptat |
|---|---|---|
| IZ-60 | Rolul de aplicație apelează direct o funcție privilegiată neexpusă | refuz |
| IZ-61 | Fiecare apel privilegiat scrie în `privileged_access_log` | rând prezent, în aceeași tranzacție |
| IZ-62 | Un apel privilegiat care eșuează | logul reflectă încercarea (rollback-ul nu trebuie să ascundă tentativa — vezi nota de mai jos) |
| IZ-63 | UF citește read models pentru firma F | doar rândurile cu `firm_id = F` |
| IZ-64 | UF citește read models pentru altă firmă | zero rânduri |
| IZ-65 | UA (fără firmă) citește read models | zero rânduri |
| IZ-66 | `evidenta_app` încearcă `INSERT` într-un read model | refuzat — scrierea e exclusiv prin P-6 |
| IZ-67 | După revocarea engagementului, read models pentru acea pereche | șterse |

> Nota la IZ-62: dacă logul se scrie în aceeași tranzacție, un rollback îl șterge. Tentativele
> eșuate se înregistrează pe o cale separată (log de aplicație sau tabelă scrisă cu
> `AUTONOMOUS`-echivalent — PostgreSQL nu are tranzacții autonome, deci prin `dblink` sau prin
> jurnal extern). **Aceasta este o cerință, nu o observație:** o cale privilegiată apelată nelegitim
> și eșuată este exact evenimentul care trebuie văzut.

### 8.8 Suita 2 — gardian de model

| # | Verificare | Eșec dacă |
|---|---|---|
| IZ-70 | Enumeră toate tabelele din schemă | o tabelă nu are coloană de context de tenant și nu e în lista 5.4 |
| IZ-71 | Idem | o tabelă nu are politică RLS activă |
| IZ-72 | Idem | o tabelă nu are `FORCE ROW LEVEL SECURITY` |
| IZ-73 | Idem | o tabelă are politică doar pentru `SELECT`, fără `WITH CHECK` pe calea de scriere |
| IZ-74 | Rolul efectiv al suitei | nu este `evidenta_app` |
| IZ-75 | Rolul de aplicație | are `BYPASSRLS` sau este owner al vreunei tabele |
| IZ-76 | Lista de excepții (5.4) | conține o tabelă care are totuși `tenant_id` — semn că lista a fost extinsă în loc să se corecteze tabela |
| IZ-77 | Tabelele append-only (R21) | au chei străine intrând, sau coloana de partiționare e nullable |

IZ-76 și IZ-77 sunt cele care prind tabela adăugată peste trei ani de cineva care nu știe regula.
Ele sunt motivul pentru care suita 2 este mai valoroasă pe termen lung decât suita 1.

---

## 9. Restaurare, export, offboarding, retenție

Patru concepte distincte. Confundarea lor produce promisiuni imposibile.

### 9.1 Ce se promite și ce nu

| Concept | Domeniu | Mecanism | Se promite clientului? |
|---|---|---|---|
| **Recuperare tehnică în caz de dezastru** | pierdere de date la nivel de cluster | PITR, backup | **Da**, ca SLA de infrastructură |
| **Corecție de business** | erori de operare, oricât de mari | storno, reînregistrare, audit | **Da**, ca funcție de produs |
| **Export / snapshot** | cazuri forensice, litigii, offboarding | export complet la o dată | **Da**, la cerere |
| **Restaurare la o stare anterioară** | „adu-mi datele de vineri" | — | **Nu. Se refuză, cu explicație** |

Motivul refuzului, care se comunică clientului ca atare: vineri factura era emisă, e-Factura
transmisă la SFS, extrasul bancar importat, salariile declarate la CNAS. Timpul nu se dă înapoi în
afara sistemului. O „restaurare" ar produce o bază de date care contrazice ce au instituțiile.

Răspunsul produsului la aceeași nevoie: **identificarea efectelor din intervalul respectiv și
stornarea lor coerentă**.

### 9.2 Ce trebuie să existe pentru ca refuzul să fie onest

Refuzul e acceptabil doar dacă alternativa funcționează. Alternativa cere:

1. enumerarea completă a efectelor unei sesiuni, ale unui utilizator sau ale unui interval
2. stornarea lor în ordine coerentă, cu lineage păstrat
3. un raport care arată ce s-a stornat și ce nu s-a putut storna, și de ce

Punctul 1 este o **cerință funcțională**, nu un efect secundar al audit-ului.

### 9.3 Enumerarea efectelor — modelul

Corelatorul este `request_id`: generat la începutul fiecărui request și al fiecărui task, pus în
contextul de sesiune (3.1), propagat prin lanțul de task-uri copil.

Coloanele necesare, **pe entitățile care produc efecte**, nu doar în audit:

| Entitate | Coloane |
|---|---|
| `accounting_event` | `request_id`, `actor_user_id`, `occurred_at` |
| `document` | `request_id`, `created_by_user_id` |
| `journal_entry` | `request_id` (moștenit din eveniment) |
| `audit_event` | `request_id`, `actor_user_id`, `occurred_at`, `session_id` |

De ce nu e suficient audit log-ul singur: `audit_events` este append-only fără chei străine intrând
(R21). Nu se poate face `JOIN` de la audit către efecte ca să afli ce să stornezi. Legătura trebuie
să existe **în sens invers** — de la efect către corelator — și de aceea `request_id` stă pe
entitățile de efect.

Interogarea de bază pe care se sprijină corecția de business:

```sql
-- toate evenimentele contabile produse de un utilizator într-un interval
SELECT ae.id, ae.event_type, ae.request_id, ae.occurred_at
FROM   accounting_event ae
WHERE  ae.tenant_id  = app.current_tenant_id()
  AND  ae.company_id = $1
  AND  ae.actor_user_id = $2
  AND  ae.occurred_at >= $3 AND ae.occurred_at < $4
ORDER  BY ae.occurred_at;
```

Index necesar: `(tenant_id, company_id, actor_user_id, occurred_at)`. Fără el, întrebarea „ce a
făcut acest utilizator luni" devine seq scan pe tabela cea mai mare din sistem.

**`DECIZIE NECESARĂ (DN-20)` — granularitatea sesiunii.** `request_id` identifică o cerere. Un
utilizator care lucrează două ore produce sute. Cererea reală a clientului este „ce a stricat
Maria luni" — adică o sesiune, nu o cerere. Opțiuni: (A) doar `request_id`, iar gruparea pe sesiune
se face după `actor_user_id` + interval, ceea ce e suficient în practică și nu costă nimic;
(B) `session_id` propriu, propagat în plus, care dă răspunsuri exacte dar adaugă o coloană pe
fiecare entitate de efect; (C) `session_id` doar în audit, cu maparea `request_id → session_id`
acolo, ceea ce evită coloana suplimentară dar face interogarea un `JOIN` peste cea mai mare tabelă.

### 9.4 Offboarding

Stările tenantului și ce se întâmplă la fiecare:

| Stare | Acces utilizatori | Task-uri periodice | Date | Facturare |
|---|---|---|---|---|
| `active` | normal | rulează | vii | activă |
| `suspended` | **doar citire** | oprite, cu excepția celor de conformitate | vii | suspendată |
| `offboarding` | doar citire și export | oprite | vii, în perioadă de grație | oprită |
| `archived` | niciun acces prin aplicație | oprite | arhivate, accesibile doar prin P-8 | oprită |

Traseul: `active → suspended → offboarding → archived`. Fiecare tranziție are dată, autor și
notificare către tenant.

**`DECIZIE NECESARĂ (DN-21)` — durata perioadei de grație** dintre `offboarding` și `archived`, și
dacă suspendarea pentru neplată taie și accesul de citire. Implicație: un client care nu poate
descărca ce a produs, pentru că nu a plătit, are o problemă legală, nu doar comercială — documentele
contabile îi aparțin și are obligație de păstrare.

Ce **nu** se oprește niciodată, în nicio stare în afară de `archived`: capacitatea de a exporta.

### 9.5 Retenția

**Termenele de păstrare sunt parametri fiscali** — [ADR-008](../decisions/008-retention-fiscal-parameters.md).

- Pe documentul core stă `retention_class`, nu un termen.
- Termenul se rezolvă din `fiscal_parameter`, cu cheia `retention.<class>`, la data efectivă
  relevantă. Aceeași structură ca orice parametru fiscal: `valid_from` / `valid_to` și `source_id`
  către actul normativ, cu număr de Monitorul Oficial și dată de publicare.
- Tabela `retention_policy` **nu există**. Un mecanism de versionare cu proveniență, nu două.

**Valorile rămân deschise** (`OD-21`). Se completează ca date, cu confirmare de la contabil sau
jurist. Această specificație nu le enunță, pentru că nu le are dintr-o sursă citabilă, iar
legislația fiscală nu se ghicește.

Un singur lucru se afirmă despre conținut, și chiar și acela stă în `Propus` până la confirmare:
termenele **diferă substanțial** între documentele contabile obișnuite și cele de personal și
salarizare, deci `retention_class` are de la început cel puțin două valori distincte. Un termen unic
pe tenant ar fi greșit indiferent de cifră.

Rămâne de răspuns, tot pentru contabil sau jurist: **cine poartă obligația de păstrare după ce
tenantul pleacă** — clientul, odată cu exportul, sau platforma? Dacă platforma, `archived` nu
înseamnă „șters", ci „mutat în stocare rece cu acces controlat", și e nevoie de o politică de
ștergere efectivă la expirarea termenului.

Consecința asupra F0: **una singură** — `retention_class` pe documentul core, la F0.6.1. Restul e F3.

### 9.6 Exportul

Un export complet conține, pentru un tenant și un interval:

- toate documentele, cu atașamentele lor
- ledgerul complet: evenimente contabile, înregistrări, linii, cu lineage
- master data: parteneri, articole, plan de conturi instanțiat
- payroll: angajați, contracte, rulări, cumulative
- declarațiile depuse și confirmările primite
- audit log-ul aferent
- un manifest cu: momentul exportului, cine l-a cerut, ce interval acoperă, sumele de control

**Formatul** trebuie să fie „utilizabil" (V2 §12.2). Aceasta înseamnă cel puțin: citibil fără
Evidenta, cu structură documentată. Vezi `DN-23`.

Exportul rulează prin calea privilegiată P-8 și se auditează. Un export este el însuși un eveniment
care apare în raportul de conformitate — este momentul în care toate datele unui tenant părăsesc
sistemul.

---

## 10. Billing și release

### 10.1 Principiul

**Capability set ≠ plan comercial.** Sunt axe ortogonale. Planul propune un set implicit de
capabilități; nu îl definește rigid. În modelul wholesale, firma plătește preț de partener pentru
tenanții gestionați și facturează cum vrea; un client de-al ei poate avea nevoie de Inventory fără
să corespundă vreunui tier din grila directă.

Consecință de model: `CapabilityActivation` (1.8) **nu** are cheie străină către plan. Legătura e în
sens invers — un plan produce un set implicit de activări la subscriere, după care ele trăiesc
independent.

### 10.2 Entități

`billing_account` — cine plătește. Nivel tenant.

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id` | uuid | NOT NULL — tenantul facturat |
| `channel` | text | NOT NULL, CHECK în `('direct','wholesale')` |
| `payer_firm_id` | uuid | NULL — obligatoriu când `channel='wholesale'` |
| `billing_email`, `billing_address` | text / jsonb | |
| `currency` | char(3) | NOT NULL — vezi `DN-24` |
| `status` | text | NOT NULL, CHECK în `('active','past_due','suspended','closed')` |

`CHECK ((channel = 'wholesale') = (payer_firm_id IS NOT NULL))`.

`subscription` — ce s-a cumpărat. Nivel tenant.

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id` | uuid | NOT NULL |
| `billing_account_id` | uuid | NOT NULL |
| `plan_code` | text | NOT NULL — `start`, `business`, `erp`, `enterprise` |
| `valid_from` | date | NOT NULL |
| `valid_to` | date | NULL |
| `price_amount`, `price_currency` | numeric / char(3) | prețul efectiv, care în wholesale diferă de grilă |
| `status` | text | NOT NULL |

Neîntrepătrundere pe `(tenant_id, daterange(valid_from, valid_to))` — un tenant are un singur
abonament activ la un moment dat.

`plan` — catalogul. Tabelă **globală**: `plan_code`, `name`, `default_capabilities jsonb`,
`list_price`, `valid_from`, `valid_to`. Versionată, pentru că grila se schimbă și abonamentele
existente trebuie să știe ce grilă li s-a aplicat.

### 10.3 Relația cu capabilitățile

```
plan.default_capabilities  ──(la subscriere, o singură dată)──►  CapabilityActivation*
                                                                  │
                                          activări suplimentare ──┘
                                          (manual, prin firmă, prin migrare)
```

Reguli:

1. Schimbarea planului **nu** dezactivează automat capabilități. Dezactivarea unei capabilități cu
   date deja postate este o operațiune cu efect contabil (ce se întâmplă cu stocul existent?), nu o
   consecință a unei schimbări de tarif. Este proces separat, cu dată efectivă și aprobare.
2. Capabilitățile de conformitate nu apar niciodată ca activări dezactivabile (1.8, R24).
3. Neplata suspendă **facturarea și accesul**, nu capabilitățile. Un tenant `past_due` nu pierde
   TVA-ul; pierde accesul, conform 9.4 și `DN-21`.

### 10.4 Wholesale

- Firma are `billing_account` pentru fiecare tenant gestionat, cu `channel='wholesale'` și
  `payer_firm_id` propriu.
- Prețul de partener nu e derivabil din grila publică — de aceea `subscription.price_amount` este
  explicit.
- Ce facturează firma clientului ei nu trece prin Evidenta. Platforma nu are opinie și nu are date
  despre asta.
- La revocarea engagementului, `billing_account` **nu** se schimbă automat: cineva trebuie să
  decidă dacă tenantul trece pe canal direct sau se închide. Vezi `DN-25`.

### 10.5 Feature flags și release rings

Distincția, care se pierde ușor:

- **Capabilitate** = ce a activat tenantul. Funcțională. Are dată efectivă și stare de
  inițializare. Vizibilă clientului.
- **Feature flag** = ce cod e activ. Tehnic. Fără dată efectivă contabilă. Invizibil clientului.

`feature_flag` (global): `key`, `description`, `default_state`.
`release_ring` (global): `code` (`internal`, `early`, `general`), `description`.
`tenant_release_ring` (nivel tenant): `tenant_id`, `ring_code`, `assigned_at`, `assigned_by`.
`feature_flag_override` (nivel tenant): `tenant_id`, `flag_key`, `state`, `reason`, `expires_at`.

Reguli:

1. Un singur codebase (R23). Ringurile controlează *când* ajunge codul la un tenant, niciodată *ce
   cod* rulează pentru el.
2. Modificările de conformitate **nu trec prin ringuri**. Ajung la toți simultan (R24). Un flag care
   ascunde o schimbare fiscală de o parte din tenanți este defect critic.
3. Fiecare override are `reason` și `expires_at`. Un flag permanent per tenant este o versiune per
   tenant deghizată.

---

## 11. DECIZII NECESARE — lista completă

**28 de puncte** — 25 la scrierea specificației, plus `DN-26`–`DN-28`, apărute odată cu §12 și §13.
*Decise la 2026-08-31: `DN-18` ([ADR-077](../decisions/077-grantul-de-suport.md)), `DN-26`
([ADR-078](../decisions/078-cine-poate-crea-un-tenant.md)), `DN-27`
([ADR-079](../decisions/079-tenantul-nerevendicat.md)).*

Închise ulterior prin ADR-uri: `DN-01` (ADR-014, ADR-016), `DN-04` și `DN-05`
([ADR-039](../decisions/039-valuta-si-perioade.md)), `DN-06` și `DN-07` (ADR-018, ADR-019), `DN-08`
(ADR-020), `DN-09` (ADR-021), `DN-11` (ADR-003), `DN-12` (ADR-004), `DN-16`
([ADR-030](../decisions/030-atasamente.md)), `DN-22` parțial. Restul **nu au fost alese în această
specificație**. Coloana **Blochează** spune ce nu
poate fi implementat până la închidere; coloana **Unde** trimite la blocul cu opțiuni, când acesta
e dezvoltat în text.

| # | Decizie | Blochează | Unde |
|---|---|---|---|
| ~~DN-01~~ | **ÎNCHISĂ.** Rusa e strat de prezentare exclusiv; contabilitatea se ține în română prin lege (nr. 287/2017, art. 7). Denumirile de referință rămân valoare unică | — | [ADR-014](../decisions/014-limba-rusa.md), [ADR-016](../decisions/016-limba-contabilitatii.md) |
| DN-02 | Subdomeniu: se poate schimba? se eliberează pentru realocare? | F0.3 | 11.2 |
| DN-03 | IDNO: unic global între tenanți, sau doar per tenant? **Restrânsă** — indexul nu se creează (ar decide tăcut o regulă comercială), dar duplicatul devine modul normal de eșec, deci se avertizează la creare, doar unei firme verificate | F0.3 | 11.3, [ADR-081](../decisions/081-revendicarea-optionala.md) §7 |
| ~~DN-04~~ | **ÎNCHISĂ.** `MDL` fix; linia poartă valută din ziua 1, cu numele din Spec B și cu `rate_date` | — | [ADR-039](../decisions/039-valuta-si-perioade.md) |
| ~~DN-05~~ | **ÎNCHISĂ.** Nu — exercițiul are `start_date`/`end_date` explicite; perioada TVA e entitate distinctă de perioada contabilă | — | [ADR-039](../decisions/039-valuta-si-perioade.md) |
| ~~DN-06~~ | **ÎNCHISĂ.** Da — mai multe firme, separate prin scope de module. Unicitatea rămâne per pereche firmă–tenant; un `module_key` aparține unui singur engagement viu | — | [ADR-018](../decisions/018-engagementuri-multiple.md) |
| ~~DN-07~~ | **ÎNCHISĂ.** `module_key` = numele modulului de business din harta §4.1; drepturi `read`/`write`, `write` include `read`; lista impusă prin `CHECK` | — | [ADR-019](../decisions/019-vocabular-scope.md) |
| DN-08 | Vocabularul de roluri pentru `Membership` și `CompanyAccess` | F0.3, RBAC | 11.8 |
| DN-09 | MFA: obligatoriu, opțional, sau obligatoriu pentru anumite roluri? | F0.3 | 11.9 |
| ~~DN-10~~ | **DECIS** — listă curatoriată după ce cere inițializare; `payroll` se activează, ieșirile lui declarative nu | — | [ADR-060](../decisions/060-vocabularul-capabilitatilor.md) |
| ~~DN-11~~ | **DECIS** — `app.company_id` opțional, îngustează; izolarea prin `has_company_access()` | — | [ADR-004](../decisions/004-company-context.md) |
| ~~DN-12~~ | **DECIS** — predicate `SECURITY DEFINER` sub un rol dedicat cu `BYPASSRLS`; politici neîncrucișate pe tabelele de tenancy | — | [ADR-003](../decisions/003-rls-tenancy-tables.md) |
| DN-13 | Expirarea invitațiilor de engagement și de membership | F0.3 | 11.13 |
| DN-14 | Poate firma revoca unilateral? cu preaviz? | F0.3 | 11.14 |
| DN-15 | Suprapunerea la transferul între firme | F0.3 | §4.5 |
| DN-16 | Nivelul metadatelor de atașament: tenant sau companie? | F0.6 | 11.16 |
| DN-17 | Mecanismul căilor privilegiate: funcții `SECURITY DEFINER` sau rol separat | F0.1 | §6.1 |
| ~~DN-18~~ | **DECIS** — varianta (B): grant cerut privilegiat, aprobat de client, doar-citire, expirat în predicat | — | [ADR-077](../decisions/077-grantul-de-suport.md) |
| DN-19 | Read models pentru tenantul fără firmă | F3, model acum | §7.5 |
| DN-20 | Granularitatea corelatorului: `request_id`, `session_id`, sau ambele | F0.4 | §9.3 |
| DN-21 | Durata perioadei de grație la offboarding; accesul de citire la neplată. **Promovată la condiție de lansare** ([ADR-081](../decisions/081-revendicarea-optionala.md) §6): pe un tenant nerevendicat, neplata firmei suspendă registrele unui client care n-a contractat cu nimeni | **lansarea**, nu F3 | §9.4 |
| DN-22 | Termenele legale de păstrare — **mecanismul e decis** (parametri fiscali), valorile rămân deschise (`OD-21`) | F3 | [ADR-008](../decisions/008-retention-fiscal-parameters.md), `Propus` |
| DN-23 | Formatul exportului complet | F3 | 11.23 |
| DN-24 | Moneda de facturare și tratamentul TVA pe abonament | F3 | 11.24 |
| DN-25 | Ce se întâmplă cu `billing_account` la revocarea engagementului wholesale. **Restrânsă la politică** — mecanismul e decis: plătitorul e o atribuire cu dată, iar revocarea nu-l schimbă de la sine ([ADR-081](../decisions/081-revendicarea-optionala.md) §5). **Promovată la condiție de lansare** | **lansarea**, nu F3 | §10.4 |
| ~~DN-26~~ | **DECIS** — două canale: autoservire și creare de către firmă; invitația e poartă de lansare, nu canal | — | [ADR-078](../decisions/078-cine-poate-crea-un-tenant.md) |
| ~~DN-27~~ | **DECIS** — revendicarea e opțională, calea de revendicare (`P-11`) nu; mandat declarat, plătitor mutabil cu dată | — | [ADR-081](../decisions/081-revendicarea-optionala.md) *(înlocuiește [ADR-079](../decisions/079-tenantul-nerevendicat.md))* |
| DN-28 | Granițele exacte ale ferestrei de îngheț și procesul de excepție | Prima lansare | §13.4 |

### 11.1 DN-01 — limba rusă

`ru` apare doar ca director în arborele repo-ului din documentul de implementare; convenția de limbă
spune „interfață în română"; V2 nu menționează limba rusă în poziționare, roadmap sau structura
comercială.

- **A — doar `ro`.** Cel mai ieftin. Denumirile contabile, de documente și de rapoarte sunt text
  simplu. Riscă să excludă o parte reală a pieței.
- **B — `ro` + `ru` doar în interfață**, cu denumirile de business în română. Fișiere de resurse,
  fără efect asupra schemei. Utilizatorul rus vede meniuri traduse și conturi în română.
- **C — `ro` + `ru` inclusiv pentru denumirile stocate** (conturi, tipuri de documente, rapoarte).
  Cere coloane sau tabele de traduceri pe fiecare entitate cu denumire vizibilă, **din F0**, pentru
  că adăugarea ulterioară atinge fiecare tabelă de nomenclator.

Implicația care contează: B și C diferă în modelul de date, nu în efort de traducere. Decizia se ia
înainte de F0.7, nu la lansare.

### 11.2 DN-02 — subdomeniul

- **A — imutabil.** Simplu, dar o companie care își schimbă denumirea rămâne cu subdomeniul vechi.
- **B — schimbabil, cu subdomeniul vechi rezervat permanent.** Evită preluarea identității de către
  alt tenant. Costă o tabelă de alias-uri și redirecționare.
- **C — schimbabil, cu eliberare după o perioadă.** Cel mai flexibil, cel mai riscant: un fost
  subdomeniu realocat primește e-mailuri, linkuri și integrări vechi.

### 11.3 DN-03 — unicitatea IDNO

Specificația impune `UNIQUE (tenant_id, idno)`. Întrebarea este dacă același IDNO poate apărea la
doi tenanți.

- **A — unic global.** Corect juridic: o entitate juridică există o dată. Blochează însă cazuri
  legitime de tranziție (migrare între tenanți, testare, holding restructurat) și cere o procedură
  de transfer.
- **B — unic per tenant** (cum e specificat). Permite duplicate între tenanți, ceea ce înseamnă că
  registrul global de contrapărți și efectul de rețea al e-Facturii (OD-12) trebuie să știe care
  tenant este „cel real" pentru un IDNO.
- **C — unic global cu excepții marcate**, prin stare (`primary` / `secondary`).

### 11.4 DN-04 — moneda funcțională

- **A — `MDL` fix.** Contabilitatea RM se ține în lei; simplifică tot. Blochează o filială a unui
  grup străin care raportează în altă monedă.
- **B — configurabilă per companie**, cu `MDL` implicit. Costă: fiecare raport și fiecare regulă
  de postare trebuie să știe care e moneda funcțională, iar cursul BNM nu mai e suficient.

Legislația RM determină răspunsul. Nu se presupune aici.

### 11.5 DN-05 — anul fiscal

Câmpul `fiscal_year_start_month` există în specificație cu implicit 1. Dacă legislația RM impune an
calendaristic fără excepție, câmpul se elimină — este mai bine să nu existe decât să sugereze o
flexibilitate care produce rapoarte invalide. **Necesită confirmare contabilă.**

### 11.8 DN-08 — vocabularul de roluri

Documentele spun „`Membership` cu roluri" și „`CompanyAccess` cu rol", fără să enumere niciunul.
Se știe doar că există cel puțin o permisiune privilegiată: redeschiderea unei perioade contabile
(V2 §7.5).

- **A — set fix de roluri, cu permisiuni implicite în cod.** Simplu, testabil, previzibil. Rigid:
  fiecare cerere de granularitate devine un rol nou.
- **B — roluri ca date, cu permisiuni compozabile.** Flexibil, dar mută autorizarea într-o tabelă
  editabilă de utilizatori, ceea ce înseamnă că un client își poate acorda drepturi pe care
  produsul nu le-a anticipat.
- **C — set fix de roluri + permisiuni punctuale delegabile** (redeschidere de perioadă, aprobare de
  plată, acces la salarii). Compromisul obișnuit, cu cost de implementare mediu.

Ce trebuie decis în orice variantă: rolurile din firma de contabilitate (delegare internă, V2 §9.3)
sunt același vocabular ca rolurile din tenant, sau unul separat?

### 11.9 DN-09 — MFA

- **A — opțional pentru toți.** Cea mai mică fricțiune, cea mai mare expunere: un cont de contabil
  compromis deschide 60 de tenanți.
- **B — obligatoriu pentru utilizatorii firmelor**, opțional pentru membrii tenantului. Proporțional
  cu riscul.
- **C — obligatoriu pentru toți.** Cel mai sigur; fricțiune reală la onboarding-ul unei
  microîntreprinderi.

Observație care nu e decizie: indiferent de variantă, contul care poate revoca un engagement sau
poate redeschide o perioadă are nevoie de MFA.

### 11.10 DN-10 — vocabularul de capabilități

> **DECISĂ 2026-08-30 — varianta B**, [ADR-060](../decisions/060-vocabularul-capabilitatilor.md).
> Lista curatoriată e exact cea pe care documentele o numeau: `payroll`, `inventory`,
> `multi_company`, peste cele trei de conformitate — criteriul de apartenență fiind *ce cere
> inițializare cu stare*. Tuplu în cod, materializat ca CHECK.
>
> **Tensiunea dintre §1.8 și §13, tranșată:** `payroll` **nu** intră în `COMPLIANCE_CAPABILITIES`.
> Se activează și are inițializare; dar odată activată, **ieșirile ei declarative nu se dezactivează
> și nu se plătesc separat** — `R24` se ține pe ieșiri, în cod, nu pe rândul de capabilitate.
>
> **Ierarhia (C) se amână**, cu declanșator: prima cerință de produs care o cere efectiv. Amânarea e
> ieftină **doar fiindcă `SNAPSHOT_VERSION` există** — despicarea unei chei se face cu o versiune
> nouă de snapshot, nu prin rescrierea evenimentelor deja postate.

Documentele numesc explicit: `inventory`, `payroll`, `multi_company`. Restul nu e enumerat.

- **A — capabilitățile corespund modulelor** din harta §4.1. Previzibil, dar unele module nu au sens
  ca unitate de activare (`numbering`, `audit`).
- **B — listă curatoriată**, mai scurtă decât modulele, definită de ce cere inițializare. Corespunde
  intenției din V2 §8, unde exemplele sunt toate lucruri care cer un pas de inițializare.
- **C — ierarhie** (capabilitate → subcapabilități), pentru cazuri ca „payroll de bază" vs. „payroll
  complet" din grila comercială.

Grila din V2 §13 presupune deja C („payroll de bază" în Start, „payroll complet" în Business).

### 11.13 DN-13 — expirarea invitațiilor

O invitație de engagement sau de membership neacceptată rămâne valabilă la nesfârșit?

- **A — fără expirare.** Simplu; lasă invitații vechi active, ceea ce e un vector de acces.
- **B — expirare fixă** (ex. 30 de zile), cu reinvitare posibilă.
- **C — expirare configurabilă per tenant.**

Oricare ar fi, invitația trebuie să fie un token cu durată de viață proprie, distinct de starea
`invited` a engagementului.

### 11.14 DN-14 — revocarea de către firmă

Tenantul poate revoca oricând și fără motivare — decurge din INV-7. Simetric?

- **A — firma poate revoca oricând.** Firma nu poate fi ținută ostatecă de un client care nu
  plătește. Riscul: clientul rămâne brusc fără cine îi depune declarația.
- **B — firma revocă cu preaviz** (relația trece în `suspended`, apoi în `revoked` după N zile).
  Protejează clientul; complică modelul cu o stare tranzitorie temporizată.
- **C — firma cere revocarea, tenantul o confirmă**, cu revocare automată după un termen.

Are consecințe contractuale, nu doar tehnice.

### 11.16 DN-16 — nivelul atașamentelor

Metadatele de atașament (`attachment_metadata`) sunt listate provizoriu la nivel tenant (5.2).

- **A — nivel tenant.** Permite reutilizarea aceluiași fișier între companiile unui holding.
- **B — nivel companie.** Consecvent cu documentele pe care le însoțesc; izolare mai strictă;
  duplicare la reutilizare.

Legat de asta, dar separat: layout-ul în S3 (bucket per tenant, sau prefix per tenant), semnarea
URL-urilor, limitele de dimensiune și tip, scanarea antivirus, și ce se întâmplă cu fișierele la
`archived`.

### 11.23 DN-23 — formatul exportului

„Utilizabil" (V2 §12.2) nu este o specificație.

- **A — CSV per entitate + fișiere de atașament**, cu un manifest. Citibil de oricine, pierde
  structura relațională, greu de reimportat.
- **B — JSON structurat**, cu schema documentată și versionată. Păstrează structura; cere unealtă
  pentru a fi citit de un contabil.
- **C — ambele**, plus PDF pentru documentele care au formă legală (facturi, state de salarii,
  situații financiare).

Criteriul real de decizie: exportul servește un litigiu, un audit fiscal și o migrare către alt
sistem. Cele trei cer lucruri diferite.

### 11.24 DN-24 — moneda de facturare și TVA pe abonament

Abonamentul se facturează în MDL? Către o firmă care gestionează tenanți, factura e una singură sau
per tenant? Se aplică TVA, și dacă da, cu ce regim pentru un client nerezident? Fiecare variantă are
efect asupra structurii `billing_account` și `subscription`.

---

## 12. Onboarding

Secțiunea aceasta lipsea, iar lipsa ei nu era de text: `OD-53` a arătat că **nicio cale de producție
nu creează un tenant sau o companie**. Politicile fail-closed o interzic prin construcție, iar
[ADR-040](../decisions/040-crearea-tenantului-si-a-companiei.md) răspunde cu calea privilegiată
`P-9`. Ce urmează descrie ce se întâmplă pe acea cale și în ce ordine.

Onboarding-ul e locul unde produsul ia **cele mai puțin reversibile decizii ale sale**, într-un
moment în care utilizatorul știe cel mai puțin despre produs. Asta e tensiunea pe care secțiunea o
tratează; restul e formular.

### 12.1 Ce este ireversibil, și de ce

| Alegere | De ce nu se mai schimbă | Unde e fixat |
|---|---|---|
| **Subdomeniul** | Este singura sursă a contextului de tenant (`C8`). Se poate schimba administrativ, dar cel vechi nu se eliberează pentru realocare | 1.1, `DN-02` |
| **Prima perioadă contabilă** | După postarea soldurilor inițiale și închiderea ei, registrul are conținut anterior oricărei alte date. Ledgerul e append-only (`R10`): nu există „mut începutul cu o lună" | [ADR-039](../decisions/039-valuta-si-perioade.md) §11 |
| **Exercițiul fiscal** | `start_date`/`end_date` determină perioada fiscală la impozitul pe venit. Se schimbă doar prin cazurile din art. 24 alin. (1) | [ADR-039](../decisions/039-valuta-si-perioade.md) §6 |
| **IDNO-ul companiei** | Cheie naturală de business; apare pe documente emise, deci pe artefacte care au ieșit din sistem | 1.2 |

**Regula de prezentare:** o alegere din tabelul de mai sus nu se afișează ca un câmp printre altele.
Are ecran propriu, spune ce se întâmplă dacă e greșită, și cere o confirmare separată. Un dropdown
care schimbă permanent conținutul unui registru contabil este un defect de produs, nu o economie de
click-uri.

### 12.2 Ordinea, și de ce este exact aceasta

```
1. utilizatorul                    →  identitate globală, fără tenant (1.5)
2. al doilea factor                →  obligatoriu, înainte de orice sesiune (ADR-021)
3. tenantul                        →  P-9: subdomeniu + membership de administrare
4. compania                        →  P-9: IDNO, denumire legală, exercițiu fiscal
5. capabilitățile                  →  activări cu dată efectivă (R25), nu bifе
6. planul de conturi               →  instanțiere din șablonul versionat
7. prima perioadă                  →  ALEGERE IREVERSIBILĂ
8. soldurile inițiale              →  opening.balance.posted
```

Trei lucruri din ordinea asta sunt constrângeri, nu preferințe:

- **(2) precede (3).** `ADR-021` face al doilea factor obligatoriu pentru toți, iar `ADR-026` arată
  că autentificarea precede contextul. Un tenant creat de un utilizator neînrolat ar fi un tenant cu
  un administrator care nu se poate autentifica. *Aici se lovește de `OD-48`: înrolarea MFA n-are
  încă o cale de request. Onboarding-ul este primul consumator real al acelei decizii.*
- **(6) precede (7).** Soldurile inițiale se postează pe conturi; conturile trebuie să existe.
- **(7) precede (8), și amândouă preced orice altceva.** Nu există „începem să lucrăm și punem
  soldurile mai târziu": o postare într-o perioadă anterioară soldurilor inițiale face ca soldurile
  să nu mai fie inițiale.

### 12.3 Cele trei căi de intrare

| Cale | Cine apelează `P-9` | Ce diferă |
|---|---|---|
| **Autoservire** | Viitorul administrator al tenantului | Creatorul devine membru cu rol de administrare; facturarea merge pe grila directă (10.1) |
| **Firmă care aduce un client** | Un membru al unei firme `active`, adică verificate ([ADR-080](../decisions/080-tipul-nu-se-stocheaza.md) §4.1) | Tenantul se creează cu `claimed_at` nul și cu engagement `active` pe **mandat declarat** — `acceptance_basis`, `mandate_ref`, `claim_contact_email` ([ADR-081](../decisions/081-revendicarea-optionala.md) §3.3). Revendicarea rămâne posibilă permanent, prin `P-11`, dar nu e obligatorie |
| **Migrare din alt sistem** | Ca autoservirea, plus importul | Soldurile inițiale vin din `import.*` ([ADR-038](../decisions/038-vocabularul-de-evenimente.md) §7.3): suma din sursă e autoritativă, nu recalculată |

A doua cale este cea care merită atenție. Un tenant creat de o firmă rămâne **al clientului** —
`INV-7`, datele n-au fost niciodată ale firmei. Iar clientul poate să nu revendice niciodată: e cazul
normal, nu unul marginal. Formularea ascuțită a problemei: **dreptul de revocare din `INV-7` aparține
unui proprietar care nu există ca persoană.** Răspunsul nu e să forțezi persoana să apară, ci să
ancorezi dreptul în IDNO și să garantezi calea către el —
[ADR-081](../decisions/081-revendicarea-optionala.md).

> **`DN-26` — DECISĂ 2026-08-31**, prin
> [ADR-078](../decisions/078-cine-poate-crea-un-tenant.md): **două canale**, autoservire și creare
> de către firmă, corespunzând exact celor două canale de facturare din 10.1. Invitația nu e un al
> treilea canal — lansarea controlată se face cu feature flag și ring (13.5, `R23`), ca poarta să
> nu devină entitate. Anti-abuzul e în cea mai mare parte deja acolo, în ordinea din 12.2: e-mail
> verificat, al doilea factor înrolat, abia apoi `P-9`; se adaugă limitare de rată și verificarea
> numelor rezervate în funcție, nu în formular. IDNO-ul se **declară** la creare și nu se verifică
> încă (`OD-116`); `DN-03` rămâne deschisă.

> **`DN-27` — DECISĂ 2026-08-31**, prin
> [ADR-081](../decisions/081-revendicarea-optionala.md), care **înlocuiește
> [ADR-079](../decisions/079-tenantul-nerevendicat.md)**, scris și retras în aceeași zi.
> **Revendicarea e opțională; calea de revendicare nu.** Tenantul nerevendicat nu e o anomalie care
> expiră — e o stare normală, permanentă și plătită. Dreptul clientului e **dormant, nu absent**:
> ancorat în IDNO (`ADR-075`), exercitabil oricând prin `P-11` (6.2). Linia care contează, fiindcă
> poate fi trasată greșit fără să se observe: **ținerea contabilității nu cere un proprietar
> revendicat; dispoziția asupra datelor, da** — postările și depunerile merg, exportul complet,
> transferul, arhivarea și schimbarea IDNO-ului nu. Mandatul e **declarat de firmă, neverificat de
> platformă**, iar `acceptance_basis` îl face vizibil pe fiecare rând, deci enumerabil. Plătitorul e
> o atribuire cu dată și se poate muta între firmă și client, dar niciodată unilateral (10.4).
> `DN-21` și `DN-25` devin **condiții de lansare**, nu decizii de F3: modelul produce scenariul de
> neplată pe cazul normal. Standardul de probă la revendicare e juridic și rămâne `OD-118`.
>
> *Formularea originală a lui `DN-27`, păstrată: „un tenant creat de o firmă și niciodată acceptat de
> client — se șterge, expiră, sau rămâne? Ștergerea fizică nu există în această specificație (1),
> deci întrebarea reală e ce `status` primește și după cât timp." Întrebarea era greșită, nu doar
> răspunsul: presupunea că acceptarea e obligatorie.*

### 12.4 Ce nu face onboarding-ul

- **Nu creează utilizatori pentru alții.** Un administrator invită; invitatul își face parola și al
  doilea factor. Altfel platforma ar cunoaște, măcar o clipă, credențialele cuiva.
- **Nu presupune că un tenant are o singură companie.** Modelul le separă de la început (1.2), iar
  onboarding-ul creează prima, nu singura.
- **Nu activează capabilități de conformitate ca opțiune.** `R24`: TVA, e-Factura și raportarea SNC
  funcționează indiferent de plan. Ecranul de capabilități nu le afișează ca bife.

---

## 13. Lansare, release rings și ferestrele de îngheț

Nici această secțiune nu exista, iar absența ei a fost vizibilă: o propunere de decizie a citat
„fereastra de îngheț propusă în Spec A" ca pe un lucru deja scris. Nu era. Se scrie aici.

### 13.1 Constrângerea, care nu e a produsului

Codul fiscal, art. 115: declarația TVA se depune și taxa se plătește **până la data de 25** a lunii
următoare celei în care s-a încheiat perioada fiscală. Perioada fiscală e luna, pentru toți, fără
variantă trimestrială (art. 114 alin. (1)).

Consecința operațională: **între 1 și 25 ale fiecărei luni, fiecare contabil din baza de clienți
lucrează la același termen, simultan.** Nu e un vârf de trafic, e un vârf de consecință — o schimbare
de interfață care încetinește introducerea cu treizeci de secunde per document se înmulțește cu tot
volumul unei luni și cu presiunea unui termen legal.

Un produs contabil nu are utilizatori distribuiți uniform în timp. Are un calendar, și calendarul e
al statului.

### 13.2 Fereastra de îngheț

**Între 1 și 25 ale lunii nu se livrează schimbări de interfață și nu se schimbă comportamentul de
introducere.**

Ce rămâne livrabil oricând, fără excepție:

| Categorie | De ce nu e îngheț |
|---|---|
| Corecturi de defecte | Un defect în perioada de raportare e mai scump decât orice schimbare |
| Schimbări legislative | `R15`–`R18`: parametrii sunt date, iar o cotă nouă intră prin `INSERT`, nu prin deploy. Când cere totuși cod, termenul legal bate fereastra |
| Securitate | Fără discuție |
| Performanță, fără schimbare vizuală | Ajută exact în fereastră |

Ce se amână la după 25: redesign, mutarea comenzilor, câmpuri noi în ecrane de introducere,
schimbări de ordine de tabulare sau de comportament al tastaturii (`OD-36`).

**Distincția care face regula aplicabilă:** îngheață *ce vede și ce atinge contabilul*, nu *ce
livrăm*. Un backend refăcut integral, cu aceeași interfață, nu încalcă fereastra.

### 13.3 Cum se impune — prin release rings, nu prin disciplină

`R23` interzice ramuri sau versiuni per tenant; diferențierea se face prin feature flags și release
rings (10.5). Fereastra de îngheț folosește același mecanism:

- o schimbare de interfață se livrează **în cod** oricând, dezactivată prin flag;
- activarea trece prin inele, iar inelele au calendar: nimic nu ajunge în inelul general între 1 și
  25;
- un tenant poate cere explicit inelul devreme — un cabinet care vrea funcționalitatea nouă și
  acceptă riscul.

Consecință: fereastra **nu blochează dezvoltarea**. Blochează activarea. Diferența e ce face regula
sustenabilă — o echipă care nu poate livra trei săptămâni din patru va găsi motive să facă excepții,
iar excepțiile golesc regula.

### 13.4 Prima lansare

Prima companie reală nu intră în producție într-o fereastră de îngheț. Nu din superstiție: o
instalare nouă produce în primele săptămâni defecte care cer corecturi rapide, iar suprapunerea peste
un termen legal pune produsul și clientul în conflict direct la primul contact.

> **`DECIZIE NECESARĂ (DN-28)` — granițele exacte și cine acordă excepții.** Ziua 25 e din lege, dar
> restul e politică: fereastra începe pe 1 sau la închiderea lunii precedente? Se aplică inelului de
> early adopters? Cine aprobă o excepție și pe ce criteriu? Întrebările par mici și nu sunt: o
> fereastră fără un proces de excepție scris devine, la a treia urgență, o fereastră care nu există.

### 13.5 Ce nu decide această secțiune

Cadența de release, procesul de deploy, mediile și strategia de rollback. Sunt decizii de
infrastructură, iar `F0.0.3` le-a lăsat explicit deschise: imaginile de container sunt scrise și
niciodată rulate, fiindcă docker nu e instalat pe mașina de dezvoltare.

---

## 14. Consola platformei

Sursa: [ADR-076](../decisions/076-planul-de-control-al-platformei.md) (decizia),
[ADR-091](../decisions/091-consola-scrie-referinta-din-procesul-web.md) (mecanismul scrierii). Aici
stă doar ce e normativ pentru schemă și pentru calea cererii; argumentele sunt în ADR-uri.

**Principiul.** Administratorul de platformă administrează platforma, nu datele. Testul de
proiectare: dacă o pagină a consolei afișează o balanță, un jurnal, un salariu sau o factură a unui
client, `DN-18` a fost închisă din greșeală — de un ecran, nu de un ADR.

**Gazda.** `admin.` — pe lista rezervată din §1.1, nealocabilă unui tenant. Pe ea nu există subdomeniu
de tenant, deci nu există context de tenant (C8, R4): sub un context de consolă orice politică de
tenant ridică eroare, fiindcă `app.current_tenant_id()` e fail-closed — măsurat în
`tests/isolation/test_console.py`. Măsurătoarea a găsit și condiția ei: `SET LOCAL` supraviețuiește
savepoint-ului, deci un context deschis după altul în aceeași tranzacție moștenea cheile nesetate;
`_apply` le **golește** acum, nu le sare. Gazda servește **doar** `/api/v1/auth/` și `/api/v1/platform/`
(`CONSOLE_PATH_PREFIXES`); orice altă cale primește `404 console.not_found`, cu sau fără sesiune.

**Sesiunea.** Emisă pe `admin.` cu `tenant_id` și `actor_firm_id` nule, doar unei persoane cu rând viu
în `platform_staff`; altfel `401 auth.no_access_to_console`, **după** ce parola și al doilea factor au
fost acceptate. O sesiune de consolă e refuzată pe orice gazdă de tenant și reciproc
(`auth.session_tenant_mismatch`). Aceeași persoană, două sesiuni, niciun meniu între ele.

**`platform_staff`.** Tabelă globală la nivelul lui `user`, declarată în `infra/rls/exceptions.toml`
(`self_row`, `writer_role = "evidenta_refdata"`, fără DELETE): `user_id` (PK), `staff_role` în
(`support`, `operator`, `admin`), `granted_by_user_id`, `granted_at`, `revoked_at`. Un rând aici nu
apare în niciun predicat de acces și nu deschide nicio politică. Primul rând se scrie din
`grant_platform_staff`, sub rolul de instalare (ca `create_tenant`); acordarea din consolă e `OD-133`.

**Cine apelează ce.** `operator` — `P-3`, `P-4`, `P-5`, `P-10`; `support` — cererea grantului din
`P-7` (ADR-077); `admin` — `P-12`, `platform_staff`. Orice angajat viu citește paginile. Verificat în
cod la fiecare ușă (`platform/api/permissions.py`), nu doar afirmat; catalogul acțiunilor rămâne
`OD-113`.

**Funcțiile de citire ale consolei** ([ADR-092](../decisions/092-consola-citeste-metadate-si-administreaza-personalul.md),
`infra/migrations/0076`). Paginile consolei sunt interogări cross-tenant prin definiție, iar `R7` le
permite doar în read models și în căile enumerate aici. Enumerare **limitativă**, ținută și în
`tests/schema_guard/test_function_privileges.py`: `rls.console_tenants()`, `rls.console_staff()`,
`rls.console_user_by_email(text)`, `rls.console_privileged_log(text, text, integer)`,
`rls.console_capabilities()`, `rls.console_release_rings()`, `rls.console_flag_overrides()`. Toate
încep cu paznicul intern `rls.console_caller_role()`, care refuză când există context de tenant și
refuză un apelant fără rând viu în `platform_staff`, și toate întorc doar coloanele din ADR-076 §4.3.
Nu lasă rând în `privileged_access_log`: sunt citiri de metadate ale platformei, aceeași clasă ca
`rls.resolve_tenant_by_subdomain` și `rls.auth_*`.

**Paginile** (ADR-076 §4.3) și starea lor la 2026-09-03. **Construite:** Spații (rândul din `tenant`,
cu numărul de companii și de membri; fără creare, suspendare sau arhivare — vezi ADR-092 §4),
Capabilități (doar citire), Ringuri și flaguri (doar citire; nimic din produs nu scrie încă o
atribuire), Angajații platformei (citire pentru toți, acordare și retragere prin `P-12` pentru
`admin`), Parametri fiscali (versiune nouă datată și activare prin `P-4`, ADR-091), Planuri de
conturi (doar citire; încărcarea e `P-10` din fișier), Jurnalul căilor privilegiate (filtrabil pe cale
și pe spațiu). **Neconstruite, cu motivul:** Abonamente și planuri (modulul de facturare nu există),
Granturi de suport (ADR-077 acceptat, neconstruit), Incidente (nu există stare de joburi de citit).
Nedesenate în interfață până când au server; interfața spune de ce. Ce nu apare niciodată: registre,
documente, solduri, salarii, declarații, atașamente, denumiri de parteneri, sume.

## 15. Ce urmează după această specificație

1. **Review uman**, cu atenție la punctele rămase din secțiunea 11. Cele trei care blocau sarcini
   F0 — DN-11, DN-12, DN-22 — sunt închise prin ADR-003, ADR-004 și ADR-008.
2. **ADR pentru fiecare decizie luată**, conform `docs/decisions/README.md`.
3. ~~Actualizarea listei de excepții (5.4) după DN-12~~ — făcută: lista trăiește în
   `infra/rls/exceptions.toml`.
4. **Spec B** este scrisă; șablonul company-scoped din ADR-004 se aplică tuturor tabelelor ei.
