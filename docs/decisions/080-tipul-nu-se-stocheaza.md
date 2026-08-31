# ADR-080 — Tipul de cont nu se stochează: se descompune într-o capabilitate și un rând de firmă

- **Stare:** Acceptat — produs, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Închide:** întrebarea proprietarului *„poate un tenant să se transforme, după înregistrare, în
  holding sau în companie de contabilitate?"*; și jumătatea rămasă din `DN-26` — **unde** se atașează
  verificarea
- **Deschide:** `OD-119`
- **Atinge:** ecranul de înregistrare, `rls.provision_tenant` (`P-9`), `firm.status`,
  `platform/capabilities`, Spec A §12.2–12.3
- **Legate:** [ADR-060](060-vocabularul-capabilitatilor.md),
  [ADR-078](078-cine-poate-crea-un-tenant.md), [ADR-081](081-revendicarea-optionala.md)

## 1. Întrebarea, și de ce răspunsul ei desființează întrebarea

Propunerea era ca omul să declare la înregistrare ce este — holding, companie de contabilitate, sau
companie simplă — toate primind tenant și companie, dar numai primele două putând adăuga alte
companii. Iar întrebarea care o însoțea: *se poate transforma mai târziu, poate cu ajutorul unui
administrator?*

**Nu e o transformare.** Măsurat în cod, cele trei „tipuri" se descompun în două fapte care există
deja, iar niciunul nu e un tip:

| Ce alege omul la înregistrare | Ce se provizionează | Unde e în cod |
|---|---|---|
| companie simplă | `Tenant` + `Company` | `rls.provision_tenant`, `rls.provision_company` ([ADR-040](040-crearea-tenantului-si-a-companiei.md)) |
| holding | idem, plus activarea `multi_company` | `CapabilityActivation`; cheia e în vocabularul curatoriat din [ADR-060](060-vocabularul-capabilitatilor.md) §3 |
| companie de contabilitate | idem, plus un rând `Firm` legat `OneToOne` de tenantul lui | `platform/engagement/models.py` |

Deci „a te transforma în holding" e o activare de capabilitate, iar „a deveni firmă de
contabilitate" e un rând. Nimic de migrat, niciun ledger atins, nicio companie recreată. Întrebarea
despre transformare era grea doar cât timp presupunea că tipul e stocat undeva.

## 2. Ce nu se adaugă: `tenant.kind`

Coloana nu se creează, sub niciun nume — `kind`, `type`, `account_type`, `user_type`.

Motivul nu e purismul. **O coloană de tip devine o ramificație în logică**, iar în ziua în care un
serviciu conține `if tenant.kind == 'accounting'`, transformarea devine exact migrarea pe care
absența coloanei o evită azi. Este aceeași familie cu booleanul de capabilitate pe care `R25` îl
interzice: o stare care ar trebui să aibă dată efectivă și istoric, colapsată într-o valoare care nu
le are.

Se păstrează în schimb **consecințele**, fiecare verificabilă și reversibilă separat: activarea cu
dată efectivă, rândul `Firm`, iar alegerea de la înregistrare rămâne în rândul de audit al lui `P-9`
— care înregistrează deja creatorul și subdomeniul sau IDNO-ul. Cifra pentru marketing se ia din
`privileged_access_log`, nu dintr-o coloană citită de logica de business.

## 3. Holdingul: autoservire, și regula e o consecință, nu o permisiune

Formularea „doar holdingurile pot adăuga companii" produce un zid: o companie simplă care cumpără o
filială lovește un refuz pentru un fapt normal de business, și sună la suport. Un tichet pentru ceva
ce sistemul ar trebui doar să înregistreze.

Formularea corectă: **a doua companie activează `multi_company`**, cu efectul comercial arătat
înainte de confirmare, fiindcă schimbă grila (Spec A §10.3 — planul propune un set implicit de
capabilități, nu îl definește rigid). Nu se cere administrator, nu se cere aprobare.

Observația care arată de ce e capabilitate și nu tip: **nici „firmă de contabilitate" nu înseamnă o
singură companie.** O firmă cu două persoane juridice proprii are nevoie de aceeași activare.
`multi_company` înseamnă *mai mult de una*, nu *ești holding*.

## 4. Firma de contabilitate: verificare, atașată statutului și nu momentului lui

Statutul de firmă merită un standard, iar holdingul nu, dintr-un motiv care nu e de mărime:
**firma capătă putere asupra conturilor terților** — creează tenanți pentru alții, trimite invitații
de angajament, va citi portofoliu cross-tenant. Holdingul capătă doar o a doua companie a lui.

Iar standardul se atașează **statutului**, nu momentului în care e cerut:

> Dacă la înregistrare declari „sunt firmă de contabilitate" gratis, iar mai târziu același lucru
> cere aprobare, ai făcut minciuna mai ieftină decât adevărul. Toți vor bifa „contabil" la
> înregistrare, ca să nu ceară voie mai târziu.

### 4.1 Poarta stă pe acțiune, nu pe cont

