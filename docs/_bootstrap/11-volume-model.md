# 11 — Modelul de volum de date

- **Sarcina:** F0.11 — ultimul criteriu de ieșire din F0 rămas deschis
- **Decide:** `OD-01` — cheia de partiționare pentru tabelele append-only de volum mare (`R21`)
- **Data:** 2026-08-25

## Ce trebuie să răspundă, și ce nu

Modelul servește **o singură decizie**: dacă și după ce coloană se partiționează `journal_lines`,
`audit_event`, `document_event` și celelalte tabele din `infra/schema/append_only.toml`.

Pentru decizia asta contează **ordinul de mărime și asimetria**, nu exactitatea. Diferența dintre
40 și 60 de milioane de rânduri pe an nu schimbă nicio alegere; diferența dintre 4 și 400 de
milioane o schimbă pe toate. La fel, dacă un singur tenant ține jumătate din rânduri, `tenant_id`
este o cheie de partiționare proastă indiferent de total — iar asta se vede din distribuție, nu din
medie.

Consecința practică: modelul nu are nevoie de date reale. Are nevoie de **ordine de mărime cu sursă
și de ipoteze declarate ca ipoteze**.

## De ce nu mai depinde de o firmă colaboratoare

`OD-30` blochează F0.11 cu motivul „firma de contabilitate colaboratoare nu este identificată", iar
Amendamentul 1 cere „date reale de la o firmă de contabilitate colaboratoare".

Cerința se împarte în trei, și doar una are nevoie de firmă:

| Ce | Cine o cere | Are nevoie de firmă? |
|---|---|---|
| **Volumul** — ordine de mărime, distribuție pe clase | F0.11, `OD-01` | **Nu.** Statistică publică plus cifrele deja scrise în Amendament |
| **Structura** — plan de conturi real, parteneri, un an de rulaje, ca fixture pentru grile | F1.G0, `OD-28` | Da — un extras anonimizat |
| **Adevărul numeric** — o balanță de verificare reală, verificabilă la leu | F1.2 | Da — un raport |

Ce urmează acoperă **doar prima linie**. Celelalte două rămân deschise și nu blochează F0.

## Sursele

Fapte publice, fiecare cu sursa lui. Nimic dedus din memorie.

