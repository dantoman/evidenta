# ADR-081 — Revendicarea e opțională, calea de revendicare nu; plătitorul e un fapt cu dată

- **Stare:** Acceptat — produs și tehnic, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Înlocuiește:** [ADR-079](079-tenantul-nerevendicat.md) *(acceptat și înlocuit în aceeași zi — §1)*
- **Corectat de:** [ADR-085](085-spatiul-apartine-unui-utilizator.md) §6 — ancora lui `P-11` din §3.4
- **Închide:** `DN-27`, a doua oară și pe premisa corectă
- **Restrânge:** `DN-03`, `DN-25` *(mecanismul plătitorului; politica rămâne)*
- **Promovează:** `DN-21` și `DN-25` din „F3" în **condiții de lansare a modelului**
- **Deschide:** `OD-118`
- **Atinge:** `tenant.claimed_at`, `engagement.acceptance_basis`, Spec A §6.2 (`P-11` nouă), §9.4,
  §10.4, §12.3
- **Legate:** [ADR-075](075-identitatea-titularului.md), [ADR-077](077-grantul-de-suport.md),
  [ADR-080](080-tipul-nu-se-stocheaza.md)

## 1. De ce se înlocuiește un ADR acceptat acum câteva ore

`ADR-079` a răspuns la întrebarea *„ce se întâmplă dacă clientul nu acceptă niciodată?"* cu o
fereastră provizorie de 30 de zile, un `tenant.status = 'unclaimed'` și o stare `provisional` pe
engagement. Mecanismul era coerent. Întrebarea era greșită.

Întrebarea corectă e **„trebuie clientul să accepte vreodată?"**, iar răspunsul comercial e nu: în
Republica Moldova un SRL mic predă totul contabilului și nu deschide niciodată aplicația. QuickBooks
nu obligă contabilul să trimită clientului date de acces, și nu din neglijență. Prima formulare
presupunea răspunsul — a cerut un mecanism de forțare pentru o stare care e normală, nu anormală.

Este modul de eșec pe care secțiunea E a registrului îl descrie la `OD-66`: **o eroare de încadrare
care se implementează impecabil și trece toate testele.** Fereastra de 30 de zile ar fi înghețat
conturi care funcționează, plătite, la zi cu declarațiile, fiindcă nimeni n-a semnat ceva ce nu era
nevoie să semneze. Se consemnează ca atare, nu se netezește: e prima decizie din proiect răsturnată
în aceeași zi, iar cauza e identificabilă și repetabilă.

Ce se păstrează din `ADR-079`: nimic din mecanism. Ce se păstrează din raționamentul lui: constatarea
că **dreptul de revocare al clientului nu poate aparține unei persoane care nu există**. Aici primește
răspunsul corect — nu forțând persoana să apară, ci ancorând dreptul altundeva.

## 2. Principiul

> **Opțional nu înseamnă imposibil. Dreptul clientului poate fi dormant, nu absent. Ce trebuie să
> existe permanent nu e o acceptare, ci o cale de revendicare.**

Tenantul nerevendicat nu e o anomalie care expiră. E o stare normală, permanentă și plătită.

## 3. Piesele

### 3.1 `tenant.claimed_at` — fapt cu dată, nu status

`timestamptz NULL`. Statusul rămâne ce era: un tenant nerevendicat e perfect `active`, fiindcă cele
două axe sunt ortogonale — una spune dacă contul funcționează, cealaltă dacă cineva l-a preluat.
`ADR-079` le confunda.

**Nu se derivă din „n-are niciun `membership` viu"**, oricât ar fi de elegant: politica pe
`membership` e `self_row`, deci nimeni nu poate număra membrii altcuiva — `OD-37`, a treia oară în
acest registru.

### 3.2 Linia: ținerea contabilității nu cere un proprietar revendicat; dispoziția asupra datelor, da

Aceasta e piesa de proiectare care contează, fiindcă e singura care poate fi trasată greșit fără să
se observe.

| Permis fără revendicare | Cere revendicare |
|---|---|
| introducere, postare, închideri de lună și de exercițiu | exportul complet (`P-8`) |
| declarații, depuneri, e-Factura | transferul către altă firmă (Spec A §4.5) |
| adăugarea de companii în scope-ul angajamentului | arhivarea sau închiderea tenantului (§9.4) |
| tot ce e muncă de contabil | schimbarea IDNO-ului sau a formei juridice |
| | schimbarea plătitorului către canalul direct (§5) |

Gâtuirea depunerilor ar rupe produsul: depunerea **e** meseria delegată. Gâtuirea dispoziției e
altceva — sunt acte de proprietar, nu de contabil. Criteriul, când apare un caz nou: *actul acesta
schimbă registrele, sau schimbă cine are registrele?*

