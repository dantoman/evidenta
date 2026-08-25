# 000 — Registrul deciziilor deschise

- **Status:** viu. Se actualizează la fiecare decizie luată sau apărută.
- **Ultima revizuire:** 2026-08-25 (ADR-018 engagementuri multiple, ADR-019 vocabular de scope, ADR-020 roluri ca date, ADR-021 MFA obligatoriu, ADR-022 numerotare; `OD-43` nouă; `OD-41`/`OD-42` erau folosite fiecare pentru două decizii — perechea apărută la F0.3.3 a devenit `OD-44` și `OD-45`)
- **Sursa:** `docs/_bootstrap/00-inventory.md`, secțiunile 3 și 5.

O decizie din acest registru **nu se închide în cod**. Se închide printr-un ADR numerotat, iar
rândul de aici trece în „Închise" cu trimitere la ADR.

Coloana **Blochează** spune ce nu se poate face până la închidere. Coloana **Termen** este cel mai
târziu moment la care decizia trebuie luată fără să genereze rescriere.

---

## A. Decizii înregistrate în Amendamentul 1

| # | Decizie | Blochează | Termen | Ce se știe |
|---|---|---|---|---|
| **OD-01** | **Cheia de partiționare** pentru tabelele append-only de volum mare | Nimic — disciplina o substituie (fără FK-uri intrând, coloană `NOT NULL`, indecși cu context) | După modelul de volum, în F0 | Candidați: `accounting_date` (an) pentru tabele contabile, `tenant_id` pentru audit și evenimente. Primul candidat real este `audit_events`, nu `journal_lines` — volum mare de scriere, valoare care scade cu vechimea |
| **OD-03** | **Politica de propagare** a modificărilor din template-ul planului de conturi către instanțele existente | `accounting/coa` (F1.1) | Spec B | Nicio opțiune descrisă în documente. Întrebarea din V2 §7.1 rămâne deschisă: ce se întâmplă cu companiile care au instanțiat versiunea veche când legislația modifică un cont |
| **OD-04** | **Modelul cumulativelor payroll** la activarea salarizării în cursul anului | Schema `payroll` | Înainte de F2 | Cerința cunoscută: cumulative de la 1 ianuarie per angajat, altfel IPC-ul iese greșit. Amendamentul o declară închisă în text și deschisă în tabel — vezi `00-inventory.md`, X-1. Tratată ca deschisă |
| **OD-05** | **Relația cu AvaBoss:** integrare prin evenimente sau portare ulterioară | Nimic acum | După F3 | POS-ul nu se rescrie în Evidenta. Fie devine sursă de evenimente către Posting Engine, fie se portează deliberat mai târziu |
| **OD-06** | **Confirmare contabilă** pe politica de evaluare a stocurilor per categorie | Schema `inventory` (F4) | Înainte de F4 | Modelul este decis (implicit per companie, suprascriere per categorie; FIFO și CMP în MVP). Lipsește validarea de la contabilul practicant. Nu blochează Spec A |

---

## B. Decizii apărute din contradicțiile documentelor de intrare

Descoperite în Etapa 0. Nu existau în niciun registru.

