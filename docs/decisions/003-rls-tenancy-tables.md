# ADR-003 — Politica RLS pentru tabelele care definesc tenancy-ul

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `DN-12` (Spec A §2.7); parțial `OD-07`
- **Afectează:** F0.1.1, F0.1.3, F0.2.2, F0.3.1–F0.3.4, și forma fiecărei politici RLS din sistem

## Context

Politicile RLS de pe tabelele business trebuie să răspundă la întrebarea „are utilizatorul curent
drept asupra acestui rând", iar răspunsul se află citind `membership`, `engagement` și
`company_access`. Acele tabele au ele însele politici. O politică ce interoghează o tabelă a cărei
politică o interoghează pe prima este recursivă.

PostgreSQL nu degradează performanța în acest caz: ridică eroare
(`infinite recursion detected in policy for relation ...`). Nu este o optimizare de evitat, este o
condiție de funcționare.

A doua constrângere vine dintr-o regulă pe care ne-am impus-o singuri: `FORCE ROW LEVEL SECURITY`
este obligatoriu pe fiecare tabelă business (R2). Tutorialele de `SECURITY DEFINER` presupun că
proprietarul tabelei ocolește politicile. Cu `FORCE`, nu le mai ocolește. O funcție
`SECURITY DEFINER` deținută de rolul de migrare ar fi deci supusă acelorași politici — și
recursiunea revine pe ușa din dos.

## Opțiuni evaluate

1. **Politici auto-referențiale scrise direct în politică.** Funcționează doar dacă subinterogarea
   ocolește RLS, adică tot printr-o funcție privilegiată — dar cu logica de acces duplicată în două
   locuri, care vor diverge.
2. **Predicate `SECURITY DEFINER`, apelate din politici.** Un singur loc unde trăiește logica de
   acces. Riscul se concentrează în corectitudinea acelor funcții.
3. **Tabelele de tenancy inaccesibile rolului de aplicație**, expuse doar prin funcții care
   returnează exact ce are voie utilizatorul să vadă. Cea mai strictă; rescrie ORM-ul pentru aceste
   entități — `Membership.objects.filter(...)` nu mai funcționează.

## Decizie

**Opțiunea 2**, cu un al treilea rol de bază de date.

### Trei roluri, nu două

| Rol | Atribute | Rol în sistem |
|---|---|---|
| `evidenta_owner` | `LOGIN`, `NOBYPASSRLS` | rol de migrare; deține tabelele; nu se folosește la runtime |
| `evidenta_app` | `LOGIN`, `NOBYPASSRLS`, fără ownership | rolul aplicației și al testelor |
| `evidenta_rls` | **`BYPASSRLS`**, `NOLOGIN` | deține **exclusiv** predicatele de acces; nimic altceva |

`evidenta_app` primește **doar `EXECUTE`** pe predicate. Nu primește `evidenta_rls` ca membru.
`evidenta_owner` primește `evidenta_rls` ca membru, strict pentru a putea crea și înlocui funcțiile
în migrații — atributul `BYPASSRLS` nu se moștenește prin apartenență, ci se activează doar prin
`SET ROLE`.

### Predicatele

În schema **`rls`**, deținută de `evidenta_rls`, `SECURITY DEFINER`, cu `search_path` fixat în
definiție. Funcțiile de context (care citesc doar GUC-uri, fără privilegii) rămân în `app`:

- `app.current_user_id()` — citește GUC-ul de sesiune, fail-closed (schema `app`)
- `rls.has_tenant_access(uuid)` — membru activ al tenantului **sau** engagement activ al firmei în
  numele căreia acționează utilizatorul
- `rls.has_company_access(uuid)` — drept efectiv asupra companiei
- `rls.can_see_engagement(uuid, uuid)` — utilizatorul este membru al tenantului client **sau** al
  tenantului firmei

`search_path` fixat nu este cosmetic: fără el, o funcție `SECURITY DEFINER` deținută de un rol cu
`BYPASSRLS` este un vector de escaladare de privilegii.

Marcate `STABLE`. Dacă apare o problemă de performanță pe dashboard, setul rezolvat se cachează per
tranzacție — **dar nu acum, fără măsurătoare** (Spec A §2.8).

### Politicile

**Tabelele business** apelează predicatele, niciodată tabelele de tenancy direct.

**Tabelele de tenancy** primesc politici simple, neîncrucișate:

| Tabelă | Politică |
|---|---|
| `user` | `id = app.current_user_id()` |
| `membership` | `user_id = app.current_user_id()` |
| `company_access` | `user_id = app.current_user_id()` |
| `engagement` | `rls.can_see_engagement(client_tenant_id, firm_id)` — vizibil ambelor părți |
| `tenant` | `rls.has_tenant_access(id)` |
| `firm` | membru al tenantului firmei, sau tenant cu engagement viu asupra firmei |

Ultimele două nu erau enumerate explicit în decizie, dar decurg din același principiu: apelul
predicatului nu recursează, pentru că predicatul rulează sub un rol cu `BYPASSRLS`.

### Ce nu apără RLS — model de amenințare

**RLS te apără de un filtru uitat în cod. Nu te apără de un server de aplicație compromis** — acela
poate seta orice GUC, deci poate revendica orice `app.tenant_id` și orice `app.user_id`.

Sunt două amenințări diferite, și numai prima este acoperită de acest ADR. A doua se tratează prin
securizarea serverului, a secretelor și a lanțului de livrare — nu prin politici. Confuzia dintre
ele produce fie fals confort, fie efort irosit în a „întări" RLS împotriva a ceva ce nu poate opri.

