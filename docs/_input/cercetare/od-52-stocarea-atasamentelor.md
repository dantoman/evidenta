# `OD-52` — Stocarea atașamentelor: dispunere, semnare, scanare, furnizor, retenție

- **Data cercetării:** 2026-08-25/26
- **Convenția de provenienţă**, folosită în tot fișierul: **[V]** citit azi din documentaţia sau
  pagina de preţuri a furnizorului · **[S]** sursă secundară · **[D]** derivat de cercetător dintr-o
  cifră primară sau din documentele proiectului

---

## 1. Bucket per tenant sau prefix per tenant — prefix, și e aproape forțat

**Recomandare: un bucket per mediu, plus unul de arhivă. Cheia rămâne exact cum o derivă azi
`storage.py`.**

Limitele dure nu lasă alternativă:

- **AWS: cotă implicită 10.000 de bucket-uri per cont**, ridicabilă la 1 milion; **primele 2.000
  gratuite, taxă lunară peste**; peste 10.000, orice `ListBuckets` nepaginat e respins **[V]**.
  Modelul propriu de volum al proiectului (`_bootstrap/11-volume-model.md`) ţinteşte **10.000–15.000
  de tenanţi în 10 ani** — adică fix pe cotă, într-un singur mediu, înainte de staging şi dev.
- **Hetzner plafonează la 100 de bucket-uri per cont**, peste toate proiectele **[V]**. Acolo
  bucket-per-tenant nu e incomod, e imposibil.
- **Politica de bucket e plafonată la 20 KB**; politica IAM inline la 10.240 de caractere, cea
  gestionată la 6.144, iar o politică de sesiune STS la **2.048 inclusiv ARN-urile** **[V]**. Orice
  desen care enumeră tenanţii într-o politică moare la câteva sute.
- **GuardDuty Malware Protection acoperă maximum 25 de bucket-uri** per cont şi regiune **[V]** —
  bucket-per-tenant exclude din start scanarea nativă AWS.
- **Lifecycle: 1.000 de reguli per bucket [V]**, deci nici regulile de retenţie per tenant nu scalează
  într-un bucket comun. Ștergerea se face din job, nu din regulă.

Ce **nu** diferă: ștergerea per tenant și exportul per tenant sunt echivalente ca efort. Singurul
avantaj real al bucket-per-tenant ar fi cheia de criptare proprie — și nu supravieţuieşte aritmeticii:
pe AWS o cheie KMS costă **1 $/lună [V]**, adică **180.000 $/an la 15.000 de tenanţi**, înainte de
orice cerere. În afara AWS, **doar Scaleway oferă SSE-KMS**; R2 şi Hetzner au doar SSE-C **[V]**.

