# Spec B — Accounting Core

- **Status:** draft. **Necesită review uman și validare contabilă înainte de a fi considerat valid.**
- **Data:** 2026-08-24
- **Derivă din:** `_input/evidenta-master-plan-v2.md`, `_input/evidenta-master-plan-v2-amendament-1.md`
  (prevalează), `_input/evidenta-implementation-spec.md`
- **Blochează:** F1.1–F1.8. Parțial și F0.8 (structura parametrilor fiscali) și F0.9 (modelul de
  sumă multi-valută), care sunt sarcini F0.

## Cum se citește

Textul normal este specificație. Blocurile **`DECIZIE NECESARĂ (DNB-nn)`** sunt puncte unde
documentele de intrare nu dau suficient; conțin opțiunile identificate și implicațiile fiecăreia și
**nu au fost alese aici**. Lista completă: secțiunea 11.

**Nicio valoare fiscală și niciun cod de cont din planul SNC nu apare în acest document.** Unde ar
fi nevoie de unul, textul folosește un substituent de forma `<cont de creanțe comerciale>`.
Legislația fiscală și planul de conturi nu se deduc din memorie — vezi OD-22 și OD-23 în
`../decisions/000-open-decisions.md`.

Dependența de Spec A: politicile RLS ale tuturor tabelelor de aici sunt cele company-scoped din
Spec A §2.6, iar forma lor depinde de `DN-11`.

---

## 1. Structura ledgerului

```
Business Module
      │  emite
      ▼
AccountingEvent ──► Posting Engine ──► JournalEntry ──► JournalLine*
      │                                      │
      └──── Source Document ◄────────────────┘   (lineage, INV-9)
```

Trei niveluri, trei responsabilități:

- **`AccountingEvent`** — ce s-a întâmplat economic, în termenii modulului sursă. Idempotent.
  Nu conține conturi.
- **`JournalEntry`** — ce s-a înregistrat contabil. Imutabil după postare.
- **`JournalLine`** — liniile, cu conturi, sume, valută și dimensiuni analitice.

Regula care structurează totul: **niciun modul business nu scrie în ledger** (R9). Modulele scriu
evenimente. Doar Posting Engine scrie înregistrări.

### 1.1 `accounting_event`

Nivel companie. Nu este tabelă append-only de volum mare în sensul R21 — poate primi chei străine.

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | uuid | PK | |
| `tenant_id` | uuid | NOT NULL | context RLS |
| `company_id` | uuid | NOT NULL | |
| `event_type` | text | NOT NULL | taxonomie — vezi 1.4 |
| `event_version` | smallint | NOT NULL, DEFAULT 1 | versiunea structurii `payload` |
| `source_module` | text | NOT NULL | `sales`, `purchases`, `payroll`, `banking`, `assets`, `migration`, `manual` |
| `source_document_type` | text | NOT NULL | tipul documentului sursă |
| `source_document_id` | uuid | NOT NULL | **fără cheie străină** — vezi nota de mai jos |
| `occurred_at` | timestamptz | NOT NULL | momentul economic |
| `accounting_date` | date | NOT NULL | **data care determină perioada, parametrii fiscali și versiunea de logică** |
| `idempotency_key` | text | NOT NULL | vezi 10 |
| `payload` | jsonb | NOT NULL | datele necesare postării, în termenii modulului sursă |
| `capability_snapshot` | jsonb | NOT NULL | capabilitățile active la rezoluție (R26) |
| `status` | text | NOT NULL, CHECK în `('pending','posted','failed','superseded')` | |
| `posted_at` | timestamptz | NULL | |
| `posting_error` | jsonb | NULL | cod stabil + detalii, la eșec |
| `actor_user_id` | uuid | NOT NULL | uman sau de sistem (Spec A §3.4) |
| `request_id` | text | NOT NULL | corelator pentru enumerarea efectelor (Spec A §9.3) |
| `created_at` | timestamptz | NOT NULL | |

Constrângeri și indici:

- `UNIQUE (company_id, idempotency_key)` — inima idempotenței (R19)
- `(tenant_id, company_id, accounting_date)` — rezoluție și rapoarte
- `(company_id, actor_user_id, occurred_at)` — enumerarea efectelor (Spec A §9.3)
- `(company_id, status) WHERE status IN ('pending','failed')` — coada de repostare
- `(source_document_type, source_document_id)` — navigarea inversă document → efecte

> **De ce `source_document_id` nu are cheie străină.** Documentul sursă trăiește în modulul care
> l-a produs — `sales`, `purchases`, `payroll`. O cheie străină ar obliga `accounting` să cunoască
> schema acelor module, ceea ce încalcă D2 (contabilitatea nu cunoaște sursa). Integritatea se
> asigură în serviciu, la emiterea evenimentului, iar existența documentului se verifică prin
> serviciul public al modulului sursă, nu prin `JOIN`.

### 1.2 `journal_entry`

Nivel companie. Imutabil după postare (R10).

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | uuid | PK | expus extern (C6) |
| `tenant_id` | uuid | NOT NULL | |
| `company_id` | uuid | NOT NULL | |
| `entry_number` | text | NOT NULL | numerotare per companie, tip și an |
| `accounting_date` | date | NOT NULL | |
| `period_id` | uuid | NOT NULL, REFERENCES `period` | |
| `entry_type` | text | NOT NULL, CHECK în `('standard','reversal','opening','closing','adjustment')` | |
| `accounting_event_id` | uuid | NOT NULL, REFERENCES `accounting_event` | inclusiv pentru notele manuale — vezi 1.5 |
| `reverses_entry_id` | uuid | NULL, REFERENCES `journal_entry` | a doua legătură a stornoului (R14) |
| `corrects_period_id` | uuid | NULL, REFERENCES `period` | perioada **la care se referă** corecția, când diferă de cea în care se postează — [ADR-006](../decisions/006-reversal-two-dates.md) |
| `status` | text | NOT NULL, CHECK în `('draft','posted')` | |
| `posted_at` | timestamptz | NULL | |
| `posted_by_user_id` | uuid | NULL | |
| `description` | text | NOT NULL | |
| `total_debit` | numeric(20,4) | NOT NULL, DEFAULT 0 | denormalizat, vezi 1.6 |
| `total_credit` | numeric(20,4) | NOT NULL, DEFAULT 0 | idem |
| `request_id` | text | NOT NULL | |
| `created_at`, `updated_at` | timestamptz | NOT NULL | |

Constrângeri:

- `CHECK (total_debit = total_credit)` — echilibrul, materializat (1.6)
- `CHECK (status <> 'posted' OR posted_at IS NOT NULL)`
- `CHECK (entry_type <> 'reversal' OR reverses_entry_id IS NOT NULL)`
- `CHECK (corrects_period_id IS NULL OR entry_type IN ('reversal','adjustment'))`
- `UNIQUE (company_id, entry_number)`

Indici: `(tenant_id, company_id, accounting_date)`; `(company_id, period_id)`;
`(accounting_event_id)`; `(reverses_entry_id) WHERE reverses_entry_id IS NOT NULL`;
`(company_id, corrects_period_id) WHERE corrects_period_id IS NOT NULL` — interogarea din care se
generează declarația rectificativă.

> **Două date, nu una.** `accounting_date` spune *unde se postează*; `corrects_period_id` spune *la
> ce perioadă se referă*. Pentru o înregistrare obișnuită coincid și al doilea câmp e `NULL`. Pentru
> o corecție a unei perioade închise sunt diferite — iar fără distincție declarația rectificativă nu
> se poate genera, pentru că nu se știe ce raportare a fost afectată.

