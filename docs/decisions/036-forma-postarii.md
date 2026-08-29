# ADR-036 — Forma postării stă în cod; restul configurării stă în date

- **Status:** **Acceptat** — 2026-08-29, de proprietar, contabil practicant (ADR-010): clasificarea
  `C1`–`C5` din §11 aprobată prin instrucțiune scrisă; `C3` ștearsă cu motiv. Versiunea `Propus` din
  2026-08-25 rămâne vizibilă în istoric; §11 e singura secțiune rescrisă
- **Data:** 2026-08-25; `Acceptat` 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** `DNB-04` (Spec B §3.2, §11)
- **Afectează:** Posting Engine (F1.4), `posting_rule` / `posting_rule_line` din Spec B §3.2,
  `journal_line`, importatorul 1C (F1.9), [ADR-029](029-dimensiuni-analitice.md)

---

## 0. Ce NU decide acest ADR

Această secțiune există pentru că versiunea 1 a documentului a generat confuzie reală. Termenul
„forma postării" a fost citit ca „formularele aplicației". Nu este cazul.

**„Forma postării" înseamnă strict trei lucruri:**

1. Câte linii de jurnal produce un eveniment
2. Ce semn are fiecare linie (debit/credit)
3. Din ce câmp al evenimentului derivă fiecare sumă

**Atât.** Nimic despre interfață, formulare, ecrane, rapoarte sau tipar. Vezi §4 pentru lista
explicită a ceea ce rămâne integral configurabil.

---

## 1. Context

Posting Engine transformă un eveniment de business într-un set de linii de jurnal. Decizia este cu
sens unic: registrul e append-only (`R10`), deci orice postare produsă sub o regulă greșită rămâne
acolo permanent.

### 1.1 Ce fac concurenții

**1C** separă metadatele (plan de conturi, registre) de logica de postare, care e cod în modulul de
postare al fiecărui document. Peste asta are un strat de date — registre de „conturi de evidență"
care leagă grupe de nomenclator, depozite și tipuri de contrapărți de conturi concrete — plus
„operațiuni tipice" configurabile pentru note manuale. Subconto (dimensiunile analitice) sunt
definibile de utilizator.

Granița 1C este corectă. Problema este că **stratul de cod e editabil per client**: configurația e
deschisă, fiecare partener o modifică per client. De aici: actualizări cu îmbinare manuală,
imposibilitatea actualizării centralizate, dependența de rețeaua de integratori.

Observație verificată: în 1C, convențiile de rotunjire se schimbă intrând în configurator și
modificând obiectul de configurație. Nu e o setare de utilizator.

**UNA (Unisim-Soft)** a mers invers: ERP pe Oracle, cu un „limbaj de contabilitate universal" bazat
pe dubla înregistrare. Trei registre — documente primare, formule contabile, registre speciale —
iar formulele se generează pornind de la tipul operației. Postarea ca date, DSL interpretat.

Costul declarat public: peste 160 de specialiști formați din 2000 pentru a dezvolta și susține
soluții verticale, cu ~30 de angajați permanenți. Poziționare: holdinguri, fabrici, rețele de
supermarketuri.

### 1.2 Constrângerea reală

Ambii, prin arhitecturi opuse, ajung la aceeași necesitate: **o rețea de oameni între produs și
client.**

Modelul nostru de distribuție e self-service prin cabinete de contabilitate. Nu avem și nu
construim o rețea de implementatori.

**Ipoteza nouă, care schimbă calculul:** configurarea asistată de AI poate elimina rețeaua de
implementatori pentru scrierea configurației. Este o capacitate pe care niciun concurent din
Moldova nu o are, și e tratată ca mecanism de prim rang în §9.

Dar AI-ul schimbă **cine scrie** configurația, nu **unde ajunge**. Costul rețelei de implementatori
nu stă în orele de scris — stă în divergență: N variante de întreținut, actualizat și depanat.
Acesta este criteriul care structurează tot ADR-ul.

---

## 2. Opțiuni evaluate

1. **Postare integral în date — modelul UNA.** Registru de formule interpretat la runtime, ca
   opțiunea (A) din Spec B §3.2. *Avantaje:* orice tratament nou se scrie fără deployment.
   *Dezavantaje:* produce un limbaj de programare în baza de date — erori tăcute și fiscale,
   verificare statică imposibilă. Costul real e vizibil în cifrele UNA: 160+ specialiști formați.
   *Cost de schimbare ulterioară:* maxim — registrul postat sub DSL rămâne acolo.

2. **Postare integral în cod, fără strat de date** — opțiunea (B) din Spec B §3.2. *Avantaje:*
   spațiu de test minim, totul verificabil static. *Dezavantaje:* orice schimbare legislativă de
   numerotare devine deploy; subconturile proprii devin imposibile. *Cost de schimbare:* mediu.