| # | Decizie | Blochează | Termen | De ce e deschisă |
|---|---|---|---|---|
| **OD-09** | **Mecanismul** căilor privilegiate: funcții `SECURITY DEFINER` sau rol dedicat. **Restrânsă:** enumerarea celor opt căi e făcută în Spec A §6.2; ADR-003 creează deja precedentul unui rol cu `BYPASSRLS` pentru predicate, ceea ce nu decide însă și căile privilegiate | F0.1, R7 | Spec A | V2 §4.2 dă patru exemple (facturarea abonamentelor, polling SFS, curs BNM, aplicarea regulilor fiscale noi) și le numește „singurele locuri" — dar exemplele nu sunt o enumerare, iar mecanismul (rol separat? variabilă dedicată? `SECURITY DEFINER`?) nu e ales. Vezi G-10 |
| **OD-11** | **Unde locuiesc modelele „modelate în F0, implementate mai târziu"** | F0.7 și orice sarcină care atinge un modul marcat „Model F0" | Înainte de F0.7 | F0.7 cere modelele `Warehouse` și dimensiunile analitice în F0; harta le dă Fază F4, respectiv F1; regula §4.2 interzice app-uri Django goale. Trei variante posibile: app creat devreme cu doar modelul, model găzduit într-un app părinte, sau amânare cu reducerea lui F0.7. Se aplică la ~15 module. Vezi X-5 |
| **OD-12** | **Efectul de rețea al e-Facturii vs. interdicția cross-tenant** | Modelul `CounterpartyRegistry` și fluxul de documente primite | Spec A | Amendamentul §C.1 promite că, atunci când emitentul și destinatarul sunt amândoi în Evidenta, factura apare direct în lista de documente primite a destinatarului. Aceasta este o cale prin care date ale tenantului A ajung la tenantul B; nu apare nici în read models, nici în căile privilegiate. Vezi G-22 |
| **OD-45** | **Trei corecții în contractul RLS, aplicate la F0.3.3, care cer confirmare.** Fișierul își declară singur modificarea drept ADR. (1) `firm` era declarată fără coloană de tenant, dar Spec A §1.3 îi dă tenant propriu — prinsă de `IZ-76`, verificarea scrisă exact pentru drift de contract. (2) `engagement_company_scope` declarată cu `tenant_column = "client_tenant_id"`; forma de declarare a fost extinsă ca să accepte un nume de coloană, nu doar boolean. (3) `engagement_module_scope` declarată fără coloană de tenant: e atribut pur al engagementului **Renumerotată din `OD-42`** (număr folosit deja pentru entitatea `assignment`, citat în ADR-017). | Nimic — suita e verde cu ele | Confirmare la următoarea revizuire |
| **OD-44** | **Cum răspunde produsul la „la ce tenanți aparțin"?** Politica pe `tenant` a fost strânsă la `id = app.current_tenant_id() AND rls.has_tenant_access(id)`, pentru că forma extrapolată în ADR-003 lăsa rândurile altor tenanți ai aceluiași utilizator să apară în contextul unei alte cereri. Consecința: comutatorul de tenant nu se mai poate alimenta din această tabelă. Fiind întrebare cross-tenant prin natură, locul ei este în read models (INV-10) sau pe o cale privilegiată **Renumerotată din `OD-41`** (număr folosit deja pentru biblioteca de grilă). `infra/migrations/0012_tenant_context_binding.up.sql` o citează cu numărul vechi și **rămâne așa**: fișierul e aplicat, iar `C31` îl face append-only — corecția ar fi un fișier nou, nu o editare. | Comutatorul de tenant (F0.10.3); înrudită cu `OD-37` | Înainte de F0.10.3 |
| **OD-40** | **Acoperă art. 7 și conținutul documentelor primare emise de entitate?** Art. 11 nu prescrie limba pentru documentele întocmite de entitate; singura prevedere de limbă, alin. (11), privește documentele **primite din străinătate** și acceptă româna, engleza și rusa fără traducere. Rămâne de stabilit dacă o denumire de articol tastată în rusă, ajunsă pe o factură fiscală emisă, e conformă. **Până la răspuns, produsul nu restricționează nimic** | Nimic acum; determină dacă apare o restricție | Decizie contabilă |
| **OD-37** | **Cum se listează membrii unui tenant.** ADR-003 stabilește politica `user_id = app.current_user_id()` pe `membership` și `company_access`, deci ecranul „echipa mea" nu se poate face prin queryset. Opțiuni: funcție `SECURITY DEFINER` dedicată; serviciu care trece prin predicat; sau politică extinsă cu o a doua ramură — ultima reintroduce încrucișarea pe care ADR-003 o evită | F0.3.2, ecranele de administrare a echipei | Înainte de F0.3.2 |

---

## C. Decizii de infrastructură, necesare pentru a începe F0

Reversibile individual, dar fiecare devine scumpă după ce se scrie cod peste ea.

