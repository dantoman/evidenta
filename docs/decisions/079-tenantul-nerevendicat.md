# ADR-079 — Tenantul nerevendicat: statutul `unclaimed`, fereastra provizorie în predicat, re-invitarea rămâne a firmei

- **Stare:** **Înlocuit de [ADR-081](081-revendicarea-optionala.md)** — 2026-08-31, în aceeași zi în
  care a fost acceptat. Nimic din mecanismul de mai jos nu se implementează: nu există
  `tenant.status = 'unclaimed'`, nu există starea `provisional`, nu există fereastră de 30 de zile,
  iar predicatul rămâne neatins. **Motivul, fiindcă e diagnosticabil:** ADR-ul de față răspunde la
  întrebarea *„ce se întâmplă dacă clientul nu acceptă niciodată"*, când întrebarea era *„trebuie
  clientul să accepte vreodată"*. Prima presupune răspunsul și cere un mecanism de forțare pentru o
  stare care e normală, nu anormală — modul de eșec descris la `OD-66` în secțiunea E a registrului.
  Ce supraviețuiește, și trece în ADR-081: constatarea că dreptul de revocare nu poate aparține unei
  persoane care nu există, și regula despre subdomeniul schimbabil o dată la revendicare.
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Închide:** `DN-27` din Spec A §12.3 — *închidere retrasă; `DN-27` se închide prin ADR-081*
- **Deschide:** `OD-117`
- **Atinge:** `tenant.status`, `engagement.status`,
  `infra/bootstrap/0003_access_predicates.sql`, Spec A §4.1–4.2, §12.3
- **Legate:** [ADR-018](018-engagementuri-multiple.md),
  [ADR-078](078-cine-poate-crea-un-tenant.md)

## 1. Problema, formulată exact

Spec A §12.3 spune că un tenant creat de o firmă se creează **cu un engagement `invited`, nu activ**
— altfel firma și-ar acorda singură acces. Corect, și rămâne corect. Gaura e imediat după:

> „dacă clientul nu acceptă niciodată, tenantul rămâne un tenant fără membri activi: caz real, nu
> ipotetic."

Iar consecința e mai ascuțită decât „lipsește o politică de expirare”: dreptul de revocare din
`INV-7` aparține unui proprietar **care nu există ca persoană**. Proprietate pe care nimeni n-o poate
exercita nu e un drept, e o declarație.

Al doilea capăt, comercial și la fel de real: o firmă cu șaizeci de clienți trebuie să vâneze
șaizeci de acceptări **înainte să lucreze o zi**. Onboarding-ul se rupe acolo, nu la ecranul de
înregistrare.

## 2. Opțiuni evaluate

1. **Strict ca azi — fără acceptare, zero acces.** *Avantaje:* invariantul e curat, nu se atinge
   nimic. *Dezavantaje:* fricțiunea comercială de mai sus, care e probabil fatală la onboarding-ul
   prin firme — canalul principal. *Cost de schimbare:* mic.
2. **Fereastră provizorie: firma lucrează un interval definit; dacă nimeni nu revendică, accesul se
   stinge.** *Avantaje:* sarcina cade pe partea care beneficiază. *Dezavantaje:* introduce o stare
   în care o firmă atinge un tenant pe care niciun client nu l-a încuviințat, și — dacă nimic nu
   repară asta — produce **registre orfane**: un tenant cu documente reale și zero persoane care pot
   ajunge vreodată la ele. *Cost de schimbare:* mediu, atinge predicatul.
3. **Tenant nerevendicat plus link de revendicare emis de platformă**, platforma exercitând
   revocarea la cererea clientului până la revendicare. *Avantaje:* rezolvă orfanii.
   *Dezavantaje:* platforma devine deținător temporar al unui drept al clientului — adică atinge
   `DN-18` dintr-o direcție care nu se vede din consolă, și o atinge **după** ce `DN-18` a fost
   închisă cu „platforma nu are drepturi asupra datelor" ([ADR-077](077-grantul-de-suport.md)).
   *Cost de schimbare:* mare — un drept acordat platformei nu se retrage curat.

## 3. Decizia

**Opțiunea 2, cu statutul din opțiunea 3 și cu re-invitarea la firmă, nu la platformă.**

Cheia care face varianta 2 să nu producă orfani nu e un job și nu e platforma: **firma păstrează
dreptul de a re-emite invitația**, fiindcă îl are oricum. A invita nu e acces; e aceeași acțiune
repetată. Platforma nu primește niciun drept nou, și de aceea opțiunea 3 se respinge deși statutul ei
se păstrează.