| Fapt | Valoare | Sursă |
|---|---|---|
| Întreprinderi raportoare, 2025 | 74,6 mii — IMM 74,4 mii (99,7%), mari 0,2 mii | [BNS, IMM 2025](https://statistica.gov.md/ro/activitatea-intreprinderilor-mici-si-mijlocii-in-anul-2025-9557_62556.html) |
| Salariați, 2025 | 548,6 mii — IMM 393,0 mii, mari 155,6 mii | idem |
| Venituri din vânzări, 2025 | 767,6 mld lei — IMM 563,3 mld, mari 204,3 mld | idem |
| Media per IMM, 2025 | 7,6 mln lei venituri, 6 salariați | idem |
| Clase de mărime | micro ≤9 salariați · mici 10–49 · mijlocii 50–249 | idem |
| Întreprinderi **active**, 2023 | 41,8 mii, din care **28,7 mii (68,6%) cu 0–4 salariați** | [BNS, demografia întreprinderilor 2023](https://statistica.gov.md/index.php/ro/demografia-intreprinderilor-in-republica-moldova-in-anul-2023-9557_62184.html) |
| Întreprinderi create, 2023 | 2,314 mii — 81,4% în clasa 0–4 salariați; 5,1% cu 10+ | idem |
| Distribuția exactă pe clase, 2021–2025 | tabelul `ANT030040` | [BNS Statbank](https://statbank.statistica.md/PxWeb/pxweb/ro/40%20Statistica%20economica/40%20Statistica%20economica__24%20ANT__ANT030/) |
| Plăți cu carduri, 2023 | 183,0 mln plăți, 60,7 mld lei | [BNM, sistemele de plăți](https://bnm.md/ro/content/sistemul-national-de-plati) |

Din documentele proprii ale proiectului, care sunt tot surse și au precedență asupra oricărei
estimări proprii:

| Fapt | Valoare | Sursă |
|---|---|---|
| Ordinul de mărime al pieței | ≈60.000 de companii active; **scenariu optimist 10–15.000 de tenanți în 10 ani, majoritatea micro** | Amendament 1, §B.3 |
| Profil „contabil mediu" | **60 de clienți** | Master plan V2, §9.2 |
| Profil „contabil mare" | **100 de clienți** | Master plan V2, §12 |
| Retenție online cerută | **balanță de verificare pe 5 ani de date** | Master plan V2, §12 |
| Primul candidat la partiționare | **`audit_events`, nu `journal_lines`** | Amendament 1, §B.3 |

### Trei capcane în sursele publice, semnalate ca să nu se propage

1. **Comunicatele IMM 2024 și 2025 nu sunt comparabile.** Ponderea IMM în vânzări sare de la 46,1%
   (2024) la 73,4% (2025), iar numărul de la 68,2 la 74,4 mii. O creștere reală de asemenea formă nu
   există; este schimbare de metodologie sau de populație raportoare. **Nu se construiește o
   tendință peste ele.**
2. **Două populații diferite, ușor de amestecat.** „74,6 mii întreprinderi raportoare" (situații
   financiare) și „41,8 mii întreprinderi active" (demografia întreprinderilor) numără lucruri
   diferite. Cifra Amendamentului — ≈60.000 — stă între ele, ceea ce este exact ce ar trebui.
3. **Ancora e-Factura este slabă și nu se folosește.** Cifrele publice (medie lunară ~175 mii
   facturi în 2019, de la ~50,3 mii contribuabili) provin din perioada în care sistemul era
   preponderent pentru relația cu sectorul public. Ca rată per companie, este un **prag inferior**,
   nu o medie, și nu intră în calculele de mai jos.

## Ce este fapt și ce este ipoteză

Un singur lucru din lanț nu are sursă publică: **câte documente pe lună produce o companie dintr-o
clasă de mărime**. Nu se poate deduce din venituri fără valoarea medie a unui document, care nu e
publică nici ea.

Deci se declară ca ipoteze, cu interval, și se testează la sensibilitate:

| # | Ipoteză | Valoare centrală | Interval |
|---|---|---|---|
| `A1` | Documente economice pe lună, companie **micro** (0–9 salariați) | 30 | 10–80 |
| `A2` | Documente economice pe lună, companie **mică** (10–49) | 300 | 150–800 |
| `A3` | Documente economice pe lună, companie **mijlocie** (50–249) | 1.500 | 800–4.000 |
| `A4` | Linii de înregistrare per document economic | 3 | 2–6 |
| `A5` | Evenimente de audit per document economic | 5 | 3–12 |

`A4` merită explicat, fiindcă pare mică: o factură cu TVA se contabilizează în 3 linii (creanță,
venit, TVA). Documentele de salarizare și cele de stoc produc mult mai multe, iar intervalul le
acoperă. `A5` numără fiecare schimbare de stare, nu doar crearea — plus autentificările și căile
privilegiate, care se auditează fără să existe document.

**Ipotezele nu sunt măsurători și nu se citează ca atare.** Un singur punct de date real de la orice
contabil — „câte documente pe lună are un client tipic" — colapsează tot intervalul. Este o
întrebare de cinci minute, nu un extras de bază de date.

## Cele trei scenarii

Definite pe **tenant**, fiindcă tenantul este unitatea de izolare. Firma de contabilitate este ea
însăși un tenant, dar rândurile clienților ei **nu** sunt în tenantul ei — ceea ce contează pentru
partiționare și se pierde ușor din vedere.

### Per tenant, pe an și cumulat pe 5 ani de retenție

| Scenariu | Profil | Documente/an | `journal_lines`/an | `journal_lines` la 5 ani | `audit_event`/an |
|---|---|---|---|---|---|
| **Mic** | o companie micro, `A1` | 360 | 1.080 | 5.400 | 1.800 |
| **Mediu** | o companie mică, `A2` | 3.600 | 10.800 | 54.000 | 18.000 |
| **Mare** | o companie mijlocie, `A3` | 18.000 | 54.000 | 270.000 | 90.000 |

Concluzia la nivel de tenant este că **nu există problemă de volum per tenant**. Chiar la capătul de
sus al intervalelor, un tenant singur rămâne cu ordinul milionului de linii pe cinci ani. Nicio
tabelă nu se partiționează pentru asta.

### La nivel de platformă — unde se ia decizia

Volumul care contează este suma peste tenanți, fiindcă tabelele sunt comune. Scenariul optimist din
Amendament — **15.000 de tenanți în 10 ani** — cu distribuția pe clase din BNS (68,6% în clasa cea
mai mică):

| Clasă | Tenanți | Documente/an | `journal_lines`/an | `audit_event`/an |
|---|---|---|---|---|
| micro (68,6%) | 10.290 | 3,7 mln | 11,1 mln | 18,5 mln |
| mici (25%) | 3.750 | 13,5 mln | 40,5 mln | 67,5 mln |
| mijlocii (6,4%) | 960 | 17,3 mln | 51,8 mln | 86,4 mln |
| **Total** | **15.000** | **34,5 mln** | **≈103 mln** | **≈172 mln** |

Cumulat pe cei 5 ani de retenție: **≈515 milioane de linii de înregistrare** și **≈860 milioane de
evenimente de audit**.

Repartiția pe clase de mai sus (25% / 6,4%) este o **ipoteză de mix**, nu o măsurătoare: BNS dă
68,6% pentru clasa 0–4 salariați, restul l-am împărțit între mici și mijlocii. Se înlocuiește cu
distribuția exactă din `ANT030040` când se interoghează tabelul, iar totalul se schimbă cu cel mult
un factor de doi — sub pragul care schimbă decizia.

### Ce confirmă asta

Două lucruri, ambele scrise deja în Amendament și verificate acum prin calcul independent:

1. **„sute de milioane de linii cumulat, nu pe an"** — calculul dă 515 milioane cumulat pe cinci
   ani, față de 103 milioane pe an. Formularea Amendamentului era corectă.
2. **`audit_event` este primul candidat, nu `journal_lines`** — 172 față de 103 milioane pe an, cu
   `A5` la valoarea centrală. La capătul de sus al lui `A5` raportul devine 2,5:1. Și, spre
   deosebire de ledger, valoarea unui eveniment de audit **scade cu vechimea**, deci partițiile
   vechi se pot detașa și arhiva — ceea ce este chiar motivul pentru care partiționarea plătește.

## Sensibilitate — ce ar schimba decizia

| Dacă | Atunci |
|---|---|
| `A1`–`A3` la capătul de sus (×2,7) | ≈280 mln `journal_lines`/an; partiționarea `journal_lines` devine necesară în anul 3, nu în anul 10 |
| `A1`–`A3` la capătul de jos (×0,4) | ≈41 mln/an; nimic nu se partiționează niciodată în orizontul planului |
| Adopția rămâne la 1.000 de tenanți | ≈7 mln linii/an — nicio decizie de luat |
| **Un singur tenant ajunge la 30%+ din rânduri** | `tenant_id` devine cheie de partiționare inutilizabilă — partiții inegale, iar cea mare nu se poate sparge |

Ultimul rând este cel care contează cel mai mult și este cel mai puțin sensibil la ipoteze:
distribuția BNS arată o piață dominată de micro, deci **asimetria pe tenant este garantată**. O
platformă cu 10.000 de tenanți micro și 100 de tenanți mijlocii are un raport de volum per tenant de
50:1. `tenant_id` ca cheie de partiționare produce partiții care diferă cu două ordine de mărime.

## Măsurători

Rulate sub `evidenta_app`, cu politicile active, prin `backend/tests/volume/`. Scara implicită
(2.000 de rânduri) rulează în suita obișnuită, ca harness-ul să nu putrezească neobservat; scara
reală se cere cu `EVIDENTA_VOLUME_ROWS`.

**Mediul contează și se scrie:** mașina de dezvoltare, o instanță PostgreSQL 18 locală, fără
concurență. Cifrele sunt utile ca **raporturi**, nu ca praguri de producție.

| Măsurătoare | Valoare |
|---|---|
| Scriere prin rolul aplicației, cu `WITH CHECK` evaluat pe rând | **13.000–18.000 rânduri/s** |
| Enumerarea Spec A §9.3 (`LIMIT 50`), 1 mln rânduri, **înainte** de index | **6.749 ms**, 1.000.000 de rânduri citite |
| Aceeași interogare, **după** index | **1,05 ms**, 50 de rânduri citite |
| `count(*)` pe tot tenantul, 1 mln rânduri | ≈5,7–6,6 s |
| `count(*)` pe fereastră de 30 de zile | ≈500–600 ms peste ≈82.000 de rânduri |
| Costul de scriere al indexului al patrulea | 8–20% între rulări |

### Ce a găsit măsurătoarea, și nu era partiționarea

**Enumerarea „ce s-a întâmplat în tenantul ăsta, cel mai recent întâi" citea un milion de rânduri ca
să întoarcă cincizeci.** Nu printr-un scan secvențial — printr-un *index scan* peste tot. Cauza este
forma indexului: `audit_event_scope_idx` este `(tenant_id, company_id, occurred_at)`, deci în
interiorul unui tenant rândurile sunt ordonate întâi după companie și abia apoi după timp. O
ordonare după `occurred_at` singur nu se poate servi din el.

Verificarea scrisă inițial căuta absența cuvântului „Seq Scan" și **trecea mulțumită la 6,7
secunde**. Acum verifică rândurile citite, nu absența unui cuvânt.

Remediul este `audit_event_recent_idx` — `(tenant_id, occurred_at DESC)`, migrarea `audit/0002`.
Costul: un al patrulea index pe tabela cu cel mai mare volum de scriere, măsurat între 8% și 20%
între rulări. Varianța între rulări este de același ordin, deci afirmația onestă este „cost de
scriere măsurabil, dar mic", nu un procent anume.

### O constatare de planificator, care depășește această tabelă

**Planificatorul nu poate estima selectivitatea prin `app.current_tenant_id()`** și presupune un
număr fix de rânduri, indiferent de tabelă — s-a văzut `rows=1` și `rows=4` acolo unde realitatea
era 1.000.000 și 2.000. Funcția este `STABLE`, dar nu are statistici.

Două consecințe, ambele valabile pentru **orice** interogare din sistem, fiindcă toate filtrează
prin acea funcție:

1. **Forma planului se schimbă cu dimensiunea reală** în feluri pe care un fixture mic nu le arată
   niciodată. La 2.000 de rânduri planificatorul alege *bitmap scan* plus sortare top-N, ceea ce e
   corect acolo; la 1.000.000 trece la *index scan*. O verificare care afirmă forma planului trebuie
   să spună la ce scară o afirmă
2. Un plan prost ales din cauza estimării nu se repară cu `ANALYZE`, fiindcă nu statisticile tabelei
   lipsesc, ci selectivitatea predicatului

## Ce recomandă modelul pentru `OD-01`

Concluzia se propune, nu se închide aici: `OD-01` se închide printr-un ADR **după benchmark**, iar
criteriul lui F0.11 cere ca măsurătorile să ruleze cu politicile RLS active și sub rolul de
aplicație. Ce urmează este ipoteza de testat, nu rezultatul.

| Tabelă | Cheie propusă | Motiv |
|---|---|---|
| `audit_event`, `document_event` | `occurred_at`, lunar sau trimestrial | Volumul cel mai mare de scriere; valoarea scade cu vechimea; partițiile vechi se detașează și se arhivează în loc să fie șterse rând cu rând |
| `journal_lines` | `accounting_date`, anual | Fiecare interogare contabilă este mărginită de perioadă; închiderea și arhivarea sunt tot pe perioadă, deci retezarea coincide cu granița de business |
| oricare | **niciodată `tenant_id`** | Asimetria măsurată mai sus. În plus, numărul de tenanți crește, deci ar cere partiții noi la fiecare client — operațiune de schemă declanșată de o vânzare |

**Declanșatorul nu este o dată, ci un număr:** partiționarea se face când tabela trece de ~100
milioane de rânduri **și** interogările se pot elaga după cheie. Până atunci, disciplina din `R21`
și `R22` — fără chei străine intrând, coloana de partiționare `NOT NULL` de la început, indecși care
încep cu contextul de tenant — face ca trecerea să fie o operațiune, nu o rescriere.

## Limita acestui document, scrisă ca să nu fie presupusă

Modelul stă pe **agregate publice și cinci ipoteze declarate**, nu pe o bază reală. Pentru o decizie
de partiționare este suficient, fiindcă decizia se schimbă la ordine de mărime, iar intervalele de
sensibilitate acoperă un factor de aproape șapte între capete fără să răstoarne concluzia.

Nu este suficient pentru altceva. În particular, **nu** spune nimic despre forma datelor — câte
conturi analitice folosește o companie reală, cât de lungi sunt denumirile, câte dimensiuni poartă o
linie. Aceea este `OD-28` și cere extrasul de la F1.G0.