**Imutabilitate — trei bariere:**

1. Serviciul refuză orice modificare a unei înregistrări `posted`.
2. Un trigger `BEFORE UPDATE OR DELETE` refuză la nivel de bază de date când `status = 'posted'`,
   cu excepția tranziției `draft → posted` însăși.
3. `REVOKE UPDATE, DELETE ON journal_entry, journal_line FROM evidenta_app` — cu observația că
   tranziția la `posted` trebuie atunci să treacă printr-o funcție `SECURITY DEFINER` îngustă.

Primele două sunt obligatorii. A treia este recomandată și se decide la implementare, pentru că
schimbă modul în care Django scrie.

### 1.3 `journal_line`

Nivel companie. **Tabelă append-only de volum mare** (R21, R22): nicio cheie străină nu arată spre
ea, coloana de partiționare este `NOT NULL`, cheia primară este `bigint` (C6).

| Câmp | Tip | Constrângeri | Note |
|---|---|---|---|
| `id` | bigint | PK, generat de identitate | |
| `tenant_id` | uuid | NOT NULL | |
| `company_id` | uuid | NOT NULL | |
| `accounting_date` | date | **NOT NULL** | coloana naturală de partiționare (R22) |
| `journal_entry_id` | uuid | NOT NULL | referință *ieșitoare*, permisă |
| `line_number` | smallint | NOT NULL | |
| `account_id` | uuid | NOT NULL | contul din instanța companiei (2.4) |
| `debit` | numeric(20,4) | NOT NULL, DEFAULT 0, CHECK `>= 0` | |
| `credit` | numeric(20,4) | NOT NULL, DEFAULT 0, CHECK `>= 0` | |
| `currency` | char(3) | NOT NULL | |
| `amount_currency` | numeric(20,4) | NOT NULL | suma în valuta tranzacției |
| `exchange_rate` | numeric(18,8) | NOT NULL | 1 pentru moneda funcțională |
| `quantity` | numeric(20,6) | NULL | pentru conturile cu urmărire cantitativă |
| `uom_id` | uuid | NULL | |
| `description` | text | NULL | |
| dimensiuni analitice | vezi 1.7 | | |

Constrângeri:

- `CHECK ((debit = 0) <> (credit = 0))` — o linie are exact una dintre ele nenulă. O linie cu ambele
  zero este zgomot; una cu ambele nenule este o eroare de modelare mascată
- `CHECK (currency = <moneda funcțională> OR exchange_rate > 0)`
- `CHECK ((quantity IS NULL) OR (uom_id IS NOT NULL))`

Indici obligatorii (fiecare începe cu contextul — regula din amendament §B.3):

```
(tenant_id, company_id, accounting_date)
(company_id, account_id, accounting_date)
(company_id, partner_id, accounting_date)      -- unde partner_id NOT NULL
(journal_entry_id)                             -- navigarea inversă, INV-9
```

> **Debit/credit ca două coloane, nu sumă cu semn.** Alternativa (o coloană `amount` semnată) e mai
> compactă și simplifică agregarea, dar pierde distincția între „linie de credit de 100" și „linie
> de debit de −100", care în practică apar amândouă și înseamnă lucruri diferite în rapoartele de
> rulaj. Balanța de verificare cere rulaj debitor și rulaj creditor separat; cu sumă semnată,
> distincția trebuie reconstruită din context. Costul: două coloane și o constrângere.

> **Fără chei străine ieșitoare către dimensiuni și cont.** `account_id`, `partner_id` și celelalte
> referințe nu au constrângeri `REFERENCES`. Motivul nu este partiționarea (cheile ieșitoare nu o
> împiedică), ci costul: fiecare `INSERT` într-o tabelă cu zece chei străine face zece verificări,
> iar postarea în masă și importul 1C sunt exact scenariile de volum. Validarea se face la rezoluția
> regulii de postare, unde conturile și dimensiunile sunt oricum încărcate. **Consecință acceptată:**
> o linie poate referi un cont șters — de aceea conturile nu se șterg niciodată, ci se dezactivează
> (2.5).

### 1.4 Taxonomia de evenimente

`event_type` este un vocabular închis, versionat împreună cu regulile de postare. Forma:
`<domeniu>.<acțiune>` — de exemplu `sales.invoice_issued`, `purchases.invoice_received`,
`banking.payment_received`, `payroll.run_approved`, `assets.depreciation_calculated`.

**`DECIZIE NECESARĂ (DNB-01)` — cine deține vocabularul.**
(A) Fiecare modul își declară tipurile, iar `accounting` le acceptă pe toate — cuplaj minim, dar
nimic nu împiedică două module să emită tipuri care se suprapun.
(B) Vocabularul e central, în `accounting/events`, iar modulele aleg dintre tipurile existente —
disciplină mai bună, dar fiecare modul nou cere o modificare în `accounting`, ceea ce se apropie
periculos de dependența interzisă de D2.
(C) Vocabular central pentru tipurile cu efect contabil, liber pentru restul.

### 1.5 Notele contabile manuale

Chiar și o notă manuală trece prin `accounting_event` (R9). Tipul este `manual.journal_entry`, iar
`payload` conține liniile propuse de utilizator. Posting Engine le validează (echilibru, conturi
existente și active, perioadă deschisă, dimensiuni obligatorii) și le postează.

Motivul pentru care nu se scrie direct în `journal_entry`: altfel apar două căi către ledger, iar
lineage-ul, idempotența și enumerarea efectelor trebuie implementate de două ori. A doua
implementare este întotdeauna cea care se strică.

### 1.6 Echilibrul verificat în bază

R11 cere ca `Σ Debit = Σ Credit` să fie verificat la nivel de bază de date. `CHECK` pe agregatul
liniilor nu există în PostgreSQL. Mecanismul specificat:

1. `journal_entry.total_debit` și `total_credit`, întreținute de un trigger pe `journal_line`
   (`AFTER INSERT OR UPDATE OR DELETE`).
2. `CONSTRAINT TRIGGER ... DEFERRABLE INITIALLY DEFERRED` pe `journal_entry`, care la commit
   verifică `total_debit = total_credit AND total_debit > 0`.

Amânarea la commit este necesară: liniile se inserează una câte una, iar între prima și ultima
înregistrarea este dezechilibrată prin construcție.

Alternativa — verificare doar în serviciu — se respinge explicit: importul în masă, migrarea 1C și
orice `INSERT` direct într-o migrare de date ocolesc serviciul, și exact acolo apar dezechilibrele.

**Cost cunoscut:** triggerul se execută pentru fiecare linie. La importul 1C, cu sute de mii de
linii, aceasta este cea mai scumpă operațiune din proces. Mitigarea (dezactivarea triggerului în
import, cu revalidare în bloc la final) este o cale privilegiată în sensul Spec A §6 și se tratează
ca atare — nu ca o optimizare locală.

### 1.7 Dimensiunile analitice

Proiectate pe linia de jurnal din prima zi, chiar dacă interfața le expune mai târziu (V2 §7.2).
Coloane pe `journal_line`, toate `uuid NULL`:

