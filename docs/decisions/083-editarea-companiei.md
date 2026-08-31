# ADR-083 — Editarea companiei: două chei, la nivel de companie, și prima impunere reală

- **Stare:** Acceptat — produs, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Deschide:** `OD-121`, `OD-122`
- **Nu închide:** `OD-108` *(cheia de identitate a titularului — aceeași lipsă, un nivel mai sus)*
- **Atinge:** `identity/permissions.py`, `identity/services/roles.py`,
  `tenancy/services/companies.py`, `accounting/periods/services/resolution.py`, `/api/v1/companies/<id>`,
  ecranul *Companii*
- **Legate:** [ADR-020](020-roluri-ca-date.md), [ADR-039](039-valuta-si-perioade.md),
  [ADR-040](040-crearea-tenantului-si-a-companiei.md), [ADR-075](075-identitatea-titularului.md)

## 1. Decizia

**Două chei, nu una:** `company.edit` și `company.close`. Închiderea unei companii e ireversibilă în
practică și n-are de ce să vină la pachet cu corectarea unei adrese.

**Ambele la nivel de companie**, nu de tenant. Un holding poate avea o persoană care răspunde de o
singură companie — e chiar cazul pentru care `company_access` există — iar o cheie de nivel tenant ar
însemna că cine poate corecta adresa uneia poate închide pe oricare dintre celelalte. Precedentul e
`company.revoke_access`, singura cheie de companie din catalog.

**Clicul pe rând, în lista de companii, duce la ecranul companiei**, nu la planul de conturi. Ecranul
poartă mai departe intrările în registre; altfel se pierde singura ușă de intrare, fiindcă bara
laterală nu arată secțiunile contabile cât timp nicio companie nu e selectată.

## 2. Trei lucruri măsurate, care schimbă ce înseamnă „adaugă cheile"

### 2.1 Catalogul de permisiuni nu e impus nicăieri

`require_permission` are **zero apelanți** în codul de producție; singurul e propriul corp, plus
testele. Nu există `permission_classes` în niciun view. Cele opt chei existente — `tenant.manage_roles`,
cele șase de engagement, `company.revoke_access` — au coloana `enforced_in` completată, dar codul
numit acolo nu le verifică.

Este exact modul de eșec pe care `ADR-020` îl descrie ca regulă 1 a catalogului: *„o cheie apare aici
doar când ceva o impune"*. Regula e scrisă; catalogul o încalcă în opt locuri.

**Consecința pentru acest ADR:** `company.edit` și `company.close` sunt **primele două chei impuse
efectiv** în produs. Asimetria e reală și se consemnează, nu se netezește — impunerea celorlalte opt
e `OD-121`, sesiune proprie, fiindcă fiecare cere decis *cine* o ține și ce se întâmplă cu tenanții
existenți.

### 2.2 `has_permission` nu poate vedea o cheie de nivel companie

Citește prin `role__membership__user_id`, adică prin rolul de membership. O permisiune ținută prin
`company_access.role` — singurul loc unde stă un rol de nivel companie — e invizibilă pentru ea.
Deci `company.revoke_access` n-ar fi fost verificabilă nici dacă cineva ar fi chemat funcția.

Se adaugă `has_company_permission` / `require_company_permission`, care citesc prin `company_access`
viu. Aceeași restricție ca la sora lor: răspund **doar despre apelant**, fiindcă `company_access` e
politicat `user_id = app.current_user_id()`, iar o întrebare despre altcineva ar întoarce un `False`
sigur și greșit (`OD-37`, a patra oară).

### 2.3 `company.status` nu e citit de nimic

`CompanyStatus` e definit, are `CHECK`, și nu apare în nicio interogare. Azi, `closed` nu înseamnă
nimic: e o valoare pe care n-o consultă niciun motor.

E aceeași formă de defect ca `covers_all_companies` înainte de F0.3.3 — *„coloana promitea o regulă
pe care n-o impunea nimeni"*. Un buton „Închide compania" peste starea asta ar fi a doua promisiune
de acest fel, și prima ar fi descoperită abia când cineva postează într-o companie închisă.

