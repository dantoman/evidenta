# ADR-020 — Rolurile sunt date compozabile, peste un catalog fix de permisiuni

- **Status:** Acceptat — decizie de produs și model, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `DN-08` (Spec A §11.8)
- **Afectează:** `membership.role`, `company_access.role`, F0.3.7, fiecare ecran de administrare

## Context

`membership.role` și `company_access.role` există ca `text` fără `CHECK` din F0.3.2, tocmai ca
vocabularul să nu fie închis într-o migrare. Spec A §11.8 punea trei opțiuni: set fix în cod, roluri
ca date, sau set fix plus permisiuni delegabile.

## Decizie

**Rolurile sunt date, per tenant, compozabile din permisiuni** — iar un administrator al tenantului
cu dreptul potrivit le poate crea și modifica.

Riscul evident al acestei alegeri este că autorizarea ajunge într-o tabelă pe care clientul o
editează, deci și-ar putea acorda drepturi pe care produsul nu le-a anticipat. **Nu se rezolvă prin
încredere, ci prin construcție:**

### Catalogul de permisiuni este fix, în cod

Clientul compune **roluri**, nu **permisiuni**. Cheile de permisiune sunt o listă închisă,
versionată în `platform/identity`, impusă prin cheie străină către un tabel global alimentat din
cod. Un rol poate conține doar permisiuni pe care produsul le cunoaște și le verifică undeva.

Consecința care contează: nu există combinație de roluri care să producă un drept neanticipat.
Clientul poate greși *cui* îi dă un drept — asta e treaba lui — dar nu poate inventa un drept.

### Trei roluri de sistem, care nu se șterg și nu se golesc

`owner` la nivel de tenant, plus echivalentele minime la nivel de companie. Fără ele, primul client
care își editează rolurile greșit rămâne blocat în afara propriului tenant, iar recuperarea e o
intervenție manuală în producție.

Regulile: rolurile de sistem nu se șterg, nu pot pierde permisiunea de administrare a rolurilor, și
ultimul utilizator cu `owner` activ nu poate fi retrogradat.

### Editarea rolurilor este ea însăși o permisiune

`tenant.manage_roles`. Cine o are poate modifica roluri; cine nu, nu. Acordarea ei este audit
obligatoriu — este permisiunea din care se pot deriva toate celelalte.

## Consecințe

- **Model nou:** `permission` (global, alimentat din cod), `role` (nivel tenant), `role_permission`,
  iar `membership.role` și `company_access.role` devin chei străine către `role`.
- `CHECK`-ul pe `role` nu mai apare: unicitatea și existența le asigură cheia străină.
- **F0.3.7 se deblochează.**
- Migrarea rolurilor de sistem se face la crearea tenantului, nu prin fixture globală: rolurile
  aparțin tenantului.
- Ecranele de administrare a rolurilor sunt F0.10+; modelul intră acum.

## Ce rămâne în afara deciziei

Confidențialitatea salariilor individuale față de **firma** de contabilitate rămâne guvernată de
`module_key` (ADR-019), nu de roluri. Aici se decide ce poate face **omul** în interiorul unei
organizații; acolo, ce poate vedea **firma** la client. Nu se închid una prin cealaltă.

## Surse

- Spec A §11.8, §1.6, §1.7
- [ADR-019](019-vocabular-scope.md) — distincția firmă/om
