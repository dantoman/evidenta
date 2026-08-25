# ADR-035 — Delegarea nu este tranzitivă

- **Status:** Acceptat — tehnic și de produs
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** — *(nu era în registru; **deschide `OD-54`**)*
- **Afectează:** `infra/bootstrap/0003_access_predicates.sql`, Spec A §1.4, §7.1, §8.7,
  `CLAUDE.md` §1.1 (`R27`), suita de penetrare

## Context

Modelul are o singură formă de acces delegat: `Firm → Engagement → Tenant`. Firma este ea însăși
tenant, deci poate fi la rândul ei client al altei firme — cazul real fiind cel banal: un cabinet
își dă propria contabilitate altui cabinet.

Întrebarea care nu era pusă nicăieri: **cabinetul B, care ține contabilitatea cabinetului A,
primește ceva din clienții lui A?**

Măsurat pe predicatul în vigoare: nu. `rls.has_tenant_access` caută un engagement **activ** între
firma din `app.actor_firm_id` și tenantul cerut, plus apartenența activă a utilizatorului la
tenantul acelei firme. Un singur salt. Nu urcă niciun lanț, fiindcă nu are cum: nu există nici
recursie, nici a doua interogare.

Deci proprietatea e adevărată — **din formă, nu din intenție declarată.** Nimic nu o numea, niciun
test nu o acoperea, iar predicatul este exact genul de cod care se „extinde" pentru un motiv
plauzibil: cabinetul A are vârf de sezon, subcontractează o lună, cineva adaugă un `JOIN`. Din acel
moment clientul nu mai poate răspunde la „cine îmi vede datele", iar revocarea nu mai înseamnă ce
scrie în contract.

## Opțiuni evaluate

1. **Delegare tranzitivă cu acordul clientului** — un indicator pe engagement care permite firmei
   să cedeze accesul mai departe. *Avantaje:* acoperă subcontractarea fără ca clientul să semneze cu
   cineva nou. *Dezavantaje:* semantica revocării se destramă — clientul revocă relația cu A și
   trebuie să știe singur pe cine mai atinge asta; lista persoanelor care îi ating datele devine
   nemărginită; fiecare test de izolare capătă o dimensiune în plus, iar predicatul devine recursiv
   pe calea fierbinte. *Cost de schimbare:* mare — se scrie în predicat, deci se scoate greu.
2. **Fără delegare tranzitivă.** Cabinetul care vrea să subcontracteze cere clientului să semneze un
   al doilea engagement, direct cu al doilea cabinet. *Avantaje:* revocarea rămâne o singură
   operațiune cu un singur înțeles; clientul vede și decide fiecare relație; predicatul rămâne cu un
   salt. *Dezavantaje:* subcontractarea cere o semnătură a clientului — ceea ce este, de fapt,
   comportamentul dorit. *Cost de schimbare:* mic; `ADR-018` face deja posibile mai multe firme per
   tenant, separate prin scope de module, deci varianta legitimă există deja.
3. **Se lasă nedeclarat** — adevărat prin formă, ca azi. *Avantaje:* niciunul. *Dezavantaje:* o
   proprietate de securitate care ține de forma întâmplătoare a unei funcții dispare la prima
   refactorizare făcută cu bună-credință.

## Decizie

**Opțiunea 2.**

Invariantul, formulat ca să poată fi verificat: **`rls.has_tenant_access` nu înlănțuie niciodată
două relații.** Firma din `app.actor_firm_id` trebuie să aibă ea însăși un engagement viu cu
tenantul cerut. Intră în `CLAUDE.md` ca **`R27`**.

**Direcția inversă rămâne permisă și nu este o excepție:** cabinetul A poate fi clientul
cabinetului B pentru propria contabilitate. B primește exact ce are A în propriile registre —
inclusiv faptul că A facturează clientul X, fiindcă factura aceea este document al lui A. Nu
primește nimic din registrul lui X. Distincția nu e subtilă: datele lui A despre relația cu X
aparțin lui A; datele lui X aparțin lui X.

## Consecințe

- **Devine imposibil:** un cabinet nu poate ceda accesul la clienții săi. Dacă piața cere
  subcontractare, răspunsul este al doilea engagement, nu un indicator nou.
- **Devine vizibil:** lanțul `client → cabinet → cabinetul cabinetului` se oprește la primul salt,
  și există un test care cade dacă cineva îl prelungește.
- **De modificat:** `CLAUDE.md` §1.1 primește `R27`; Spec A §1.4 numește invariantul; §8.7 capătă
  `IZ-68` și `IZ-69`.
- **Se verifică automat:** `backend/tests/isolation/test_engagement_access.py` —
  `test_delegation_does_not_chain` (`IZ-68`, la nivel de tenant) și
  `test_delegation_does_not_chain_at_company_level` (`IZ-69`, la nivel de companie). Ambele conțin o
  aserțiune de control care demonstrează că **primul** salt chiar există; fără ea, un test care
  trece fiindcă lanțul n-a fost construit ar demonstra zero.
- **Nu răspunde la întrebarea vecină:** clientul vede *nominal* cine îi atinge datele și poate bloca
  o persoană fără să rupă relația cu cabinetul? Aceea este funcționalitate de încredere, nu
  invariant de izolare, și cere o decizie proprie despre punctul de impunere. → **`OD-54`**, nouă.

## Surse

- `infra/bootstrap/0003_access_predicates.sql`, funcția `rls.has_tenant_access` — citită și
  măsurată prin suita de penetrare, 2026-08-25.
- Spec A §1.3 („Distincția care nu se colapsează"), §1.4, §4.3.
- [ADR-018](018-engagementuri-multiple.md) — mai multe firme per tenant, separate prin scope.