| Coloană | Dimensiune | Implementare funcțională |
|---|---|---|
| `partner_id` | Partener | F1 |
| `item_id` | Articol | F4 |
| `employee_id` | Angajat | F2 |
| `contract_id` | Contract | F5 |
| `warehouse_id` | Depozit | F4 |
| `project_id` | Proiect | direcție |
| `department_id` | Departament | F5 |
| `cost_center_id` | Centru de cost | F5 |
| `asset_id` | Activ | F2 |
| `production_order_id` | Comandă de producție | direcție |

Regulile de obligativitate stau pe cont, nu pe linie: `company_account.required_dimensions` (2.4).
Postarea într-un cont care cere dimensiunea `partner` fără `partner_id` este refuzată de motor.

> **De ce coloane și nu o tabelă de dimensiuni.** V2 §7.2 spune „pe linia de jurnal". Coloanele fac
> indexarea directă (`(company_id, partner_id, accounting_date)` este indexul care produce fișa
> partenerului) și evită un `JOIN` pe cea mai mare tabelă din sistem. Prețul: zece coloane
> majoritar `NULL` și o listă închisă.

**`DNB-02` — ÎNCHISĂ prin [ADR-029](../decisions/029-dimensiuni-analitice.md), varianta (C).**

Lista de mai sus rămâne închisă, și i se adaugă **cinci sloturi generice**: `dim_1_id` … `dim_5_id`,
`uuid NULL`, cu semnificația configurată per companie într-o tabelă `company_dimension`
(`(company_id, slot)` → nume, sursa valorilor permise).

Trei lucruri fac varianta să funcționeze, și fiecare răspunde unei obiecții:

- **obligativitatea se impune la fel ca la restul** — `company_account.required_dimensions` (2.4)
  numește un slot ca pe orice altă dimensiune, iar motorul refuză postarea fără el. Este exact ce
  varianta `jsonb` nu putea oferi;
- **indexarea rămâne B-tree obișnuit** — `(company_id, dim_1_id, accounting_date)`, ca la partener,
  fără `GIN` pe cea mai mare tabelă din sistem;
- **obiecția „rapoarte ilizibile fără metadate" cade**, fiindcă tabela de metadate nu e un cost
  adăugat: interfața are nevoie de ea oricum, pentru etichetă și pentru lista de valori.

Limita de cinci este deliberată și vizibilă. Al șaselea client care cere o axă proprie cere o
migrare; alternativa fără limită era cea fără obligativitate.

`company_dimension` **nu se construiește în F0.** Se creează la `F1.2`, odată cu `journal_line`.
Motivul pentru care forma se fixează totuși acum: `journal_line` este tabelă append-only de volum
mare (`R21`), iar adăugarea unei coloane pe ea, mai târziu, nu mai e migrare ieftină.

---

## 2. Planul de conturi SNC

### 2.1 Structura pe două niveluri

```
coa_template          (global, versionat, cu sursă legislativă)
   └── coa_template_account
              │  instanțiere la crearea companiei
              ▼
company_chart         (per companie: ce versiune s-a instanțiat, când)
   └── company_account (conturi de sistem + subconturi proprii)
```

Planul este **date versionate**, nu un fixture copiat o dată (V2 §7.1). Întrebarea la care modelul
trebuie să răspundă: ce se întâmplă cu companiile care au instanțiat versiunea veche când
legislația modifică un cont.

### 2.2 `coa_template` și `coa_template_account` (globale)

`coa_template`: `id`, `code`, `version`, `valid_from`, `valid_to`, `source_act`,
`source_reference` (număr Monitorul Oficial, dată publicare), `status` (`draft`, `published`,
`superseded`).
`UNIQUE (code, version)`; neîntrepătrundere pe `(code, daterange(valid_from, valid_to))` pentru
versiunile `published`.

`coa_template_account`:

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `template_id` | uuid | NOT NULL |
| `account_code` | text | NOT NULL |
| `parent_code` | text | NULL |
| `name_ro` | text | NOT NULL |
| `account_class` | text | NOT NULL — `asset`, `liability`, `equity`, `income`, `expense` |
| `normal_balance` | text | NOT NULL — `debit` / `credit` |
| `is_system` | boolean | NOT NULL, DEFAULT true |
| `allows_subaccounts` | boolean | NOT NULL |
| `currency_tracking` | boolean | NOT NULL, DEFAULT false |
| `quantity_tracking` | boolean | NOT NULL, DEFAULT false |
| `required_dimensions` | text[] | NOT NULL, DEFAULT `'{}'` |
| `valid_from`, `valid_to` | date | valabilitatea contului în interiorul versiunii |

`UNIQUE (template_id, account_code)`.

**Conținutul efectiv al planului nu este în această specificație** — vezi OD-23. Structura de mai
sus este suficientă pentru a-l încărca atunci când există dintr-o sursă citabilă.

> **`name_ro` este valoare unică, în română.** Nu formă provizorie: contabilitatea se ține în limba
> română prin lege — nr. 287/2017, art. 7 alin. (1). O denumire de cont în altă limbă într-un
> registru ar produce un artefact neconform. Dacă vreodată se dorește o etichetă de afișare în rusă,
> ea este resursă de interfață cheiată pe codul contului, niciodată valoare stocată per companie —
> vezi [ADR-016](../decisions/016-limba-contabilitatii.md).

### 2.3 `company_chart` și `company_account`

`company_chart`: `id`, `tenant_id`, `company_id` (UNIQUE), `template_id`, `template_version`,
`instantiated_at`, `last_propagation_at`.

