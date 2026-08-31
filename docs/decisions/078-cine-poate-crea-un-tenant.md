# ADR-078 — Cine poate crea un tenant: două canale, nu trei; invitația e o poartă de lansare

- **Stare:** Acceptat — produs, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Închide:** `DN-26` din Spec A §12.3
- **Restrânge:** `OD-108`
- **Deschide:** `OD-116`
- **Atinge:** `rls.provision_tenant` (`P-9`), Spec A §12.3, `platform/tenancy`
- **Legate:** [ADR-040](040-crearea-tenantului-si-a-companiei.md),
  [ADR-080](080-tipul-nu-se-stocheaza.md), [ADR-081](081-revendicarea-optionala.md)
- **Amendat în aceeași zi:** poarta de verificare a firmei e detaliată în
  [ADR-080](080-tipul-nu-se-stocheaza.md) §4 (stă pe **acțiune**, nu pe cont), iar trimiterile de
  mai jos la `unclaimed` / engagement provizoriu au fost înlocuite —
  [ADR-081](081-revendicarea-optionala.md) a înlocuit ADR-079

## 1. Ce se decide

`DN-26` întreba dacă un tenant se creează prin autoservire deschisă, prin invitație, sau exclusiv
prin firmă. [ADR-040](040-crearea-tenantului-si-a-companiei.md) §5 a lăsat întrebarea deschisă cu
formularea corectă: *„`P-9` funcționează pentru oricare — funcția verifică ce i se cere, iar cine
are voie s-o apeleze e o decizie de deasupra ei."*

**Se aleg ambele canale reale: autoservire și creare de către o firmă.**

## 2. Opțiuni evaluate

1. **Exclusiv prin firmă.** *Avantaje:* zero suprafață de abuz, un singur canal de distribuție,
   fiecare tenant are de la început pe cineva care răspunde de el. *Dezavantaje:* închide creșterea
   organică și clientul direct; o companie care vrea să-și țină singură contabilitatea nu poate
   începe. Pe o piață în care alternativa se instalează local, „cere unui contabil să te înscrie" e
   un motiv suficient să nu începi. *Cost de schimbare:* mic tehnic, dar canalul pierdut nu se
   recuperează retroactiv.
2. **Doar prin invitație (listă de așteptare, cod).** *Avantaje:* control complet asupra cine intră,
   util la lansare. *Dezavantaje:* e o **poartă temporară modelată ca permanentă**. Codul de
   invitație devine entitate, apoi devine cod care presupune că entitatea există, apoi rămâne acolo
   după ce poarta se deschide. *Cost de schimbare:* mediu, și crescător.
3. **Autoservire și creare de către firmă.** *Avantaje:* păstrează ambele canale comerciale, care
   corespund exact celor două canale de facturare din Spec A §10.1 (`direct` și `wholesale`); nu
   inventează nicio entitate nouă. *Dezavantaje:* cere protecție anti-abuz și o poziție despre
   IDNO. *Cost de schimbare:* mic — restrângerea ulterioară a autoservirii e un feature flag.

## 3. Decizia

**Opțiunea 3.** Două canale, aceeași funcție `P-9`, două seturi de precondiții.

| Canal | Cine apelează `P-9` | Ce primește tenantul | Facturare |
|---|---|---|---|
| **Autoservire** | Viitorul administrator, pentru sine | `status = 'active'`, membership de administrare pentru creator | `billing_account.channel = 'direct'` |
| **Firmă care aduce un client** | Un membru al unei firme `active`, adică verificate — [ADR-080](080-tipul-nu-se-stocheaza.md) §4.1 | `claimed_at` nul, engagement `active` pe mandat declarat — [ADR-081](081-revendicarea-optionala.md) §3.3 | `channel = 'wholesale'`, `payer_firm_id` = firma; mutabil ulterior, cu dată |

Migrarea din alt sistem (a treia linie din Spec A §12.3) **nu e un al treilea canal de creare**: e
oricare dintre cele două, plus un import. Rămâne în tabelul specificației ca variantă de onboarding,
nu ca răspuns la `DN-26`.

### 3.1 Invitația nu e canal, e comutator

Lansarea controlată se face cu ce există deja: **feature flag și ring de lansare** (Spec A §13.5,
`R23`). Ruta de autoservire se închide sau se deschide dintr-un flag; cât e închisă, se creează
tenanți prin firmă și prin consolă. Nu se modelează coduri de invitație, nu se creează o entitate
care va supraviețui motivului ei.

