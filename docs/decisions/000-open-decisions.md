# 000 — Registrul deciziilor deschise

- **Status:** viu. Se actualizează la fiecare decizie luată sau apărută.
- **Ultima revizuire:** 2026-08-25 (ADR-018 engagementuri multiple, ADR-019 vocabular de scope, ADR-020 roluri ca date, ADR-021 MFA obligatoriu, ADR-022 numerotare; `OD-43` nouă; `OD-41`/`OD-42` erau folosite fiecare pentru două decizii — perechea apărută la F0.3.3 a devenit `OD-44` și `OD-45`; **aceeași coliziune s-a repetat în aceeași zi**, tot din lucru în paralel — `OD-44` și `OD-45` primiseră fiecare a doua decizie, devenite `OD-46` și `OD-47`, iar una dintre ele era înregistrată de două ori)
- **Sursa:** `docs/_bootstrap/00-inventory.md`, secțiunile 3 și 5.

O decizie din acest registru **nu se închide în cod**. Se închide printr-un ADR numerotat, iar
rândul de aici trece în „Închise" cu trimitere la ADR.

Coloana **Blochează** spune ce nu se poate face până la închidere. Coloana **Termen** este cel mai
târziu moment la care decizia trebuie luată fără să genereze rescriere.

---

## A. Decizii înregistrate în Amendamentul 1

| # | Decizie | Blochează | Termen | Ce se știe |
|---|---|---|---|---|
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
| **OD-12** | **Efectul de rețea al e-Facturii vs. interdicția cross-tenant** | Modelul `CounterpartyRegistry` și fluxul de documente primite | Spec A | Amendamentul §C.1 promite că, atunci când emitentul și destinatarul sunt amândoi în Evidenta, factura apare direct în lista de documente primite a destinatarului. Aceasta este o cale prin care date ale tenantului A ajung la tenantul B; nu apare nici în read models, nici în căile privilegiate. Vezi G-22 |
| **OD-45** | **Trei corecții în contractul RLS, aplicate la F0.3.3, care cer confirmare.** Fișierul își declară singur modificarea drept ADR. (1) `firm` era declarată fără coloană de tenant, dar Spec A §1.3 îi dă tenant propriu — prinsă de `IZ-76`, verificarea scrisă exact pentru drift de contract. (2) `engagement_company_scope` declarată cu `tenant_column = "client_tenant_id"`; forma de declarare a fost extinsă ca să accepte un nume de coloană, nu doar boolean. (3) `engagement_module_scope` declarată fără coloană de tenant: e atribut pur al engagementului **Renumerotată din `OD-42`** (număr folosit deja pentru entitatea `assignment`, citat în ADR-017). | Nimic — suita e verde cu ele | Confirmare la următoarea revizuire |
| **OD-44** | **Cum răspunde produsul la „la ce tenanți aparțin"?** Politica pe `tenant` a fost strânsă la `id = app.current_tenant_id() AND rls.has_tenant_access(id)`, pentru că forma extrapolată în ADR-003 lăsa rândurile altor tenanți ai aceluiași utilizator să apară în contextul unei alte cereri. Consecința: comutatorul de tenant nu se mai poate alimenta din această tabelă. Fiind întrebare cross-tenant prin natură, locul ei este în read models (INV-10) sau pe o cale privilegiată **Renumerotată din `OD-41`** (număr folosit deja pentru biblioteca de grilă). `infra/migrations/0012_tenant_context_binding.up.sql` o citează cu numărul vechi și **rămâne așa**: fișierul e aplicat, iar `C31` îl face append-only — corecția ar fi un fișier nou, nu o editare. | Comutatorul de tenant (F0.10.3); înrudită cu `OD-37` | Înainte de F0.10.3 |
| **OD-40** | **Acoperă art. 7 și conținutul documentelor primare emise de entitate?** Art. 11 nu prescrie limba pentru documentele întocmite de entitate; singura prevedere de limbă, alin. (11), privește documentele **primite din străinătate** și acceptă româna, engleza și rusa fără traducere. Rămâne de stabilit dacă o denumire de articol tastată în rusă, ajunsă pe o factură fiscală emisă, e conformă. **Până la răspuns, produsul nu restricționează nimic** | Nimic acum; determină dacă apare o restricție | Decizie contabilă |
| **OD-37** | **Cum se listează membrii unui tenant.** ADR-003 stabilește politica `user_id = app.current_user_id()` pe `membership` și `company_access`, deci ecranul „echipa mea" nu se poate face prin queryset. Opțiuni: funcție `SECURITY DEFINER` dedicată; serviciu care trece prin predicat; sau politică extinsă cu o a doua ramură — ultima reintroduce încrucișarea pe care ADR-003 o evită | Ecranele de administrare a echipei; **și administrarea rolurilor (F0.3.7a)** — `assign_role` nu poate muta rolul altui membru, iar regula anti-blocare din ADR-020 (ultimul administrator nu poate fi retrogradat) nu poate fi verificată: ambele ar cere citirea altor membership-uri. Serviciul refuză explicit, cu cod stabil, în loc să pară că funcționează | Înainte de F0.3.2 |