`company_account`:

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id`, `company_id` | uuid | NOT NULL |
| `account_code` | text | NOT NULL |
| `parent_id` | uuid | NULL, REFERENCES `company_account` |
| `origin` | text | NOT NULL, CHECK în `('system','company')` |
| `template_account_id` | uuid | NULL — NOT NULL când `origin='system'` |
| `name_ro` | text | NOT NULL |
| `account_class`, `normal_balance` | text | NOT NULL |
| `currency_tracking`, `quantity_tracking` | boolean | NOT NULL |
| `required_dimensions` | text[] | NOT NULL |
| `is_blocked` | boolean | NOT NULL, DEFAULT false — blocat la postare, vizibil în rapoarte |
| `valid_from` | date | NOT NULL |
| `valid_to` | date | NULL |

`UNIQUE (company_id, account_code)`. Indici: `(company_id, valid_from, valid_to)`;
`(company_id, is_blocked)`.

### 2.4 Conturi de sistem vs. subconturi

| | Cont de sistem | Subcont al companiei |
|---|---|---|
| Creat de | instanțierea template-ului | utilizator |
| Cod | din template | sub un cont care permite subconturi |
| Redenumire | nu | da |
| Ștergere | **niciodată** | **niciodată** — doar `valid_to` sau `is_blocked` |
| Actualizare la modificare legislativă | central, prin propagare | nu |

**Nimic nu se șterge.** O linie de jurnal poate referi contul (fără cheie străină, 1.3), iar
ledgerul este append-only: un cont dispărut face imposibilă citirea istoricului. Închiderea unui
cont este `valid_to`; interzicerea postării este `is_blocked`.

### 2.5 Propagarea modificărilor legislative

**`DECIZIE NECESARĂ (DNB-03)` — politica de propagare.** *(= OD-03 din registrul deciziilor.)*

Scenariul: o versiune nouă de template apare cu dată efectivă. Mii de companii au instanțiat
versiunea precedentă. Unele au subconturi sub conturile modificate. Unele au deja postări pe ele.

- **Opțiunea A — propagare automată la data efectivă.** Toate companiile primesc modificarea în
  aceeași zi. Conform cu R24 (conformitatea nu e opțională). Riscul: un cont redenumit sau
  reclasificat schimbă rapoartele istorice fără ca cineva să fi apăsat ceva. Cere ca fiecare
  modificare de template să fie ne-distructivă prin construcție.
- **Opțiunea B — propagare cu confirmare per companie.** Modificarea apare ca sarcină în interfața
  contabilului, cu previzualizarea efectelor. Sigur pentru client, dar produce un parc de companii
  pe versiuni diferite — exact ce vrea să evite un plan versionat, și o problemă pentru raportarea
  statutară care presupune un plan comun.
- **Opțiunea C — automat pentru conturile de sistem, confirmare pentru cele care ating subconturi
  ale companiei.** Acoperă cazul frecvent automat și izolează cazul dificil. Cost: două căi de cod
  și o regulă de detecție a „atingerii".
- **Opțiunea D — fără propagare; versiunea instanțiată e înghețată.** Cel mai simplu, incompatibil
  cu conformitatea ca obligație.

Ce trebuie decis în plus, în orice variantă:

1. Ce se întâmplă cu un cont de sistem care **dispare** din versiunea nouă și are postări. `valid_to`
   la data efectivă și interzicerea postării, probabil — dar soldul lui trebuie mutat undeva, iar
   aceea este o operațiune contabilă cu eveniment propriu, nu o modificare de schemă.
2. Ce se întâmplă cu un cont **reclasificat** (activ → pasiv): situațiile financiare istorice se
   întocmesc cu clasificarea de atunci sau cu cea nouă? R18 spune „cu cea de atunci", ceea ce
   implică versionarea clasificării pe cont, cu dată efectivă — și asta trebuie să existe în schemă
   de la început.

Punctul 2 este consecința cea mai scumpă a acestei decizii și motivul pentru care `valid_from` /
`valid_to` stau pe `company_account`, nu doar pe template.

---

## 3. Posting Engine

### 3.1 Fluxul

```
AccountingEvent
      │
      ├─► selectarea regulilor candidate:  event_type + accounting_date ∈ [valid_from, valid_to)
      ├─► filtrarea pe condiții:           expresii peste payload
      ├─► filtrarea pe capabilități:       capability_snapshot al evenimentului  (R26)
      ├─► rezoluția: exact o regulă        (zero sau ≥2 ⇒ eroare, nu alegere implicită)
      │
      ├─► pentru fiecare șablon de linie:
      │       rezoluția contului
      │       calculul sumei
      │       rezoluția dimensiunilor
      │       conversia valutară
      │
      └─► JournalEntry + JournalLine*, într-o singură tranzacție