### 3.2 Ce apără autoservirea, și ce era deja acolo

Cea mai mare parte a protecției **exista deja**, în ordinea din Spec A §12.2, și n-a fost pusă acolo
pentru anti-abuz:

1. utilizator cu e-mail verificat;
2. **al doilea factor înrolat** ([ADR-021](021-mfa-obligatoriu.md)) — un cont MFA nu se creează în
   masă;
3. abia apoi `P-9`.

Se adaugă strict ce lipsește:

- **limitare de rată** pe utilizator și pe adresă IP, la crearea de tenanți;
- **subdomeniu**: lista de nume rezervate din Spec A §1.1, verificată în `P-9`, nu în formular;
- **IDNO declarat la creare** de către creator, nu completat ulterior — vezi §4.

Nu se adaugă: verificare telefonică, plată în avans, aprobare manuală. Fiecare ar muta fricțiunea pe
utilizatorul corect, ca să oprească unul incorect care nu s-a arătat încă.

## 4. IDNO — ce se decide și ce nu

Se decide **momentul**: la autoservire, identitatea titularului (`idno`, `legal_form`) se scrie de
creator, în tranzacția lui `P-9`, prin `set_tenant_identity`. Un tenant creat fără IDNO e un tenant
care va emite documente fără el.

**Nu se decide validarea.** Formatul, cifra de control și confruntarea cu registrul de stat cer o
sursă externă și o poziție juridică — nu se deduc (`CLAUDE.md` §4). Până atunci IDNO-ul e **declarat**,
nu **verificat**, iar produsul nu are voie să afirme contrariul nicăieri în interfață. Unicitatea
rămâne `DN-03`, deschisă și neatinsă aici.

**`OD-116`** — verificarea IDNO la înregistrare: sursa (`counterparty_registry`, alimentat prin
`P-5`, e candidatul evident), ce se întâmplă la nepotrivire (refuz, avertisment, marcaj), și dacă
verificarea e blocantă. Se decide când există sursa, nu înainte.

### 4.1 Ce se restrânge din `OD-108`

`OD-108` spunea că identitatea titularului nu se poate edita din produs, fiindcă îi lipsește cheia de
permisiune, și nota: *„legată de `DN-26`: dacă înregistrarea devine self-service, identitatea se
scrie la înregistrare și întrebarea se mută."*

**S-a mutat.** Scrierea inițială are acum un apelant legitim: creatorul, în tranzacția lui `P-9`.
Ce rămâne din `OD-108` este strict **editarea ulterioară** — cheia `tenant.manage_identity`, cine o
ține implicit, și dacă trece prin cale privilegiată sau prin politica obișnuită. `OD-108` rămâne
deschisă, cu jumătate mai puțin.

## 5. Consecințe

- **Devine posibil:** un client direct, fără contabil; o firmă care aduce șaizeci de clienți fără să
  aștepte șaizeci de înregistrări.
- **Devine imposibil:** un tenant fără IDNO declarat; un subdomeniu rezervat alocat de un formular.
- **Devine explicit:** canalul de facturare se stabilește la creare și nu se ghicește mai târziu.
  Un tenant creat de o firmă și niciodată revendicat rămâne pe canalul `wholesale` — cine plătește
  atunci e [ADR-081](081-revendicarea-optionala.md) §5, nu acest ADR — iar răspunsul lui e că
  plătitorul se poate muta, cu dată și cu acordul ambelor părți.
- **De modificat ca urmare:** `P-9` verifică apelantul după canal; Spec A §12.3 pierde blocul
  `DN-26` și capătă decizia; ruta de autoservire primește flag de ring.
- **Ce se verifică automat:** un test că `P-9` refuză un subdomeniu rezervat și unul ocupat; un test
  că un utilizator fără al doilea factor confirmat nu ajunge la `P-9`; limitarea de rată are test
  propriu, la nivel de request.

## Surse

- Spec A §1.1 (subdomenii rezervate), §10.1 (cele două canale de facturare), §12.2 (ordinea de
  onboarding), §12.3 (`DN-26`), §13.5 (ringuri și flags).
- [ADR-021](021-mfa-obligatoriu.md), [ADR-040](040-crearea-tenantului-si-a-companiei.md) §5,
  [ADR-075](075-identitatea-titularului.md) §4, `OD-108`, `DN-03`.
- `CLAUDE.md` `R23`, §4 („nu se deduc reguli … din memorie").
- Conversație 2026-08-31.