### 3.3 Mandatul declarat, nu verificat

În realitate există un contract de deservire pe hârtie. Analogul ieftin, care nu cere platformei să
verifice nimic:

`Engagement` primește **`acceptance_basis`**, `CHECK` în `('client','declared_mandate')`, `NOT NULL`
odată cu `accepted_at`. Plus `mandate_ref` (referința contractului, declarată de firmă) și
`claim_contact_email` — **obligatoriu**, declarat, neverificat.

Ce câștigă forma asta față de alternativa „firma primește `membership` în tenantul nerevendicat":

- **predicatul de acces nu se atinge deloc.** `engagement.status = 'active'` e deja calea 2 din
  `rls.has_tenant_access`; nu apare nicio ramură, niciun cost pe calea fierbinte, nicio stare nouă;
- constrângerea `engagement_active_requires_acceptance` rămâne satisfăcută, iar docstring-ul care
  spune că *„delegarea pe care n-a acceptat-o nimeni nu e delegare"* nu devine fals — devine
  **explicit pe fiecare rând** care dintre cele două temeiuri stă dedesubt;
- toate relațiile din sistem pe care niciun client nu le-a confirmat sunt **enumerabile printr-o
  interogare**. Este exact proprietatea pe care o vrei când cineva întreabă cât din baza ta stă pe
  declarații;
- la revendicare nu se retrage și nu se re-provizionează nimic. Un cuvânt de schimbat, nu o migrare.

Răspunderea pentru mandat stă la firmă, nu la platformă. Clientul vede declarația — cine a declarat-o,
când, cu ce referință — în secunda în care revendică.

**La revendicare, angajamentul rămâne `active`.** Nu cade în `invited`: căderea ar opri lucrul exact
în momentul în care clientul intră pentru prima oară, adică ar pedepsi revendicarea. Ce primește
clientul e ecranul „contabilul meu — contract declarat la data X, referința Y" cu butonul de revocare
alături, disponibil imediat și fără motivare (`INV-7`). Dormant, apoi exercitabil — nu absent, apoi
acordat.

### 3.4 `P-11` — revendicarea

Cale privilegiată nouă în enumerarea limitativă din Spec A §6.2, cu aceleași obligații ca celelalte
zece: scop îngust, semnătură fără SQL, rând în `privileged_access_log` în aceeași tranzacție,
`justification` obligatoriu, și un test că nu poate fi folosită pentru altceva.

Ce face: **acordă un `membership` de administrare pe baza unei probe**, și scrie `claimed_at`. Ce nu
face: nu citește nicio dată de business, nu atinge registre, nu schimbă angajamente.

Ancora dreptului e **IDNO-ul, nu un rând de utilizator**. Tenantul poartă deja `idno`
([ADR-075](075-identitatea-titularului.md)), iar compania proprie se identifică prin potrivire pe
IDNO. Deci există un răspuns la „cine poate revoca în ziua 1" fără ca cineva să fi acceptat ceva:
cel care poate dovedi că reprezintă acel IDNO.

> **Corectat în aceeași zi prin [ADR-085](085-spatiul-apartine-unui-utilizator.md) §6.** Propoziția
> de mai sus e scrisă ca afirmație generală și e falsă pentru orice spațiu care nu declară o
> identitate — adică pentru cazul obișnuit, fiindcă spațiul aparține unui **utilizator**, nu unei
> companii. Forma corectă: *se revendică dovedind că reprezinți identitatea declarată a spațiului
> sau, în lipsa ei, IDNO-urile **tuturor** companiilor din el.* „Toate", nu „una" — un spațiu cu
> companii ale mai multor proprietari nu se predă cuiva care reprezintă una dintre ele.

`P-11` **nu contaminează `DN-18`** și nu redeschide [ADR-077](077-grantul-de-suport.md): acordă un
drept pe bază de dovadă, nu vede date. Rază de acțiune diferită — același criteriu prin care
`ADR-062` a ținut `platform_operator` în afara aprobatorului din producție.

Costul real, care nu se ascunde: **platforma ajunge să arbitreze cine reprezintă persoana juridică.**
Are nevoie de un standard de probă scris, iar acela e conținut **juridic**, deci
[ADR-002](002-guvernanta-deciziilor.md) cere co-semnătură, iar contabilul practicant nu există
(`OD-32`). **`OD-118`** ține standardul; mecanismul lui `P-11` nu-l așteaptă, dar nu funcționează în
producție fără o procedură scrisă și aplicată manual.

### 3.5 Anti-ostatic — de ce calea există chiar dacă 95% n-o folosesc

Dacă firma poate crea contul, îl poate lucra, și clientul nu poate scoate datele fără cooperarea
firmei, atunci ai construit o luare de ostatici, iar `INV-7` — *„datele n-au fost niciodată ale
firmei"* — devine text decorativ. `P-11` plus `P-8` (exportul complet) este mecanismul care o
împiedică, și acesta e cel mai bun motiv ca ele să existe.