---

## C. Decizii de infrastructură, necesare pentru a începe F0

Reversibile individual, dar fiecare devine scumpă după ce se scrie cod peste ea.

| # | Decizie | Blochează | Termen |
|---|---|---|---|
| **OD-19** | Stack-ul frontend peste React: management de stare, client HTTP, rutare, i18n, formatare pentru RM. **Restrânsă:** grila de date a ieșit prin ADR-001; biblioteca de componente prin ADR-009 | F0.10 | Înainte de F0.10 |
| **OD-35** | **Scara de densitate**, fixată ca **set de tokeni** (ADR-009 `C26`) înainte de primul ecran. Valorile implicite Tailwind și shadcn sunt calibrate pentru SaaS aerisit; un contabil vrea maximum de rânduri pe ecran. Comprimarea după 40 de ecrane construite pe spațierea implicită înseamnă rescriere | Primul ecran de frontend | Înainte de primul ecran |
| **OD-36** | **Contractul de introducere cu tastatura**: ordine de tab, taste rapide, deplasare pe linii, tastatura numerică. Contabilul venit de la 1C introduce documente fără mouse; nicio bibliotecă nu oferă asta. Este preocupare de arhitectură frontend, nu de styling | `EntryGrid` (ADR-001), notele contabile manuale | Înainte de `EntryGrid`, în F1 |
| **OD-41** | **A doua bibliotecă de grilă pentru suprafețele de reconciliere** (import 1C, extrase bancare). Glide Data Grid — canvas, MIT, întreținut activ — este **variantă de rezervă**, nu alegere. **Nu are declanșator:** un prag măsurabil cere modelul de volum (`OD-30`), care nu există. Se **reevaluează** la F1.9, fără pretenție de criteriu. *Ce ar transforma-o în declanșator real: latența de interacțiune la percentila 95, pe un set de date numit, cu volumul luat din `OD-30`.* **Două lucruri de verificat înainte de a decide:** (1) reconcilierea probabil **nu este o grilă** — interacțiunea dominantă e acceptarea/respingerea unei sugestii calculate pe server, nu editarea de celule; forma potrivită e un panou de potrivire în două coloane cu tastatură. Decizia nu se ia din analogie vizuală cu o foaie de calcul. (2) dacă `EntryGrid` e construit ca primitivă generală (`F1.G2`), probabil acoperă și reconcilierea, iar întrebarea dispare. **Dacă totuși intră, intră mărginit:** doar ecranele de reconciliere; niciodată rapoarte contabile — canvas nu are Ctrl+F, selecție nativă de text sau afordanțe de link, de care depinde drill-down-ul din Cartea Mare și balanță | F1.9, F2 | **Reevaluare** la F1.9 |
| **OD-42** | **Entitatea din spatele lui `assignment`** — repartizarea internă `user` → `tenant` în cadrul unei firme. `ADR-017` fixează cuvântul; schema nu îl are. Spec A §1.6 are `Membership` (`user` ↔ `tenant`) și §1.7 `CompanyAccess` (`user` ↔ `company`), dar niciuna nu e repartizare organizațională: `CompanyAccess` e fapt de **autorizare**, citit de RLS, iar `assignment` e fapt **organizațional** — poate exista fără acces și poate lipsi când accesul există. Variante: entitate proprie care *conduce* acordarea de `CompanyAccess`; sau doar o citire peste `CompanyAccess` cu `granted_via='engagement'`. **Până la decizie, termenul nu se folosește în cod** | Ecranele de portofoliu ale firmei; modelul de acces delegat | Spec A, înainte de F0.3 |