> **Consecinţa de scris în ADR, nu de lăsat implicită.** Cu dispunere pe prefix — și pe orice
> furnizor non-AWS, indiferent de dispunere — **depozitul de obiecte nu este a doua linie de
> apărare.** Există o singură credenţială; graniţa de izolare stă integral în rândul RLS din
> PostgreSQL plus faptul că **cheia e derivată, niciodată primită de la client**. Asta e deja ce
> spune `storage.py` („authorisation happened before, in the database"), e o poziţie apărabilă, dar
> face din derivarea cheii un control de securitate portant — deci merită test de gardian propriu.

## 2. Semnarea URL-urilor — clientul nu primeşte URL semnat pe calea normală

**Recomandare:** Django autorizează → generează un GET presemnat de **60 de secunde** → îl întoarce
prin `X-Accel-Redirect` → nginx aduce fişierul şi îl transmite clientului. Presemnat direct spre
client e excepţie, şi atunci ≤ **5 minute**, cu `response-content-disposition=attachment`.

- **Un URL presemnat este un token la purtător şi nu se poate revoca.** Formularea AWS: *„presigned
  URLs are bearer tokens that grant access to those who possess them"* **[V]**. Singurele opriri
  premature — ştergerea obiectului, schimbarea politicii, revocarea credenţialei — lovesc toate
  URL-urile semnate cu aceeaşi credenţială.
- Durata maximă: 7 zile cu credenţiale de utilizator IAM; **1 minut–12 ore** din consolă; cu
  credenţiale temporare **URL-ul moare odată cu ele** **[V]**. Ghidul propriu Google pentru GCS
  recomandă 15–60 de minute la descărcare **[V/S]**.
- **Fereastra de revocare e exact cazul pentru care `T2` cere deja test.** Cu `company_access`
  revocat sau engagement expirat, un URL presemnat în zbor lasă contabilul revocat cu factura încă o
  fereastră întreagă. Nu e catastrofal la 5 minute; e complet evitabil la zero.
- Precedentul de copiat dacă totuşi e nevoie de presemnat: **Stripe File Links** — un rând deţinut de
  aplicaţie cu `expires_at`, revocabil punând `expires_at: now` **[V]**. Plus condiţia de politică
  **`s3:signatureAge`**, care respinge server-side orice cerere presemnată mai veche de N ms **[V]**.

Două note mecanice pe codul existent: `put(key, data: bytes, ...)` materializează tot fişierul în
memorie — la 25 MB × concurenţă e o amprentă reală, ar trebui flux; iar `signed_url(key, *,
expires_in)` nu are cum să transmită antete de răspuns, deci apărarea `Content-Disposition` **nu are
azi unde să stea**.

## 3. Scanare antivirus — verdictul stă în PostgreSQL, nu într-un tag de obiect

**Flux:** încărcare → prefix de carantină → ClamAV prin `clamd` INSTREAM → la `CLEAN` se copiază pe
cheia finală şi `scan_status='clean'`; la `THREAT` cheia finală nu se scrie niciodată; **la scaner
indisponibil sau fişier peste limita scanerului → `scan_status='unscanned'`, care nu e descărcabil.**

Trei stări, nu două. Motivul e o capcană măsurată: **un fişier peste `MaxFileSize` nu e scanat, iar
clamd îl raportează curat [V].** „Peste limită" trebuie să fie stare distinctă, niciodată o trecere.

De ce nu tiparul tag-then-deny, care e cealaltă arhitectură documentată: AWS îl livrează ca funcţie
de sine stătătoare şi e **fail-closed**, fiindcă un obiect nescanat n-are tag **[V]** — dar
**GuardDuty e doar AWS**, plafonat la 25 de bucket-uri, **nu suportă SSE-C**, iar **R2, B2 şi Hetzner
nu suportă deloc etichetarea obiectelor [V]**. Tiparul e indisponibil pe furnizorul recomandat.

ClamAV, spus cinstit:

- **RAM: „upwards of 1.2 GiB simply to load the signature definitions"**, recomandat **3 GiB minim /
  4 GiB preferabil**, şi **dublu în timpul reîncărcării bazei [V]**. Deci **serviciu comun de lungă
  durată, nu sidecar per replică** — un sidecar de 1 GiB e omorât de OOM la primul freshclam.
- Implicite `clamd.conf` care muşcă **[V]**: `MaxFileSize` 100M, `MaxScanSize` 400M,
  `StreamMaxLength` 100M, `MaxRecursion` 17, `MaxFiles` 10000.
- **freshclam: documentaţia spune explicit că gazdele din spaţiul IP al furnizorilor cloud „will most
  likely be rate limited"**, că 429 înseamnă prea multe descărcări şi că **doar freshclam şi cvdupdate
  sunt suportate** — wget/curl scriptat e *„explicitly denied"* **[V]**. N replici cu freshclam
  propriu vor fi blocate: **o singură oglindă `cvdupdate`**.
- **Eficacitate: 59,94%** pe 416.561 de mostre MalwareBazaar — bun pe docx/DLL/ELF, **slab pe exe,
  xls\* şi zip** **[S, noiembrie 2022, anterior ClamAV 1.5.0]**. Contabilii încarcă xls\*.
  **ADR-ul trebuie să spună la ce serveşte de fapt ClamAV:** să împiedice platforma să devină vector
  de distribuţie când contabilul A descarcă ce a încărcat clientul B, şi să se poată afirma că
  încărcările sunt scanate. Nu protecţie împotriva unui atacator determinat.

**Descalificate, cu motiv:** *Cloudflare WAF Content Scanning* — doar Enterprise, plafon 50 MB cu
trunchiere tăcută peste, şi **exclude explicit `text/xml`**, deci XML-ul e-Factura n-ar fi scanat
**[V]**. *API-ul public VirusTotal* — mostrele se stochează în Corpus şi se împart cu partenerii;
termenii lor spun *„do not send it/contribute it to the service"* dacă nu vrei să devină public
**[V]**. Un registru de salarii al unui client trimis acolo e problemă de Legea 133 / 195, nu opţiune
de proiectare.

## 4. Limite de mărime şi tip

**Recomandare: se păstrează 25 MB per fişier; se adaugă plafon de 10 ataşamente per document;
`content_type` devine determinat de server; SVG şi HTML nu se acceptă niciodată.**

> **Tabelul de mai jos înlocuieşte o versiune anterioară, secundară — şi două cifre erau greşite.**
> Limitele Xero erau **pe dos**: 25 MB e pe endpointul de ataşamente din Accounting API, iar 10 MB pe
> Files API, nu invers. Iar QuickBooks Online **nu publică nicio limită de mărime**: cifra de ~30 MB
> circula din răspunsuri de forum, unde **agenţii proprii ai Intuit se contrazic** între ei dacă
> plafonul de 20 MB e per fişier sau per tranzacţie. Preluat: 26 august 2026.

| Platformă | Per fişier | Per document | Total | Politica de tipuri | Provenienţă |
|---|---|---|---|---|---|
| **Xero** — Accounting API | **25 MB** | **10 ataşamente** | nepublicat | fără executabile, audio, video | **[V]** documentat per endpoint |
| **Xero** — Files API | **10 MB** | — | nepublicat | listă la `help.xero.com/filesupload` — **pagina nu se poate prelua** | **[V]** |
| **QuickBooks Online** | **nedocumentată** | nedocumentată | pretins nelimitat **[S]** | **listă albă**: PDF, JPEG, PNG, DOC, XLSX, CSV, TIFF, GIF, XML | **[V]** doar tipurile |
| **Sage Accounting** | **2,5 MB** | **10 ataşamente** | nepublicat | **listă albă**: PDF, GIF, JPG, JPEG, PNG | **[V]** |
| **Zoho Books** | 5 MB | 5 fişiere | nepublicat | nedocumentată | **[V]** |
| **FreeAgent** | 5 MB | 50 *(tranzacţie bancară)* | **1 GB** pe cont | largă, enumerată neexhaustiv | **[V]** |
| **Wave** | 5 MB | 25 fişiere / 20 MB *(factură)* | nepublicat | listă albă per suprafaţă, **inconsecventă între suprafeţe** | **[V]** |

**Trei observaţii care contează pentru desen:**

1. **Vendorii de contabilitate se grupează la 2,5–25 MB per fişier şi 5–10 ataşamente per document.**
   **10 × 25 MB e chiar plafonul de sus al pieţei**, Sage e podeaua. Cei 25 MB din schelet sunt la
   marginea superioară, nu la mijloc — şi rămân sub pragul de 100 MB de la care ClamAV trece tăcut.
   **Plafonul de număr lipseşte azi din cod.**
2. **Fiecare vendor de contabilitate foloseşte listă albă de tipuri; vendorii de stocare folosesc
   listă neagră sau nimic.** Listele albe converg pe PDF + JPEG/PNG/GIF/TIFF; **doar QBO admite
   DOC/XLSX/CSV/XML.** Ceea ce înseamnă că lista noastră, care trebuie să conţină XML pentru
   e-Factura, e mai largă decât a majorităţii — deci regula `defusedxml` de la §4 nu e prudenţă
   teoretică, e ce plătim pentru lărgime.
3. **Niciun vendor de contabilitate nu publică plafon total, cu excepţia FreeAgent (1 GB).** Xero,
   QBO, Sage şi Zoho îl lasă nedocumentat — **ceea ce înseamnă că există şi nu e divulgat**, nu că
   lipseşte.

- **Tipul MIME declarat de client nu valorează nimic.** OWASP: *„The Content-Type for uploaded files
  is provided by the user, and as such cannot be trusted, as it is trivial to spoof"*; iar despre
  octeţii magici, *„This should not be used on its own"* **[V]**. Trei verificări independente care
  trebuie să coincidă: extensie (validată **după** decodare — extensii duble, octet nul), MIME
  declarat, octeţi magici prin libmagic. Se stochează valoarea **determinată de server**.
- **Capcana OOXML, care se declanşează în prima săptămână:** `.xlsx` e container ZIP şi, după versiunea
  de libmagic, se adulmecă drept `application/zip` sau `application/octet-stream`, **nu** tipul OOXML
  **[S]**. O egalitate strictă respinge încărcări legitime.
- **Cuvintele Django, de citat verbatim în ADR [V]:** *„No bulletproof technical solution exists at
  the framework level to safely validate all user uploaded file content"* și — *„It's **not**
  sufficient to serve content from a subdomain like `usercontent.example.com`."*
  > **Asta se ciocneşte direct cu `C8`.** Contextul de tenant vine din subdomeniu, deci orice se
  > serveşte de sub `*.evidenta.md` stă în domeniul de cookie al fiecărui subdomeniu de tenant.
  > Ieşirile sunt două: un domeniu înregistrabil separat, sau — cum se recomandă la §2 — servirea
  > prin aplicaţie, astfel încât octeţi controlaţi de atacator să nu fie niciodată aduşi de la o
  > origine în care sesiunea are încredere.
- `X-Content-Type-Options: nosniff` **[V]** plus `Content-Disposition: attachment` — strat, nu răspuns.
- **SVG şi HTML: refuz.** SVG e XML care poate purta `<script>`, atribute `on*` şi `javascript:`;
  servit inline într-o platformă multi-tenant înseamnă acces cross-tenant prin sesiunea victimei.
  Nu există caz de utilizare contabil. Lista actuală le omite corect — **de păstrat deliberat, cu
  comentariu**.
- **XML trebuie să rămână** (e-Factura), ceea ce impune **`defusedxml` şi numai el** pe acea cale:
  OWASP documentează că `sax`, `ElementTree`, `minidom` şi `pulldom` sunt **toate** vulnerabile la
  Billion Laughs **[V]**. E o regulă impozabilă prin lint, de aceeaşi formă cu `no-restricted-imports`
  din `C16`.
- **PDF** poartă `/OpenAction`, `/Launch`, `/EmbeddedFile` **[S]**. OWASP recomandă CDR — dar atenţie
  la tensiune: **un PDF regenerat nu mai e identic la octet cu ce a depus clientul**, ceea ce atinge
  lanţul `R13` spre documentul sursă. **Originalul se păstrează imuabil; CDR doar pe o copie de
  previzualizare, dacă vreodată.**

## 5. Furnizor — Scaleway, regiunea `pl-waw`

| | AWS S3 eu-central-1 | Cloudflare R2 | Backblaze B2 | Hetzner | **Scaleway** | OVHcloud |
|---|---|---|---|---|---|---|
| Stocare /GB-lună | 0,0245 $ **[V]** | 0,015 $ **[V]** | 0,00695 $ **[V]** | €6,49 bază cu 1 TB **[V]** | €0,01606 Multi-AZ **[V]** | ≈€0,0071 **[D]** |
| Ieşire | 0,09 $/GB **[V]** | **0** **[V]** | liber până la 3× stocat **[V]** | 1 TB inclus **[V]** | 75 GB/lună liber **[V]** | **0** **[V]** |
| Object Lock | complet **[V]** | **niciunul** **[V]** | complet **[V]** | neverificat | **complet + legal hold** **[V]** | neverificat |
| Politici de bucket | da | **nu** **[V]** | nu | **nu** **[V]** | **da** **[V]** | — |
| SSE-KMS | da | **nu** **[V]** | nu | **nu** **[V]** | **da** **[V]** | — |
| Expunere CLOUD Act | da | da (companie SUA) | da | **nu** | **nu** | **nu** |
| Cost la 2 TB + 200 GB/lună | ≈59 $ **[D]** | ≈31 $ **[D]** | ≈14 $ **[D]** | ≈€13 **[D]** | ≈€34 **[D]** | ≈€15 **[D]** |

**Scaleway e singurul furnizor european care le are pe toate deodată** — Object Lock în mod
compliance cu legal hold, politici de bucket, SSE-KMS, IAM real — şi **Varşovia** e cea mai apropiată
regiune de Chişinău. Companie franceză, fără expunere CLOUD Act. Prima peste Hetzner e **≈20 €/lună**
la scara derivată, ceea ce nu e o cifră de decizie faţă de o obligaţie legală de păstrare.

**R2 e descalificat în ciuda ieşirii gratuite.** Pagina proprie de compatibilitate a Cloudflare
listează **toate operaţiile Object Lock, `Put/GetBucketVersioning`, politicile de bucket, ACL-urile,
etichetarea şi SSE-KMS drept neimplementate [V]**. Ce a apărut în martie 2025 sunt „bucket locks" —
reguli pe prefix, **revocabile, fără moduri şi fără legal hold**, prin API propriu Cloudflare **[V]**.
`boto3.put_object_retention()` pur şi simplu eşuează. Pentru o platformă a cărei disciplină întreagă
e imuabilitatea, e fundaţia greşită.

**MinIO e descalificat:** `minio/minio` e **arhivat** pe GitHub, ultimul push 2026-04-24, prima linie
din README *„THIS REPOSITORY IS NO LONGER MAINTAINED"*; ediţia comunitară e **doar sursă**, fără
binare şi fără imagini Docker Hub; succesorul gratuit e **mononod** **[V]**. Rămâne apărabil ca
container de dezvoltare pinuit, atât.

> **Capcană boto3 care nu e opţională.** botocore **1.36.0** (ianuarie 2025) a schimbat
> `request_checksum_calculation` la `when_supported`, trimiţând CRC32 prin **codificare cu trailer
> `aws-chunked`** la fiecare PUT. Serverele compatibile S3 care nu parsează trailerul **stochează
> octeţii trailerului ca parte din corpul obiectului** — încărcări corupte tăcut, raportat pe
> SeaweedFS (#6548) şi Apache Ozone (HDDS-12488). Poziţia AWS în boto3#4392 e că SDK-urile sunt
> *„designed for usage with official AWS services"* — nu se repară. De setat **înainte de prima
> încărcare**: `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` şi
> `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required`. Plus `signature_version="s3v4"`,
> `AWS_S3_ADDRESSING_STYLE` explicit, niciun `x-amz-acl` (R2 şi Hetzner îl resping) şi **fără puncte
> în numele bucket-ului** — certificatul wildcard Scaleway nu e recursiv.

## 6. Retenţie şi legal hold

**Recomandare:** Object Lock + versionare activate la crearea bucket-ului; **fără retenţie implicită
pe bucket**; retenţie per obiect în **mod governance** aplicată ca prag la încărcare şi extinsă când
`retention_class` devine cunoscută; modul compliance şi legal hold rezervate unei suspendări reale.

- **Semantica Object Lock [V]:** cere versionare; **odată activat nu se poate dezactiva**, iar
  versionarea nu se mai poate suspenda. Mod **governance** — se poate ocoli cu
  `s3:BypassGovernanceRetention`; mod **compliance** — *„can't be overwritten or deleted by any user,
  including the root user"*, iar *„The only way to delete an object under the compliance mode before
  its retention date expires is to delete the associated AWS account"*. **Legal hold** n-are expirare
  şi supravieţuieşte expirării retenţiei. **Retenţia se poate prelungi, niciodată scurta.**
- **Fără retenţie implicită pe bucket:** ADR-008 a decis deja că termenul e **parametru fiscal**,
  cheie `retention.<clasă>`, rezolvat la data efectivă. Un implicit pe bucket ar impune un singur
  termen tuturor claselor — greşit prin construcţie, iar ADR-008 spune explicit că un termen unic per
  tenant ar fi greşit *„indiferent de cifră"*.
- **Cazul `document` nulabil se potriveşte exact.** `Attachment.document` e nulabil prin desen — scanul
  soseşte înainte să se ştie al cărui document e — deci clasa de retenţie e necunoscută la încărcare.
  Fiindcă retenţia **se extinde dar nu se scurtează**, forma corectă e prag conservator la încărcare,
  extins la termenul rezolvat când ataşamentul se leagă. Constrângerea unidirecţională e chiar
  garanţia dorită.
- **Governance, nu compliance, ca implicit.** Modul compliance intră în coliziune frontală cu o
  obligaţie de ştergere, iar portiţa documentată e *ştergerea contului AWS*. **Care mod se aplică e
  întrebare juridică, nu tehnică**, şi aparţine lui `OD-21` plus unui jurist.
- **„Tenantul a plecat, dar documentele trebuie să supravieţuiască"**, pe stările din Spec A §9.4:
  `offboarding` — doar citire şi export, prin **P-8**; `archived` — **obiectele nu se mută şi nu se
  şterg**, se retrage accesul rolului de aplicaţie la prefix, singura cale rămâne P-8; **ştergerea
  efectivă** e job programat, nu regulă de lifecycle, condiţionat de două lucruri independente —
  fiecare obiect peste data de retenţie **şi** niciun legal hold. Object Lock impune prima condiţie
  chiar dacă job-ul greşeşte, ceea ce e tot rostul lui.
- **Crypto-shredding e capcana aici.** Ştergerea unei chei KMS per tenant e povestea curată — AWS
  documentează *„all data that was encrypted under the KMS key is unrecoverable"*, cu 7–30 de zile de
  aşteptare **[V]**. Dar e **incompatibilă frontal cu o obligaţie de păstrare care supravieţuieşte**:
  nu poţi şi să distrugi cheia, şi să prezinţi documentul unui control mai târziu. Deci cheile per
  tenant merită costul **doar dacă** răspunsul la Spec A §9.5 — *cine poartă obligaţia de păstrare
  după ce tenantul pleacă* — e „clientul, prin export". **Întrebarea aia n-a fost atinsă**; până la
  răspuns, cheile per tenant nu se construiesc, fiindcă cele două desene arată în direcţii opuse.

---

## Ce nu s-a putut verifica

**Documentat de furnizor, se poate cita:** toate cifrele AWS de mai sus (cote de bucket, 20 KB
politică, 6.144/10.240/2.048 caractere IAM, 1.000 reguli lifecycle, semantica URL-urilor presemnate,
`s3:signatureAge`, modurile Object Lock şi formularea pentru compliance, KMS 1 $/cheie/lună, cotele
GuardDuty); toate preţurile şi faptele de compatibilitate R2, Scaleway, Hetzner, B2 citite azi de pe
paginile lor; preţurile S3 eu-central-1 luate din **Price List Bulk API** (`publicationDate
2026-08-18`), nu de pe pagina de marketing randată în JS; implicitele `clamd.conf` din exemplul
upstream; cifrele de RAM ClamAV şi formularea despre rate limiting; fişele OWASP de File Upload şi
XXE; MDN pe `nosniff`; documentaţia de securitate Django; starea de arhivare MinIO citită din API-ul
GitHub.

**Secundar sau derivat — de verificat înainte să intre într-un ADR:**

- **Cifrele Xero şi QuickBooks Online au fost între timp reluate din documentaţia vendorilor** şi
  tabelul de la §4 e înlocuit — vezi nota de acolo. Ce rămâne **neobţinut**: plafonul total de stocare
  Xero Files şi cel al inboxului; **lista explicită de tipuri permise de Xero** (`help.xero.com/filesupload`
  întoarce CAPTCHA); **limita oficială de mărime a QBO**, care pur şi simplu nu e publicată; limitele
  entităţii `Attachable` din API-ul QBO (pagina e SPA şi nu întoarce conţinut); plafonul modulului
  Documents din Zoho Books. *Enumerate ca să nu fie confundate cu absenţa unei limite.*
- **Dropbox şi Google Drive** au fost obţinute, dar **nu sunt comparabile**: sunt vendori de stocare, nu
  de contabilitate, cu limite de ordinul GB–TB. *Notă utilă totuşi: două pagini oficiale Dropbox se
  contrazic — una spune că încărcările din browser peste 375 GB „may cause timeouts", cealaltă că
  fişierele de pe `dropbox.com` trebuie să fie sub 50 GB.*
- **Regiunea UE a Backblaze B2** (`eu-central-003` Amsterdam) e doar din sursă secundară; documentul
  propriu de endpoint-uri a dat 404.
- **Modurile Object Lock la Hetzner** — listat ca suportat, semantica neverificată. **OVHcloud** —
  neverificat. **Wasabi** — integral secundar.
- **Scenariul de cost 2 TB / 200 GB ieşire e derivat [D]**, din modelul de volum al proiectului ori o
  rată presupusă de ataşamente. Verificare de ordin de mărime, nu prognoză.
- **Eficacitatea ClamAV (59,94%)** e un studiu Splunk din noiembrie 2022, anterior versiunii 1.5.0.
- **Legea 195/2024 a RM**, dată de intrare în vigoare 23 august 2026: consecvent în mai multe surse de
  practică juridică, dar **textul oficial n-a fost citit**.
- **Termene de retenţie citate pentru Moldova** (documente primare 5 ani, situaţii financiare anuale
  10, personal 75, după Indicatorul Arhivei de Stat din 1997) — **nu se raportează ca fapt**: două
  surse nu cad de acord asupra articolului din legea contabilităţii care poartă obligaţia (17 sau 43).
  Aparţin lui `OD-21`, cu sursă primară.

**Părea actual şi nu mai e:** blogul APN al AWS despre partiţionarea multi-tenant în S3 încă spune
*„a default quota of 100 buckets and the hard quota of 1,000"* — depăşit din noiembrie 2024. **Orice
articol GuardDuty din 2024** dă 5 GB obiect maxim, 1.000 fişiere extrase, adâncime 5 şi 0,60 $/GB —
**toate patru sunt acum greşite**. Preţul Hetzner de €4,99 se repetă peste tot; pagina proprie spune
**€6,49**. *„Object Lock se poate activa doar la crearea bucket-ului"* se repetă larg şi **nu mai e
adevărat**. Trend Micro Cloud One File Storage Security a ieşit din vânzare la 31.07.2025.

**Trei lucruri pe care nu le publică nimeni:** latenţa GuardDuty de la încărcare la verdict; preţul
per GB GuardDuty pentru eu-central-1 anume; preţurile şi limitele Cloudmersive.

**Decizii lăsate deliberat deschise:** valorile de retenţie per clasă (`OD-21`), perioada de graţie la
offboarding (`DN-21`), şi întrebarea din Spec A §9.5 — **cine poartă obligaţia de păstrare după ce
tenantul pleacă** — care schimbă material răspunsul de la §6 şi e rezervată proprietarului sau unui
jurist.
