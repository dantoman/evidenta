# Evidenta.md — Amendamentul 1 la Master Plan V2

**Statut:** modifică V2. Unde există conflict, acest document prevalează.
**Scop:** închide deciziile rămase deschise înainte de Spec A și corectează patru formulări din V2.

---

## A. Invarianți arhitecturali — versiune actualizată

Secțiunea 2 din V2 se înlocuiește integral cu lista de mai jos. Invarianții 1, 2, 3, 5, 6, 7 rămân neschimbați; 4 este reformulat; 8–11 sunt noi.

**1.** Niciun modul business nu scrie în ledger. Toate trec prin Posting Engine, prin evenimente contabile.

**2.** Ledgerul postat este imutabil. Corecția se face prin storno și reînregistrare, niciodată prin UPDATE.

**3.** Nicio interogare nu rulează fără context de tenant. Absența contextului înseamnă refuz, nu acces total.

**4.** *(reformulat)* Conformitatea are două straturi, ambele versionate după dată efectivă:

- **Parametri fiscali → date.** Cote, praguri, plafoane, scutiri, coeficienți, mapări de conturi, termene. Modificarea lor este INSERT, nu deployment.
- **Logică fiscală → cod versionat.** Algoritmi de calcul, scheme de declarații, validări, comportament API. Modificarea lor este deployment.

Selecția implementării se face **printr-un registru, după data efectivă a perioadei calculate** — niciodată prin condiții pe anul curent împrăștiate în cod. Recalcularea unei perioade din 2026, executată în 2028, trebuie să folosească algoritmul și schema valabile în 2026.