3. **Postare configurabilă per tenant, fixată după alegere.** Clientul alege tipul de postare la
   onboarding; odată ales, rămâne fix. *Avantaje:* fixarea chiar limitează divergența — e cea mai
   bună variantă a ideii. *Dezavantaje:* rămâne divergență semantică permanentă între tenanți, cu
   expunere legală per tenant și spațiu de test multiplicat. *Cost de schimbare:* mare, per tenant.

4. **Cod editabil per tenant, scris de AI.** *Avantaje:* viteză aparentă. *Dezavantaje:* AI-ul
   schimbă autorul, nu destinația; divergența rămâne identică, produsă mai rapid, de un autor care
   nu poate fi tras la răspundere. *Cost de schimbare:* același ca (1), atins mai devreme.

5. **Hibrid, în straturi, cu destinație diferențiată a configurării** — opțiunea (C) din Spec B
   §3.2, cu granița definită explicit aici. *Avantaje:* o singură semantică de registru pentru toți;
   configurare completă acolo unde contabilul o folosește zilnic. *Dezavantaje:* un tratament
   contabil inexistent cere muncă de produs, nu configurare în tenant. *Cost de schimbare:* mic
   dacă granița e trasată acum, mare dacă migrează în timp — de aceea §11 și testul de falsificare.

---

## 3. Decizie

**Opțiunea 5: hibrid, în straturi, cu destinație diferențiată a configurării.**

| Strat | Conținut | Cine schimbă | Unde ajunge |
|---|---|---|---|
| 0 | Interfață, formulare, tipar, rapoarte | Clientul, direct sau prin AI | În tenant, imediat |
| 1 | Forma postării | Echipa de produs (AI redactează, produsul absoarbe) | În produs, pentru toți |
| 2 | Legarea rol → cont, subconturi | Clientul, direct sau prin AI | În tenant, imediat |
| 3 | Politici contabile | Clientul, alegere din listă | În tenant, imediat |
| 4 | Șabloane operațiuni tipice | Clientul, editare liberă | În tenant, imediat |

**Regula fundamentală: codul deține forma postării; totul în jurul ei e configurabil per tenant.**

---

## 4. Stratul 0 — Interfață și prezentare (integral configurabil)

Nimic din acest strat nu e restricționat. Configurabil per tenant, direct sau prin AI, fără
implicare de produs:

- **Formulare de listă** — coloane, ordine, lățimi, filtre implicite, grupări, sortare
- **Formulare de detaliu** — dispunere, secțiuni, ce se afișează, ce se ascunde
- **Câmpuri suplimentare** pe documente, nomenclatoare și contrapărți
- **Formulare de tipar** — șabloane de documente, layout, conținut
- **Rapoarte** — prin report builder, definite de utilizator
- **Ergonomia introducerii** — ordinea de tabulare, valori implicite, câmpuri obligatorii,
  comportament la tastatură (vezi `OD-36`)
- **Terminologie și denumiri** — inclusiv glosarul rus aliniat la terminologia 1C
- **Profiluri de activitate** — seturi preconfigurate care setează implicitele pentru un tip de
  business

### 4.1 Constrângerea unică

Formularele de tipar ale documentelor cu regim special (factura fiscală) trebuie să respecte
formularul tipizat aprobat prin ordin. Layoutul e impus de lege, nu de produs. Restul formularelor
de tipar sunt libere.

*Notă de reconciliere:* stratul 0 nu suspendă `C32` (șirurile în fișiere de resurse), `C33`/`C38`
(documentul legal se generează în context românesc) și `C39` (pe document apare denumirea legală).
Un client poate reticheta orice în interfață; nu poate reticheta un registru.

---

## 5. Stratul 1 — Forma postării (cod, o singură versiune)

Pentru fiecare `event_type` există un handler tipizat care declară:

- câte linii de jurnal produce
- semnul fiecărei linii
- din ce câmp al evenimentului derivă fiecare sumă
- ce **roluri de cont** solicită (nu conturi concrete)
- ce invarianți trebuie să țină

### 5.1 Proprietăți

- **O singură versiune pentru toți tenanții.** Nu există variantă per tenant.
- **Determinist.** Aceleași intrări → aceleași linii, oricând, pentru orice tenant.
- **Pur.** Primește evenimentul și legările; returnează linii. Nu citește starea registrului.
- **Fără cont de rezervă.** Un rol nelegat e eroare la postare — aceeași poziție ca Spec B §3.3.
  Postarea tăcută pe cont generic e cel mai prost mod de eșec: se descoperă luni mai târziu.

### 5.2 Invarianți verificați de motor

1. Suma debitelor = suma creditelor, în moneda funcțională (`R11`)
2. Toate liniile aparțin aceluiași tenant (`R1`)
3. Toate liniile cad în aceeași perioadă, iar perioada e deschisă (`R12`)
4. Fiecare linie referă un cont existent și valid la data postării
5. Nicio linie cu sumă zero, cu excepția cazurilor declarate de handler
6. Postarea e legată de exact un document sursă sau o notă manuală (`R13`)