---
| **OD-53** | **Nicio cale de producție nu creează o companie.** Politica pe `company` cere `rls.has_company_access(id)` și în `WITH CHECK`, deci un `INSERT` prin rolul aplicației este imposibil: compania nu are cum să aibă acces la ea însăși înainte de a exista. Azi companiile apar doar în fixture-uri, ca superuser. Onboarding-ul are deci nevoie de o cale privilegiată proprie — care, când se scrie, **trebuie să apeleze `engagement.services.provisioning.provision_company_access`** în aceeași tranzacție, altfel `IZ-27` redevine literă moartă. Aceeași întrebare acoperă și crearea unui tenant. **De decis:** cine are voie să creeze o companie, și dacă cel care o creează primește automat acces pe ea (`granted_via = 'membership'`) | Onboarding-ul; F0.2.4 e livrat fără el, cu provizionarea testată prin apel direct | Înainte de primul ecran de administrare |
| **OD-47** | **Privilegiile implicite fac orice tabelă nouă scriibilă.** `0001_roles.sql` acordă INSERT/UPDATE/DELETE către `evidenta_app` pentru fiecare tabelă creată de owner — corect pentru tabelele de business, greșit pentru cele globale, unde scrierea era oprită doar de absența unei politici de INSERT. Retras explicit pentru `counterparty_registry`, `feature_flag` și `release_ring`. **De decis:** dacă privilegiile implicite ar trebui restrânse la `SELECT`, cu acordarea scrierii per tabelă — mai sigur, dar face din fiecare tabelă nouă un GRANT în plus de scris **Renumerotată din `OD-45`**, număr deja folosit pentru corecțiile din contractul RLS | Nimic acum; cele trei tabele sunt acoperite | Înainte de F1 |
| **OD-48** | **Înrolarea MFA nu are cale de request.** `ADR-021` face al doilea factor obligatoriu, iar `authenticate()` refuză cu `auth.mfa_enrolment_required` un utilizator care nu are unul confirmat. Corect — și circular: fără sesiune nu se ajunge la niciun ecran, deci nici la cel de înrolare. Serviciile există (`enrol_totp`, `confirm_totp`) și rulează sub context, adică după autentificare, adică niciodată pentru cine are nevoie de ele. Variante: un token de înrolare cu viață scurtă, emis la invitație și consumat pe o a doua cale exemptată de context; o stare intermediară „autentificat parțial" care nu deschide context de tenant, ci doar înrolarea; sau înrolarea făcută de administratorul care invită, cu predarea codurilor în afara benzii. Prima e cea mai apropiată de `ADR-026` — cale îngustă, scop unic; ultima mută secretul pe un canal pe care nu-l controlăm | Invitarea oricărui utilizator nou; F0.10 | Înainte de primul utilizator care nu e creat prin fixture |
| **OD-50** | **Canalul de e-mail al notificărilor nu are transport.** Modelul are canalul, expedierea nu. Două lucruri lipsesc, și niciunul nu e cod: (1) expeditorul rulează **fără identitate de utilizator**, iar politica pe `notification` îngustează la destinatar — deci are nevoie de o cale privilegiată proprie, ca `P-3`; (2) nu e ales niciun furnizor SMTP. **A treia întrebare, care se decide odată cu ele:** ce are voie să conțină un e-mail. Un e-mail iese permanent din controlul de acces al sistemului — un engagement revocat nu-l retrage, iar o căsuță poștală nu intră sub obligația de păstrare a tenantului. Rândurile de livrare stau pe `unavailable`, nu pe `pending`: sunt numărabile, iar o notificare pierdută tăcut nu e | Notificările prin e-mail; nimic din in-app | Înainte de F1 |
| **OD-51** | **Politica pe `firm` nu implementează ce spune comentariul ei.** Comentariul din `0013_engagement.up.sql` zice că firma se vede „și tenanților clienți care au un engagement viu cu ea" — motivul fiind că clientul trebuie să poată răspunde la „cine îmi ține contabilitatea". Predicatul este `rls.has_tenant_access(tenant_id)` peste tenantul **firmei**, iar un administrator al clientului nu e nici membru al lui, nici nu acționează pentru el: **măsurat, întoarce fals.** Deci clientul nu poate citi numele contabilului său. Consecință imediată: notificările nu numesc cealaltă parte (F0.6.5), ceea ce e oricum corect — numele aparține altui tenant — dar un client cu doi contabili nu poate spune din notificare care a plecat. **De decis:** dacă predicatul se extinde cu direcția inversă, sau dacă numele firmei se expune printr-un read model. Nu e alegere de produs, e o divergență între comentariu și cod | Numele contabilului în interfața clientului; textul notificărilor | Înainte de F0.10 |
| **OD-52** | **Coada lui `DN-16`: stocarea propriu-zisă a atașamentelor.** Nivelul e decis ([ADR-030](030-atasamente.md), companie); restul nu. Rămân: layout-ul în S3 (bucket per tenant sau prefix per tenant), schema de semnare a URL-urilor și durata lor, limitele reale de dimensiune și tip (`base.py` are valori **SCHELET**, reversibile — o limită lipsă nu e o funcționalitate lipsă, e o scriere nemărginită accesibilă din afară), scanarea antivirus, și ce se întâmplă cu obiectele când tenantul ajunge `archived`. **Ce e deja fixat și nu depinde de răspuns:** cheia de obiect se derivă în cod, nu din intrare de utilizator, și poartă `tenant_id/company_id` în față — deci orice layout păstrează granița. Fără provider configurat, `RefusingStorage` ridică la fiecare apel: alternativa, un fallback pe sistemul de fișiere, merge în dezvoltare, trece toate testele și pierde fișiere în producție în spatele unui load balancer | Încărcarea și descărcarea propriu-zisă de fișiere | Înainte de F1 |
| **OD-49** | **Serverul WSGI și modelul de worker.** Imaginea de container rulează `gunicorn` cu workeri sincroni. Alegerea nu e neutră față de `R3`: fiecare request rulează într-o tranzacție care poartă `SET LOCAL`, iar contextul de tenant stă într-un `ContextVar` pe durata ei. Un worker asincron care întrețese requesturi pe același fir nu e automat greșit, dar nici automat corect — **și nimic din suită n-ar observa diferența**, fiindcă testele nu rulează prin server. **De decis:** dacă rămâne WSGI sincron, sau dacă trecem la ASGI, caz în care propagarea contextului are nevoie de o probă proprie înainte, nu după | Nimic acum; imaginea rulează, nu s-a măsurat | Înainte de primul deploy real |
| **OD-46** | **Extinderea gardianului la coloanele `*_key`.** `C34` cere colație explicită pe coloanele de cod; gardianul verifică sufixele `code`, `idno`, `sku`, `number`, `series`. Coloanele terminate în `_key` — `capability_key`, `module_key`, `flag_key`, `parameter_key` — sunt aceeași clasă de identificatori, dar nu sunt verificate. Extinderea listei ar semnala retroactiv tabele existente și cere migrări proprii | Nimic acum; e o lacună **înregistrată**, nu tăcută. **Renumerotată din `OD-44`**, număr deja folosit pentru listarea tenanților | Înainte de F1 |
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
| **OD-30** | **Restrânsă prin [ADR-032](032-cheia-de-partitionare.md).** Volumul **nu** mai cere o firmă colaboratoare: modelul stă pe agregate publice (BNS, BNM) plus cifrele din Amendament, cu cinci ipoteze declarate și testate la sensibilitate — vezi `_bootstrap/11-volume-model.md`. Rămâne deschis ce chiar cere date reale: **structura** (plan de conturi, parteneri, un an de rulaje, ca fixture pentru grile — `OD-28`, F1.G0) și **verificarea la leu** contra unei balanțe 1C reale (F1.2) | F1.G0, F1.2 — **nu mai blochează F0.11** | Înainte de F1.7 |
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

