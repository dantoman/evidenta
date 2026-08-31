# ADR-075 — Identitatea fiscală a titularului contului; compania proprie se propune, nu se impune

- **Status:** **Acceptat** — **decizie de produs**, luată de proprietar în sesiunea din 2026-08-31,
  din întrebarea proprie: *„Alpha SRL titularul contractului când se înregistrează trebuie să
  stipuleze datele sale… IDNO, e ÎI sau SRL, să aibă cont propriu de contabilitate"*. Ambele variante
  au fost alese explicit, dintre trei propuse fiecare.
- **Data:** 2026-08-31
- **Decide:** proprietarul proiectului
- **Închide:** întrebarea *„care dintre companii este titularul"*, la care produsul nu avea cu ce
  răspunde
- **Deschide:** `OD-107` (facturarea abonamentului), `OD-108` (editarea identității titularului din
  produs)
- **Afectează:** `platform/tenancy` (model, migrare `0009`, `infra/migrations/0070`, comenzi,
  `GET /api/v1/workspace`), ecranul *Spațiul de lucru*, `CompaniesScreen`
- **Legate:** [ADR-015](015-colatie-icu.md), [ADR-020](020-roluri-ca-date.md),
  [ADR-040](040-crearea-tenantului-si-a-companiei.md), [ADR-074](074-sistemul-de-design-evidenta.md);
  `DN-26` (cine poate înregistra prin produs) rămâne deschisă și nu se atinge aici

## 1. Ce a produs întrebarea

Proprietarul s-a uitat la lista de companii a spațiului `alpha` și a întrebat a cui e pagina. Lista
arăta două companii — `II TOMȘA DAN` și `tominter ds` — și niciuna nu era **Alpha SRL**, titularul
contractului. Întrebarea următoare a fost cea corectă: *dacă Alpha SRL e titularul, unde e
contabilitatea lui?*

**Măsurat, nu presupus.** `tenant` purta: `subdomain`, `legal_name`, `status`, `default_locale`,
`primary_contact`. Fără IDNO, fără formă juridică, fără monedă, fără dată de început al evidenței,
fără exercițiu, fără registru. Contabilitatea e legată de `company` fără excepție — docstring-ul
modelului o spune de la prima versiune: *„the legal entity with its own ledger"*.

Deci: **titularul își ține contabilitatea proprie doar dacă există și ca `company`**. Nu era o eroare
de model. Era un pas pe care nimeni nu-l decisese: nici `create_tenant`, nici vreun ecran nu creau
compania titularului, și nimic nu spunea că lipsește.

## 2. Prima decizie: titularul poartă identitate fiscală

`tenant` primește **`idno`** și **`legal_form`**.

**De ce nu se potrivește după denumire.** „Alpha SRL" și `SRL "Alpha"` sunt aceeași firmă scrisă
altfel; la fel „ÎI Tomșa Dan" și „II TOMSA DAN". O potrivire pe nume ar răspunde **încrezător și
greșit** exact acolo unde răspunsul contează. IDNO e cod, se compară cifră cu cifră, iar `COLLATE "C"`
(`C34`, ADR-015) e ce face potrivirea cu `company.idno` exactă și nu lingvistică. Testul din suită e
scris ca să cadă dacă cineva implementează potrivirea pe nume: tenantul și **două** companii poartă
aceeași denumire, cu IDNO-uri diferite.

**Nullable**, fiindcă tenanții existenți nu au IDNO și o coloană obligatorie i-ar face invalizi
retroactiv (`C5` — migrările sunt aditive). Ce costă absența e **spus pe ecran**, nu ascuns.

**Fără `UNIQUE`**, deliberat. *„O entitate juridică are un singur abonament"* e o regulă de **produs**,
nu un fapt fiscal, și nu a fost decisă. Un index unic pus azi ar închide-o tacit și s-ar sparge la
primul caz real: aceeași firmă cu două spații, sau o migrare între planuri.

**Fără `CHECK` pe forma juridică.** Vocabularul formelor de organizare (SRL, SA, ÎI, ÎM, CO…) stă în
Clasificatorul formelor juridice de organizare, iar **acel act nu e în acest repo**. O enumerare
scrisă din memorie ar refuza forme reale — exact motivul pentru care `cuatm_code` și `caem_code` sunt
text liber pe `company` (migrarea 0068). `CLAUDE.md` §4: nu se deduc clasificatoare din memorie.

## 3. A doua decizie: compania proprie se **propune**