```

**Zero reguli sau mai mult de una înseamnă eroare.** Evenimentul rămâne `failed`, cu `posting_error`
explicit, și intră în coada de rezolvat. Alternativa — „ia prima regulă după prioritate" — produce
postări plauzibile și greșite, care se descoperă la balanță, luni mai târziu.

### 3.2 `posting_rule`

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `rule_set` | text | NOT NULL — gruparea versionată |
| `event_type` | text | NOT NULL |
| `conditions` | jsonb | NOT NULL, DEFAULT `'{}'` — expresii peste `payload` |
| `required_capabilities` | text[] | NOT NULL, DEFAULT `'{}'` |
| `excluded_capabilities` | text[] | NOT NULL, DEFAULT `'{}'` |
| `valid_from` | date | NOT NULL |
| `valid_to` | date | NULL |
| `company_id` | uuid | NULL — regulă specifică unei companii; `NULL` = globală |
| `description` | text | NOT NULL |
| `status` | text | `draft`, `active`, `retired` |

`posting_rule_line` (șablonul liniilor): `rule_id`, `line_number`, `side` (`debit`/`credit`),
`account_resolution jsonb`, `amount_expression jsonb`, `dimension_resolution jsonb`,
`condition jsonb NULL` (linia se generează doar dacă se evaluează adevărat).

**`DECIZIE NECESARĂ (DNB-04)` — reprezentarea regulilor.**
(A) **Date în bază**, ca mai sus, cu `jsonb` interpretat de un evaluator propriu. Se modifică fără
deployment, se versionează per companie, se auditează. Costă: un limbaj de expresii de scris, testat
și documentat — adică un DSL, cu toate problemele lui.
(B) **Cod versionat**, o clasă per regulă, selectată prin registru după dată efectivă — exact
mecanismul din invariantul 4 pentru logica fiscală. Ușor de testat și de citit, dar orice ajustare
cere deployment, iar regulile specifice unei companii devin cod condiționat.
(C) **Hibrid:** structura în date (ce conturi, ce dimensiuni, ce condiții simple), calculele în cod
înregistrat. Cel mai probabil corect, dar granița trebuie definită exact, altfel migrează în timp.

Amendamentul §A.4 rezolvă întrebarea pentru *conformitate* (parametri = date, logică = cod). Nu o
rezolvă pentru regulile de postare, care nu sunt nici una, nici alta.

### 3.3 Rezoluția contului

Surse posibile, în ordinea în care se evaluează:

1. **Cont fix** din regulă — rar, doar pentru conturi tehnice.
2. **Din master data:** `company_partner.receivable_account`, `.payable_account`, categoria
   articolului, categoria activului.
3. **Din parametrii fiscali:** „mapările implicite de conturi" sunt parametri (Amd §B.1), deci
   versionate cu dată efectivă și cu sursă. Aici intră conturile de TVA, de contribuții, de impozit.
4. **Din configurarea companiei:** conturi implicite per companie, pentru cazurile pe care
   legislația nu le impune.

Rezoluția eșuează → evenimentul eșuează. Nu există „cont implicit de rezervă": o postare pe un cont
greșit e mai scumpă decât o postare care nu s-a făcut.

### 3.4 Calculul sumei și data efectivă

Expresiile operează peste `payload` și peste rezultatele calculelor fiscale. Orice apel către logica
fiscală transmite **`accounting_date` al evenimentului**, nu data curentă (R17, R18).

Consecință practică: repostarea unui eveniment din 2026, executată în 2028, produce aceleași linii,
pentru că regula, parametrii și algoritmul se selectează după `accounting_date`. Acesta este testul
care demonstrează că motorul e corect construit și intră în corpusul de regresie.

### 3.5 Capabilitățile ca input

`capability_snapshot` se scrie **pe eveniment**, la emitere, și nu se recitește la postare. Motivul:
repostarea trebuie să folosească profilul de atunci, nu pe cel de acum.

Exemplul canonic din V2 §7.4: o factură de achiziție de marfă se contabilizează diferit după cum
tenantul are sau nu `inventory` activat — cu Inventory, `<cont de stocuri>`; fără, `<cont de
cheltuieli>`. Aceeași factură, două rezultate corecte, în funcție de o stare cu dată efectivă.

Dacă profilul s-ar citi la postare, activarea Inventory ar schimba contabilizarea documentelor deja
emise dar nepostate — adică ar produce, în aceeași lună, două tratamente pentru documente identice.

---

## 4. Maparea document → postare

### 4.1 Formatul

O regulă leagă un tip de eveniment de un set de linii. Forma de mai jos este ilustrativă pentru
opțiunea A din `DNB-04`; dacă se alege B sau C, aceleași elemente apar ca atribute de clasă.

```jsonc
{
  "rule_set": "sales-2026",
  "event_type": "sales.invoice_issued",
  "valid_from": "2026-01-01",
  "conditions": { "payload.invoice_kind": "goods" },
  "required_capabilities": [],
  "lines": [
    {
      "side": "debit",
      "account_resolution": { "from": "partner", "field": "receivable_account" },
      "amount_expression": { "field": "payload.total_with_vat" },
      "dimension_resolution": { "partner_id": "payload.partner_id" }
    },
    {
      "side": "credit",
      "account_resolution": { "from": "item_category", "field": "revenue_account" },
      "amount_expression": { "field": "payload.total_without_vat" },
      "dimension_resolution": { "partner_id": "payload.partner_id",
                                "item_id": "line.item_id" }
    },
    {
      "side": "credit",
      "condition": { "company.vat_registered_at": "event.accounting_date" },
      "account_resolution": { "from": "fiscal_parameter",
                              "key": "<mapare cont TVA colectată>" },
      "amount_expression": { "from": "fiscal_logic",
                             "key": "vat.calculate_output",
                             "effective_date": "event.accounting_date" }
    }
  ]
}
```

Elementele obligatorii ale oricărei reprezentări:

| Element | De ce e obligatoriu |
|---|---|
| `valid_from` / `valid_to` | R17 — selecția după data perioadei calculate |
| `conditions` | aceeași operațiune se contabilizează diferit după atributele documentului |
| `required_capabilities` | R26 — profilul de capabilități este input |
| rezoluția contului prin referință, nu prin cod literal | R15 — mapările de conturi sunt parametri |
| apelul logicii fiscale cu dată efectivă | R18 — recalcularea folosește algoritmul de atunci |

### 4.2 Exemple în cuvinte

Fiecare exemplu este o pereche eveniment → efect. Conturile sunt substituenți; valorile fiscale nu
apar deloc (OD-22).

**Factură de vânzare de servicii, companie plătitoare de TVA.**
`sales.invoice_issued` → debit `<creanțe comerciale>` cu totalul; credit `<venituri din servicii>`
cu baza; credit `<TVA colectată>` cu suma calculată de logica fiscală pentru `accounting_date`.
Dimensiunea `partner_id` obligatorie pe linia de creanțe.

**Aceeași factură, companie neînregistrată ca plătitor de TVA.**
Condiția pe `company_vat_registration` la `accounting_date` (Spec A §1.2) este falsă → linia de TVA
nu se generează. **Nu** printr-un `if` în cod, ci prin condiția regulii.

**Factură de achiziție de marfă, tenant cu Inventory activ.**
`purchases.invoice_received` cu `capability_snapshot` conținând `inventory` → debit `<stocuri>`.

**Aceeași factură, tenant fără Inventory.**
Aceeași regulă nu se aplică (`required_capabilities` nesatisfăcut); se aplică regula alternativă →
debit `<cheltuieli>`. Două reguli distincte, ambele explicite, niciun `if`.

**Încasare bancară care stinge o factură.**
`banking.payment_received` → debit `<cont curent>`; credit `<creanțe comerciale>`, cu dimensiunea
`partner_id` și cu legătura de decontare către factură. Decontarea este entitate proprie în
`receivables` (F2), nu o coloană pe linia de jurnal.

**Rulare de salarii aprobată.**
`payroll.run_approved` → un set de linii pentru cheltuiala salarială, rețineri, contribuții
angajator și angajat. Fiecare sumă vine din logica fiscală selectată pentru perioada rulării, nu
pentru luna curentă. Dimensiunea `employee_id` pe liniile individuale — **decizie de granularitate
în `DNB-05`**.

**`DECIZIE NECESARĂ (DNB-05)` — granularitatea postării de payroll.**
(A) O linie per angajat și per tip de sumă: fișa contului arată direct cine, dar o companie cu 200
de angajați produce mii de linii pe lună. (B) Linii agregate pe tip de sumă, cu detaliul rămas în
`payroll`: ledger compact, dar drill-down-ul din contabilitate către angajat trece printr-un alt
modul, ceea ce complică lanțul cerut de INV-9. (C) Agregat în ledger + un read model de detaliu.
Are consecințe asupra volumului lui `journal_line` și asupra modelului de volum (OD-30).

### 4.3 Ce nu se face în mapare

- Nu se scriu conturi literale în cod. Nici în teste care apoi devin fixture de producție.
- Nu se calculează TVA sau contribuții în regula de postare. Regula **cere** rezultatul de la logica
  fiscală; calculul e acolo (5).
- Nu se ramifică pe an sau pe dată curentă. Ramificarea se face prin `valid_from` / `valid_to` ale
  regulii.
- Nu se generează linii cu sumă zero pentru simetrie vizuală.

---

## 5. Motorul de reguli fiscale

Structura este impusă de invariantul 4 reformulat (Amd §A.4, §B.1): parametrii sunt date, logica
este cod versionat, selecția se face printr-un registru după data efectivă a perioadei calculate.

```
FISCAL PARAMETERS  (date, versionate valid_from/valid_to, cu sursă)
        │
        ├── cote TVA, cote CNAS / CNAM
        ├── praguri și plafoane salariale, scutiri personale
        ├── cote impozit pe venit, praguri de înregistrare
        ├── termene de raportare, coeficienți de amortizare
        └── mapări implicite de conturi
                        │  consumate de
                        ▼
FISCAL LOGIC  (cod versionat, selectat prin registru după dată efectivă)
        ├── algoritmi de calcul salarial
        ├── algoritm de calcul TVA și proratare
        ├── scheme de declarații (XML / format)
        ├── reguli de validare
        └── comportament API instituțional
```

### 5.1 `fiscal_parameter` (global)

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `parameter_key` | text | NOT NULL — identificator stabil, ex. `vat.standard_rate` |
| `scope` | text | NOT NULL, CHECK în `('global','company_class','company')` — vezi `DNB-06` |
| `value_type` | text | NOT NULL, CHECK în `('decimal','integer','money','percentage','date','boolean','table')` |
| `value` | jsonb | NOT NULL — scalar sau structură, după `value_type` |
| `unit` | text | NULL — `MDL`, `%`, `luni` |
| `valid_from` | date | NOT NULL |
| `valid_to` | date | NULL |
| `source_id` | uuid | NOT NULL, REFERENCES `fiscal_parameter_source` |
| `status` | text | NOT NULL, `draft`, `approved`, `active`, `superseded` |
| `approved_by_user_id` | uuid | NULL — contabilul practicant (Amd §D.1) |

Constrângeri: neîntrepătrundere pe `(parameter_key, scope_ref, daterange(valid_from, valid_to))`
pentru rândurile `active`; `CHECK (valid_to IS NULL OR valid_to > valid_from)`.

`fiscal_parameter_source`: `id`, `act_type`, `act_number`, `official_gazette_number`,
`published_at`, `effective_from`, `url`, `notes`. **Un parametru fără sursă nu se activează** —
regula pe care o verifică `fiscal-reviewer`.

**`DECIZIE NECESARĂ (DNB-06)` — `value_type = 'table'`.**
Multe reguli fiscale nu sunt scalari: grile progresive, plafoane pe tranșe, coeficienți pe categorii
de active. Opțiuni: (A) un singur `jsonb` cu structură liberă per cheie — flexibil, imposibil de
validat generic; (B) tabele dedicate per formă (grilă, tranșă, matrice), cu structură strictă —
validabil, dar fiecare formă nouă e o migrare; (C) `jsonb` cu schemă JSON declarată pe cheie și
validată la inserare. C pare cel mai bun, dar cere un registru de scheme, adică încă un artefact
versionat.

### 5.2 Registrul de logică

`fiscal_logic_version` (global):

| Câmp | Tip | Note |
|---|---|---|
| `logic_key` | text | NOT NULL — ex. `payroll.calculate_contributions` |
| `implementation_ref` | text | NOT NULL — referință stabilă la implementare |
| `version` | text | NOT NULL |
| `valid_from` | date | NOT NULL |
| `valid_to` | date | NULL |
| `source_id` | uuid | NULL — actul care a impus schimbarea |
| `regression_case_set` | text | NOT NULL — setul din corpusul de regresie care o acoperă |
| `approved_by_user_id` | uuid | NULL |

Rezoluția: `resolve(logic_key, effective_date) → implementation`. Un singur rezultat; zero sau două
înseamnă eroare de configurare, nu alegere implicită.

**Interdicția care face mecanismul să funcționeze:** nicio condiție pe an sau pe data curentă în
codul de business (R17). Implementarea pentru 2026 nu știe că există 2027; registrul știe.

**Regula de retragere:** o implementare nu se șterge niciodată. Recalcularea unei perioade din 2026,
executată în 2030, o cere. Codul vechi rămâne în repo, acoperit de corpusul de regresie.

### 5.3 Fluxul de conformitate

Din Amd §D.1, ca proces care produce rânduri în tabelele de mai sus:

```
act normativ publicat
   → evaluare impact: parametru? algoritm? schemă de declarație?
   → implementare cu dată efectivă
   → rulare pe corpusul de regresie
   → aprobare de contabil practicant   (approved_by_user_id)
   → activare programată                (status → active la valid_from)
   → comunicare către tenanți și firme