Formularea care ține totul: **proprietate fără titular nu e un invariant încălcat — e un tenant în
starea `unclaimed`, în care singura mutație permisă este revendicarea.**

### 3.1 De ce fereastra provizorie nu e o breșă de consimțământ

Obiecția evidentă la varianta 2 este că firma atinge date fără acordul clientului. Nu e cazul, și
motivul e verificabil: **în fereastra provizorie, tot ce se află în tenant a fost scris de firmă.**
Clientul n-a ajuns încă; nu există date ale lui care să fie expuse. Momentul în care apare o parte a
cărei încuviințare contează este chiar revendicarea — și acolo accesul se oprește (§3.4).

Asta e ce distinge fereastra provizorie de orice altă lărgire de acces, și e motivul pentru care ea
nu se aplică niciodată unui tenant existent: **`provisional` e accesibil numai la creare, numai
firmei creatoare.**

### 3.2 `tenant.status` primește `unclaimed`

`CHECK` devine `('unclaimed','active','suspended','offboarding','archived')`. Migrare aditivă
(`C5`), fără date existente afectate.

- Un tenant creat prin autoservire pornește `active`, ca azi.
- Un tenant creat de o firmă pornește `unclaimed`.
- `unclaimed → active` la revendicare. Este singura ieșire în sus.
- `unclaimed → offboarding → archived` pe calea obișnuită, dacă nimeni nu revendică niciodată.
  **Durata până acolo nu se decide aici:** e o valoare de retenție, deci `OD-21` / `DN-21`, unde stau
  toate celelalte. Mecanismul e cel existent; nu se inventează un al doilea.

Nu se introduce ștergere fizică. Spec A §1 nu o are, și `DN-27` întreba de la început *ce status
primește*, nu *dacă se șterge*.

### 3.3 `engagement.status` primește `provisional`

O stare nouă, între `invited` și `active`, cu un câmp propriu `provisional_until date`.

`invited` **nu-și schimbă înțelesul**: continuă să nu acorde nimic, iar testul din Spec A §8.2 care
demonstrează asta rămâne verde și neatins. Aceasta e cerința care exclude soluția „lărgim `invited`”.

Constrângeri, care fac starea inaccesibilă din alte direcții:

- `CHECK`: `status = 'provisional'` cere `initiated_by = 'firm'`, `accepted_at IS NULL` și
  `provisional_until IS NOT NULL`;
- `engagement_active_requires_acceptance` rămâne **neatins** — `active` cere în continuare
  acceptare, iar `provisional` nu e `active`;
- `provisional` intră în `LIVE_ENGAGEMENT_STATES`: ocupă slotul, deci unicitatea parțială pe
  `(firm, client_tenant)` și regula de neîntrepătrundere pe module din
  [ADR-018](018-engagementuri-multiple.md) îl includ fără modificare.

Tranziții noi în matricea din Spec A §4.2:

| Din | În | Cine declanșează | Efect asupra accesului |
|---|---|---|---|
| — | `provisional` | firma, **numai** la crearea tenantului (`P-9`) | acces conform scope-ului, până la `provisional_until` |
| `provisional` | `invited` | revendicarea tenantului de către client | **acces tăiat instantaneu** |
| `provisional` | `revoked` | firma, oricând | niciun acces |
| `provisional` | `expired` | fereastra trecută — prin predicat; `status` de job, cosmetic | niciun acces |

**Fereastra propusă: 30 de zile.** Valoare de produs, a proprietarului; stă lângă `provisional_until`
ca implicit al serviciului, nu ca literal presărat.

### 3.4 Predicatul

Calea 2 din `rls.has_tenant_access` schimbă o singură condiție:

```sql
AND ( e.status = 'active'
      OR (e.status = 'provisional' AND e.provisional_until >= <ziua din context>) )
```

Trei consecințe, toate voite:

1. **Înghețarea nu depinde de niciun job** — Spec A §4.4, aceeași regulă ca la expirare. Un job care
   nu rulează nu are voie să lase acces deschis.
2. **Ziua rămâne ziua**, comparată ca în restul predicatului; când
   [ADR-041](041-ziua-ca-argument.md) §6 se implementează, condiția asta primește `p_on_date` odată
   cu celelalte. Nu e o excepție de la regulă, e încă un consumator al ei. *(Fereastra grantului de
   suport din [ADR-077](077-grantul-de-suport.md) e altceva: acolo se compară momente, cu `now()`.)*
3. **Revendicarea taie accesul fără nicio scriere în `company_access`.** Trecerea
   `provisional → invited` schimbă un cuvânt, iar predicatul nu mai găsește nimic. Accesele derivate
   se revocă totuși în aceeași tranzacție, ca `company_access` să nu rămână cu rânduri vii pe care
   nimic nu le mai justifică — aceeași curățenie ca la Spec A §4.3 pasul 2.