| # | Decizie | Blochează | Termen |
|---|---|---|---|
| **OD-16** | Platforma CI și modul concret în care suitele de izolare rulează **sub rolul de aplicație** într-un runner efemer | F0.2 | Înainte de F0.2 |
| **OD-17** | Unealta care verifică mecanic regulile de dependență D1–D6 | Aplicarea D1–D6 | Înainte de primul modul cu dependențe |
| **OD-19** | Stack-ul frontend peste React: management de stare, client HTTP, rutare, i18n, formatare pentru RM. **Restrânsă:** grila de date a ieșit prin ADR-001; biblioteca de componente prin ADR-009 | F0.10 | Înainte de F0.10 |
| **OD-35** | **Scara de densitate**, fixată ca **set de tokeni** (ADR-009 `C26`) înainte de primul ecran. Valorile implicite Tailwind și shadcn sunt calibrate pentru SaaS aerisit; un contabil vrea maximum de rânduri pe ecran. Comprimarea după 40 de ecrane construite pe spațierea implicită înseamnă rescriere | Primul ecran de frontend | Înainte de primul ecran |
| **OD-36** | **Contractul de introducere cu tastatura**: ordine de tab, taste rapide, deplasare pe linii, tastatura numerică. Contabilul venit de la 1C introduce documente fără mouse; nicio bibliotecă nu oferă asta. Este preocupare de arhitectură frontend, nu de styling | `EntryGrid` (ADR-001), notele contabile manuale | Înainte de `EntryGrid`, în F1 |
| **OD-41** | **A doua bibliotecă de grilă pentru suprafețele de reconciliere** (import 1C, extrase bancare). Glide Data Grid — canvas, MIT, întreținut activ — este **variantă de rezervă**, nu alegere. **Nu are declanșator:** un prag măsurabil cere modelul de volum (`OD-30`), care nu există. Se **reevaluează** la F1.9, fără pretenție de criteriu. *Ce ar transforma-o în declanșator real: latența de interacțiune la percentila 95, pe un set de date numit, cu volumul luat din `OD-30`.* **Două lucruri de verificat înainte de a decide:** (1) reconcilierea probabil **nu este o grilă** — interacțiunea dominantă e acceptarea/respingerea unei sugestii calculate pe server, nu editarea de celule; forma potrivită e un panou de potrivire în două coloane cu tastatură. Decizia nu se ia din analogie vizuală cu o foaie de calcul. (2) dacă `EntryGrid` e construit ca primitivă generală (`F1.G2`), probabil acoperă și reconcilierea, iar întrebarea dispare. **Dacă totuși intră, intră mărginit:** doar ecranele de reconciliere; niciodată rapoarte contabile — canvas nu are Ctrl+F, selecție nativă de text sau afordanțe de link, de care depinde drill-down-ul din Cartea Mare și balanță | F1.9, F2 | **Reevaluare** la F1.9 |
| **OD-42** | **Entitatea din spatele lui `assignment`** — repartizarea internă `user` → `tenant` în cadrul unei firme. `ADR-017` fixează cuvântul; schema nu îl are. Spec A §1.6 are `Membership` (`user` ↔ `tenant`) și §1.7 `CompanyAccess` (`user` ↔ `company`), dar niciuna nu e repartizare organizațională: `CompanyAccess` e fapt de **autorizare**, citit de RLS, iar `assignment` e fapt **organizațional** — poate exista fără acces și poate lipsi când accesul există. Variante: entitate proprie care *conduce* acordarea de `CompanyAccess`; sau doar o citire peste `CompanyAccess` cu `granted_via='engagement'`. **Până la decizie, termenul nu se folosește în cod** | Ecranele de portofoliu ale firmei; modelul de acces delegat | Spec A, înainte de F0.3 |
| **OD-20** | Rezoluția subdomeniului în dezvoltare locală (contextul de tenant vine exclusiv din subdomeniu) | F0.10 | Înainte de F0.10 |

---
| **OD-43** | **Cum se atribuie în audit efectul produs printr-un asistent automat.** Poziția proprietarului, consemnată: asistentul este **instrument, nu actor**. Răspunde tenantul, iar cel care a activat asistentul verifică ce a făcut — aceeași poziție ca pentru un contabil angajat sau o firmă cu engagement: execută unul, răspunde altul. Consecințe deja acoperite de model: (1) nu se adaugă identitate non-umană — `audit_event.actor_user_id` rămâne `NOT NULL`, iar `ADR-020` nu are de acoperit un actor non-uman; (2) „cine a pornit asistentul" **este** activarea capabilității (R25), nu un câmp nou. **Rămâne de decis o singură coloană:** legătură nulabilă din `audit_event` către activarea prin care s-a produs efectul — exact forma lui `actor_firm_id`, care există deja pentru „a acționat ca firmă". Fără ea, „ce a făcut asistentul luna trecută" nu are răspuns. **Condiția care face răspunderea reală:** asistentul propune, motorul postează (R9) — fără un moment în care propunerea se poate respinge, „verifică" devine „constată după" | Nimic acum | Cât `audit_event` este goală în producție — după, e migrare pe tabelă append-only de volum mare |