## Verificat empiric

Rulat pe PostgreSQL 18.6, cu tabele de tenancy minime, `FORCE ROW LEVEL SECURITY` activ pe toate,
politicile de mai sus, și interogări sub `evidenta_app`. Rezultatele au corectat două afirmații pe
care le făcusem din raționament.

**1. Recursivitatea este reală, dar numai în forma naivă.** O politică pe `membership` care conține
o subinterogare directă pe `membership` produce:

```
ERROR:  infinite recursion detected in policy for relation "membership"
```

Confirmă că opțiunea 1 nu este o alegere de stil: nu funcționează.

**2. Indirecția prin `SECURITY DEFINER` nu produce recursiune — dar fără `BYPASSRLS` eșuează
silențios.** Aceasta este nuanța care contează la depanare. Cu rolul corect configurat, predicatul
returnează corect. Cu `BYPASSRLS` scos de pe `evidenta_rls`, interogarea **nu dă eroare**: predicatul
citește `membership` ca `evidenta_rls`, nicio politică nu se aplică acelui rol, default-deny
returnează zero rânduri, predicatul întoarce `false`, iar utilizatorul vede o bază goală.

Eșecul este **fail-closed, dar tăcut și total**. Un inginer care caută o eroare nu va găsi niciuna;
va găsi un sistem în care nimeni nu vede nimic. De aceea verificarea din `0001_roles.sql` — care
refuză migrarea dacă `evidenta_rls` nu are `BYPASSRLS` sau dacă `evidenta_app` îl are — nu este
ceremonie, ci singurul semnal.

**3. Predicatele trăiesc în schema `rls`, nu în `app`.** Descoperit la execuție: rolul de rezolvare
are `USAGE` pe `app`, nu `CREATE`, deci nu poate crea funcții acolo; iar a crea în `app` și a
transfera proprietatea cere ca noul proprietar să aibă `CREATE` pe `app` — exact privilegiul
permanent pe care separarea îl evită. O schemă proprie, deținută de `evidenta_rls`, rezolvă
problema și face din „ce rulează privilegiat" o proprietate a schemei: tot ce e în `rls` ocolește
politicile, nimic altceva nu o face. `evidenta_owner` primește `USAGE` și `EXECUTE` pe ea, ca să
poată **referi** predicatele când creează politici.

**4. `FORCE ROW LEVEL SECURITY` blochează și rolul de migrare.** Cu politici scrise `TO evidenta_app`,
`evidenta_owner` nu are nicio politică aplicabilă, deci nu poate nici citi, nici insera în tabelele
de tenancy. Consecință operațională pentru F0.3 și F0.1.6: **datele de bootstrap se inserează
înainte de activarea politicilor**, sau printr-o cale explicită. Nu este un defect — este exact ce
înseamnă `FORCE` — dar surprinde prima migrare care încearcă să semene date.

Scenariile rulate, toate cu rezultatul așteptat: IZ-01, IZ-03, IZ-08, IZ-10, IZ-11 (engagement
expirat, fără ca vreun job să fi rulat), IZ-18 (împrumut de `actor_firm_id`), IZ-30, IZ-50.
Proba este în [`infra/rls/smoke_test.sql`](../../infra/rls/smoke_test.sql).

## Consecințe

**Devine posibil:**

- politicile business se scriu o singură dată, ca șablon (Spec A §2.5, §2.6)
- logica celor două căi de acces trăiește într-un singur loc
- funcțiile pot fi testate direct, independent de suita de izolare

**Devine imposibil sau scump:**

- un membru **nu** vede ceilalți membri ai tenantului său prin ORM. Politica pe `membership` este
  strict `user_id = current_user_id()`. Ecranul „echipa mea" are nevoie de un serviciu dedicat, nu
  de un queryset. Consecință acceptată; forma acelui serviciu rămâne de decis — **`OD-37`**.
- orice interogare care are nevoie de vizibilitate laterală pe tenancy trece printr-o funcție
  explicită, ceea ce face costul vizibil la scriere

**Ce trebuie modificat:**

- Spec A §2.2 — trei roluri în loc de două
- Spec A §2.4 — predicatele aparțin lui `evidenta_rls`, nu lui `evidenta_owner`
- Spec A §2.7 — decizia înlocuiește blocul `DN-12`
- Spec A — se adaugă secțiunea de model de amenințare
- `infra/rls/exceptions.toml` — cele cinci tabele de tenancy au formă de politică diferită, iar
  gardianul de model trebuie să verifice **forma așteptată**, nu să le sară

**Ce se verifică automat:**

| Verificare | Unde |
|---|---|
| `evidenta_app` nu are `BYPASSRLS` și nu deține tabele | suita 2, IZ-75 |
| `evidenta_app` nu este membru al lui `evidenta_rls` | suita 2 |
| fiecare predicat are `search_path` fixat și e `SECURITY DEFINER` | suita 2 |
| predicatele returnează corect pentru: membru activ, membru suspendat, engagement activ, expirat, revocat, firmă nerevendicată | teste proprii, F0.1.3 |
| tabelele de tenancy au exact forma de politică declarată | suita 2 |

Testele predicatelor **nu** fac parte din suita de izolare. Sunt suplimentare, pentru că acele
funcții sunt singurul loc din sistem unde o greșeală deschide toate datele tuturor tenanților.

## Surse

- Spec A §2.7 (`DN-12`), §2.4, §2.2
- `_input/evidenta-master-plan-v2.md` §4.2
- `_input/evidenta-master-plan-v2-amendament-1.md` §A.11, §D.3