### 3.5 Revendicarea, și subdomeniul

Firma emite invitația de revendicare; clientul își face contul, al doilea factor, și devine membru cu
rol de administrare. În aceeași tranzacție: `tenant.status → 'active'`,
`engagement.status → 'invited'`, accesele provizorii revocate. Clientul decide apoi, liber, dacă
acceptă contractul de deservire — iar dacă nu, îl refuză fără să fi pierdut nimic.

**Firma poate re-emite invitația oricând cât tenantul e `unclaimed`.** Aici moare problema
registrelor orfane, fără ca platforma să primească vreun drept.

**Subdomeniul.** Cine creează tenantul îi alege eticheta — deci, pe canalul „firmă", firma alege
identitatea vizibilă a clientului. Docstring-ul din `engagement/models.py` argumentează exact contra
situației în care *„subdomeniul ajunge al contabilului, nu al clientului"*; prin creare, ajunge.

**La revendicare, clientul poate schimba subdomeniul o dată, necondiționat.** Fără asta, „clientul e
proprietarul" e fals în cel mai vizibil câmp al produsului. Subdomeniul vechi **nu se eliberează
pentru realocare** — `DN-02` rămâne cum e; schimbarea nu e o excepție de la ea, e un caz al ei.

## 4. Cine plătește

`billing_account` se creează odată cu tenantul, cu `channel = 'wholesale'` și `payer_firm_id` =
firma creatoare ([ADR-078](078-cine-poate-crea-un-tenant.md) §3). Deci **plătitorul există de la
minutul zero**, iar `DN-27` nu mai are un capăt fără răspuns.

Ce **nu** se decide aici: dacă fereastra provizorie se facturează. E preț, nu arhitectură — și e
exact felul de întrebare pe care un ADR tehnic ar închide-o tacit dacă ar trece pe lângă ea.
**`OD-117`**: se facturează cele 30 de zile, sau sunt gratuite ca instrument de vânzare, și ce se
întâmplă cu abonamentul unui tenant care nu e revendicat niciodată. Plus `DN-25`, deja deschisă, care
întreabă ce se întâmplă cu `billing_account` la revocarea unui engagement wholesale — același nod,
văzut din partea cealaltă.

## 5. Consecințe

- **Devine posibil:** o firmă își aduce portofoliul și lucrează din prima zi; un client care nu
  răspunde nu blochează nimic; un tenant nerevendicat are întotdeauna pe cineva care poate redeschide
  ușa.
- **Devine imposibil:** un registru orfan; un tenant `provisional` fără plătitor; extinderea ferestrei
  provizorii asupra unui tenant existent.
- **Se lărgește accesul, și se spune pe față:** `provisional` este o stare în care o firmă citește și
  scrie într-un tenant pe care nimeni nu l-a acceptat. Este exact clasa de excepție pentru care `R1`
  cere confirmarea proprietarului; confirmarea e dată prin acceptarea acestui ADR. Ce o face
  suportabilă e §3.1 — nu există încă date ale altcuiva — și nimic altceva.
- **De modificat ca urmare:** `tenant.status` și `engagement.status` (migrare aditivă); predicatul;
  `LIVE_ENGAGEMENT_STATES`; Spec A §4.1 (diagrama), §4.2 (matricea), §12.3.
- **Ce se verifică automat**, în suita de penetrare (`C13`, `T1`):
  1. engagement `provisional` cu `provisional_until` în trecut → zero acces, fără job rulat;
  2. `provisional` pe un tenant `active` (revendicat) → refuzat la tranziție și fără acces;
  3. revendicare → interogarea firmei întoarce zero rânduri imediat, în aceeași sesiune;
  4. `invited` continuă să nu acorde nimic — testul existent din §8.2, care **nu** are voie să se
     schimbe la această trecere.

## Surse

- Spec A §1.1 (`tenant.status`, subdomeniul), §4.1–4.4, §8.2, §10.4, §12.3 (`DN-26`, `DN-27`),
  `DN-02`, `DN-21`, `DN-25`.
- [ADR-018](018-engagementuri-multiple.md), [ADR-041](041-ziua-ca-argument.md),
  [ADR-077](077-grantul-de-suport.md), [ADR-078](078-cine-poate-crea-un-tenant.md).
- `backend/evidenta/platform/engagement/models.py`, docstring-ul modulului și
  `engagement_active_requires_acceptance`.
- `CLAUDE.md` `R1`, `C5`, `C13`, `T1`.
- Conversație 2026-08-31.
