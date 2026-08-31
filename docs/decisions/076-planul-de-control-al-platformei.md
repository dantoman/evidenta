# ADR-076 — Planul de control: platforma se administrează pe sine, nu datele clienților

- **Stare:** Acceptat — produs și tehnic, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Închide:** nimic din registru — decizie descoperită, nu programată (`decisions/README.md`,
  „când o sarcină descoperă o alegere care nu era în registru")
- **Deschide:** `OD-113`, `OD-114`
- **Atinge:** `infra/rls/exceptions.toml`, `platform/identity`, rutarea pe gazdă, Spec A §14 (nouă)
- **Precondiție pentru:** [ADR-077](077-grantul-de-suport.md) (`DN-18`)

## 1. Problema: două lucruri diferite sub aceleași cuvinte

Spec A §3.4 descrie **utilizatorul de sistem** — `system:billing`, `system:bnm`, `system:efactura`:
`is_active = false`, fără `membership`, incapabil să treacă de `rls.has_tenant_access`. Există ca
`app.user_id` pentru audit, ca o rulare de job să aibă un autor. Este un robot.

**Administratorul-om al platformei nu e modelat nicăieri.** [ADR-062](062-aprobatorul-din-productie.md)
l-a ținut deliberat afară, cu motivul scris: *„aprobatorul atinge doar tabele globale, `DN-18`
atinge datele tenantului, RLS și `R27` — raze de acțiune diferite"*. Motivul era corect atunci și
rămâne corect; ce s-a schimbat e că `DN-18` se închide acum, iar `DN-18` nu se poate închide fără
să existe cineva căruia i se acordă grantul.

Pericolul concret, dacă lipsa rămâne: **omul primește calea robotului.** Un utilizator de sistem cu
`is_active = true` și o membership pusă „temporar" este exact ușa din spate pentru care există
întreaga arhitectură de izolare. Nu se ajunge acolo printr-o decizie, ci prin absența ei — la primul
incident de producție, la ora la care se rezolvă incidentele.

## 2. Principiul, dintr-o propoziție

> **Administratorul de platformă administrează platforma, nu datele.**

Restul acestui ADR este consecința ei mecanică. Iar consecința se poate testa:

**Testul de proiectare.** Dacă o pagină din consolă afișează o balanță, un jurnal, un salariu sau o
factură a unui client, `DN-18` a fost închisă din greșeală — de un ecran, nu de un ADR.

## 3. Opțiuni evaluate

1. **Fără consolă. Operarea se face din `manage.py` și `psql`.** *Avantaje:* zero suprafață nouă,
   zero cod. *Dezavantaje:* cele zece căi privilegiate din Spec A §6.2 au deja nevoie de un
   declanșator uman (`P-4` aplică reguli fiscale noi, `P-10` încarcă planul de conturi), iar azi
   declanșatorul e o comandă rulată de cineva pe un shell. `privileged_access_log` înregistrează
   *ce* s-a rulat, nu *cine a avut voie*. Auditul devine „lista celor cu acces SSH".
   *Cost de schimbare:* mic acum, mare după primul audit de conformitate.
2. **Consolă ca plan de control, fără nicio cale spre datele tenantului.** *Avantaje:* granița e
   structurală, nu disciplinară — consola rulează fără context de tenant, deci nu are ce interoga;
   fiecare operațiune trece pe o cale enumerată, cu rând în `privileged_access_log`.
   *Dezavantaje:* suportul nu poate reproduce un defect pe date reale — de aceea nu e completă
   singură, ci împreună cu [ADR-077](077-grantul-de-suport.md), care adaugă **singura** cale spre
   date, consimțită și mărginită. *Cost de schimbare:* mic.
3. **Rol de super-utilizator care poate intra în orice tenant.** *Avantaje:* rezolvă orice incident
   imediat. *Dezavantaje:* contrazice `INV-7` în fundație, nu la margine: proprietatea clientului
   asupra datelor devine condiționată de bunăvoința furnizorului, iar RLS-ul devine decor.
   *Cost de schimbare:* nu se poate desface — un privilegiu acordat o dată e presupus de tot codul
   scris după el.

## 4. Decizia

**Opțiunea 2**, cu patru piese.

### 4.1 `platform_staff` — cine e angajat al platformei

Tabelă **globală**, la nivelul lui `user`, cu politică proprie. Nu are `tenant_id` și nu poate avea:
un angajat al platformei nu aparține niciunui tenant. Se declară în `infra/rls/exceptions.toml`.

| Câmp | Tip | Note |
|---|---|---|
| `user_id` | uuid | PK, REFERENCES `user` — identitate, nu al doilea tip de actor |
| `staff_role` | text | NOT NULL, CHECK în `('support','operator','admin')` |
| `granted_by_user_id` | uuid | NOT NULL, REFERENCES `user` — cine a adăugat |
| `granted_at` | timestamptz | NOT NULL |
| `revoked_at` | timestamptz | NULL — retragerea e o dată, nu o ștergere |

Trei roluri, fixe în cod și nu date compozabile:

- **`support`** — poate *cere* un grant de suport ([ADR-077](077-grantul-de-suport.md)). Nu poate
  aproba, nu poate atinge tabele globale de referință.
- **`operator`** — rulează căile `P-1` … `P-6`, `P-8`, `P-10`; parametri fiscali, cursuri, plan de
  conturi, ringuri de lansare, feature flags.
- **`admin`** — administrează `platform_staff` însuși. Nimic altceva.

**De ce nu roluri ca date, cum cere [ADR-020](020-roluri-ca-date.md):** ADR-020 compune roluri *ale
unui tenant*, dintr-un catalog de permisiuni cu `scope` `tenant` sau `company`. Un rol de platformă
n-are tenant, deci n-are unde să stea, iar catalogul n-are scope pentru el. Trei valori într-un
`CHECK` sunt sincere; o a patra e o migrare, deliberat.

**`R1` — excepția lărgește accesul, deci cere confirmarea proprietarului.** `platform_staff` nu e
`global_read_only` însămânțată din migrare: se scrie la runtime, de către oameni. Intră deci în
clasa pe care [ADR-072](072-exceptia-care-nu-largeste.md) o lasă explicit sub confirmare.
Confirmarea e dată prin acceptarea acestui ADR și se consemnează aici, nu în `exceptions.toml`.

**Ce nu face `platform_staff`:** nu apare în `rls.has_tenant_access`, nu apare în
`rls.has_company_access`, nu acordă nimic. Un rând aici nu deschide nicio politică. Este o listă de
persoane, citită de căile privilegiate ca să afle dacă apelantul are voie să le apeleze — și atât.
`MFA` e deja obligatoriu pentru toți ([ADR-021](021-mfa-obligatoriu.md)), deci nu se repetă aici.

### 4.2 Gazda: `admin.`, și de ce granița e structurală

`admin` e deja pe lista de subdomenii rezervate (Spec A §1.1) și nu poate fi alocat unui tenant.

`C8` spune că **contextul de tenant vine din subdomeniu, niciodată din payload**. Pe `admin.` nu
există subdomeniu de tenant, deci nu există context, deci — prin `R4` — orice interogare pe o tabelă
tenant-scoped întoarce zero rânduri sau eroare. Consola nu se abține de la a citi datele clienților:
**nu are cu ce.**

Consecință de sesiune: o sesiune creată pe `admin.` are `tenant_id` și `actor_firm_id` nule, iar
gazdele de tenant o refuză. Reciproc, o sesiune de pe o gazdă de tenant nu e acceptată pe `admin.`.
Sunt două sesiuni pentru aceeași persoană, și asta e proprietatea dorită: cineva care e și angajat
al platformei, și contabil într-o firmă, nu trece dintr-una în alta printr-un meniu.

### 4.3 Ce administrează consola

Lista nu e o alegere de produs, e ce rezultă din propoziția din §2: obiectele platformei, nu ale
tenantului.

| Pagină | Obiectul |
|---|---|
| Spații | `tenant` — subdomeniu, denumire legală, `status`, data creării. **Nu conținutul lor** |
| Abonamente și planuri | `billing_account`, `subscription`, `plan` (Spec A §10.2) |
| Capabilități | `capability_activation` — activări cu dată efectivă (`R25`) |
| Ringuri și feature flags | Spec A §13.5, `R23` |
| Parametri fiscali | `fiscal_parameter`, cu actul normativ și marginile (`R15`, `C14`) |
| Versiuni de plan de conturi | `coa_template` (`P-10`) |
| Jurnalul căilor privilegiate | `privileged_access_log`, filtrabil pe cale și pe tenant |
| Granturi de suport | cererile, aprobările și expirările din [ADR-077](077-grantul-de-suport.md) |
| Incidente | starea joburilor, cozile, erorile de integrare |

Și ce nu apare **niciodată**, oricât de utilă ar fi pagina: registre, documente, solduri, salarii,
declarații, atașamente, denumiri de parteneri, sume. Un raport agregat peste tenanți (câți tenanți
au TVA activ) e metadată și e permis; același raport cu o sumă în el nu mai e.

### 4.4 Limba consolei

`C37` ține: `tenant`, `firm`, `engagement`, `assignment` nu apar în interfață. Consola nu e o
excepție fiindcă publicul ei e intern — șirurile ei stau în aceleași fișiere de resurse (`C32`) și
trec prin același grep. Pe ecran scrie **spații**, **contracte de deservire**, **granturi de
suport** — harta fixă din [ADR-017](017-terminologie.md), care numește deja `platform` drept
*„furnizorul platformei: planul de control, grantul de suport"*.

## 5. Consecințe

- **Devine posibil:** închiderea lui `DN-18`, care avea nevoie de un titular al grantului;
  declanșarea căilor `P-1` … `P-10` de către o persoană identificată, nu de către cine are shell;
  un raport lunar de conformitate care se citește dintr-un ecran, nu dintr-un `psql`.
- **Devine imposibil, prin construcție:** ca o pagină de consolă să afișeze date de tenant — nu
  există context pe gazda `admin.`.
- **Devine scump, deliberat:** orice funcționalitate de consolă care ar avea nevoie de datele unui
  client. Trebuie să treacă prin [ADR-077](077-grantul-de-suport.md), adică prin consimțământ.
- **De modificat ca urmare:** `infra/rls/exceptions.toml` primește `platform_staff`; Spec A capătă
  §14 (consola platformei) și §6.2 notează cine apelează fiecare cale; rutarea pe gazdă capătă
  ramura `admin.`.
- **Ce se verifică automat:** (a) gardianul de model verifică forma politicii declarate pentru
  `platform_staff`; (b) un test de izolare demonstrează că o sesiune de consolă, sub rolul
  aplicației, întoarce zero rânduri pe o tabelă tenant-scoped cu date în ea; (c) `C37` se verifică
  prin grep-ul existent peste fișierele de resurse, extins la resursele consolei.

## 6. Ce rămâne deschis

- **`OD-113` — catalogul de acțiuni al consolei.** Cele trei valori din `staff_role` decid *cine*,
  nu *ce*: „`operator` rulează `P-4`" e azi o afirmație în acest ADR, nu o verificare. Dacă lista de
  acțiuni crește, ea devine un catalog cu aceeași formă ca cel din ADR-020, dar global. **Nu se
  construiește preventiv:** ADR-020 spune că o cheie apare când ceva o impune.
- **`OD-114` — pagina de start a firmei nu e o listă de clienți.** Spec A §13.1: termenul TVA e 25
  ale lunii, pentru toți, simultan — *„nu e vârf de trafic, e vârf de consecință"*. Ecranul util e
  „care dintre cei șaizeci de clienți are declarația nedepusă la patru zile de termen", care e
  cross-tenant prin definiție, deci read model (`R7`, `D5`, `firmspace`), deci `F3`. **Ce nu se
  amână** este calea lui de scriere: proiecție cu `engagement_id` pe fiecare rând, ca revocarea să
  taie prin predicat, sau interogare cross-tenant sub rol privilegiat, caz în care revocarea devine
  ștergere — adică job, adică reziduu. Este exact `DN-19`, și se decide înainte să existe primul
  rând în `firmspace`, nu după.

## Surse

- Spec A §1.1 (subdomenii rezervate), §3.4 (utilizatorul de sistem), §6.2 (`P-1` … `P-10`), §10.2,
  §13.1, §13.5.
- [ADR-017](017-terminologie.md) (`platform` = planul de control și grantul de suport),
  [ADR-020](020-roluri-ca-date.md), [ADR-021](021-mfa-obligatoriu.md),
  [ADR-062](062-aprobatorul-din-productie.md) §„nivelul `platform_operator` rămâne la `DN-18`",
  [ADR-072](072-exceptia-care-nu-largeste.md).
- `CLAUDE.md` `R1`, `R4`, `R7`, `R23`, `R25`, `C8`, `C32`, `C37`, `D5`.
- Conversație 2026-08-31.