> Formularea din V2 („dacă o modificare de cotă necesită deployment, procesul a eșuat") era prea largă. Statul poate schimba algoritmul, structura declarației, validările sau schema XML — acelea sunt inevitabil cod.

**5.** Un singur codebase. Diferențierea prin feature flags și release rings, niciodată prin versiuni per tenant.

**6.** Modificările de conformitate nu sunt opționale pentru niciun tenant și nu sunt niciodată paywall.

**7.** Tenantul este proprietarul datelor. Firma de contabilitate are acces delegat și revocabil.

**8.** *(nou)* **Idempotență.** Orice comandă sau eveniment extern care produce efect financiar trebuie să fie idempotent. Cheia de idempotență stă pe **evenimentul contabil**, nu doar pe endpoint-ul API.

Se disting două mecanisme, ambele necesare:

| Mecanism | Problema rezolvată | Implementare |
|---|---|---|
| Idempotență | Retry tehnic: aceeași cerere de două ori | `idempotency_key` unic pe eveniment |
| Deduplicare | Același document economic pe două căi (import bancar + introducere manuală, e-Factura + PDF scanat) | Chei naturale de business + constrângeri unice |

Se aplică la: e-Factura, import bancar, POS, API public, task-uri Celery, import 1C, rulări payroll, amortizare.

**9.** *(nou)* **Trasabilitatea documentului sursă.** Pentru orice efect financiar trebuie să existe lanțul complet, navigabil în ambele sensuri:

```
Journal Line → Journal Entry → Accounting Event → Source Document → Sursă (utilizator / sistem / integrare)
```

Lanțul trebuie să supraviețuiască corecției. O înregistrare de storno are **două** legături: spre documentul sursă și spre înregistrarea pe care o anulează. Fără a doua, drill-down-ul pe un cont cu corecții devine incoerent.

**10.** *(nou)* **Interogarea cross-tenant este permisă exclusiv în stratul de read models.** Nicio interogare din logica de business nu presupune că doi tenanți sunt fizic în aceeași bază de date. Read models sunt conceptual un store separat, chiar dacă azi trăiesc în același cluster.

> Fără această regulă, primul dashboard scris cu un JOIN peste tabelele operaționale încalcă principiul și nimeni nu observă timp de doi ani.

**11.** *(nou)* **Fiecare tabelă business are context de tenant și politică RLS.** Verificat automat, nu prin convenție. Vezi secțiunea D.3.

---

## B. Secțiuni corectate din V2

### B.1 — Secțiunea 5 (Motorul de reguli fiscale)

Se restructurează în două componente:

```
FISCAL PARAMETERS  (date, versionate valid_from/valid_to)
├── cote TVA
├── cote CNAS / CNAM
├── praguri și plafoane salariale
├── scutiri personale
├── cote impozit pe venit
├── praguri de înregistrare
├── termene de raportare
├── coeficienți de amortizare
└── mapări implicite de conturi

FISCAL LOGIC  (cod versionat, selectat prin registru după dată efectivă)
├── algoritmi de calcul salarial
├── algoritm de calcul TVA și proratare
├── scheme de declarații (XML/format)
├── reguli de validare
└── comportament API instituțional
```

Fiecare parametru păstrează sursa: act normativ, număr Monitorul Oficial, dată publicare, dată intrare în vigoare.

Fiecare implementare de logică păstrează intervalul de valabilitate și este selectabilă retroactiv.

### B.2 — Secțiunea 12.1 (Restaurare per tenant) — reformulată integral

Formularea din V2 sugera că un tenant poate fi readus arbitrar la o stare anterioară. Este greșită și periculoasă ca promisiune de produs. Vineri factura era emisă, e-Factura transmisă la SFS, extrasul bancar importat, salariile declarate la CNAS. Timpul nu se dă înapoi în afara sistemului.

Se separă în trei concepte, cu limite explicite:

| Concept | Domeniu | Mecanism | Promis clientului |
|---|---|---|---|
| **Recuperare tehnică în caz de dezastru** | Pierdere de date la nivel de cluster | PITR, backup | Da, ca SLA de infrastructură |
| **Corecție de business** | Erori de operare, oricât de mari | Storno, reînregistrare, audit | Da, ca funcție de produs |
| **Export / snapshot** | Cazuri forensice, litigii, offboarding | Export complet la o dată | Da, la cerere |

**Cererea „restaurează-mi compania la starea de vineri" se refuză, cu explicație.** Răspunsul produsului este identificarea efectelor din intervalul respectiv și stornarea lor coerentă — ceea ce necesită ca audit log-ul și lineage-ul (invariantul 9) să permită enumerarea completă a efectelor unei sesiuni, ale unui utilizator sau ale unui interval.

Această capacitate de enumerare este o cerință funcțională, nu un efect secundar al audit-ului. Intră în Spec A.

### B.3 — Secțiunea 4.4 (Partiționare) — retrogradată din invariant

V2 cerea decizia cheii de partiționare înainte de prima migrare. Se retrage ca cerință blocantă și se înlocuiește cu o disciplină ieftină plus o decizie amânată.

**Motivul retragerii:** ordinul de mărime realist pentru Moldova (≈60.000 de companii active în total; scenariu optimist 10–15.000 de tenanți în 10 ani, majoritatea micro) produce sute de milioane de linii **cumulat**, nu pe an. PostgreSQL gestionează asta cu indecși corecți. Nu justifică constrângerea tuturor cheilor primare din MVP.

**Ce se păstrează — disciplina, nu decizia:**

Se desemnează acum un set de tabele „append-only, volum mare":
`journal_lines`, `inventory_movements`, `audit_events`, `document_events`, arhive payload e-Factura, arhive extrase bancare.

Pentru acestea:

1. **Nicio cheie străină nu arată spre ele.** Legăturile se fac invers. *(Aceasta este regula care contează. O tabelă fără FK-uri intrând se repartiționează greu; o tabelă cu zece FK-uri intrând nu se repartiționează, se redesenează.)*
2. Coloana naturală de partiționare (`accounting_date`, `occurred_at`) există ca `NOT NULL` de la început — oricum necesară.
3. Indecșii încep cu contextul de tenant și companie.

**Model de volum — livrabil în F0.** Scenarii mic / mediu / mare, cu date reale de la o firmă de contabilitate colaboratoare. Decizia de partiționare se ia după benchmark.

**Observație de prioritizare:** primul candidat real la partiționare nu este `journal_lines`, ci `audit_events` — volum mare de scriere, valoare care scade rapid cu vechimea, partiții vechi arhivabile sau eliminabile.

---

## C. Decizii închise

### C.1 — Partener: model pe trei niveluri

Decizia deschisă nr. 9 din V2 se închide astfel:

```
CounterpartyRegistry   (global, referință)
        ↓
Partner                (tenant, master)
        ↓
CompanyPartner         (companie, configurare)
```

**CounterpartyRegistry** — registru global după IDNO, alimentat din surse publice.
Conține: IDNO, denumire, formă juridică, statut TVA, adresă oficială, stare (activ/radiat).

Justificare — trei beneficii, al treilea fiind cel mai important:
- validare la introducere (IDNO existent, denumire corectă, statut TVA)
- rezoluția contrapărții la importul facturilor primite prin e-Factura, fără potrivire după text
- **efect de rețea:** când emitentul și destinatarul sunt amândoi în Evidenta, factura apare direct în lista de documente primite a destinatarului, deja structurată

Ultimul punct este potențial mai valoros comercial decât orice modul din fazele 5+. Costă puțin acum; costă mult după ce mii de tenanți au parteneri creați liber.

**Partner** — nivel tenant. IDNO, denumire, cod TVA, adrese, persoane de contact, conturi bancare, tags. Într-un holding, METRO Moldova se introduce o singură dată.

**CompanyPartner** — nivel companie. Cont de creanțe, cont de datorii, termene de plată, limită de credit, agent de vânzări, listă de prețuri, status, blocări.

### C.2 — Payroll și Financial/Tax în paralel în F2

Se adoptă organizarea pe două fluxuri paralele după stabilizarea Accounting Core, nu secvențial.

```
                  ACCOUNTING CORE (F1)
                          │
              ┌───────────┴───────────┐
              ↓                       ↓
      Commercial / Tax            Payroll
              │                       │
        Sales                    Angajați
        Purchases                Contracte
        Bank / Cash              Salarizare
        TVA                      IPC / CNAS / CNAM
        e-Factura                Concedii / medicale
              │                       │
              └───────────┬───────────┘
                          ↓
                   Posting Engine
```

Ambele fluxuri consumă parametri fiscali și emit evenimente contabile. Niciunul nu scrie în ledger.

### C.3 — Rulare în paralel pentru Payroll: funcție de produs, nu testare internă

*(Nu exista în V2.)*

Nicio companie nu mută salarizarea pe baza încrederii. Evidenta trebuie să poată calcula o lună **în paralel** cu sistemul existent și să producă un raport de diferențe la ban, per angajat și per contribuție.

Este echivalentul pentru payroll a ceea ce este reconcilierea la zero diferență pentru migrarea contabilă. Intră în scopul F2, nu în F3.

### C.4 — Evaluarea stocurilor: politică per categorie

Decizia deschisă nr. 3 din V2 se închide provizoriu astfel:

```
Company Inventory Policy   (metodă implicită)
        ↓
Category Inventory Policy  (suprascriere per categorie de stoc)
```

Metodele suportate în MVP: FIFO și cost mediu ponderat.

**Justificare:** SNC 2 este aliniat la IAS 2, care permite formule diferite pentru stocuri de natură sau utilizare diferită, cerând consecvență în interiorul aceleiași categorii. Modelul „o metodă per companie" e prea rigid pentru o fabrică; override-ul per articol e prea permisiv și nesusținut de standard.

**Schimbarea metodei nu este un dropdown.** Necesită: dată efectivă aliniată la granița perioadei, închiderea perioadei anterioare, reevaluare documentată, aprobare, urmă în audit.

**Confirmare necesară** de la contabilul practicant al echipei înainte de schema Inventory (F4). Nu blochează Spec A.

---

## D. Adăugiri operaționale

### D.1 — Compliance Admin ca produs intern

Instrument intern al echipei Evidenta, nu funcție pentru clienți. Necesar operațional din F2.

```
Act normativ publicat
        ↓
Evaluare impact (parametru? algoritm? schemă?)
        ↓
Implementare + dată efectivă
        ↓
Rulare pe corpus de regresie
        ↓
Aprobare de contabil practicant
        ↓
Activare programată
        ↓
Comunicare către tenanți și firme de contabilitate
```

### D.2 — Corpus de regresie pentru conformitate

*(Nu exista în V2. Necesar din F1.)*

Set de cazuri reale anonimizate, cu rezultatul corect cunoscut și verificat de un contabil: calcule salariale pe configurații diverse, decontări TVA, amortizări, situații financiare.

Rulat automat la **fiecare** modificare de parametru sau algoritm fiscal.

Fără el, o modificare de cotă pentru 2027 poate strica recalcularea lui 2025, iar asta se află de la un client.

### D.3 — Teste de izolare în CI — două suite distincte

Ambele rulează la fiecare release. Ambele rulează **sub rolul de aplicație**, niciodată sub superuser sau owner de tabelă — altfel nu testează nimic.

**Suita 1 — penetrare.** Autentificat ca Tenant A, se încearcă acces la fiecare tip de resursă a lui Tenant B: facturi, înregistrări contabile, payroll, atașamente, obiecte API, read models. Rezultat așteptat: acces zero, în toate cazurile.

Se testează inclusiv: engagement expirat, engagement revocat, engagement cu scope restrâns, task Celery fără context setat.

**Suita 2 — gardian de model.** Enumeră toate tabelele din schemă și eșuează dacă vreuna:
- nu are coloană de context de tenant (cu excepțiile enumerate explicit: registru global, parametri fiscali, curs BNM)
- nu are politică RLS activă
- nu are `FORCE ROW LEVEL SECURITY`

Prima suită prinde bug-urile de azi. A doua prinde tabela pe care cineva o adaugă peste trei ani fără să știe regula.

---

## E. Decizii care rămân deschise

| # | Decizie | Blochează | Termen |
|---|---|---|---|
| 1 | Cheia de partiționare | Nimic (disciplină aplicată) | După modelul de volum, F0 |
| 2 | Numerotarea documentelor: per companie sau per filială | Document core | Spec A |
| 3 | Politica de propagare a modificărilor din template-ul planului de conturi | Accounting core | Spec B |
| 4 | Modelul cumulativelor payroll la activare în cursul anului | Payroll schema | Înainte de F2 |
| 5 | Relația cu AvaBoss: integrare prin evenimente sau portare | Nimic acum | După F3 |
| 6 | Confirmare contabilă pe politica de evaluare per categorie | Inventory schema | Înainte de F4 |

Deciziile 1, 3, 6, 7, 9 din lista V2 sunt închise prin acest amendament.

---

## F. Ce rămâne neschimbat din V2

Pentru claritate: nu se modifică viziunea, poziționarea, straturile arhitecturale, modelul Tenant/Company/Firm/Engagement, mecanismele RLS, structura Accounting Core, modelul de activare a capabilităților, workspace-ul contabilului, roadmap-ul F0–F5, structura comercială, registrul de riscuri sau secțiunea „ce nu se face".

Pasul următor rămâne cel indicat în V2: **Spec A — Identitate, tenancy, engagement, billing, release**, urmată de Spec B.