> **Tabela asta derivă și se strică într-o singură direcție.** Când o decizie se închide, registrul
> se actualizează și tabela nu — deci lista se umflă cu blocaje expirate, niciodată invers. Efectul
> nu e cosmetic: o listă de blocaje pe care nimeni n-o curăță încetează să fie o listă de blocaje și
> devine un motiv de a nu începe. Măturată la 2026-08-25, când trei intrări expirate au ieșit la
> iveală într-o singură zi — inclusiv `DN-08` și `DN-09`, închise prin ADR-020 și ADR-021 și
> neapărute deloc în tabela de decizii închise.

| Sarcină | Decizii |
|---|---|
| F0.1 (căi privilegiate) | `OD-09` = `DN-17` |
| F0.3.1 | `DN-02`, `DN-03` |
| F0.3.2 | `OD-37` |
| F0.3.5 | ~~`OD-20`~~ — închisă prin ADR-025 |
| F0.3.6 | `DN-13`, `DN-14`, `DN-15` |
| F0.3.7 | ~~`DN-08`~~ ADR-020, ~~`DN-09`~~ ADR-021 |
| F0.4.3 | `DN-20` |
| F0.5.1 | `DN-10` |
| F0.6.2 | ~~`OD-02`~~ — închisă prin ADR-022 |
| F0.6.3 | ~~`DN-16`~~ ADR-030; rămâne `OD-52` *(providerul, semnarea, limitele)* |
| F0.7.1 | `OD-12` |
| F0.8.1 | `DNB-06` |
| F0.10.3 | ~~`OD-19`~~ ADR-031; `OD-35` *(nu blochează scheletul — `C21` privește ecranele cu grile)* |