Dacă documentele primare aparțin de drept entității — foarte probabil, dar **de verificat cu
contabilul practicant, nu din memorie** — atunci calea nu mai e opțiune de produs, e obligație. Intră
tot în `OD-118`.

Veriga slabă, numită ca să nu treacă drept rezolvată: **unde ajunge invitația de revendicare.**
Platforma n-are adresa clientului; firma o are. De aceea `claim_contact_email` e obligatoriu la
declararea mandatului. Nu e verificat, deci nu e o garanție — e singurul canal propriu pe care
`INV-7` îl are.

## 4. Ce nu mai există din `ADR-079`

`tenant.status` **nu** primește `unclaimed`; `engagement.status` **nu** primește `provisional`; nu
există `provisional_until`; predicatul rămâne cum e. Modificările corespunzătoare din Spec A §1.1,
§4.1, §4.2 și §12.3 se derulează înapoi odată cu acest ADR.

Regula despre subdomeniu se păstrează, fiindcă nu depindea de mecanismul înlocuit: **la revendicare,
clientul poate schimba subdomeniul o dată, necondiționat.** Cine creează tenantul îi alege eticheta;
pe canalul „firmă", firma alege identitatea vizibilă a clientului. Subdomeniul vechi nu se eliberează
pentru realocare — `DN-02` rămâne cum e, iar schimbarea e un caz al ei, nu o excepție.

## 5. Plătitorul e un fapt cu dată, și oricare parte îl poate prelua — nu impune

În QuickBooks firma decide cine plătește: clientul sau ea. Consecința de model e că
`billing_account.channel` **nu e o proprietate fixată la creare.**

Se adaugă `billing_payer_assignment`, nivel tenant, cu forma casei — aceeași ca la `subscription`:
`(tenant_id, channel, payer_firm_id, valid_from, valid_to)`, cu neîntrepătrundere pe
`daterange(valid_from, valid_to)`. Plătitorul devine astfel reconstituibil pentru orice zi trecută,
ceea ce facturile deja emise cer oricum. Un `UPDATE` peste `billing_account.channel` ar șterge
tocmai ce trebuie păstrat.

**Cine poate muta plătitorul — și regula e simetrică:**

| Direcție | Cine o poate face | De ce |
|---|---|---|
| firmă → client (`wholesale` → `direct`) | firma inițiază, **clientul confirmă** | plata e act de proprietar (§3.2), deci **cere un tenant revendicat**: nu poți factura pe cineva care nu există |
| client → firmă (`direct` → `wholesale`) | clientul inițiază, **firma confirmă** | firma acceptă o factură; nimeni nu poate arunca o obligație de plată în curtea altcuiva |

Niciuna dintre părți nu poate împinge unilateral factura către cealaltă. Ce firma **poate** face
oricând unilateral e să înceteze plata — dar aceea nu e o mutare de plătitor, e o neplată, și cade pe
calea din §6.

Efectul secundar util, și e cel care aliniază interesele: **ieșirea firmei din plată trece prin
revendicarea clientului.** Firma care nu mai vrea să plătească are un motiv propriu să trimită
invitația de revendicare — exact acțiunea de care `INV-7` are nevoie și pe care nimic altceva nu o
încuraja.

Asta restrânge `DN-25` la politică: **mecanismul** e decis aici (plătitorul e o atribuire cu dată,
revocarea unui angajament nu-l schimbă de la sine), iar ce rămâne deschis e ce se întâmplă efectiv cu
abonamentul când angajamentul wholesale se revocă fără ca cineva să preia plata.

## 6. Scenariul urât, și de ce nu mai e F3

Firma încetează să plătească → tenantul intră `past_due` → accesul se suspendă → **registrele
clientului sunt suspendate de o parte cu care clientul n-a contractat niciodată**, și nu există
nimeni pe partea lui care să repare.

`DN-21` (durata grației la neplată, accesul de citire) și `DN-25` nu mai sunt decizii de F3. Devin
**condiții de lansare a modelului**, fiindcă modelul le produce pe cazul normal, nu pe cel marginal.

Propunerea, ca punct de plecare și nu ca decizie: un tenant **nerevendicat** în `past_due` primește o
fereastră de citire și export mai lungă decât unul revendicat, plus o invitație de revendicare
trimisă la `claim_contact_email`. Motivul asimetriei: pe un tenant revendicat există cineva care
poate plăti sau exporta; pe unul nerevendicat, nu.

## 7. `DN-03` — duplicatul de IDNO devine modul normal de eșec