## D. Decizii care necesită surse externe sau expertiză contabilă

**Nu se deduc, nu se completează din memorie, nu se aproximează.** Fiecare are nevoie de o sursă
citabilă sau de contabilul practicant al echipei.

| # | Ce lipsește | Blochează | Sursa necesară |
|---|---|---|---|
| **OD-21** | **Valorile** termenelor de păstrare, per clasă de retenție, cu temei legal; perioada de grație la offboarding; regimul de arhivare. **Restrânsă:** mecanismul e decis prin ADR-008 — termenele sunt parametri fiscali. Nu mai blochează F0; impactul e în F3 | F3 (offboarding) | Legislație citată + contabil sau jurist |
| **OD-22** | Valorile fiscale efective: cote TVA, cote CNAS și CNAM, plafoane, scutiri personale, cote de impozit pe venit, praguri de înregistrare, termene de raportare, coeficienți de amortizare | F1.6, F2 | Acte normative + contabil practicant |
| **OD-23** | Conținutul planului de conturi SNC — lista efectivă a conturilor | F1.1 | SNC + contabil practicant |
| **OD-24** | e-Factura / SFS: contract API, autentificare, statusuri, retry, mediu de test | F2 | SFS |
| **OD-25** | CNAS, CNAM, BNS: formatele rapoartelor și canalele de depunere | F2 | Instituțiile |
| **OD-26** | BNM: endpoint, format, cadență, comportament în zile nelucrătoare | F0.9 | BNM |
| **OD-27** | Bănci: formatele de extras acceptate și lista băncilor vizate | F2 | Băncile |
| **OD-28** | 1C: versiunile și configurațiile suportate, metoda de extragere | F1.9 | Investigație tehnică |
| **OD-29** | Țintele numerice de performanță pentru cele patru scenarii din V2 §12.4 | Indecșii și read models | Decizie umană, înainte de F1 |
| **OD-30** | Modelul de volum de date (scenarii mic / mediu / mare) — firma de contabilitate colaboratoare nu este identificată | OD-01 | Date reale |
| **OD-31** | SLA-ul intern de conformitate (propunerea neconfirmată: 5 zile lucrătoare pentru cote și praguri, 15 pentru formulare noi) | Operațiunea de conformitate | Decizie umană |

---

## F. Puncte deschise ridicate de specificații

Spec A și Spec B au produs puncte suplimentare, marcate în text ca „DECIZIE NECESARĂ". Nu sunt
copiate aici — trăiesc în specificațiile care le explică, cu opțiunile și implicațiile lor.

| Sursă | Câte | Rămase deschise | Cele care mai blochează F0 |
|---|---|---|---|
| `../specs/spec-a-tenancy.md` §11 | 25 (`DN-01` … `DN-25`) | 20 — DN-11, DN-12 închise; DN-01 prin ADR-014/016; DN-06, DN-07 prin ADR-018/019; DN-22 închisă parțial | DN-09, DN-10, DN-16 |
| `../specs/spec-b-accounting.md` §11 | 11 (`DNB-01` … `DNB-11`) | 10 — DNB-09 împărțită și rezolvată structural | DNB-06 → F0.8.1. **DNB-08 nu mai blochează F0.9.1**: invariantele sunt fixate, valorile așteaptă SFS |

Corespondențe cu registrul de mai sus, ca să nu se decidă de două ori:

- `OD-03` = `DNB-03` (propagarea planului de conturi)
- ~~`OD-07`~~ = ~~`DN-12`~~ — închise prin ADR-009
- ~~`OD-08`~~ = ~~`DN-11`~~ — închise prin ADR-004
- `OD-09` = `DN-17` (mecanismul căilor privilegiate); enumerarea e făcută în Spec A §6.2
- `OD-13` = `DN-01` (limba rusă)
- `OD-21` = `DN-22` — mecanismul închis prin ADR-008, valorile rămân

Sarcinile blocate de fiecare: `../_bootstrap/06-f0-backlog.md`, „Sinteza blocajelor".

---

## G. Triaj

