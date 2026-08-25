# Evidenta.md — Master Product & Implementation Plan

**Versiunea 2** — revizuire structurală

---

## 0. Ce s-a schimbat față de versiunea 1

| Domeniu | V1 | V2 | Motiv |
|---|---|---|---|
| Tenancy | Absent (`Account → Company`) | Strat zero explicit: Tenant / Company / Firm / Engagement | Determină fiecare tabelă din sistem; retrofit imposibil |
| Payroll | Faza 4 | Faza 2 | Compania de servicii — primul segment țintă — are angajați |
| Raportare statutară | „basic" în Faza 2 | Pachet complet în Faza 2 (SFS, CNAS, CNAM, BNS, SNC) | Este produsul, nu un accesoriu |
| Active fixe | Faza 3 | Faza 2 | Amortizarea afectează rezultatul și situațiile financiare |
| Workspace contabil | Absent | Faza 3, fază proprie | Este canalul principal de distribuție |
| Reguli fiscale | Sub `tax/` | Serviciu transversal | Payroll depinde de ele la fel ca TVA |
| Migrare 1C | Faza 3 | Livrare incrementală F1→F3 | Este instrumentul de vânzare, nu o funcție |
| Faze | 8 | 5 angajate + direcție | Fazele 6–8 erau promisiuni fără termen |
| DB dedicat enterprise | Faza 8 | Eliminat din roadmap | Dublează suprafața de testare; rupe dashboard-ul transversal |
| Conformitate ca operațiune | Absent | Funcție permanentă, secțiunea 6 | Riscul operațional numărul unu |
| Restaurare / offboarding | Absent | Secțiunea 11 | Cerere reală frecventă; obligație legală de retenție |

---

## 1. Viziune și poziționare

Evidenta.md este o platformă cloud construită exclusiv pentru Republica Moldova, cu obiectivul de a înlocui gradual ecosistemul 1C din întreprinderile moldovenești.

**Formularea internă:** entitățile core sunt ERP-ready, livrarea este accounting-first.

Diferența față de „construim un ERP" nu este semantică. Prima formulare justifică echipei să construiască module. A doua justifică doar să nu se blocheze structural. Ce vinde în Moldova este conformitatea — SNC, TVA, e-Factura, IPC, rapoartele către SFS, CNAS, CNAM și BNS. Aceea este partea pe care nimeni nu vrea să o construiască și care te apără de concurență.

**Poziționare comercială:** „De la prima factură până la ERP."

Promisiunea explicită se limitează la traseul acoperibil credibil în 24 de luni: contabilitate, vânzări, achiziții, stocuri, salarizare, active, multi-company. Producția, MRP-ul și WMS-ul rămân direcție de produs, nu argument de vânzare, până când există.

### Principiul North Star

> Un document se introduce o singură dată, la locul unde se produce operațiunea economică, iar toate consecințele — stoc, contabilitate, TVA, cost, cash-flow, raportare — sunt generate automat de Evidenta.

### Principiile derivate