Azi `tenant.idno` nu e unic, cu motivația explicită din cod: *„one legal entity, one subscription is
a product rule nobody has decided, and an index would decide it silently."* Motivația rămâne corectă
și indexul **nu** se creează.

Ce se schimbă e frecvența: cu tenanți creați de firme și fără revendicare obligatorie, duplicatul
devine modul normal de eșec. Clientul schimbă contabilul, noul contabil nu știe că există deja un
cont, creează al doilea, iar acum două conturi cu același IDNO țin registre și depun declarații.
Când clientul revendică — pe care din ele?

**Decizia: avertisment la creare, nu index.** Textul pune întrebarea corectă — *există deja un cont
pentru această întreprindere: revendici accesul sau creezi al doilea?* — și lasă răspunsul omului.

**Avertismentul se arată numai unei firme `active`** (verificată, [ADR-080](080-tipul-nu-se-stocheaza.md)
§4). Motivul e o divulgare pe care formularea inițială o ascundea: un avertisment arătat oricui, la
orice creare, spune oricui cu un IDNO public dacă întreprinderea aceea e client Evidenta. Interogarea
în sine e cross-tenant, deci trece prin `P-9` și răspunde doar cu *există / nu există* — niciodată cu
subdomeniul, denumirea sau firma care îl ține.

## 8. Consecințe

- **Devine posibil:** modelul comercial care face produsul vandabil unei firme cu șaizeci de clienți;
  un tenant care funcționează, plătește și depune declarații fără ca titularul să deschidă vreodată
  aplicația.
- **Devine imposibil:** un cont pe care clientul nu-l poate revendica niciodată; o mutare unilaterală
  a facturii de la o parte la cealaltă.
- **Rămâne posibil, și e limita onestă a modelului:** o firmă care nu declară un contact real de
  revendicare face `P-11` inutilizabilă în practică pentru acel client. Câmpul e obligatoriu; adevărul
  lui nu e verificabil.
- **De modificat ca urmare:** `tenant.claimed_at`, `engagement.acceptance_basis` / `mandate_ref` /
  `claim_contact_email`, `billing_payer_assignment` (toate aditive, `C5`); Spec A §6.2 primește
  `P-11`, §9.4 primește asimetria de grație, §10.4 primește atribuirea cu dată, §12.3 se rescrie;
  `ADR-079` trece în `Înlocuit`.
- **Ce se verifică automat:**
  1. un angajament cu `acceptance_basis = 'declared_mandate'` dă exact același acces ca unul acceptat
     de client — **și acesta e testul care demonstrează că predicatul n-a fost atins**;
  2. `P-11` nu poate citi nicio tabelă de business — același test de scop îngust ca la celelalte căi;
  3. actele din coloana dreaptă a tabelului din §3.2 sunt refuzate pe un tenant cu `claimed_at IS
     NULL`, cu cod de eroare stabil (`C10`);
  4. o mutare de plătitor fără confirmarea celeilalte părți e refuzată;
  5. avertismentul de IDNO duplicat nu întoarce nimic în afara lui *există / nu există*, și nimic
     unui apelant care nu e firmă `active`.

## 9. Ce rămâne deschis

**`OD-118` — standardul de probă la revendicare.** Ce documente dovedesc că o persoană reprezintă
IDNO-ul; dacă documentele primare aparțin de drept entității, ceea ce ar transforma calea din opțiune
în obligație; cine aplică standardul; ce se întâmplă la contestație. Conținut juridic — co-semnătură
(`ADR-002`), contabil practicant absent (`OD-32`). **Nu se scrie din memorie.**

## Surse

- Spec A §4.2 (matricea), §4.5 (transferul), §6.1–6.3 (căile privilegiate), §9.4 (offboarding și
  neplată), §10.1–10.4 (canalele de facturare), §12.3, `DN-02`, `DN-03`, `DN-21`, `DN-25`.
- [ADR-002](002-guvernanta-deciziilor.md), [ADR-062](062-aprobatorul-din-productie.md),
  [ADR-075](075-identitatea-titularului.md), [ADR-077](077-grantul-de-suport.md),
  [ADR-079](079-tenantul-nerevendicat.md) *(înlocuit)*,
  [ADR-080](080-tipul-nu-se-stocheaza.md).
- Măsurat în cod la 2026-08-31: `platform/tenancy/models.py` (`tenant.idno` fără unicitate, cu
  motivația în comentariu), `platform/identity/models.py` (`membership` `self_row`),
  `platform/engagement/models.py` (`engagement_active_requires_acceptance`).
- Practica QuickBooks Online Accountant, ca precedent de piață: contul creat de contabil, accesul
  clientului opțional, plătitorul mutabil între contabil și client — adus de proprietar.
- `CLAUDE.md` `R1`, `C5`, `C10`, `C13`, `T1`.
- Conversație 2026-08-31.