```

Corpusul de regresie (Amd §D.2) rulează la **fiecare** modificare de parametru sau de algoritm.
Structura unui caz: intrări anonimizate, dată efectivă, rezultat așteptat verificat de un contabil,
trimitere la sursa care justifică rezultatul.

Fără el, o modificare de cotă pentru un an viitor poate strica recalcularea unui an trecut, iar asta
se află de la un client.

---

## 6. Perioade

### 6.1 `period`

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id`, `company_id` | uuid | NOT NULL |
| `fiscal_year` | smallint | NOT NULL |
| `period_no` | smallint | NOT NULL — vezi `DNB-07` |
| `start_date`, `end_date` | date | NOT NULL |
| `status` | text | NOT NULL, CHECK în `('open','closing','closed','locked')` |
| `closed_at`, `closed_by_user_id` | | NULL |
| `reopened_count` | smallint | NOT NULL, DEFAULT 0 |
| `last_reopened_at`, `last_reopened_by_user_id` | | NULL |

`UNIQUE (company_id, fiscal_year, period_no)`; neîntrepătrundere pe
`(company_id, daterange(start_date, end_date))`.

### 6.2 Stări și tranziții

| Din | În | Cine | Efect |
|---|---|---|---|
| `open` | `closing` | contabil responsabil | postările noi refuzate; corecțiile în curs permise |
| `closing` | `open` | același | revenire, cu urmă în audit |
| `closing` | `closed` | contabil responsabil | nicio postare, nicio corecție |
| `closed` | `open` | **permisiune specială** | `reopened_count++`, eveniment de audit obligatoriu, notificare |
| `closed` | `locked` | administrator | ireversibil; se folosește după depunerea situațiilor financiare |

`locked` este terminală. Corecția unei perioade `locked` se face exclusiv prin storno în perioada
curentă deschisă (9.3).

### 6.3 Refuzul la postare

Verificarea stă în Posting Engine, nu în interfață (R12). Concret: rezoluția regulii se face
înainte, dar scrierea înregistrării verifică starea perioadei corespunzătoare lui
`accounting_date` și refuză cu un cod de eroare stabil (C10).

A doua barieră, la nivel de bază de date: un trigger `BEFORE INSERT` pe `journal_entry` care
citește starea perioadei. Motivul pentru care nu e suficientă doar prima: importul 1C, migrările de
date și orice `INSERT` direct ocolesc motorul.

**`DECIZIE NECESARĂ (DNB-07)` — granularitatea perioadei și blocarea per modul.**
(A) Perioada lunară, o singură stare pentru tot. Simplu, dar închiderea TVA-ului și închiderea
salariilor nu se întâmplă în aceeași zi, iar prima o blochează pe a doua. (B) Perioadă lunară cu
blocări per modul (`period_module_lock`): TVA se poate închide independent de payroll. Corect
operațional, mai complicat de verificat — refuzul la postare devine o interogare pe două tabele.
(C) Perioade separate per domeniu. Cel mai flexibil, cel mai ușor de folosit greșit.

Legat, dar distinct: anul fiscal este întotdeauna calendaristic în RM? Vezi `DN-05` din Spec A.

---

## 7. Multi-valută

### 7.1 Modelul de sumă

Fiecare linie de jurnal poartă patru elemente (1.3):

```
amount_currency   suma în valuta tranzacției
currency          valuta
exchange_rate     cursul folosit
debit / credit    suma în moneda funcțională, rotunjită
```

Regula de derivare: `debit|credit = round(amount_currency * exchange_rate, <precizie>)`, cu
precizia și regula de rotunjire din `DNB-08`.

**De ce se stochează toate patru.** Nu este alegere de proiectare, este **cerință legală**:

> Legea nr. 287/2017, art. 7 alin. (2): „Contabilitatea faptelor economice efectuate în valută
> străină se ţine atît în monedă naţională, cît şi în valută străină, în conformitate cu standardele
> de contabilitate."

Motivul tehnic se adaugă peste, nu îl înlocuiește: cursul se schimbă, iar o înregistrare postată
este imutabilă — suma în moneda funcțională trebuie să rămână exact ce a fost, nu ce ar rezulta
dintr-un recalcul. Fiind cerință legală, modelul **nu se optimizează** la o revizuire ulterioară de
performanță.

### 7.2 `exchange_rate` (global)

`id`, `currency` (char(3)), `rate_date` (date), `rate` (numeric(18,8)), `rate_type`
(`bnm_official` / `manual` / `contractual`), `source`, `fetched_at`.
`UNIQUE (currency, rate_date, rate_type)`.

Cursul BNM se preia prin calea privilegiată P-3 din Spec A §6.2. Comportamentul în zile
nelucrătoare, formatul și cadența depind de OD-26 — nu se presupun aici.

### 7.3 Diferențe de curs

Două categorii, cu tratamente diferite:

- **Realizate** — apar la decontare: factura la un curs, plata la altul. Se postează la decontare,
  ca eveniment contabil propriu (`receivables.settlement_created`), nu ca ajustare tăcută.
- **Nerealizate** — apar la reevaluarea soldurilor în valută la sfârșit de perioadă. Se postează ca
  eveniment de închidere (`accounting.revaluation_calculated`), reversibil la începutul perioadei
  următoare dacă politica o cere.

Conturile de diferențe (favorabile / nefavorabile) sunt **mapări de conturi**, deci parametri
fiscali (5.1), nu constante.

**Reevaluarea nu se implementează în F0.** Modelul de sumă, da (F0.9). Reevaluarea vine cu F1
sau F2 — vezi OD-10 pentru statutul conectorului BNM în F0.

### 7.4 Precizie și rotunjire