Înregistrarea **nu** creează compania titularului. Ecranul *Spațiul de lucru* arată că titularul nu
are companie proprie și deschide formularul cu denumirea și IDNO-ul completate.

**De ce nu automat.** O companie poartă `accounting_start_date` și moneda funcțională. Prima e o dată
**contabilă**: postarea înaintea ei e refuzată de motor, iar corectarea după prima înregistrare nu e
o editare, e o repornire. Un implicit ales aici — 1 ianuarie anul curent — ar fi o dată de început pe
care nimeni n-a observat că o alege. Câmpul completat automat este cel care nu are consecință
(denumirea, IDNO-ul); cel care are rămâne al omului.

**Trei adevăruri sub același `null`**, și ecranul le desparte în loc să le confunde:

| `own_company_id` e `null` fiindcă | Ce spune ecranul |
|---|---|
| titularul n-are IDNO înregistrat | nu e cu ce potrivi; se completează la înregistrare |
| are IDNO, nu există compania | titularul nu-și ține contabilitatea aici — **ofertă** |
| există, dar cititorul n-o poate vedea | absentă, ca orice rând inaccesibil (`IZ-04`) |

Al treilea rând nu e o scăpare: un rând inaccesibil este **absent, niciodată interzis**, și a-l
distinge ar spune cititorului că există o companie pe care n-are voie s-o vadă.

## 4. Cum se scrie identitatea, azi

Prin comenzi de operator: `create_tenant --idno --legal-form` la înregistrare,
`set_tenant_identity --subdomain --idno --legal-form` pentru un tenant existent. Amândouă sub rolul
de instalare, ca `create_tenant` — politica pe `tenant` e scrisă `TO evidenta_app`, deci proprietarul
n-are nicio politică aplicabilă și e refuzat.

**Nu din produs, și motivul e o regulă, nu o lipsă de timp:** ar cere o cheie de permisiune pe care
nimeni n-a decis-o. `tenant.manage_roles` e despre roluri; folosită aici ar fi **inventarea unui
drept**, exact ce catalogul din ADR-020 există ca să prevină — *„o cheie apare acolo doar când ceva o
impune"*. Rămâne `OD-108`.

## 5. Ce **nu** decide acest ADR

**Facturarea abonamentului** — `OD-107`. Întrebarea proprietarului avea două laturi și doar una atinge
produsul:

- *Latura clientului*: factura de abonament e **o factură de la furnizor ca oricare alta**. Se
  înregistrează în compania titularului, prin modulul de achiziții (F2). Nu-i trebuie mecanism
  special — îi trebuie compania titularului, adică §3, și F2.
- *Latura vendorului*: emiterea, încasarea, mijlocul de plată. `billing` e numit explicit în
  `MODULE_KEYS` ca **operațiune de platformă, nedelegabilă**, și nu există. Dacă vendorul e rezident
  în RM, factura de abonament e ea însăși document fiscal moldovenesc, deci intră în e-Factura — un
  produs în sine. Nu blochează nimic din F1 sau F2.

**Lista persoanelor din spațiu** rămâne `OD-37`: `membership` are politică „rând propriu", deci o
listă ar întoarce doar cititorul și ar arăta ca un răspuns.

## 6. Ce s-a livrat odată cu decizia

- `tenant.idno` + `tenant.legal_form` (migrarea Django `tenancy/0009`, SQL-ul pereche
  `infra/migrations/0070` pentru colație).
- `GET /api/v1/workspace`: titularul cu identitatea lui și compania proprie **derivată**, drepturile
  cititorului, rolurile spațiului cu ce poate fiecare, firmele cu mandat.
- Ecranul *Spațiul de lucru* și oferta care deschide formularul completat.
- Șapte teste de izolare, sub rolul aplicației (`T1`), inclusiv capcana pentru potrivirea pe nume.

**Și un defect găsit pe drum, nu căutat:** pe `alpha`, rolul de sistem `owner` avea **zero**
permisiuni și rolul `company_admin` lipsea — tenantul fusese creat înainte ca `create_system_roles`
să însămânțeze permisiunile, iar `proba` și `proba2` aveau 7 și 1. Nimic nu semnalase: un rol fără
permisiuni e un rând valid, și niciun test nu acoperă un tenant creat înaintea codului care îl
repară. Primul simptom ar fi fost proprietarul spațiului incapabil să-și editeze propriile roluri.
Remediul e `repair_system_roles`, idempotent fiindcă `create_system_roles` era deja idempotent —
o comandă de operator, nu o a doua implementare a însămânțării.