**No Re-platforming** (nu „No Migration"). Compania nu schimbă sistemul și nu pierde istoricul când crește. Dar fiecare capabilitate nouă are o dată efectivă și, uneori, un pas de inițializare. A promite „zero migrare" este fals și va genera bug-uri raportate.

**Progressive Complexity.** Interfața arată doar complexitatea necesară acum. Dar modelul cere întotdeauna minimul structural pentru toate modulele viitoare. Se ascund câmpuri opționale, niciodată câmpuri structurale.

---

## 2. Invarianți arhitecturali

Reguli care nu se negociază pe durata proiectului. Orice excepție se documentează explicit și se aprobă.

1. **Niciun modul business nu scrie în ledger.** Toate trec prin Posting Engine, prin evenimente contabile.
2. **Ledgerul postat este imutabil.** Corecția se face prin storno și reînregistrare, niciodată prin UPDATE.
3. **Nicio interogare nu rulează fără context de tenant.** Absența contextului înseamnă refuz, nu acces total.
4. **Regulile fiscale și legislative sunt date versionate**, cu `valid_from` / `valid_to`. O modificare legislativă este un INSERT, nu un deployment.
5. **Un singur codebase.** Diferențierea se face prin feature flags și release rings, niciodată prin versiuni per tenant.
6. **Modificările de conformitate nu sunt opționale** pentru niciun tenant și nu sunt niciodată paywall.
7. **Tenantul este proprietarul datelor.** Firma de contabilitate are acces delegat și revocabil.

---

## 3. Straturi arhitecturale

```
                    React + TypeScript
                            │
                     Django REST API
                            │
              ┌─────────────┴─────────────┐
              │   Tenant Context Layer    │   ← strat zero
              └─────────────┬─────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
 PLATFORM              FINANCIAL CORE          OPERATIONS
    │                       │                       │
 Identity              Accounting              Sales
 Tenancy               Fiscal Rules            Purchases
 Engagement            Tax / TVA               Inventory
 Documents             Banking                 Pricing
 Numbering             Cash                    Payroll
 Audit                 AR / AP                 HR
 Master Data           Fixed Assets
 Notifications         Statutory Reporting
    │                       │                       │
    └───────────────────────┼───────────────────────┘
                            │
                     INTEGRATIONS
                     SFS · CNAS · CNAM · BNS · BNM · Bănci · 1C
                            │
                   PostgreSQL + RLS
                   Redis · Celery · S3
```

**Modular monolith.** Nu microservicii. Modulele au ownership clar, modele proprii, servicii proprii, evenimente și limite explicite — astfel încât unul să poată fi extras ulterior fără rescriere.

**Graful de dependențe este aciclic.** Regulile fiscale nu depind de niciun modul business. Accounting nu depinde de Sales. Sales și Payroll depind amândouă de reguli fiscale și emit evenimente către Posting Engine.

---

## 4. Tenancy și identitate — Faza 0

Aceasta este componenta care trebuie fixată înaintea oricărei alte decizii de schemă.

### 4.1 Entități

| Entitate | Rol |
|---|---|
| **Tenant** | Clientul SaaS, proprietarul datelor. Are subdomeniu. |
| **Company** | Entitatea juridică cu ledger propriu. Un tenant poate avea mai multe (holding). |
| **Firm** | Firma de contabilitate. Este ea însăși un actor, cu propriul tenant pentru propria contabilitate. |
| **Engagement** | Relația Firm → Tenant. Delegată, revocabilă, cu `valid_from` / `valid_to`, scope și stare. |
| **User** | Identitate **globală**. Un contabil are un singur cont pentru toți clienții. |
| **Membership** | Apartenența unui user la un tenant, cu roluri. |
| **CompanyAccess** | Accesul unui user la o companie, cu rol. |

**Distincția critică.** Holdingul și firma de contabilitate nu se modelează identic:

```
Holding                          Firmă de contabilitate
──────────────────               ──────────────────────
Tenant: ABC Holding              Firm: Conta Expert
├── Company Moldova SRL          ├── Engagement → Tenant: Client A
├── Company Logistics SRL        ├── Engagement → Tenant: Client B
└── Company Retail SRL           └── Engagement → Tenant: Client C
   (proprietate comună)             (acces delegat, revocabil)
```

Dacă se colapsează în același model, schimbarea contabilului devine migrare de date pe un ledger imutabil cu ani de istoric, subdomeniul aparține contabilului și nu clientului, iar clienții rămân captivi dacă firma se închide.

### 4.2 Izolare — Row Level Security

Aplicație și bază de date, două bariere independente.

**Politica admite două căi de acces:** membru al tenantului, sau engagement activ al firmei asupra tenantului. Contextul de sesiune conține `app.tenant_id` și `app.actor_firm_id`.

Cerințe care nu sunt opționale:

- **`FORCE ROW LEVEL SECURITY`** și rol de aplicație separat de rolul de migrare. Implicit, owner-ul tabelei ocolește politicile — RLS activat fără asta este inefectiv.
- **Comportament fail-closed.** Context absent înseamnă zero rânduri sau eroare. Niciodată „toate".
- **Tot request-ul într-o tranzacție.** `SET LOCAL` trăiește doar în tranzacție. Trecerea ulterioară la pgbouncer în transaction pooling sparge izolarea silențios altfel.
- **Celery cu context explicit.** Fiecare task primește `tenant_id` și `company_id` și setează contextul înainte de orice query. Se aplică la e-Factura, BNM, payroll, amortizare, rapoarte, import, migrare 1C.
- **Căi privilegiate enumerate limitativ.** Facturarea abonamentelor, polling SFS, curs BNM, aplicarea regulilor fiscale noi — singurele locuri unde izolarea se ridică intenționat, auditat.

### 4.3 Ce nivel are fiecare tabelă

| Nivel | Exemple |
|---|---|
| **Global** | Users, reguli fiscale, plan de conturi SNC (template), curs BNM |
| **Tenant** | Membership, abonament, chei API, setări, parteneri (opțional partajat) |
| **Company** | Journal entries, perioade, plan de conturi (instanță), TVA, bancă, stocuri, payroll, active |

Contabilitatea este **obligatoriu company-scoped**, fără excepții.

### 4.4 Constrângeri de schemă cu efect ireversibil

**Cheia de partiționare trebuie decisă acum**, chiar dacă partiționarea efectivă vine peste ani. În PostgreSQL, cheia de partiționare face parte din cheia primară și din constrângerile unice. Adăugarea ulterioară pe `journal_lines` cu sute de milioane de rânduri și chei străine spre ele nu este o migrare, este un proiect.

Candidate: `accounting_date` (an) pentru tabelele contabile, `tenant_id` pentru audit și evenimente.

**Indecși compuși**, întotdeauna începând cu contextul:
```
(tenant_id, company_id, accounting_date)
(company_id, account_id, accounting_date)
(company_id, partner_id, accounting_date)
```

---

## 5. Motorul de reguli fiscale — Faza 0

Serviciu transversal, nu submodul al `tax`.

**Ce conține:** cote TVA, cote CNAS și CNAM, praguri și plafoane salariale, scutiri personale, cote de impozit pe venit, praguri de înregistrare, termene de raportare, coeficienți de amortizare fiscală.

**Formă:** date versionate cu `valid_from` / `valid_to`. Fiecare regulă are sursă (act normativ, Monitorul Oficial, dată publicare).

**Rezoluție:** orice consumator cere o regulă pentru o dată efectivă. Recalcularea unei perioade închise folosește regula valabilă atunci, nu cea curentă.

**Consumatori:** Tax/TVA, Payroll, Fixed Assets, Statutory Reporting, Posting Engine.

Dacă acest modul stă sub `tax`, în șase luni `payroll` importă din `tax` și ai un ciclu de dependențe.

---

## 6. Operațiunea de conformitate — funcție permanentă

Aceasta nu este o fază. Este o capabilitate organizațională care trebuie să existe din ziua lansării și pe toată durata vieții produsului. Este riscul operațional numărul unu al oricărui produs contabil.

**Ce presupune:**

- Monitorizare Monitorul Oficial, comunicate SFS, CNAS, CNAM, BNS
- Proces documentat: publicare → evaluare impact → implementare regulă → testare → livrare
- **SLA intern de livrare** pentru modificări legislative (propunere: 5 zile lucrătoare de la publicare pentru cote și praguri; 15 pentru formulare noi)
- Registru de versiuni al regulilor, cu trasabilitate la actul normativ
- Comunicare proactivă către utilizatori și firme de contabilitate
- Cel puțin un contabil practicant în echipă sau sub contract permanent

**Consecință de arhitectură:** dacă o modificare de cotă TVA necesită deployment, procesul a eșuat. Trebuie să fie configurare de date, aplicată la o dată efectivă, testabilă înainte de intrarea în vigoare.

---

## 7. Accounting Core — Faza 1

### 7.1 Planul de conturi SNC

Livrat preconfigurat, ca **date versionate**, nu ca fixture copiat o singură dată.

```
System Chart Template (versionat, global)
              ↓
Company Chart of Accounts (instanță)
```

Modelul trebuie să răspundă la: ce se întâmplă cu cele 8.000 de companii care au instanțiat versiunea veche când legislația modifică un cont?

Cerințe:
- Versiunea template-ului înregistrată pe companie
- Mecanism de propagare a modificărilor legislative
- Distincție clară între **conturi de sistem** (nu pot fi șterse, se actualizează central) și **subconturi create de companie**
- `valid_from` / `valid_to` pe cont
- Suport pentru: activ/pasiv, urmărire valutară, urmărire cantitativă, dimensiuni analitice, conturi blocate

### 7.2 Dimensiuni analitice

Proiectate din prima zi pe linia de jurnal, chiar dacă UI-ul le expune mai târziu: Partener, Articol, Angajat, Contract, Depozit, Proiect, Departament, Centru de cost, Activ, Comandă de producție.

Acesta este exemplul canonic de decizie ieftină acum și foarte scumpă peste un an.

### 7.3 General Ledger

```
Accounting Transaction → Journal Entry → Journal Lines
```

Invariant: Σ Debit = Σ Credit pe fiecare Journal Entry, verificat la nivel de bază de date acolo unde e posibil.

### 7.4 Posting Engine

```
Business Event → Posting Rule Resolution → Journal Entry
```

Regulile de postare suportă condiții, șabloane, rezoluție de cont, taxe, dimensiuni, valută și **date efective**.

**Adăugat față de V1:** profilul de capabilități al tenantului este **input al motorului de postare**. O factură de achiziție de marfă se contabilizează diferit dacă tenantul are sau nu Inventory activat. Dacă asta nu e în model de la început, apare ca bug peste un an.

### 7.5 Perioade și închidere

Perioade cu stare (deschisă, în închidere, închisă, blocată). Redeschiderea necesită permisiune specială și lasă urmă în audit. Postarea într-o perioadă închisă este refuzată la nivel de motor, nu de UI.

### 7.6 Multi-valută

Construit în core, nu adăugat ulterior. Pe fiecare tranzacție: sumă în valută, valuta, cursul, suma în MDL. Curs BNM automat, cursuri manuale, diferențe de curs, reevaluare.

### 7.7 Solduri inițiale

Componentă critică pentru migrarea din 1C: GL, clienți, furnizori, stocuri (cantitate + cost), active, angajați (cumulative anuale).

---

## 8. Capabilități: activare, nu comutator

Eroare frecventă: modelarea capabilităților ca boolean pe tenant.

**Activarea unei capabilități este o entitate** cu:
- `effective_from`, aliniat la granița perioadei contabile
- stare de inițializare (necesară / în curs / completă)
- pas de inițializare, unde e cazul

**Exemple concrete de ce contează:**

| Capabilitate | Ce cere activarea |
|---|---|
| Inventory | Solduri inițiale cantitate + cost, metodă de evaluare, dată de cutover. Ledgerul e append-only — istoricul nu devine retroactiv stoc. |
| Payroll la mijloc de an | Cumulative de la 1 ianuarie per angajat, altfel IPC-ul iese greșit. Este literalmente o migrare de date. |
| Multi-company | Apar tranzacții intercompany și eventual consolidare. |

**Capability set ≠ plan comercial.** Sunt axe ortogonale. În modelul wholesale, firma de contabilitate plătește preț de partener pentru toți tenanții gestionați și facturează cum vrea; un client de-al ei poate avea nevoie de Inventory fără să corespundă vreunui tier din grila directă. Planul propune un set implicit; nu îl definește rigid.

---

## 9. Workspace-ul contabilului — canalul de distribuție

Complet absent din V1. Este mecanismul prin care produsul ajunge la piață.

### 9.1 Ciclul de viață al Engagement-ului

```
Invitație (firmă → tenant SAU tenant → firmă)
      ↓
Acceptare
      ↓
Activ (cu scope: ce companii, ce module, ce drepturi)
      ↓
Suspendat / Revocat / Transferat
      ↓
Istoric păstrat permanent (cine a avut acces, când, ce a făcut)
```

Revocarea taie accesul instantaneu, dar nu șterge urma din audit. Transferul către altă firmă nu mută date — schimbă doar relația.

### 9.2 Dashboard transversal — read models

Contabilul cu 60 de clienți nu interoghează tabelele operaționale. Vrea: cine are declarația nedepusă, cine are TVA de plată, cine are documente neînregistrate, cine are termen săptămâna asta.

Acestea sunt **read models** — tabele de agregate cu `tenant_id` și `firm_id` denormalizat, actualizate la închiderea documentelor sau prin job. Interogarea devine trivială fără să sacrifici proprietatea datelor.

Aceasta este justificarea reală pentru shared database. Dashboard-ul transversal cere baza de date comună, dar **nu** cere ca firma de contabilitate să fie proprietar.

### 9.3 Funcții

Calendar de termene per client, operațiuni în masă, șabloane aplicabile pe portofoliu, status de conformitate, delegare internă în cadrul firmei, raportare a activității.

### 9.4 Facturare

Două canale de la lansare, ambele de primă clasă:
- **Wholesale:** firma plătește preț de partener pentru tenanții gestionați, facturează clienții independent
- **Direct:** tenantul fără firmă de contabilitate plătește direct

---

## 10. Roadmap

### Faza 0 — Fundament

Tenancy și identitate (Tenant, Company, Firm, Engagement, User, Membership), RLS fail-closed, rol de aplicație separat, context în tranzacție, Celery cu context. Chei primare pregătite pentru partiționare. Audit log. Motor de reguli fiscale. Document core, numerotare, atașamente, notificări. Master data: Partener, Articol, UM, Depozit (modelat), dimensiuni. Multi-valută în core. Feature flags și release rings. Convenții API.

**Milestone:** platforma poate izola corect doi tenanți și un engagement, demonstrat prin teste de penetrare a izolării.

---

### Faza 1 — Accounting Core

Plan de conturi SNC versionat cu propagare. Journal și journal lines cu dimensiuni. Posting Engine cu reguli condiționate de capabilități. Perioade și închidere. Note contabile manuale. Solduri inițiale. Balanță de verificare, Cartea Mare, fișa contului, jurnale. Fundamentul importatorului 1C.

**Milestone:** Evidenta produce o balanță corectă, verificabilă la leu contra unei balanțe 1C reale.

---

### Faza 2 — Primul produs vandabil: compania de servicii

Aceasta este cea mai importantă modificare față de V1.

Vânzări (factură, notă de credit, retur), Achiziții, AR / AP cu decontare și avansuri, Bancă cu import de extras și matching, Casă, valută operațională.

**TVA complet:** registre, declarație, corecții.

**e-Factura / SFS:** creare, validare, transmitere, status, anulare, import facturi primite, retry, arhivare payload.

**Payroll:** angajați, contracte, salarizare, concedii, medicale, rețineri, contribuții, IPC, postare în GL, fluturași, plată bancară.

**Pachet complet de raportare statutară:** SFS, CNAS, CNAM, BNS, situații financiare SNC.

**Active fixe:** registru, punere în funcțiune, amortizare lunară, transfer, casare, vânzare.

Print/PDF, căutare globală, import/export.

**Milestone:** o companie de servicii cu angajați poate abandona complet 1C. **Primul release comercial.**

> V1 plasa acest milestone în Faza 2 fără payroll și fără raportare completă. Nu era realizabil — o companie de servicii are salarii, IPC și rapoarte lunare către trei instituții.

---

### Faza 3 — Workspace contabil și migrare

Ciclul complet de Engagement. Dashboard transversal pe read models. Calendar de termene. Operațiuni în masă. Facturare wholesale și directă. **1C Migration Center productizat**, cu wizard, mapare, validare și reconciliere finală la zero diferență.

**Milestone:** o firmă de contabilitate poate muta întregul portofoliu în Evidenta. Începe distribuția reală.

---

### Faza 4 — Comerț și stocuri

Inventory ledger. Evaluare FIFO și cost mediu ponderat. Loturi (în schema V1, obligatoriu). Numere de serie modelate. Mișcări, transferuri, ajustări, inventariere cu variație și postare. Import, vamă, landed cost. Comenzi de vânzare și achiziție. Liste de prețuri.

**Milestone:** o companie de distribuție sau comerț poate abandona 1C.

---

### Faza 5 — ERP operațional

HR separat de Payroll. CRM peste același Partener. Contracte. Workflow și aprobări ca platform capability. Contabilitate de gestiune. API public.

**Milestone:** competitor direct pentru 1C Managementul Companiei și Managementul Comerțului.

---

### Dincolo de Faza 5 — direcție, neangajat

Producție și MRP. Calitate. Retail și POS. WMS. Procurement avansat. Logistică. Contabilitate de proiect. Bugetare. BI avansat. AI.

Aceste domenii se proiectează pentru compatibilitate, dar **nu se promit comercial** și nu au termen. Ordinea reală se va decide din cererea pieței după Faza 3.

**Notă privind Retail/POS:** AvaBoss există deja. Nu se rescrie POS-ul în Evidenta. Fie se integrează ca sursă de evenimente către Posting Engine, fie se portează mai târziu deliberat. Nu se planifică ca teren gol.

---

## 11. Ce trebuie modelat acum, implementat mai târziu

| Concept | Modelat | Implementat |
|---|---|---|
| Tenancy și engagement | F0 | F0 |
| Dimensiuni analitice | F0 | F1 |
| Multi-valută | F0 | F2 |
| Cheie de partiționare | F0 | (când e nevoie) |
| Loturi | F0 | F4 |
| Numere de serie | F0 | F4+ |
| Locații / bin-uri | F0 | direcție |
| Centre de cost | F0 | F5 |
| Proiecte | F0 | direcție |
| Workflow și aprobări | F0/F1 | F5 |
| Producție | F0 | direcție |
| API public | F0 | F5 |

Regula: nu construim funcțiile acum, dar nu construim schema într-un mod care le face imposibile.

---

## 12. Operațional și non-funcțional

Secțiune absentă din V1, cu elemente care afectează modelul de date.

### 12.1 Restaurare per tenant

Cea mai frecventă cerere reală în software contabil: „am stricat ceva luni, adu-mi datele de vineri."

În shared database, PITR restaurează tot clusterul — inutilizabil. Ledgerul append-only plus audit log complet fac reversibilitatea posibilă **la nivel logic**, dar asta trebuie proiectat, nu presupus. Necesită: capacitatea de a identifica toate efectele unei sesiuni sau ale unui interval, și de a le storna coerent.

### 12.2 Offboarding și retenție

Documentele contabile au termene legale de păstrare în Moldova. Nu poți nici să ștergi imediat, nici să ții la infinit gratuit.

Necesar: export complet într-un format utilizabil, perioadă de grație, regim de arhivare, politică de retenție. Afectează modelul de date, deci se decide acum.

### 12.3 Securitate

Din Faza 0: TLS, secrete criptate, MFA, RBAC, audit log, backup, PITR, izolare tenant testată automat, rate limiting, control sesiuni.

Ulterior: SSO, SCIM, restricții IP.

**Eliminat din roadmap: DB dedicat per tenant.** Două topologii înseamnă dublarea suprafeței de testare pentru fiecare migrare, raport, job și feature — și rup dashboard-ul transversal al contabilului. Disciplina de a nu avea interogări cross-tenant în cod face mutarea posibilă tehnic mai târziu; nu construim router-ul acum și nu vindem opțiunea. Dacă apare o instituție care cere izolare fizică, este o discuție comercială separată, cu preț pe măsură.

### 12.4 Ținte de performanță

De fixat înainte de F1, pentru că influențează indecșii și read models:
- Balanță de verificare pe 5 ani de date
- Închiderea de perioadă pentru o companie cu volum mare
- Dashboard contabil cu 100 de clienți
- Generarea declarației TVA

---

## 13. Structura comercială

Toate planurile rulează pe aceeași platformă. Licența activează capabilități.

| Plan | Conținut |
|---|---|
| **Start** | Facturare, bancă, casă, contabilitate, **TVA, e-Factura, raportare statutară, payroll de bază** |
| **Business** | Start + stocuri, achiziții, comenzi, active, prețuri, payroll complet |
| **ERP** | Business + CRM, contracte, workflow, contabilitate de gestiune, API |
| **Enterprise** | ERP + securitate avansată, SSO, integrări, workflow custom, SLA |

### Regula care nu se încalcă

**Conformitatea nu poate fi capability plătibilă.** TVA, e-Factura și raportarea SNC nu pot fi add-on-uri dezactivate. Dacă un client emite facturi în Evidenta, e-Factura funcționează indiferent de plan. Altfel îți asumi răspundere pentru clienți care nu-și îndeplinesc obligațiile fiscale folosind produsul tău.

Diferențierea se face pe volum, module operaționale și complexitate. Niciodată pe conformitate.

> V1 avea în „Evidenta Start" doar „basic accounting" și e-Factura, fără TVA. O microîntreprindere înregistrată ca plătitor de TVA nu poate funcționa așa.

### Unit economics

Conformitatea costă aproape la fel per tenant indiferent de plan. Planul Start are cost apropiat de un plan mare și venit mic.

Ce salvează economia este canalul wholesale: când clientul mic vine prin firma de contabilitate, suportul de nivel 1 îl face contabilul. Clientul micro pe canal direct este cel scump.

**Consecință:** planul Start se împinge prioritar prin contabili. Canalul direct pentru micro fie are preț mai mare, fie suport strict self-service.

---

## 14. Registrul de riscuri

| Risc | Impact | Mitigare |
|---|---|---|
| Modificare legislativă nelivrată la timp | Critic — clienți în neconformitate | Operațiunea de conformitate, SLA intern, reguli ca date |
| API SFS instabil sau nedocumentat | Ridicat — blochează e-Factura | Coadă cu retry, degradare controlată, contact instituțional direct |
| Calitatea datelor din 1C la migrare | Ridicat — blochează vânzarea | Reconciliere obligatorie la zero diferență, refuz de import parțial |
| Subestimarea complexității payroll | Ridicat — F2 alunecă | Contabil practicant în echipă din F0 |
| Extindere de scop din framing-ul ERP | Ridicat — nu se termină nimic | Faze angajate vs. direcție, explicit |
| Reacția incumbentului pe preț | Mediu | Diferențierea pe conformitate și migrare, nu pe preț |
| Lipsa expertizei contabile în echipă | Critic | Angajare sau contract permanent, condiție de start |
| Dependența de un singur canal (contabili) | Mediu | Canal direct funcțional de la lansare |

---

## 15. Decizii deschise care blochează schema DB

Trebuie închise înainte de prima migrare Django.

1. **Modelul Tenant / Firm / Engagement** — confirmat definitiv? (Blochează totul.)
2. **Cheia de partiționare** pentru `journal_lines`, `inventory_movements`, `audit_events`.
3. **Metoda de evaluare a stocurilor** — per companie sau per articol? Poate fi schimbată? Cu ce efect asupra istoricului?
4. **Numerotarea documentelor** — per companie sau per filială? Serii pe an?
5. **Politica de propagare** a modificărilor din template-ul planului de conturi către instanțele existente.
6. **Identitatea globală a utilizatorului** — confirmată? (Necesară pentru contabilul cu 60 de clienți.)
7. **Cumulativele payroll** la activare în cursul anului — model de date.
8. **Relația cu AvaBoss** — integrare prin evenimente sau portare ulterioară?
9. **Partenerii** — tenant-level partajat între companii, sau company-level cu suprascriere?

---

## 16. Ce nu se face

- Nu se copiază arhitectura 1C. Se preia funcționalitatea, nu limitările istorice.
- Nu se construiesc aplicații separate. Un produs, module.
- Nu se pornește cu microservicii. Separare de domenii, da; complexitate distribuită, nu.
- Nu se hardcodează contabilitatea în documente. Tot prin Posting Engine.
- Nu se hardcodează legislația în cod. Reguli versionate ca date.
- Nu se modifică ledgerul postat. Storno și reînregistrare.
- Nu se construiesc verticale în core. Module de industrie peste ERP Core.
- Nu se creează versiuni per tenant. Feature flags și release rings.
- **Nu se vinde ce nu există.** Producția și WMS sunt direcție, nu promisiune.

---

## 17. Pasul următor

Cele două specificații paralele, cu contradicțiile din V1 rezolvate:

**Spec A — Identitate, tenancy, engagement, billing, release**
Entități și relații, proprietate vs. acces delegat, forma politicilor RLS pentru ambele căi, comportament fail-closed, nivelurile tabelelor, căi privilegiate enumerate, read models pentru dashboard transversal, restaurare, export, offboarding, retenție, strategia de release.

**Spec B — Accounting core**
Ledger append-only, plan de conturi SNC ca date versionate cu propagare, dimensiuni, maparea document → postare condiționată de capabilități, motorul de reguli fiscale, perioade și închidere, multi-valută, solduri inițiale.

Ambele trebuie să producă **constrângerile de cheie primară** care intră direct în prima migrare.