**Deciziile rămase nu trebuie închise.** Închiderea preventivă este la fel de costisitoare ca cea
tacită: fixează o alegere înainte să existe informația care o justifică, apoi codul se construiește
peste ea. Triajul de mai jos spune *când* devine fiecare relevantă, ca să nu fie nevoie să
recitească nimeni tot registrul.

Fiecare identificator apare **o singură dată**, în prima categorie aplicabilă. Detaliile rămân
acolo unde sunt: `OD-*` mai sus, `DN-*` în `../specs/spec-a-tenancy.md` §11, `DNB-*` în
`../specs/spec-b-accounting.md` §11.

### T1 — Blochează F0

Trebuie închise pentru a termina faza. Sarcina blocată e în `../_bootstrap/06-f0-backlog.md`.

| Sarcină | Decizii |
|---|---|
| F0.0.4, F0.2.6 | `OD-16` |
| F0.0.5 | `OD-17` |
| F0.1 (căi privilegiate) | `OD-09` = `DN-17` |
| F0.3.1 | `DN-02`, `DN-03` |
| F0.3.2 | `OD-37` |
| F0.3.5 | `OD-20` |
| F0.3.6 | `DN-13`, `DN-14`, `DN-15` |
| F0.3.7 | `DN-08`, `DN-09` |
| F0.4.3 | `DN-20` |
| F0.5.1 | `DN-10` |
| F0.6.2 | `OD-02` |
| F0.6.3 | `DN-16` |
| F0.7.1 | `OD-12` |
| F0.7.5 | `OD-11` |
| F0.8.1 | `DNB-06` |
| F0.10.3 | `OD-19`, `OD-35` *(`OD-34` — ADR-009; `DN-01`/`OD-13` — ADR-014 și ADR-016, închise)* |
| F0.11 | `OD-30` |

### T2 — Blochează F1

`OD-01` *(după modelul de volum)*, `OD-03` = `DNB-03`, `OD-29`, `DNB-01`, `DNB-02`, `DNB-04`,
`DNB-10`, `OD-36` *(înainte de `EntryGrid`)*, `OD-41` *(reevaluare la F1.9, fără declanșator)*, `DN-04`,
`DN-05`.

### T3 — Are nevoie de contabilul practicant

**`OD-32` este închisă prin `ADR-010`:** rolul este acoperit de proprietarul proiectului, deci
intrările de mai jos sunt **deblocate**. Nu sunt răspunse — fiecare cere în continuare ADR-ul ei, cu
actul normativ citat (`CLAUDE.md` §4).

Numărul de intrări de aici **nu mai este** măsura riscului contabil. Cu rolurile colapsate, a doua
semnătură nu mai este verificare independentă. Măsura devine **acoperirea corpusului de regresie
fiscală** cu cazuri reale, cu rezultat verificat — vezi `ADR-010`.

Excepție care rămâne blocată extern: `DNB-08` (rotunjirea TVA) depinde de validatorul SFS, nu de
expertiză contabilă.

`OD-06`, `OD-23`, `DNB-05`, `DNB-07`, `DNB-09` *(partea din ADR-007, `Propus`)*, `DNB-11`,
`OD-21` *(și jurist)*, `DN-05` *(confirmarea anului fiscal)*.

### T4 — Are nevoie de informație externă

Nu se pot închide intern, oricâtă discuție ar exista.

| Sursă | Decizii |
|---|---|
| SFS | `OD-24`, `DNB-08` *(valorile; invariantele sunt fixate)* |
| CNAS, CNAM, BNS | `OD-25` |
| BNM | `OD-26` |
| Bănci | `OD-27` |
| Acte normative | `OD-22` |
| Investigație tehnică 1C | `OD-28` |
| Firmă de contabilitate colaboratoare | `OD-30` *(și în T1)* |

### T5 — Nu blochează nimic acum

Se decid la momentul lor. `OD-04` *(înainte de F2)*, `OD-05` *(după F3)*, `OD-31`, `DN-18`, `DN-19`, `DN-21`, `DN-23`, `DN-24`, `DN-25`, `OD-43` *(cât `audit_event` e goală în producție)*, `OD-44` și `OD-45` *(confirmări de contract, suita e verde cu ele)*.

---

## E. Închise