Verificați de motor, nu de handler. Un handler care îi încalcă eșuează la postare, nu produce date
greșite.

### 5.3 De ce acest strat rămâne în produs

Motivul nu e că flexibilitatea ar fi rea. Este răspunderea.

Dacă un tenant își reconfigurează postarea și declarația TVA iese greșită, la 1C există un partener
care a semnat lucrarea. La UNA există un specialist certificat. În modelul nostru, la capătul
lanțului e produsul — cu o postare pe care nimeni nu a validat-o.

Nu e o problemă tehnică rezolvabilă cu teste mai bune. E expunere legală care crește proporțional cu
succesul: N tenanți cu semantică de postare divergentă = N moduri în care produsul poate genera o
declarație neconformă.

Observație: opțiunea 3 din §2 — „clientul alege tipul de postare, iar odată ales rămâne fixat" —
conține deja recunoașterea implicită a aceleiași probleme. Fixarea e o formă de îngrădire a
divergenței.

---

## 6. Stratul 2 — Conturi și analitică (configurabil de client)

### 6.1 Legarea rol → cont

Handler-ele referă **roluri de cont** — sloturi semantice de tipul `TVA_DEDUCTIBIL`, `MARFA_STOC`,
`DATORII_FURNIZORI`. Legarea rol → cont concret trăiește în date, cu `valid_from` / `valid_to`, per
tenant.

Rezolvă: schimbări legislative de numerotare (insert), subconturi proprii (insert), planuri de
conturi diferite pe același handler.

### 6.2 Legare condiționată

Un rol poate avea legări diferite după o cheie de context — grupă de nomenclator, depozit, tip de
contraparte, cotă TVA. Echivalentul „conturilor de evidență" din 1C.

**Decisă prin [ADR-051](051-chei-de-context-enumerate.md)** (închide `OD-55`): cheile de context
sunt **enumerate în cod**, valorile și legările sunt date, per companie. O cheie de context
extensibilă de client ar însemna un evaluator de condiții peste `payload`, adică exact DSL-ul
respins în §2, opțiunea 1; o cheie nouă e o versiune de platformă, nu o setare de tenant.

### 6.3 Subconturi — definibile de client, în limita din ADR-029

> **Corecție față de versiunea 1** a documentului, care restricționa dimensiunile analitice la un
> set închis definit în cod. Restricția, formulată așa, era nejustificată.

O dimensiune analitică e o referință tipizată atașată liniei de jurnal. Nu atinge invarianții
registrului, nu schimbă sumele, nu afectează declarațiile. 1C însuși permite definirea tipurilor de
subconto de către utilizator.

**Constrângerea nu e arhitecturală, ci de schemă — și e deja luată.**
[ADR-029](029-dimensiuni-analitice.md) (`Acceptat`, închide `DNB-02`) fixează forma:
zece dimensiuni din lista închisă plus **cinci sloturi generice** (`dim_1_id` … `dim_5_id`), cu
semnificația configurată per companie în `company_dimension`. Sloturile *sunt* mecanismul prin care
subconturile devin definibile de client; ele nu sunt o restricție adăugată de ADR-ul de față.

Ce nu se poate, și trebuie spus explicit ca să nu reapară ca „mică extindere":

- **Nu „orice număr rezonabil per cont".** Plafonul e cinci sloturi per companie, fiindcă
  dimensiunile sunt **coloane** pe `journal_line`, iar `journal_line` e tabelă append-only de volum
  mare (`R21`): adăugarea unei coloane pe ea nu mai e migrare ieftină. ADR-029 spune deschis că
  numărul cinci **nu e măsurat** și se ridică la prima companie care cere a șasea.
- **Nu `jsonb` cu tipuri arbitrare.** Respins în ADR-029 pentru că pierde obligativitatea
  (`company_account.required_dimensions`) și integritatea — `balti` și `Balti` devin două filiale.