Aceasta e forma care face verificarea manuală suportabilă. `firm.status` primește o valoare nouă,
`pending_verification`, iar `FirmStatus` devine
`('pending_verification','active','suspended','closed')`.

| Ce poate o firmă `pending_verification` | Ce așteaptă `active` |
|---|---|
| există ca rând, cu tenantul și companiile ei | crearea unui tenant **pentru altcineva** (`P-9`, canalul „firmă") |
| își ține propria contabilitate, integral | trimiterea unei invitații de angajament către un tenant existent |
| își invită propriii angajați | — |

Contabilul care se înscrie vineri seara își face planul de conturi în weekend și adaugă clienți luni.
Fără această separare, aprobarea manuală ar fi un blocaj la înregistrare, iar recomandarea ar fi
fost alta.

Cele două acțiuni se verifică într-un singur loc, în SQL, acolo unde apelantul nu poate uita:
`rls.provision_tenant` refuză un apelant a cărui firmă nu e `active`, la fel serviciul de invitație.
Nu în interfață.

### 4.2 Standardul de probă e manual, și e explicit că e manual

Verificarea automată contra registrului de stat n-are sursă — e `OD-116`, deschisă în aceeași zi, și
nu se închide căutând mai bine. Deci: aprobare de către un `admin` din `platform_staff`
([ADR-076](076-planul-de-control-al-platformei.md)), pe probă documentară, cu rândul de aprobare
înregistrat.

Amânarea cu declanșator s-a respins pentru un motiv precis: ar însemna statut de firmă **autodeclarat
până la prag**, adică exact situația pe care argumentul de mai sus o elimină, liberă pe toată
perioada dinaintea declanșatorului.

**`OD-119`** ține ce nu se poate scrie acum: ce documente se acceptă ca probă, cine aprobă când
proprietarul nu mai e singurul om, și declanșatorul automatizării — care e conjuncția dintre `OD-116`
(sursa există) și volumul care depășește un om.

## 5. Ecranul de înregistrare rămâne, dar întreabă altceva

Nu **„ce ești"** — care cere o autodefinire și produce o coloană — ci **„ce vrei să faci întâi"**,
care alege rețeta de provizionare și primul ecran de după:

| Răspuns | Rețeta | Primul ecran |
|---|---|---|
| țin contabilitatea clienților | tenant + companie + rând `Firm` `pending_verification` | „adaugă primul client" *(după verificare)* |
| am mai multe companii | tenant + companie + activare `multi_company` | „adaugă a doua companie" |
| am o companie | tenant + companie | „planul de conturi" |

Ordinea de onboarding din Spec A §12.2 rămâne neatinsă și e oricum fixă, cu alegeri ireversibile în
ea: utilizator → al doilea factor → tenant → companie → capabilități → plan de conturi → prima
perioadă → solduri inițiale. Răspunsul de la înregistrare nu schimbă ordinea; alege ce rânduri se
scriu la pasul 5 și unde aterizează omul după pasul 8.

Nicăieri în cele trei rețete nu se scrie un tip.

## 6. Consecințe

- **Devine posibil:** trecerea de la o companie la un grup fără intervenție, în orice zi; devenirea
  unei firme de contabilitate fără să reînregistrezi nimic.
- **Devine imposibil:** ramificarea logicii pe tipul de cont — nu există unde s-o citească.
- **Devine ieftin, deliberat:** greșeala de la înregistrare. Cine bifează greșit adaugă pasul care-i
  lipsea; nu contactează suportul.
- **De modificat ca urmare:** `FirmStatus` capătă `pending_verification` (migrare aditivă, `C5`);
  `rls.provision_tenant` verifică statutul firmei apelantului pe canalul „firmă";
  Spec A §12.3 primește rețetele; [ADR-078](078-cine-poate-crea-un-tenant.md) §3 rămâne valabil pe
  canale și capătă poarta de aici.
- **Ce se verifică automat:** (a) gardianul de model refuză o coloană `kind`/`type`/`account_type` pe
  `tenant` — regula are sens doar dacă e impusă, altfel e o intenție; (b) un test că
  `provision_tenant` refuză un apelant din firmă `pending_verification`, și îl acceptă după
  aprobare; (c) un test că a doua companie într-un tenant fără `multi_company` e refuzată de
  activare, nu de un `if`.

## Surse

- Spec A §10.3 (planul propune, nu definește), §12.2 (ordinea), §12.3 (căile de intrare).
- [ADR-040](040-crearea-tenantului-si-a-companiei.md), [ADR-060](060-vocabularul-capabilitatilor.md)
  §3, [ADR-076](076-planul-de-control-al-platformei.md),
  [ADR-078](078-cine-poate-crea-un-tenant.md).
- Măsurat în cod la 2026-08-31: `platform/capabilities/models.py` (`capability_key` fără CHECK),
  `platform/engagement/models.py` (`Firm.tenant` `OneToOne`, `FirmStatus`),
  `platform/tenancy/models.py` (`Tenant` n-are coloană de tip).
- `CLAUDE.md` `R25`, `C5`, `C36`.
- Conversație 2026-08-31.