| # | Decizie | ADR | Data |
|---|---|---|---|
| **OD-02** | Numerotarea documentelor: **șabloane configurabile per companie**, general sau per tip de document, cu prefix/sufix/lungime. Filiala **nu** se modelează — `prefix` acoperă nevoia; dacă devine cerință reală, e decizie nouă cu entitate proprie | [ADR-022](022-numerotare-sabloane.md) | 2026-08-25 |
| **OD-13** | Limba rusă: **strat de prezentare exclusiv**. Contabilitatea se ține în română prin lege (nr. 287/2017, art. 7 alin. 1). Denumirile din planul de conturi rămân valoare unică, în română | [ADR-016](016-limba-contabilitatii.md) | 2026-08-24 |
| **OD-38** | Ieșire bilingvă — **nu se face.** Nu e funcționalitate amânată: pentru documentele contabile e ceva ce nu poate exista | [ADR-016](016-limba-contabilitatii.md) | 2026-08-24 |
| **OD-39** | Colația implicită a bazei: `ro-x-icu`, provider ICU. Decizie „la creare" — nu se schimbă fără reconstruirea indecșilor. Coloanele de cod primesc `COLLATE "C"` explicit | [ADR-015](015-colatie-icu.md) | 2026-08-24 |
| **OD-18** | SQL-ul de politici se aplică din migrațiile Django (`RunSQL` cu hash și pereche up/down), ca tabela și politica să fie în aceeași tranzacție. Rolurile, schemele și predicatele rămân în `infra/bootstrap/`, în afara ciclului | [ADR-012](012-sql-in-django-migrations.md) | 2026-08-24 |
| **OD-15** | Tooling Python: uv pentru mediu și dependențe, ruff pentru lint și format, pytest cu pytest-django, mypy strict **doar** pe `platform` și `accounting`. Lock file comis | [ADR-011](011-tooling-python.md) | 2026-08-24 |
| **OD-32** | Contabilul practicant: rolul este acoperit de proprietarul proiectului. Măsura de risc devine acoperirea corpusului de regresie, nu numărul de ADR-uri în `Propus` | [ADR-010](010-contabilul-practicant.md) | 2026-08-24 |
| **OD-34** | Biblioteca de componente și stratul de stil: shadcn/ui + Tailwind, componente copiate în `frontend/src/shared/`, tokeni ca sursă unică | [ADR-009](009-componente-si-stil.md) | 2026-08-24 |
| **OD-33** | Guvernanța: proprietarul aprobă; conținutul contabil, fiscal sau juridic cere co-semnătura contabilului practicant și rămâne `Propus` până există unul (`OD-32`) | [ADR-002](002-guvernanta-deciziilor.md) | 2026-08-24 |
| **OD-07** | Lista limitativă a excepțiilor, într-un singur fișier versionat: [`infra/rls/exceptions.toml`](../../infra/rls/exceptions.toml). Declară separat excepția de la `tenant_id` și forma politicii | [ADR-003](003-rls-tenancy-tables.md) | 2026-08-24 |
| **OD-08** | Contextul de sesiune: `app.tenant_id` obligatoriu și fail-closed, `app.user_id` obligatoriu, `app.actor_firm_id` și `app.company_id` opționale | [ADR-004](004-company-context.md) | 2026-08-24 |
| **OD-10** | Fazarea multi-valutei: **modelată F0**, integrare BNM și funcționalitate de bază **F1** (ledgerul are nevoie de ea), reevaluare și diferențe de curs **F2** | — *(decizie de roadmap, consemnată aici; vezi `00-inventory.md` X-4)* | 2026-08-24 |
| **OD-14** | Versiunile stack-ului: regula (LTS unde există, stabil recent unde nu, pinuit exact, upgrade între faze) plus valorile verificate — Django 5.2 LTS, Python 3.13, PostgreSQL 18, Node 24 LTS | [ADR-005](005-stack-versions.md) | 2026-08-24 |

Deciziile închise **înainte** de acest registru, prin Amendamentul 1 și Master Plan V2, sunt
inventariate în `docs/_bootstrap/00-inventory.md` §3.1. Trei dintre ele au nevoie de ADR
retroactiv, pentru că închiderea nu este susținută de text explicit:

- modelul Tenant / Company / Firm / Engagement (susținut doar de „nu se modifică" în Amendament §F)
- identitatea globală a utilizatorului (declarată închisă fără secțiune corespunzătoare — X-3)
- evaluarea stocurilor per categorie (închisă provizoriu, validare pendinte — OD-06)