### T2 — Blochează F1

`OD-01` *(după modelul de volum)*, `OD-03` = `DNB-03`, `OD-29`, `DNB-01`, `DNB-04`,
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

Se decid la momentul lor. `OD-04` *(înainte de F2)*, `OD-05` *(după F3)*, `OD-31`, `DN-18`, `DN-19`, `DN-21`, `DN-23`, `DN-24`, `DN-25`, `OD-43` *(cât `audit_event` e goală în producție)*, `OD-44` și `OD-45` *(confirmări de contract, suita e verde cu ele)*, `OD-46` *(gardianul pe `*_key`)*, `OD-47` *(privilegiile implicite)*.

---

## E. Închise

| # | Decizie | ADR | Data |
|---|---|---|---|
| **DNB-02** | **Dimensiuni definite de utilizator: lista închisă rămâne, plus cinci sloturi generice** (`dim_1_id` … `dim_5_id`), cu semnificația configurată per companie în `company_dimension`. Obligativitatea se impune ca la restul, prin `company_account.required_dimensions`; indexarea rămâne B-tree. Varianta `jsonb` s-a respins fiindcă pierde exact obligativitatea și integritatea, iar varianta cu subconturi fiindcă două axe simultane produc produsul cartezian al conturilor. Limita de cinci e deliberată și vizibilă | [ADR-029](029-dimensiuni-analitice.md) | 2026-08-25 |
| **DN-16** | **Metadatele de atașament stau la nivel de companie**, nu de tenant. Aceeași graniță ca documentul pe care îl însoțesc (Spec A §5.3), iar accesul se acordă per companie: la nivel de tenant, un contabil cu acces la o singură companie a unui holding ar vedea atașamentele celorlalte — calea de scurgere pe care `company_access` există s-o închidă. Prețul acceptat: același fișier urcat la două companii se stochează de două ori | [ADR-030](030-atasamente.md) | 2026-08-25 |
| **OD-19** | **Stack frontend minimal:** TanStack Query pentru starea de server, React Router pentru rutare, `fetch` învelit subțire care ridică erori după codul stabil din `C10`, `Intl` cu `ro-MD` într-un singur modul de formatare (`C18`), șiruri în fișiere de resurse (`C32`) fără bibliotecă i18n până când rusa devine reală. **Fără bibliotecă de stare globală:** într-un ERP aproape toată starea este stare de server, iar un store devine a doua sursă de adevăr pentru aceleași date | [ADR-031](031-stack-frontend.md) | 2026-08-25 |
| **DN-08** | **Rolurile sunt date compozabile**, peste un catalog fix de permisiuni: un administrator al tenantului cu permisiunea necesară poate crea și modifica roluri, iar cele de sistem sunt protejate prin trigger | [ADR-020](020-roluri-ca-date.md) | 2026-08-25 |
| **DN-09** | **Al doilea factor este obligatoriu pentru toți.** Fără opțiune de dezactivare: `authenticate()` refuză cu `auth.mfa_enrolment_required` un utilizator fără factor confirmat | [ADR-021](021-mfa-obligatoriu.md) | 2026-08-25 |
| **OD-20** | Subdomeniul în dezvoltare locală: `*.evidenta.localhost`, cu `TENANT_BASE_DOMAIN` implicit doar în `dev.py` și obligatoriu din mediu în staging și producție. Browserele rezolvă orice `*.localhost` la loopback fără intrare în `hosts`, deci un tenant nou de dezvoltare nu costă nimic. `http://localhost:8000/` răspunde **404** și așa rămâne: o gazdă fără subdomeniu nu are tenant | [ADR-025](025-subdomeniu-in-dezvoltare.md) | 2026-08-25 |
| **OD-11** | **Nu se creează app-uri pentru module din faze viitoare.** Decizia era deja luată de `CLAUDE.md` §4, care are prioritate declarată asupra backlogului: „modelat în F0" este o obligație **negativă** — nimic din structura fazei curente nu face modulul viitor imposibil — și se **verifică**, nu se construiește. `masterdata/warehouses` și `masterdata/dimensions` rămân la F4, respectiv F1. `X-5` se rezolvă în favoarea hărții. Regula a primit și un gardian, cu probă care cade | [ADR-028](028-modelat-in-f0.md) | 2026-08-25 |
| **OD-01** | Cheile de partiționare se **desemnează acum și se aplică la prag**: `occurred_at` pentru `audit_event`, `document_event` și arhive; `accounting_date` pentru `journal_line` și `inventory_movement`; **niciodată `tenant_id`** — distribuția BNS dă un raport de volum de ordinul 50:1 între tenanți, deci partiții inegale cu două ordine de mărime. Pragul: peste ~100 mln de rânduri **și** interogări care se pot elaga după cheie. Benchmark-ul a găsit întâi altceva: un index greșit ca formă, care făcea enumerarea să citească un milion de rânduri pentru cincizeci | [ADR-032](032-cheia-de-partitionare.md) | 2026-08-25 |
| **OD-17** | Contractele de dependență se impun printr-un **gardian propriu, în suită** — parcurgere AST, contract în `infra/modules/dependencies.toml`, fiecare regulă cu probă că poate eșua. `import-linter` a fost evaluat și respins: un contract de straturi nu poate exprima `D6` (comunicare prin modelele altui modul), nu distinge `accounting.events` de `accounting.ledger` (`D3`), și tace despre pachetul pe care nimeni n-a știut să-l declare | [ADR-024](024-gardian-de-dependente.md) | 2026-08-25 |
| **OD-16** | CI pe **GitHub Actions**, cu Postgres ca serviciu configurat cu aceeași colație ca producția. Bootstrap-ul rulează cu roluri per fișier, nu ca superuser — altfel pipeline-ul ar fi mai permisiv decât producția și n-ar prinde lipsa unui privilegiu | [ADR-023](023-ci-github-actions.md) | 2026-08-25 |
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
