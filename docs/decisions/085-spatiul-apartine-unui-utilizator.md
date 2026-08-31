# ADR-085 — Spațiul de lucru aparține unui utilizator, nu unei companii; „compania titularului" e adevărată doar pentru un holding

- **Stare:** Acceptat — produs, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Restrânge:** [ADR-075](075-identitatea-titularului.md) §2 și §3
- **Corectează:** [ADR-081](081-revendicarea-optionala.md) §3.4 — ancora lui `P-11`
- **Închide:** întrebarea proprietarului *„cum înregistrez antreprenorul care are mai multe companii
  și vrea să le țină într-un loc"*
- **Deschide:** `OD-125`
- **Atinge:** `platform/tenancy` (model), ecranul *Spațiul de lucru*, `GET /api/v1/workspace`,
  Spec A §1.1
- **Legate:** [ADR-080](080-tipul-nu-se-stocheaza.md), [ADR-082](082-unitatea-facturabila.md),
  [ADR-083](083-editarea-companiei.md)

## 1. Întrebarea, și cât din temere era întemeiată

Un antreprenor cu mai multe companii e, în această piață, mai frecvent decât un holding constituit ca
atare. Vrea toate companiile într-un loc. Temerea proprietarului: *„m-am grăbit să oblig orice tenant
să fie companie."*

**Măsurat: obligația nu există în schemă.** `tenant.idno` și `tenant.legal_form` sunt nullable
([ADR-075](075-identitatea-titularului.md) §2), iar §3 al aceluiași ADR spune direct că *înregistrarea
nu creează compania titularului; compania proprie se propune, nu se impune*. Ordinea din Spec A §12.2
cere să existe **o** companie, nu **compania titularului** — iar pentru antreprenor prima companie e
prima lui societate. Rețeta de înregistrare nu se schimbă.

Ce era greșit nu e schema. E o idee pusă peste ea.

## 2. Decizia, care e mai simplă decât întrebarea

> **Spațiul de lucru se atribuie unui utilizator.**

O companie nu poate ține un abonament: e entitate contabilă, iar aceeași persoană ține de obicei mai
multe. Legătura persoană ↔ spațiu este `Membership`. Companiile stau **înăuntru, egale între ele**, iar
accesul la fiecare e per persoană, prin `CompanyAccess`.

**Modelul spunea asta de la început.** Docstring-ul lui `User` — *„one accountant, one account, sixty
clients"* — descrie o identitate globală fără tenant; `Company` e *„the legal entity with its own
ledger"*, iar `Membership` e ce leagă omul de spațiu. Peste el s-a suprapus, în ADR-075, noțiunea de
**„compania titularului"**, care e adevărată exact într-un caz: **holdingul**, unde societatea-mamă
chiar e o companie din spațiu și chiar ține contabilitate acolo.

Generalizarea acelui caz e ce producea întrebarea. Nu e nevoie de un tip nou, de un titular
persoană fizică modelat separat, sau de vreo entitate nouă.

## 3. Antreprenorul cu cinci companii **este** cazul `multi_company`

Un holding și un antreprenor cu cinci societăți arată identic în schemă: un spațiu, N companii.
Diferența dintre ei e cine deține părțile sociale — fapt juridic, nu structural, iar produsul n-are
niciun motiv să-l cunoască și, după [ADR-080](080-tipul-nu-se-stocheaza.md), niciun loc unde să-l
pună.

Cazul întărește formularea de acolo: **`multi_company` înseamnă *mai mult de una*, nu *ești
holding*.** Iar facturarea îl tratează deja corect — [ADR-082](082-unitatea-facturabila.md) numără
companii: cinci companii, cinci unități, indiferent de structura de proprietate și de cine plătește.

## 4. Ce mai rămâne din identitatea spațiului

`tenant.idno` și `tenant.legal_form` **nu se retrag**. Se restrânge ce înseamnă: nu „titularul", ci
**identitatea declarată a spațiului**, opțională, cu exact doi consumatori:

1. **derivarea companiei proprii, când există** — potrivirea pe `company.idno` din ADR-075 §2, care
   rămâne cum e, inclusiv capcana din suită pentru potrivirea pe nume. E cazul holdingului;
2. **ancora revendicării** (`P-11`), corectată la §6.

**`null` e o stare completă, nu una incompletă.** Un spațiu al cărui titular e un om, nu o societate,
n-are ce declara — și ecranul nu are voie să-i ceară la nesfârșit un IDNO. Tabelul celor trei adevăruri
din ADR-075 §3 primește al patrulea rând:

| `own_company_id` e `null` fiindcă | Ce spune ecranul |
|---|---|
| titularul n-are IDNO înregistrat | nu e cu ce potrivi; se completează la înregistrare |
| are IDNO, nu există compania | titularul nu-și ține contabilitatea aici — **ofertă** |
| există, dar cititorul n-o poate vedea | absentă, ca orice rând inaccesibil (`IZ-04`) |
| **spațiul nu declară nicio identitate** | **nu există companie proprie prin construcție — nicio ofertă, niciun câmp gol, nicio insistență** |

### 4.1 Coloana pe care era să o propun, și de ce s-a dizolvat

Prima formă a acestei decizii adăuga `tenant.holder_kind` — `legal_entity` sau `natural_person` —
ca ecranul să știe ce text să arate. S-a retras înainte de a fi scrisă: **singurul ei consumator era
oferta de companie proprie, iar oferta e chiar ce se restrânge aici.** O coloană care există ca să
aleagă un text este o coloană pe care cineva o va citi altundeva peste șase luni — exact
raționamentul din [ADR-080](080-tipul-nu-se-stocheaza.md) §2, aplicat la timp de data asta.

Nu se colectează nici IDNP, nici vreun echivalent personal: nu are consumator, iar un identificator
personal păstrat degeaba sunt date personale păstrate degeaba.

## 5. Denumirea spațiului nu e „legală"

`tenant.legal_name` e `NOT NULL` și se numește *legal*. Numele coloanei e scurgerea: spațiul nu e
persoană juridică. `C39` — denumirea legală pe documente — privește `company.legal_name` și
`partner.legal_name`, care chiar ajung pe artefacte ieșite din sistem; un spațiu nu ajunge niciodată
pe un document.

`tenant` primește **`display_name`**, alimentat din `legal_name` în aceeași migrare; `legal_name` nu
se mai citește nicăieri și se retrage într-o migrare ulterioară, când nimic nu-l mai referă
(`C5` — migrările sunt aditive). Se face acum fiindcă e ieftin acum.

## 6. Ancora lui `P-11` se corectează

[ADR-081](081-revendicarea-optionala.md) §3.4 spune că dreptul de revendicare e ancorat în IDNO-ul
tenantului. Scris ca afirmație generală, e fals pentru orice spațiu care nu declară o identitate —
adică pentru cazul obișnuit de mai sus.

> **Se revendică dovedind că reprezinți identitatea declarată a spațiului sau, în lipsa ei,
> IDNO-urile *tuturor* companiilor din el.**

„Toate", nu „una", și acolo e miezul: un spațiu care ține companii ale mai multor proprietari nu se
predă cuiva care dovedește că reprezintă una dintre ele. Regula nu blochează niciun caz real —
antreprenorul reprezintă toate societățile lui, iar un spațiu creat de o firmă pentru un client are
companiile acelui client — și blochează exact cazul pe care nu-l vrei.

Ce constituie dovada rămâne `OD-118`, juridic, cu co-semnătură. Aici se fixează **pe ce** se face
dovada, nu **cum**.

## 7. Ce nu se schimbă