Dacă validarea ulterioară arată că cinci sloturi nu ajung, mișcarea corectă este un ADR nou care
**înlocuiește** ADR-029, nu o formulare mai largă strecurată aici (`decisions/README.md`, „Ce nu se
face").

### 6.4 Imutabilitate

Schimbarea unei legări **nu** afectează postările existente. Legarea are `valid_from` și se aplică
doar înainte. Nu există recalculare retroactivă.

---

## 7. Stratul 3 — Politici contabile (listă închisă)

Unde SNC permite explicit mai multe tratamente, clientul alege — dintre variante implementate în
cod, fiecare cu handler propriu și teste proprii.

### 7.1 Ancorajul legal

În Moldova, politica de contabilitate e un document real, adoptat și aprobat prin ordin intern.
Ecranul de politici **este** acest document. Produsul îl poate genera din setări — funcționalitate
cu valoare comercială directă.

### 7.2 Criteriul de admitere

> **O opțiune intră în stratul 3 dacă și numai dacă SNC permite explicit alternativa, și dacă are un
> set propriu de teste de acceptanță.**

**Criteriu de buzunar:** dacă schimbarea ar trebui consemnată în documentul de politică contabilă al
companiei → e politică. Dacă nu → e convenție de platformă
([ADR-037](037-conventii-de-platforma.md)).

### 7.3 Mulțimea din lege, implicitul din 1C

Contabilii moldoveni au douăzeci de ani de reflexe 1C. Adoptarea comportamentului 1C ca **valoare
implicită** reduce frecarea de migrare la zero, fără a ceda nimic legal — mulțimea rămâne definită
de lege.

Ordinea obligatorie de construcție a catalogului:

1. Enumeră din SNC ce tratamente sunt permise
2. Verifică în 1C care e comportamentul implicit
3. Adoptă-l ca default, dacă se află în mulțimea de la pasul 1

Ordinea inversă moștenește tacit presupuneri de platformă și ratează alternative permise de lege pe
care 1C nu le implementează.

### 7.4 Simplitate prin implicite, nu prin sărăcie

Flexibilitatea și simplitatea sunt în tensiune. Fiecare opțiune expusă e o decizie mutată pe umerii
clientului. 1C este cel flexibil — și tocmai de aceea e perceput ca greu.

Principiul de produs: **implicite bune din profilul de activitate ales la onboarding**, cu opțiuni
disponibile la cerere, nu expuse din start. Un contabil care nu deschide niciodată ecranul de
politici trebuie să obțină rezultate corecte.

### 7.5 Blocare

- Politicile care afectează evaluarea se fixează la deschiderea exercițiului
- Odată ce există postări în exercițiu, ecranul devine read-only
- Ieșire: schimbare explicită, motivată, în audit, cu avertisment că necesită notă în situațiile
  financiare

### 7.6 Prezentare

Fiecare opțiune afișează **consecința**, nu doar denumirea.

- Insuficient: „Cost mediu ponderat / FIFO"
- Corect: „Cost mediu ponderat — recalculat la fiecare intrare; afectează costul vânzărilor și
  valoarea stocului"

---

## 8. Stratul 4 — Șabloane de operațiuni tipice (libere)

Echivalentul „операции типовые" din 1C. Clientul își definește șabloane de note contabile manuale:
conturi, dimensiuni, formule simple de sumă.

**Domeniu: exclusiv note contabile manuale.** Nu pot fi folosite pentru postarea automată a
documentelor.

Sigure, pentru că nota manuală e scrisă și verificată de un om înainte de postare. Absorb o mare
parte din presiunea de personalizare.

---

## 9. Configurarea asistată de AI

Mecanism de prim rang, nu funcționalitate secundară. Este avantajul competitiv structural față de 1C
și UNA: **elimină costul rețelei de implementatori pentru scrierea configurației.**

### 9.1 Destinație diferențiată

| Ce cere clientul | AI-ul scrie | Ajunge | Timp |
|---|---|---|---|
| Formular, coloane, câmp nou, raport, tipar | Configurație de strat 0 | În tenant | Imediat |
| Mapare de cont, subconto nou, legare condiționată | Configurație de strat 2 | În tenant | Imediat |
| Alegere de politică contabilă | Selecție de strat 3 | În tenant | Imediat |
| Șablon de notă manuală | Configurație de strat 4 | În tenant | Imediat |
| **Tratament contabil inexistent** | **Handler + teste + invarianți** | **În produs, pentru toți** | **Ore–zile** |

Ultima linie e singura care nu ajunge direct în tenant.

### 9.2 De ce ultima linie e diferită

AI-ul schimbă cine scrie configurația, nu unde ajunge. Dacă AI-ul scrie postare per tenant, se
obține exact divergența rețelei de implementatori — doar produsă mai repede și de un autor care nu
poate fi tras la răspundere.

Cu handler-ul absorbit în produs:

- clientul primește funcționalitatea în ore sau zile, nu luni
- al doilea client cu aceeași nevoie o primește gratuit, deja testată
- **produsul acumulează acoperire în loc să se fragmenteze**

Acumularea este mecanismul prin care se atinge obiectivul „acoperirea oricărei industrii". Nu prin
forking, ci prin bibliotecă crescândă de tratamente.

*Legat:* `OD-43` fixează deja atribuirea în audit a efectului produs printr-un asistent automat —
asistentul e instrument, nu actor, iar condiția care face răspunderea reală e că asistentul propune
și motorul postează (`R9`).

### 9.3 Comparație de viteză

| | 1C / UNA | Evidenta |
|---|---|---|
| Ciclu | Contactezi partenerul → ofertă → plată → implementare | Ceri → primești în zile |
| Cost per cerere | Facturat | Zero |
| Întreținere ulterioară | La fiecare actualizare, per client | Niciodată — e în produs |
| Al doilea client cu aceeași nevoie | Plătește din nou | O are deja |

---

## 10. Non-obiective

Formulate ca ceea ce sunt: limite pe **divergență semantică**, nu pe flexibilitate.

1. **Fără divergență semantică per tenant în ce produce registrul.** Aceleași documente + aceleași
   politici → același registru, pentru orice tenant.
2. **Fără DSL de formule contabile** interpretat la runtime pentru postarea automată.
3. **Fără cod per tenant.** O singură versiune; diferențiere prin straturile 0, 2, 3, 4 și feature
   flags (`R23`).
4. **Fără recalculare retroactivă** a postărilor la schimbarea unei legări sau politici.

### 10.1 Ce NU e non-obiectiv

Pentru claritate, următoarele sunt permise și încurajate:

- Orice configurare de interfață, formulare, tipar, rapoarte
- Subconturi și dimensiuni analitice definite de client, în limita din §6.3
- Mapări de conturi arbitrar de fine
- Configurare prin AI, în toate straturile

---

## 11. Clasificarea cazurilor — APROBATĂ

> Clasificarea de mai jos e a proprietarului (instrucțiune scrisă, 2026-08-29, punctul 5), peste
> standardele citate în `_input/cercetare/` de la `3c3fccc`. Întrebarea per caz a rămas aceeași:
> **se rezolvă prin alegerea unui cont diferit (strat 2), prin alegerea între variante permise de
> lege (strat 3), sau cere o formă diferită de postare (handler în strat 1)?** Patru din cele cinci
> presupuneri inițiale au căzut la lectură; ce urmează e ce a rămas după ea.

| # | Caz | Clasificare | Ce spune actul, și ce decurge | Sursă |
|---|---|---|---|---|
| C1 | Metoda de evaluare a stocurilor la ieșire | **Strat 3** pentru metodă; **strat 1** pentru momentul calculului și pentru costul standard / prețul cu amănuntul | Patru metode, listă **închisă**: identificare specifică, FIFO, cost mediu ponderat, **LIFO** (reintrodusă prin OMF 48/2019). Aceeași formulă, altă sumă — deci politică. **Momentul calculului cere două handlere**: *permanent*, unde ieșirea poartă costul, și *periodic*, unde costul apare la închiderea perioadei. Descrierea politicii e listă **deschisă** (pct. 37, „sau în alt mod"), forma postării e închisă. **Granularitatea** (pct. 34): politica se alege per clasă de stocuri similare — ecranul de politici nu e un selector unic. **Costul standard** și **prețul cu amănuntul** (pct. 39) sunt două handlere proprii — devieri, respectiv adaos comercial — aplicabile **concomitent** pe categorii diferite („una din" șters în 2019). Costul efectiv de intrare **nu** e opțiune la pct. 39: e regula de recunoaștere de la pct. 13 | SNC „Stocuri" pct. 13, 33, 34, 36, 37, 37¹, 39 — [`c1-c3-c5-stocuri.md`](../_input/cercetare/c1-c3-c5-stocuri.md) |
| C2 | Metoda de amortizare | **Strat 3** | Trei metode (pct. 22): liniară, unități de producție, diminuarea soldului. Metoda se stochează **per obiect**, cu implicit de la categorie — *inferență și alegere de produs, nu citat*: standardul nu fixează nivelul într-o propoziție (pct. 19, 20, 26, 27 îl sugerează). **Schimbarea metodei** (pct. 27) e **obligație**, nu opțiune, și e **modificare de estimare**: fără retratare retrospectivă, rata nouă din durata **rămasă**, baza e valoarea contabilă **fără** scăderea valorii reziduale (Exemplul 6). **Amortizarea fiscală nu e handler**: registru paralel, în afara partidei duble (art. 26¹ CF, anexa prescrisă); calculul ei rămâne blocat pe HG 704/2019, neobținută | SNC „Imobilizări necorporale şi corporale" pct. 19–27 — [`c2-amortizarea.md`](../_input/cercetare/c2-amortizarea.md) |
| ~~C3~~ | ~~Cheltuieli de transport-aprovizionare~~ | **Ștearsă din registru** | Nu e politică și nu e caz: pct. 15 spune că costul de intrare **„cuprinde"** costurile de transportare-aprovizionare — declarativ, fără alternativă; termenul apare o singură dată în 263 de pagini, iar Planul general de conturi n-are cont separat pentru ele. Ipoteza „două tratamente" era greșită; ce se confundase e mecanica costului standard (pct. 40), absorbită în C1 | SNC „Stocuri" pct. 14, 15, 40 — același fișier |
| C4 | Diferențe de curs valutar și de sumă | **Handler propriu** pentru recunoaștere | Recunoașterea e determinată: favorabile la venituri, nefavorabile la cheltuieli. **Periodicitatea** reevaluării (pct. 13) e **parametru** al handlerului — valoare aleasă în politica contabilă, nu handler separat. **Cursul contractual** (pct. 19) e câmp pe antet și decide dacă apare vreo postare: la curs de livrare sau curs fix (pct. 21) diferența **nu apare deloc**. **Trei perechi de conturi, nu două**: 6226/7224 curs valutar, 6227/7225 sumă, **6127/7147** ecartul dintre cursul BNM și cursul băncii — care aterizează în rezultatul **operațional**. **Avansul** are curs fixat la plată și e **exclus permanent** din reevaluare (pct. 11–12 în redacția 2020, pct. 23). **Handlerul de reevaluare nu se specifică** până nu se extrage Anexa 1 | SNC „Diferenţe de curs valutar şi de sumă" pct. 4, 6, 8, 11–15, 17, 19, 21–23 — [`c4-diferente-de-curs.md`](../_input/cercetare/c4-diferente-de-curs.md) |
| C5 | Repartizarea costurilor indirecte de producție | **Handler** cu formula de subabsorbție ca **regulă versionată** | Două etape obligatorii (pct. 29); variabilele integral (pct. 30(1)); constantele pe capacitatea normală, cu formula scrisă în standard și restul la cheltuieli curente (pct. 30(2)) — regulă în `fiscal_logic_version`, nu opțiune. **Baza de repartizare** (pct. 31, „de exemplu") e **nomenclator, listă deschisă**: tenantul o definește, fiindcă e o cantitate care intră în calcul, nu o structură de postare — prima confirmare a testului de falsificare din §11.1 | SNC „Stocuri" pct. 29–31 — [`c1-c3-c5-stocuri.md`](../_input/cercetare/c1-c3-c5-stocuri.md) |
| C6 | Subconturi analitice proprii | **Strat 2**, în limita din §6.3 | Referință tipizată pe linie, prin sloturile din ADR-029 și ADR-048. Fără impact pe formă | — |
| C7 | Conturi diferite per grupă / depozit | **Strat 2**, legare condiționată | Echivalent „conturi de evidență" 1C. Cheile: **enumerate în cod** ([ADR-051](051-chei-de-context-enumerate.md)) | — |
| C8 | Schimbare legislativă de numerotare | **Strat 2** | Insert cu `valid_from`. Vezi `DNB-03` = `OD-03` | — |
| C9 | Formulare de listă / detaliu, tipar, rapoarte | **Strat 0** | Integral configurabil. Nu a fost niciodată restricționat | — |
| C10 | Rotunjire TVA, granularitate postare | **Structura formularului** + convenții de platformă | Linia e autoritativă prin construcția formularului — OMF 118/2017 pct. 15–24, act citat; zecimalele (2 / 4 / `half_up`) sunt convenții aprobate, `provisional` fiindcă formularul tace. Nu se consemnează în politica contabilă | [ADR-037](037-conventii-de-platforma.md) `Acceptat` |

**Ce nu se atinge, spus explicit:** `OD-22` pentru parametrii fiscali reali; HG 704/2019 (amortizarea
fiscală); Anexa 1 din SNC „Diferențe de curs" (reevaluarea). Refuzurile existente rămân, cu
registrul lor.

### 11.1 Test de falsificare

Dacă apare un caz real care cere o **formă de postare variabilă per tenant**, imposibil de enumerat
ca listă închisă de politici — granița e greșită și trebuie mutată **acum**, cât registrul e gol.

---

## 12. Consecințe

### 12.1 Ce devine posibil

- O singură versiune de cod. Actualizările legislative sunt automate și obligatorii, fără îmbinare
  manuală.
- Configurare completă a interfeței, conturilor și analiticii, fără implicare de produs.
- Configurarea prin AI elimină costul specialistului pentru straturile 0, 2, 3, 4.
- Reproducerea deterministă a bug-urilor: același document, același registru, orice tenant.
- Spațiu de test finit: handlere × politici.
- Acumulare de acoperire: fiecare tratament nou servește toți clienții viitori.

### 12.2 Ce devine imposibil sau scump, asumat

- **Un tratament contabil inexistent cere muncă de produs.** Nu se poate crea în tenant, nici măcar
  prin AI. Ciclul e ore–zile, nu instantaneu.
- Fiecare politică nouă multiplică spațiul de test.
- Segmentele cu cerințe genuin exotice — holdinguri complexe, producție multi-profil — sunt mai bine
  servite de o platformă configurabilă. **Acesta e segmentul UNA, și e o cedare deliberată.**

### 12.3 Ce trebuie modificat ca urmare

- **Spec B §3.2** descrie `posting_rule` / `posting_rule_line` cu `conditions jsonb` și
  `amount_expression jsonb` — forma opțiunii (A). La `Acceptat`, secțiunea se rescrie: structura de
  date rămâne pentru rezoluția contului și condițiile simple, iar suma și numărul de linii vin din
  handler. Fără rescriere, schema din spec contrazice decizia.
- `CLAUDE.md` primește regula care decurge — **doar după `Acceptat`** (`decisions/README.md`).
  *Făcut la `Acceptat`, 2026-08-29: `R28`.*
- `OD-55` intră în registrul deciziilor deschise (§6.2). *Închisă prin ADR-051.*

### 12.4 Formularea onestă a compromisului

Evidenta e **mai puțin flexibilă decât 1C și UNA într-un singur punct**: forma postării nu poate fi
editată la client.

Nu e mai puțin flexibilă la conturi, subconturi, analitică, formulare, rapoarte sau tipar — acolo e
echivalentă. Iar la schimbări legislative și lucru multi-client e mai flexibilă, pentru că
schimbarea e un insert care ajunge instantaneu la toți.

Flexibilitatea nu e redusă, ci **mutată**: scoasă de unde produce divergență, păstrată unde
contabilul o folosește zilnic.

Notă de poziționare: aceeași proprietate se numește diferit din partea clientului. „Nu se poate
personaliza" pentru un partener 1C înseamnă, pentru un client SaaS, „nimeni nu-ți poate strica
contabilitatea și actualizările nu-ți sparg nimic".

### 12.5 Ce se verifică automat

Nimic încă — Posting Engine nu există. Ce va verifica, la implementare:

- corpusul de regresie fiscală (`C14`): același eveniment, aceeași dată efectivă → aceleași linii
- `C12`: fiecare efect financiar cu test de integrare până la journal line, cu sume și conturi
- gardianul de dependențe (ADR-024) pentru `D2`/`D3`: handler-ele stau în `accounting`, nu în
  modulele operaționale

---

## 13. Ce mai trebuie decis

| Referință | Ce blochează | Stare |
|---|---|---|
| `C1`–`C5` din §11 | Trecerea acestui ADR în `Acceptat` | **Închis** 2026-08-29: clasificarea aprobată de proprietar, peste SNC-ul citat de la `3c3fccc`; F1.4.4 deblocată |
| `DNB-01` | Vocabularul `event_type` — intrarea handler-elor din §5 | **Închisă** prin [ADR-038](038-vocabularul-de-evenimente.md): nucleul deține vocabularul |
| `DN-04` | Câmpurile de valută pe linia de jurnal | **Închisă** prin [ADR-039](039-valuta-si-perioade.md): moneda funcțională MDL fixă, linia poartă valuta din ziua 1 |
| `DN-05` | Modelul de perioade și exercițiu fiscal — invariantul 3 din §5.2 se sprijină pe el | **Închisă** prin [ADR-039](039-valuta-si-perioade.md): perioada operațională e luna, exercițiul are date explicite |
| `OD-55` | Mulțimea cheilor de context la legarea condiționată (§6.2) | **Închisă** prin [ADR-051](051-chei-de-context-enumerate.md): enumerate în cod |
| `OD-36` | Contractul de introducere cu tastatura | **Închisă** prin [ADR-052](052-contractul-de-tastatura.md) — e strat 0 |
| [ADR-037](037-conventii-de-platforma.md) | Rotunjire, zecimale, granularitate | **Închis** 2026-08-29: `Acceptat` — linia e autoritativă prin structura formularului; convențiile de precizie aprobate |
| `DNB-03` = `OD-03` | Propagarea planului de conturi | **Nu blochează F1** — vezi §13.1 |

### 13.1 De ce `DNB-03` nu blochează F1

Milestone-ul F1 e o balanță corectă la leu. Propagarea legislativă în planurile a mii de tenanți
apare abia când există tenanți în producție *și* se schimbă legea.

Precondiția necesară în F1: **conturile au `valid_from`/`valid_to`, nu se șterg niciodată**, iar planul
unui tenant e **instanțiere cu legătură păstrată către rândul de șablon** (`template_account_id`), nu copie
derivată care rupe legătura. Atât.

> **Corecție față de formularea inițială, găsită la implementarea F1.1.** Textul spunea „versiune de șablon +
> strat de suprascriere". Luat literal, nu ține, și motivul e ledgerul: `journal_line.account_id` are nevoie de
> un identificator stabil pe viața companiei, iar într-un strat pur de suprascriere un cont de sistem ar fi
> identificat de rândul global până la prima redenumire și de un rând de companie după — adică identitatea
> contului s-ar schimba sub o tabelă append-only care deja o referă. Ce urmărea formularea supraviețuiește
> intact prin legătura către șablon: propagarea rămâne o **actualizare peste rânduri identificate**, nu o
> migrare de date. Diferența dintre cele două formulări e invizibilă până la prima propagare și scumpă după.

*Registrul l-a ținut ca blocând `accounting/coa` (F1.1). După livrarea modulului, blocajul nu s-a mutat —
obiectul lui s-a construit sub el: `OD-03` blochează acum **propagarea**, o funcționalitate în interiorul unui
modul care există. Afirmația de aici îl restrânge, nu îl închide.*

**Starea reală la 2026-08-25, măsurată prin grep peste `backend/` și `infra/`, nu dedusă.** Schema și
serviciile F1.1 sunt livrate, cu 26 de teste sub rolul de aplicație; **niciun apelant de producție nu
există**, iar asta contează pentru cine citește ADR-ul ca stare de fapt:

- `instantiate_chart` e apelat doar din teste. O companie creată azi nu primește niciun plan — și nici nu
  poate: calea privilegiată `P-9` din [ADR-040](040-crearea-tenantului-si-a-companiei.md) e decisă, dar
  nescrisă, deci nu există cale de producție care să creeze compania de la care ar porni lanțul.
- Golurile sunt **două, nu unul**: *ce* se încarcă în șablon (`OD-23`, conținutul planului) și *prin ce*
  (`OD-56` — `evidenta_app` are `SELECT`, iar `INSERT/UPDATE/DELETE` îi sunt retrase explicit în
  `0033_coa.up.sql`). Dacă ordinul ar fi pe masă mâine, nimic nu l-ar putea introduce.
- `company_chart.last_propagation_at` există și nu e scrisă de nimic. Livrată conștient — toate cele patru
  variante de propagare din Spec B §2.5 o cer și niciuna nu-i schimbă înțelesul — dar e a doua datorie pe
  care propagarea o va aduce cu ea, alături de politica însăși. Numită aici tocmai fiindcă „structura e
  livrată", spus fără ea, ascunde clasa de defect prinsă o dată la F0.2.4 cu `covers_all_companies`.

---

## 14. Surse

- `docs/specs/spec-b-accounting.md` §3.2 (`DNB-04`, opțiunile A/B/C), §3.3 (rezoluția contului),
  §3.5 (capabilitățile ca input), §4.1, §11.
- [ADR-038](038-vocabularul-de-evenimente.md) — vocabularul `event_type`, intrarea handler-elor din §5.
- [ADR-039](039-valuta-si-perioade.md) — moneda funcțională și perioadele; invarianții 1 și 3 din §5.2 se
  sprijină pe forma de acolo (`debit`/`credit` separate, nu un `amount` cu semn).
- [ADR-029](029-dimensiuni-analitice.md) — dimensiunile analitice, `DNB-02` (§6.3).
- [ADR-010](010-contabilul-practicant.md), [ADR-002](002-guvernanta-deciziilor.md) — cine aprobă un
  ADR cu conținut contabil.
- `CLAUDE.md` — `R9`–`R14`, `R23`, `R25`, `R26`, `D2`, `D3`, §4.
- Benchmark 1C: documentație de configurare și practica partenerilor (postarea ca modul de cod,
  „conturi de evidență", операции типовые, subconto definibile).
- Benchmark UNA (Unisim-Soft): materiale publice — „limbaj de contabilitate universal", trei
  registre, 160+ specialiști formați din 2000, ~30 de angajați permanenți.
- SNC „Stocuri", SNC „Imobilizări necorporale şi corporale", SNC „Diferenţe de curs valutar şi de
  sumă" — **citite**, pentru `C1`–`C5`. Textul consolidat servit de Ministerul Finanțelor (Ordinul
  nr. 118 din 06.08.2013, 263 p., consolidat până la Ordinul MF nr. 73 din 10.06.2022), transcris cu
  numărul punctului pe fiecare citat în
  [`_input/cercetare/c1-c3-c5-stocuri.md`](../_input/cercetare/c1-c3-c5-stocuri.md),
  [`c2-amortizarea.md`](../_input/cercetare/c2-amortizarea.md) și
  [`c4-diferente-de-curs.md`](../_input/cercetare/c4-diferente-de-curs.md).
  > **Corectură factuală, `3c3fccc` (2026-08-26).** Rândul de mai sus spunea „**de citit** […] Nu au
  > fost consultate", și a rămas fals două zile după ce cercetarea a fost comisă. Se corectează aici
  > **numai afirmația despre surse**: `§11` rămâne `NECESITĂ VALIDARE`, fiindcă a citi standardul și
  > a clasifica un caz sunt două acte diferite, iar al doilea îi aparține proprietarului (ADR-002,
  > ADR-010). Ce a devenit fals prin cercetare — patru din cele cinci presupuneri din `§11` — se
  > consemnează acolo, de el, nu aici.
- Conversație 2026-08-25 (versiunea 2 a documentului, după clarificarea domeniului de configurare).