**Regula corectă nu se deduce din principii. Se citește din schema XML a e-Facturii.** Dacă
rotunjirea noastră diferă cu un ban de ce calculează SFS, factura este respinsă — deci regula
validă este cea pe care o validează sistemul lor, oricare ar fi ea.

`DNB-08` rămâne deschisă și este **blocată pe obținerea ghidului de integrare SFS** (`OD-24`), nu pe
o dezbatere internă. Ce cere deblocarea: semnătură electronică, entitate de test, descărcarea
ghidului.

**Ce se fixează acum, fără risc:**

1. **`numeric` cu scală explicită, niciodată `float`.** Nicio sumă, niciun curs, niciun procent nu
   trece prin virgulă mobilă. Nu este o preferință de stil: `float` face ca aceeași balanță să dea
   rezultate diferite după ordinea de agregare.
2. **Calculele intermediare pe linie se fac la precizie mai mare decât cea de postare.** Rotunjirea
   se aplică o singură dată, la producerea liniei de jurnal, nu la fiecare pas intermediar.
3. **Rotunjirea este logică fiscală versionată, nu funcție utilitară.** Trăiește în
   `fiscal_logic_version`, cu `logic_key` propriu, selectată după data efectivă a perioadei (R17).
   Motivul: se poate schimba legislativ, iar recalcularea unei perioade trecute trebuie să
   folosească regula de atunci. O funcție `round_money()` într-un modul de utilitare este exact
   forma în care o regulă fiscală ajunge nemarcată în cod.

**Ce rămâne deschis** până la ghidul SFS:

| # | Întrebare | Efect dacă se greșește |
|---|---|---|
| a | Precizia de stocare a sumelor în moneda funcțională: 2 sau 4 zecimale | cu 2, suma liniilor diferă de totalul calculat; cu 4, balanța arată bani care nu există |
| b | Regula de rotunjire: la jumătate în sus, la par, sau alta impusă | abateri de bani față de calculul SFS |
| c | Locul rotunjirii TVA: pe linie sau pe document | abateri pe facturi cu multe linii; declarația nu se potrivește cu factura |

Punctul (c) generează cele mai multe reclamații într-un sistem contabil real.

## 8. Solduri inițiale

### 8.1 Structura

`opening_balance_batch`: `id`, `tenant_id`, `company_id`, `as_of_date`, `source`
(`manual` / `onec_import` / `other_system`), `status` (`draft`, `validated`, `posted`, `rejected`),
`created_by_user_id`, `validated_at`, `posted_at`, `journal_entry_id` (rezultatul postării).

Șase seturi de linii, câte unul per domeniu (V2 §7.7):

| Set | Conținut minim |
|---|---|
| GL | cont, sold debitor, sold creditor, valută și sumă în valută unde contul o cere |
| Clienți | partener, document sursă, dată, sumă, valută, scadență |
| Furnizori | idem |
| Stocuri | articol, depozit, lot (dacă se urmărește), cantitate, cost unitar, cost total |
| Active | activ, cost de intrare, amortizare cumulată, dată punere în funcțiune, durată rămasă |
| Angajați | angajat, cumulative anuale per tip de venit și contribuție, de la 1 ianuarie |

Ultimul set este cel care face activarea payroll-ului la mijloc de an posibilă. Structura lui exactă
depinde de OD-04 (modelul cumulativelor payroll), care este deschisă.

### 8.2 Validarea

Un lot nu se postează dacă:

- suma soldurilor debitoare ≠ suma soldurilor creditoare pe setul GL
- soldul analitic (clienți, furnizori, stocuri, active) nu se potrivește cu soldul contului sintetic
  corespunzător din setul GL
- un cont referit nu există, e blocat sau nu e valabil la `as_of_date`
- o dimensiune obligatorie lipsește