**Punctul de impunere e `assert_postable`**, adică exact acolo unde stă deja `R12`: motorul refuză, nu
interfața. O companie `closed` sau `suspended` nu primește postări, cu cod stabil propriu — refuzul
„compania nu primește postări" și refuzul „perioada nu e deschisă" au remedii diferite și nu se
confundă.

Citirea se face prin serviciul public al lui `tenancy`, nu prin model: `accounting` nu importă modele
din `platform.tenancy` (`D6`), iar serviciul acela există deja pentru exact acest motiv — moneda
funcțională a intrat pe el.

## 3. Ce se editează, și ce nu se editează ca un câmp printre altele

| Se corectează liber | Are consecințe ieșite din sistem |
|---|---|
| `legal_name`, `short_name`, adresa | `idno` — apare pe documentele emise (Spec A §12.1) |
| `cuatm_code`, `caem_code` | `functional_currency` — motorul de postare depinde de ea (`DN-04`, ADR-039) |
| | `fiscal_year_start_month`, `accounting_start_date` — prima perioadă e alegere ireversibilă |

Prima coloană se salvează normal. A doua urmează regula de prezentare din Spec A §12.1 — ecran
propriu, spune ce se strică, confirmare separată — **și se refuză cu totul odată ce compania are
înregistrări postate.** Motivul nu e prudență: `idno` a plecat pe documente, iar moneda și data de
început au fost deja folosite ca să dateze și să evalueze ce e în registru. Ce s-a tipărit nu se
retrage printr-un `UPDATE`.

## 4. Ce nu se decide aici

- **Ștergerea unei companii** — `OD-122`. Rămâne reală doar pentru compania introdusă din greșeală,
  fără nimic postat, iar „fără nimic postat" e o măsurătoare peste un set de tabele pe care nimeni nu
  l-a enumerat. Cere cheie proprie și o definiție verificabilă, nu un `DELETE` care s-ar lovi oricum
  de `PROTECT`.
- **Impunerea celorlalte opt chei** — `OD-121`.
- **Cheia de identitate a titularului** — `OD-108` rămâne deschisă. Acest ADR nu o închide: decide
  nivelul companie, nu nivelul tenant, iar `tenant.idno` se scrie în continuare prin comenzi de operator.

## 5. Consecințe

- **Devine posibil:** corectarea unei denumiri sau a unui cod de clasificare fără o comandă de
  operator; închiderea unei companii care nu mai lucrează, cu registrele intacte.
- **Devine imposibil, prin cod:** postarea într-o companie închisă; editarea IDNO-ului, a monedei sau
  a datei de început după prima înregistrare postată; editarea de către cine are acces la companie
  dar nu ține cheia.
- **Rămâne posibil, și e limita onestă:** cine ține `tenant.manage_roles` își poate acorda singur
  ambele chei. Asta e proprietatea lui `ADR-020` — permisiunea din care se derivă toate — nu o
  scăpare a acestui ADR.
- **Ce se verifică automat:**
  1. editarea fără cheie e refuzată, cu cod stabil, sub rolul aplicației;
  2. cheia ținută pe **altă** companie a aceluiași tenant nu deschide compania asta;
  3. IDNO-ul, moneda și data de început sunt refuzate la editare când există o înregistrare postată;
  4. o companie `closed` refuză postarea **din motor**, cu cod propriu, nu din interfață;
  5. `closed` nu atinge nimic din ce e deja în registru: aceleași rânduri, aceleași solduri, după.

## Surse

- Spec A §12.1 *(ce este ireversibil)*, §12.2 *(ordinea)*, `DN-04`.
- [ADR-020](020-roluri-ca-date.md) *(regula 1 a catalogului)*, [ADR-039](039-valuta-si-perioade.md) §6.
- Măsurat în cod la 2026-08-31: `require_permission` fără apelanți în producție; `has_permission`
  citind numai prin `membership`; `CompanyStatus` fără nicio citire; `evidenta_app` are `UPDATE` pe
  `company`; `assert_postable` e poarta unică a lui `R12`.
- Conversație 2026-08-31, întrebarea proprietarului: *„cum să șterg sau să editez o companie?"*