- **Rețeta de înregistrare** — ordinea din Spec A §12.2, neatinsă.
- **Facturarea** — [ADR-082](082-unitatea-facturabila.md), neatinsă.
- **`multi_company`** — se activează la a doua companie, ca la oricine.
- **[ADR-083](083-editarea-companiei.md) și [ADR-084](084-rolul-la-provizionare.md)** — cheile de
  companie și rolul scris la provizionare rămân exact cum sunt; acest ADR e despre spațiu, nu despre
  companii.

## 8. Consecințe

- **Devine posibil:** un antreprenor își ține toate societățile într-un spațiu, fără să declare una
  dintre ele „titulară" — ceea ce juridic nu e.
- **Devine imposibil:** ecranul care cere identitate unui spațiu care n-are de ce să aibă una;
  predarea unui spațiu multi-proprietar către cine reprezintă o singură companie din el.
- **De modificat ca urmare:** `tenant.display_name` (aditiv, alimentat din `legal_name`); ecranul
  *Spațiul de lucru* și `GET /api/v1/workspace` — oferta de companie proprie apare **numai** când
  spațiul declară o identitate și nimic nu se potrivește; Spec A §1.1;
  [ADR-081](081-revendicarea-optionala.md) §3.4 primește trimitere la §6 de aici.
- **Ce se verifică automat:** (a) un test că un spațiu fără `idno` nu produce ofertă și nu raportează
  identitate incompletă — și că același spațiu cu trei companii le arată egale, fără „titulară";
  (b) un test că revendicarea pe IDNO-ul unei singure companii dintr-un spațiu cu două companii e
  refuzată, cu cod stabil (`C10`); (c) capcana existentă pentru potrivirea pe nume (ADR-075 §2) rămâne
  verde și neatinsă.

## 9. Ce rămâne deschis

**`OD-125` — mutarea unei companii dintr-un spațiu în altul.** Antreprenorul care vinde una din cele
cinci n-are unde s-o ducă: transferul modelat azi (Spec A §4.5) e al **angajamentului** — se schimbă
firma —, nu al companiei. Cu ledger append-only (`R10`), „mutarea" nu e o coloană schimbată: e export,
spațiu nou și solduri inițiale, adică drumul din `import.*`, cu întrebarea deschisă ce se întâmplă cu
istoricul rămas în spațiul vechi. Atinge `P-8`, soldurile inițiale și retenția — trei zone cu decizii
proprii încă deschise, deci **nu se decide acum**. Distinctă de `OD-122` (ștergerea unei companii
introduse din greșeală): acolo compania n-ar fi trebuit să existe, aici există și trebuie să existe în
altă parte.

**Notă înainte, nu decizie:** identitatea fiscală a plătitorului aparține probabil lui
`billing_account`, nu lui `tenant` — o factură se emite către cine plătește, iar plătitorul e deja o
atribuire cu dată ([ADR-081](081-revendicarea-optionala.md) §5). Se reașază când se construiește
facturarea (`OD-107`), nu acum: azi n-ar avea consumator, iar mutarea unei coloane fără consumator e
zgomot. Cazul nou pentru `OD-107` — factura de abonament emisă către o **persoană fizică** — se
consemnează acolo.

## Surse

- [ADR-075](075-identitatea-titularului.md) §2 și §3, [ADR-080](080-tipul-nu-se-stocheaza.md) §2–§3,
  [ADR-081](081-revendicarea-optionala.md) §3.4 și §5, [ADR-082](082-unitatea-facturabila.md),
  [ADR-083](083-editarea-companiei.md), [ADR-084](084-rolul-la-provizionare.md).
- Spec A §1.1, §4.5, §12.2.
- Măsurat în cod la 2026-08-31: `platform/identity/models.py` — docstring-ul lui `User`
  (*„one accountant, one account, sixty clients"*) și `Membership` ca legătură persoană ↔ spațiu;
  `platform/tenancy/models.py` — `idno`/`legal_form` nullable, `legal_name` `NOT NULL`, `Company` ca
  ancoră a contabilității fără excepție.
- `CLAUDE.md` `C5`, `C10`, `C39`, `R10`.
- Conversație 2026-08-31.
