# ADR-004 — Contextul de companie în sesiune

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `DN-11` (Spec A §2.6), `OD-08`
- **Afectează:** F0.1.2, F0.1.4, F0.1.5, și fiecare politică RLS pe tabelă company-scoped

## Context

Documentele de intrare numesc doar `app.tenant_id` și `app.actor_firm_id`. Majoritatea ledgerului
este însă company-scoped, iar un holding are mai multe companii sub același tenant. Întrebarea:
izolarea între companiile aceluiași tenant se face printr-o variabilă de sesiune obligatorie, sau
prin drepturile utilizatorului evaluate în politică?

## Opțiuni evaluate

1. **Fără `app.company_id`; politica verifică `has_company_access()`.** Izolarea e reală și e în
   bază. Dar „compania curentă" din interfață rămâne responsabilitatea aplicației, iar un raport
   scris greșit poate amesteca companiile aceluiași tenant fără să încalce vreo politică.
2. **`app.company_id` obligatoriu, impus de politică.** Imposibil de amestecat companii accidental.
   Dar orice operațiune legitim multi-companie — consolidare, dashboard de holding, contabilul care
   ține toate cele trei companii — devine cale privilegiată.
3. **`app.company_ids` ca listă**, calculată în aplicație. Acoperă ambele, dar mută calculul
   drepturilor exact în stratul pe care C3 îl scoate din ecuație.

## Decizie

**Opțiunea 1, plus `app.company_id` ca îngustare opțională.**

- `app.tenant_id` rămâne **obligatoriu** și fail-closed: absența lui produce eroare.
- `app.company_id` este **opțional**. Când e setat, îngustează suplimentar. Când nu e, politica
  permite toate companiile la care utilizatorul are drept.
- **Izolarea rămâne în bază**, exprimată prin `rls.has_company_access(company_id)` în politică — nu
  prin variabila de sesiune.

Șablonul pentru tabelele company-scoped devine:

```sql
USING (
    tenant_id = app.current_tenant_id()
    AND rls.has_tenant_access(tenant_id)
    AND rls.has_company_access(company_id)
    AND (app.current_company_id() IS NULL OR company_id = app.current_company_id())
)
```

`app.current_company_id()` returnează `NULL` când GUC-ul lipsește — spre deosebire de
`current_tenant_id()`, care ridică excepție. Diferența este intenționată și este chiar decizia.

### Motivul

Contabilul care ține toate cele trei companii ale unui holding, consolidarea și dashboard-ul au
nevoie legitimă de interogări peste companiile aceluiași tenant. Dacă `company_id` ar fi
obligatoriu, fiecare astfel de caz ar deveni cale privilegiată — iar lista căilor privilegiate
trebuie să rămână scurtă ca să însemne ceva.

## Consecințe

**`app.company_id` nu este mecanism de securitate.** Este mecanism de scoping pentru contextul de
interfață. Un cod care uită să îl seteze lărgește rezultatul la companiile la care utilizatorul are
oricum drept — este un bug de corectitudine, nu o scurgere de date. Această distincție trebuie să
fie clară pentru oricine citește o politică, altfel cineva va „întări" sistemul făcând variabila
obligatorie și va sparge consolidarea.

**Devine posibil:** consolidarea și dashboard-ul intern al holdingului fără cale privilegiată.

**Ce trebuie modificat:**

- Spec A §2.6 — decizia înlocuiește blocul `DN-11`
- Spec A §3.1 — `app.company_id` intră în tabelul de variabile, marcat opțional
- `infra/bootstrap/0002_app_context.sql` — funcția `app.current_company_id()`
- middleware și decoratorul Celery — setează `app.company_id` când contextul îl are

**Ce se verifică automat:**

- interogare fără `app.tenant_id` → eroare (IZ-30)
- interogare fără `app.company_id`, cu drepturi pe două companii → ambele vizibile, niciuna a altui
  tenant
- interogare cu `app.company_id` setat → doar acea companie
- `app.company_id` setat pe o companie la care utilizatorul nu are drept → zero rânduri, nu eroare;
  variabila îngustează, nu acordă

Ultimul caz este nou și intră în suita 1.

## Surse

- Spec A §2.6 (`DN-11`), §3.1
- `_input/evidenta-master-plan-v2.md` §4.3 — „contabilitatea este obligatoriu company-scoped"