Reconcilierea la **zero diferență** este condiție de import, nu obiectiv (V2 §14: „refuz de import
parțial").

### 8.3 Postarea

Un lot validat produce **o singură** `JournalEntry` cu `entry_type = 'opening'`, cu
`accounting_date = as_of_date`, în perioada corespunzătoare. Contrapartida este un cont tehnic de
deschidere care trebuie să rămână cu sold zero — verificarea lui este testul că importul e complet.

Corecția unui lot postat: storno + lot nou. Nu se editează (R10).

---

## 9. Storno și lineage

### 9.1 Lanțul complet

```
JournalLine → JournalEntry → AccountingEvent → SourceDocument → Sursă (utilizator/sistem/integrare)
```

Navigabil în ambele sensuri (INV-9). Legăturile care îl asigură:

| De la | La | Mecanism |
|---|---|---|
| linie → înregistrare | `journal_line.journal_entry_id` | coloană + index |
| înregistrare → linii | index `(journal_entry_id)` | **nu** cheie străină (R21) |
| înregistrare → eveniment | `journal_entry.accounting_event_id` | cheie străină |
| eveniment → înregistrări | index `(accounting_event_id)` pe `journal_entry` | |
| eveniment → document | `source_document_type` + `source_document_id` | fără cheie străină (1.1) |
| document → efecte | index `(source_document_type, source_document_id)` | |
| efect → sursă umană | `actor_user_id`, `request_id` | Spec A §9.3 |

### 9.2 Structura stornoului

O înregistrare de storno are **două** legături (R14):

1. `accounting_event_id` → evenimentul care a produs-o (poate fi un eveniment de tip
   `accounting.reversal_requested`, cu documentul sursă original în payload)
2. `reverses_entry_id` → înregistrarea pe care o anulează

Fără a doua, drill-down-ul pe un cont cu corecții devine incoerent: se văd două înregistrări cu
sume opuse și nimic nu spune că una o anulează pe cealaltă.

Liniile stornoului sunt liniile originale cu debit și credit inversate — **nu** cu sume negative.
O linie negativă strică rulajele: rulajul debitor al lunii ar scădea în loc să crească cu corecția,
iar balanța nu ar mai arăta activitatea reală.

### 9.3 Data stornoului

Decizia s-a împărțit în două, pentru că structura este independentă de politică:

**Structura — [ADR-006](../decisions/006-reversal-two-dates.md), `Acceptat`.** Înregistrarea de
corecție poartă două date distincte: `accounting_date` (unde se postează) și `corrects_period_id`
(la ce perioadă se referă). Necesare indiferent de politica aleasă — fără ele declarația
rectificativă nu se poate genera. Vezi §1.2.

**Politica — [ADR-007](../decisions/007-reversal-period.md), `Propus`.** Nu din lipsă de semnătură
(`OD-32` s-a închis), ci pentru că trei întrebări de tratament contabil nu au încă răspuns.
Propunerea:

| Situație | Unde se postează | `corrects_period_id` |
|---|---|---|
| Eroare descoperită în perioadă **deschisă**, aferentă acelei perioade | aceeași perioadă | `NULL` |
| Eroare descoperită după **închiderea** perioadei | perioada curentă deschisă | perioada originală |

Al doilea rând nu este preferință: R12 interzice postarea într-o perioadă închisă, iar refuzul se
face la nivel de motor. Stornoul nu este excepție de la R12 — dacă ar fi, R12 nu ar mai însemna
nimic.

Rămâne de confirmat de contabil: dacă practica din RM permite redeschiderea unei perioade închise
înainte de depunerea declarației aferente; dacă o corecție după depunere impune obligatoriu
declarație rectificativă; și cum se tratează stornoul unei perioade `locked`.

Până la acceptare, F1.2 se poate implementa pe structura din ADR-006; serviciul care alege perioada
rămâne nescris.

### 9.4 Reguli

- Se stornează doar înregistrări `posted`.
- O înregistrare are cel mult un storno activ. Un al doilea storno al aceleiași înregistrări este
  refuzat — indiciu de eroare de proces.
- Stornoul unui storno este permis (reînregistrare după o corecție greșită) și produce un lanț
  navigabil.
- Stornoul nu șterge nimic și nu marchează originalul altfel decât prin existența legăturii.
- Rapoartele oferă ambele vederi: cu și fără corecții. Fără asta, „de ce nu se potrivește balanța cu
  cea de luna trecută" nu are răspuns.

---

## 10. Idempotență și deduplicare

Două mecanisme distincte, ambele necesare (Amd §A.8). Confundarea lor este defect: un retry tehnic
și un document introdus de două ori arată la fel în bază, dar au cauze și remedii diferite.

### 10.1 Idempotență — retry tehnic

**Cheia stă pe evenimentul contabil**, nu doar pe endpoint (R19):
`UNIQUE (company_id, idempotency_key)` pe `accounting_event` (1.1).

Compoziția cheii, per sursă:

| Sursă | `idempotency_key` |
|---|---|
| API | valoarea headerului `Idempotency-Key`, furnizată de client (C9) |
| e-Factura | identificatorul documentului la SFS |
| import bancar | hash-ul liniei de extras + identificatorul fișierului |
| task Celery | `<task_name>:<task_id>` |
| import 1C | `<batch_id>:<record_id>` |
| rulare payroll | `<run_id>:<stage>` |

Comportament la conflict:

- aceeași cheie, același payload → se returnează rezultatul primei execuții, fără efect nou
- aceeași cheie, payload diferit → **eroare** cu cod stabil, niciun efect. Este cazul care
  semnalează un bug la apelant; tăcerea l-ar ascunde
- cheie absentă pe o operațiune cu efect financiar → refuz

**`DECIZIE NECESARĂ (DNB-10)` — durata de reținere a cheilor.**
Cheile trăiesc pe `accounting_event`, care nu se șterge niciodată, deci unicitatea e permanentă.
Întrebarea este dacă `Idempotency-Key` din API are o fereastră după care poate fi reutilizată
(uzual 24h), sau este permanentă. Prima e convenția din industrie; a doua e mai sigură într-un
sistem contabil, dar înseamnă că un client care își generează cheile prost blochează operațiuni
legitime la nesfârșit.

### 10.2 Deduplicare — același document pe două căi

Problema: aceeași factură ajunge prin e-Factura și e introdusă manual; același plată apare în
importul bancar și în casă. Idempotența nu ajută — sunt cereri diferite, cu chei diferite.

Mecanismul: **chei naturale de business**, cu constrângeri unice pe documentul sursă, nu pe eveniment.

| Tip de document | Cheie naturală propusă |
|---|---|
| Factură primită | `(company_id, supplier_idno, supplier_series, supplier_number, invoice_date)` |
| Factură emisă | `(company_id, document_type, series, number)` — garantată de numerotare |
| Linie de extras bancar | `(company_id, bank_account_id, statement_date, bank_reference)` |
| Document e-Factura | `(company_id, sfs_document_uid)` |
| Rulare payroll | `(company_id, period_id, run_type)` |

Fiecare este **propunere**, nu specificație închisă: cheia naturală corectă depinde de ce garantează
efectiv sursa. `DNB-11`.

**`DECIZIE NECESARĂ (DNB-11)` — cheile naturale per tip de document.**
Pentru fiecare tip trebuie confirmat: ce combinație identifică unic documentul economic în practica
din RM, ce se întâmplă când un furnizor reia seria la an nou, și ce face sistemul la coliziune —
refuz, sau semnalare ca posibil duplicat cu decizie umană. A doua variantă e mai realistă, dar cere
o stare „suspectat duplicat" pe document și un flux de rezolvare.

### 10.3 Ce se verifică în teste

- aceeași operațiune de două ori cu aceeași cheie → exact un efect financiar
- aceeași cheie cu payload diferit → eroare, zero efecte
- același document economic pe două căi → un singur document, semnalat sau refuzat conform `DNB-11`
- retry după eșec parțial → niciun efect duplicat, starea evenimentului reflectă realitatea

---

## 11. DECIZII NECESARE — lista completă

| # | Decizie | Blochează | Cine decide |
|---|---|---|---|
| DNB-01 | Cine deține vocabularul de `event_type` | F1.3 | arhitectură |
| ~~DNB-02~~ | Dimensiuni definite de utilizator — **închisă** prin ADR-029: cinci sloturi generice per companie | — | — |
| DNB-03 | Politica de propagare a template-ului planului de conturi *(= OD-03)* | F1.1 | contabil + produs |
| DNB-04 | Reprezentarea regulilor de postare: date, cod, sau hibrid | F1.4 | arhitectură |
| DNB-05 | Granularitatea postării de payroll | F2, volumul lui `journal_line` | contabil + arhitectură |
| DNB-06 | Forma parametrilor fiscali care nu sunt scalari (grile, tranșe) | F0.8 | arhitectură |
| DNB-07 | Granularitatea perioadei și blocarea per modul | F1.5 | contabil |
| DNB-08 | Precizia, regula de rotunjire, locul rotunjirii TVA. **Invariantele sunt fixate** (§7.4); valorile așteaptă ghidul de integrare SFS (`OD-24`) | F1 calcule | **SFS**, nu dezbatere internă |
| ~~DNB-09~~ | Împărțită: structura în [ADR-006](../decisions/006-reversal-two-dates.md) (`Acceptat`), politica în [ADR-007](../decisions/007-reversal-period.md) (`Propus`) | — | **contabil**, pentru ADR-007 |
| DNB-10 | Fereastra de reținere a cheilor de idempotență în API | F1.3 | arhitectură |
| DNB-11 | Cheile naturale de deduplicare per tip de document | F2 | contabil + investigație |

Decizii din registrul general care blochează această specificație și **nu** sunt reformulate aici:

| # | Ce lipsește | Efect asupra Spec B |
|---|---|---|
| OD-22 | Valorile fiscale efective | Fără ele, `fiscal_parameter` are structură dar nu conținut; niciun calcul nu funcționează |
| OD-23 | Conținutul planului de conturi SNC | `coa_template_account` are structură dar nu rânduri |
| OD-04 | Modelul cumulativelor payroll | Setul „Angajați" din soldurile inițiale (8.1) rămâne nespecificat |
| OD-29 | Țintele de performanță | Indicii din 1.3 sunt propuși pe raționament, nu pe măsurători |
| OD-30 | Modelul de volum | `DNB-05` nu poate fi decisă fără el |
| DN-11 (Spec A) | Contextul de companie în sesiune | Politicile RLS ale tuturor tabelelor de aici |

---

## 12. Ce urmează după această specificație

1. **Review contabil**, nu doar tehnic. `DNB-05` și `DNB-07` nu pot fi decise de un inginer;
   `DNB-09` este împărțită, cu partea contabilă în ADR-007, `Propus`; `DNB-08` așteaptă SFS.
2. **ADR pentru fiecare decizie luată.**
3. **Conținutul planului de conturi și parametrii fiscali** (OD-22, OD-23), fără de care structura
   de aici rămâne un schelet gol.
4. **Corpusul de regresie** (F1.10) se proiectează odată cu 5.3, nu după: cazurile lui sunt
   specificația executabilă a logicii fiscale.
