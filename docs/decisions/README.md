# Decizii de arhitectură (ADR)

Fiecare decizie care are efect asupra schemei, a izolării, a conformității sau a limitelor de scop
primește un fișier numerotat în acest director. O decizie luată într-o conversație și nescrisă aici
nu există: sesiunea următoare o va redeschide, sau — mai rău — o va contrazice tacit.

## Când se scrie un ADR

- când se închide o decizie din `000-open-decisions.md`
- când o sarcină de implementare descoperă o alegere care nu era în registru și care nu poate fi
  amânată
- când se acceptă o **excepție** de la un invariant din `CLAUDE.md`
- când se schimbă o decizie luată anterior (ADR nou care înlocuiește, nu editare a celui vechi)

Nu se scrie ADR pentru alegeri reversibile fără cost: numele unei variabile, structura unui test,
ordinea câmpurilor. Regula practică: dacă schimbarea de mâine ar cere o migrare de date sau ar
invalida cod scris între timp, e ADR.

## Ce nu se face

- Nu se închide o decizie din `000-open-decisions.md` fără ADR.
- Nu se închide o decizie tacit, în cod. Dacă o sarcină ar cere-o, sarcina se oprește și se
  întreabă — vezi `CLAUDE.md`, secțiunea 4.
- Nu se editează un ADR acceptat pentru a-i schimba conținutul. Se scrie unul nou, cu status
  `Înlocuiește ADR-nnn`, iar cel vechi trece în `Înlocuit`.
- Nu se deduc reguli fiscale, praguri, cote sau formate de raportare. O decizie despre conformitate
  citează actul normativ sau nu se ia.

## Format

Fișier: `NNN-titlu-scurt-in-kebab-case.md`, numerotat crescător, fără reutilizarea numerelor.

```markdown
# ADR-NNN — Titlu

- **Status:** Propus | Acceptat | Respins | Înlocuit de ADR-NNN
- **Data:** AAAA-LL-ZZ
- **Decide:** cine a luat decizia
- **Închide:** OD-NN din 000-open-decisions.md (dacă e cazul)
- **Afectează:** modulele, tabelele sau fazele atinse

## Context

Ce problemă a impus decizia. Ce se știa și ce nu. Ce documente sau surse au fost consultate.

## Opțiuni evaluate

1. **Opțiunea A** — descriere. Avantaje. Dezavantaje. Cost de schimbare ulterioară.
2. **Opțiunea B** — idem.

O singură opțiune înseamnă că nu a fost o decizie, ci o constatare. Reformulează sau nu scrie ADR.

## Decizie

Ce s-a ales, la obiect. O propoziție, apoi detaliile necesare implementării.

## Consecințe

- ce devine posibil
- ce devine imposibil sau scump
- ce trebuie modificat în cod, schemă sau documentație ca urmare
- ce se verifică automat, și de către ce test sau agent

## Surse

Acte normative, secțiuni din documentele de intrare, benchmark-uri, discuții.
```

## Index

| ADR | Titlu | Status | Data | Închide |
|---|---|---|---|---|
| [000](000-open-decisions.md) | Registrul deciziilor deschise | Viu | 2026-08-24 | — |
| [001](001-grila-de-date.md) | Grila de date: TanStack Table, cu două componente interne | Acceptat | 2026-08-24 | — (restrânge OD-19) |
| [002](002-guvernanta-deciziilor.md) | Guvernanța deciziilor: cine aprobă ce | Acceptat | 2026-08-24 | OD-33 |
| [003](003-rls-tenancy-tables.md) | Politica RLS pentru tabelele care definesc tenancy-ul | Acceptat | 2026-08-24 | DN-12, OD-07 |
| [004](004-company-context.md) | Contextul de companie în sesiune | Acceptat | 2026-08-24 | DN-11, OD-08 |
| [005](005-stack-versions.md) | Versiunile stack-ului: regula, apoi valorile | Acceptat | 2026-08-24 | OD-14 |
| [006](006-reversal-two-dates.md) | Stornoul are două date distincte | Acceptat | 2026-08-24 | DNB-09, structural |
| [007](007-reversal-period.md) | Perioada în care se postează stornoul | **Propus** — 3 întrebări deschise | 2026-08-24 | DNB-09, politica |
| [008](008-retention-fiscal-parameters.md) | Retenția: mecanism acum, termene ca date | Acceptat | 2026-08-24 | DN-22, mecanismul |
| [009](009-componente-si-stil.md) | Biblioteca de componente și stratul de stil: shadcn/ui + Tailwind | Acceptat | 2026-08-24 | OD-34 |
| [010](010-contabilul-practicant.md) | Contabilul practicant: rolul este acoperit de proprietar | Acceptat | 2026-08-24 | OD-32 |
| [011](011-tooling-python.md) | Tooling Python: uv, ruff, pytest, mypy strict selectiv | Acceptat | 2026-08-24 | OD-15 |
| [012](012-sql-in-django-migrations.md) | SQL-ul de politici trăiește în migrațiile Django | Acceptat | 2026-08-24 | OD-18 |
| [013](013-python-version-pin.md) | Versiunea de Python: motivul actual și condiția de revizuire | Acceptat | 2026-08-24 | — (completează ADR-005) |
| [014](014-limba-rusa.md) | Limba rusă: interfața amânată cu hedge | Acceptat | 2026-08-24 | DN-01/OD-13, parțial |
| [015](015-colatie-icu.md) | Colația: `ro-x-icu`, aleasă la crearea bazei | Acceptat | 2026-08-24 | OD-39 |
| [016](016-limba-contabilitatii.md) | Limba contabilității: cerință legală, nu preferință | Acceptat | 2026-08-24 | OD-13, OD-38 |
| [017](017-terminologie.md) | Terminologia: două straturi independente | Acceptat | 2026-08-24 | — *(deschide OD-42)* |
| [018](018-engagementuri-multiple.md) | Un tenant poate avea engagementuri cu mai multe firme | Acceptat | 2026-08-25 | DN-06 |
| [019](019-vocabular-scope.md) | Vocabularul de `module_key` și de drepturi în scope | Acceptat | 2026-08-25 | DN-07 |
| [020](020-roluri-ca-date.md) | Rolurile sunt date compozabile, peste un catalog fix de permisiuni | Acceptat | 2026-08-25 | DN-08 |
| [021](021-mfa-obligatoriu.md) | MFA obligatoriu pentru toți utilizatorii | Acceptat | 2026-08-25 | DN-09 |
| [022](022-numerotare-sabloane.md) | Numerotarea: șabloane configurabile per companie | Acceptat | 2026-08-25 | OD-02 |
| [023](023-ci-github-actions.md) | CI pe GitHub Actions, cu Postgres ca serviciu | Acceptat | 2026-08-25 | OD-16 |
| [024](024-gardian-de-dependente.md) | Contractele de dependență, impuse printr-un gardian propriu | Acceptat | 2026-08-25 | OD-17 |
| [025](025-subdomeniu-in-dezvoltare.md) | Subdomeniul tenantului în dezvoltare locală: `*.evidenta.localhost` | Acceptat | 2026-08-25 | OD-20 |
| [026](026-autentificare-inainte-de-context.md) | Autentificarea precede contextul, deci trece prin căi privilegiate înguste | Acceptat | 2026-08-25 | — *(deschide OD-48)* |
| [027](027-fiscal-ca-strat-de-schema.md) | `fiscal` intră în lista straturilor de compunere de schemă | Acceptat | 2026-08-25 | — |
| [028](028-modelat-in-f0.md) | Ce înseamnă „modelat în F0”; nu se creează app-uri pentru faze viitoare | Acceptat | 2026-08-25 | OD-11 |
| [029](029-dimensiuni-analitice.md) | Dimensiuni: listă închisă plus cinci sloturi generice per companie | Acceptat | 2026-08-25 | DNB-02 |
| [030](030-atasamente.md) | Atașamentele stau la nivel de companie, nu de tenant | Acceptat | 2026-08-25 | DN-16 |
| [031](031-stack-frontend.md) | Stack frontend minimal: react-query, react-router, fetch, Intl | Acceptat | 2026-08-25 | OD-19 |
| [032](032-cheia-de-partitionare.md) | Cheia de partiționare: desemnată acum, aplicată la prag | Acceptat | 2026-08-25 | OD-01 |
| [033](033-limba-la-generare.md) | Limba la generare: contextul românesc se forțează, nu se moștenește | Acceptat | 2026-08-25 | — *(operaționalizează ADR-016)* |
| [034](034-denumire-legala-si-interna.md) | Nomenclatoarele au denumire legală și denumire internă | Acceptat | 2026-08-25 | — *(`OD-40` rămâne deschisă)* |
| [035](035-fara-delegare-tranzitiva.md) | Delegarea nu este tranzitivă | Acceptat | 2026-08-25 | — *(deschide `OD-54`)* |
| [036](036-forma-postarii.md) | Forma postării stă în cod; restul configurării stă în date | **Acceptat — 2026-08-29, `C1`–`C5` clasificate de proprietar** — `C1`–`C5` cer SNC citat | 2026-08-25 | `DNB-04` *(la `Acceptat`; deschide `OD-55`)* |
| [037](037-conventii-de-platforma.md) | Convenții de platformă: rotunjire, zecimale, granularitatea postării | Acceptat — 2026-08-29; linia e autoritativă prin structura formularului (act citat); 2 / 4 / `half_up` aprobate | 2026-08-25 | `DNB-08` |
| [038](038-vocabularul-de-evenimente.md) | Nucleul deține vocabularul de `event_type`; handlerul se selectează după dată | Acceptat | 2026-08-25 | `DNB-01` |
| [039](039-valuta-si-perioade.md) | Moneda funcțională MDL, exercițiu cu date explicite, trei date pe linia de jurnal | Acceptat | 2026-08-25 | `DN-04`, `DN-05` |
| [040](040-crearea-tenantului-si-a-companiei.md) | Crearea unui tenant și a unei companii este cale privilegiată (`P-9`) | Acceptat | 2026-08-25 | `OD-53` |
| [043](043-privilegiile-functiilor-rls.md) | Operațiile pe obiectele lui `evidenta_rls` se fac sub rolul lui; `REVOKE` de la non-proprietar e un warning | Acceptat | 2026-08-26 | deschide `OD-64` |
| [042](042-scara-de-densitate.md) | Scara de densitate ca tokeni `--spacing-*`: 40/32/24, implicit `compact` la 32px | Acceptat | 2026-08-26 | `OD-35` |
| [041](041-ziua-ca-argument.md) | Ziua intră ca argument; niciun predicat de acces nu citește ceasul | Acceptat | 2026-08-26 | `OD-63` |
| [044](044-data-de-rezolutie.md) | Regula se rezolvă după data perioadei, niciodată după data calculului | Acceptat | 2026-08-26 | `OD-66` |
| [045](045-sursa-de-adevar-pentru-parametri.md) | Actul de rang legal dă parametrii; regulamentul dă procedura | Acceptat | 2026-08-26 | — (impune `C14`) |
| [046](046-istoricul-increderii-in-sursa.md) | Încrederea în sursă are istoric: o confirmare nu schimbă valoarea, deci nu e o versiune nouă | Acceptat | 2026-08-26 | — (`R1`: declară o excepție) |
| [047](047-stampila-parametrului-la-postare.md) | Calculul își ștampilează baza la postare: parametrul nu-și amintește pe ce s-a calculat | Acceptat | 2026-08-26 | — (închide `OD-68`) |
| [048](048-formula-si-sloturile-tipizate.md) | Formula este unitatea de postare; dimensiunile sunt sloturi tipizate, declarate per cont; antetul poartă trei versiuni | Acceptat — decizie tehnică, nimic contabil | 2026-08-29 | — (deschide `OD-69`) |
| [049](049-rolul-de-date-de-referinta.md) | Datele de referință au un rol de încărcare, o cale și un jurnal; actele au publicări | Acceptat — decizie tehnică | 2026-08-29 | `OD-67`, `OD-65`, `OD-56` |
| [050](050-lantul-de-inchidere-ca-roluri.md) | Conturile lanțului de închidere sunt roluri de cont, nu parametri fiscali; ordinea lanțului | Acceptat — domeniu contabil, proprietar | 2026-08-29 | jumătate din `OD-22` |
| [051](051-chei-de-context-enumerate.md) | Cheile de context ale legării condiționate sunt enumerate în cod; valorile sunt date | Acceptat — proprietar | 2026-08-29 | `OD-55` |
| [052](052-contractul-de-tastatura.md) | Contractul de introducere cu tastatura: nicio operațiune frecventă nu cere mouse-ul | Acceptat — produs, proprietar | 2026-08-29 | `OD-36` |
| [053](053-tinta-de-performanta.md) | Ținta de performanță: modelul de volum dă datele, fișa contului agregă pe document | Acceptat — produs, proprietar; pragurile propuse | 2026-08-29 | `OD-29` |
| [054](054-importul-e-distributie-corpusul-e-intern.md) | Importatorul 1C e instrument de distribuție (F3), nu fundație; F1 se validează pe un corpus intern; lanțul 351 e anual | Acceptat — scop, proprietar; §4 domeniu | 2026-08-29 | — |
| [055](055-precizia-cantitatii-e-a-unitatii.md) | Precizia cantității este a unității de măsură: obligatorie, fără implicit, înghețată la prima cantitate; nu e parametru fiscal | Acceptat — domeniu, proprietar | 2026-08-29 | `OD-70` |
| [056](056-inchiderea-lunii-si-a-exercitiului.md) | Închiderea: luna nu postează nimic, exercițiul postează lanțul într-o înregistrare, în perioada lui deschisă | Acceptat — decizie tehnică | 2026-08-29 | — (deschide `OD-73`) |
| [057](057-diferentele-realizate-la-decontare.md) | Diferențele realizate la decontare: termenul pe antet cu implicitul actului, discriminatorul fără implicit, trei perechi de conturi | Acceptat — decizie tehnică (C4) | 2026-08-30 | — |
| [058](058-repartizarea-costurilor-indirecte.md) | Repartizarea costurilor indirecte: formula actului ca logică versionată, baza ca date deschise, restul la 714 | Acceptat — decizie tehnică (C5) | 2026-08-30 | — |
| [059](059-linia-poarta-data-inregistrarii.md) | Linia poartă data înregistrării, nu una a ei; suma postată are două zecimale, impuse în bază | Acceptat — decizie tehnică | 2026-08-30 | — |
| [060](060-vocabularul-capabilitatilor.md) | Vocabularul capabilităților: listă curatoriată după ce cere inițializare; `payroll` se activează, ieșirile lui declarative nu se dezactivează | Acceptat — decizie tehnică | 2026-08-30 | `DN-10` |
| [061](061-cumulativele-de-salarii.md) | Cumulativele de salarii: vocabularul metodei cumulative, toate valorile pozitive, fereastra anului fiscal | Acceptat — domeniu, proprietar | 2026-08-30 | `OD-04` |
| [062](062-aprobatorul-din-productie.md) | Aprobatorul din producție e o persoană cu MFA, nu un nivel de rol; nivelul de platformă rămâne la `DN-18` | Acceptat — decizie tehnică | 2026-08-30 | `OD-71` (jumătatea „cine semnează") |
| [063](063-coliziunea-se-decide-dupa-cine-garanteaza.md) | Coliziunea se decide după cine garantează cheia; UID-ul SFS e idempotență, nu deduplicare | Acceptat — decizie tehnică | 2026-08-30 | `DNB-11` |
| [064](064-diferenta-explicata-nu-diferenta-zero.md) | Punctul 3 al criteriului de ieșire din F2: diferență explicată, nu diferență zero | Acceptat — scop, proprietar | 2026-08-30 | — |
| [065](065-schema-salarizarii.md) | Schema salarizării: sarcina angajatorului și reținerea din salariat sunt două structuri, nu una parametrizată; detaliul per angajat în registru; două date pe linia de salariu | Acceptat — domeniu, proprietar | 2026-08-30 | `DNB-05`, `OD-81` *(deschide `OD-83`, `OD-84`)* |
| [066](066-rezerva-e-decizie-deschisa.md) | O rezervă cu declanșator este o decizie deschisă și are rând în registru; marcaj auto-declarat plus gardian | Acceptat — decizie de proces | 2026-08-30 | `OD-82` *(deschide `OD-85`)* |
| [067](067-contractul-e-cap-de-serie.md) | Amendament la ADR-065: contractul de muncă e cap de serie, nu stare — orice clauză schimbată cere act adițional; o sarcină adaugă câmpuri, nu entități | Acceptat — domeniu, proprietar | 2026-08-30 | — |
| [068](068-anexa-citita-categoria-e-a-raportului.md) | Amendament la ADR-065: anexa citită mută categoria CAS de pe companie pe raportul de muncă; cota împărţită de la pct. 1.5; art. 22 ca invariant | Acceptat — domeniu, proprietar | 2026-08-30 | — *(restrânge `OD-85`, `OD-81`; deschide `OD-91`)* |
| [069](069-persoana-asigurata-nu-e-angajatul.md) | Populația declarației nominale nu e mulțimea angajaților; invariantul art. 22 e al raportului de muncă, nu al oricărei baze CAS | Acceptat — domeniu, proprietar | 2026-08-30 | — |
| [070](070-trei-feluri-nu-o-familie.md) | Trei feluri, nu o familie: operand lipsă → coloană obligatorie, întrebare nepusă → reconciliere, comparaţie nefăcută → `OD-86`. Plafonul: structura mută decizia din tăcere într-un diff, nu o ia | Acceptat — proces, proprietar | 2026-08-30 | — *(restrânge `OD-86`)* |
| [071](071-tipurile-de-raport-ca-tabela.md) | Tipurile de raport de muncă sunt tabelă de referință globală; domeniul invariantului e cheie străină spre ea, cu exact trei valori și fără valoare-coș | Acceptat — domeniu, proprietar; a treia valoare adăugată la acceptare | 2026-08-30 | `C1(b)` |
| [072](072-exceptia-care-nu-largeste.md) | `R1` cere confirmarea proprietarului doar pentru excepțiile care lărgesc accesul la date; catalogul global doar-citire, însămânțat din migrare, e commit obișnuit | Acceptat — proces, proprietar | 2026-08-30 | blocajul repetat al lui `C1(b)` |

| [073](073-forma-postarii-documentelor-comerciale.md) | Forma postării pentru documentele comerciale: patru familii, discriminatorii ceruți și nu deduși, destinația alege rolul; mărfurile refuzate până la stocuri | Acceptat — domeniu, proprietar; §9 enumeră fiecare implicit | 2026-08-31 | `F2.A0` |
| [074](074-sistemul-de-design-evidenta.md) | Identitatea vizuală și stratul de componente: sistemul de design Evidenta | Acceptat — produs, proprietar | 2026-08-31 | golul din ADR-009 *(revizuiește scara din ADR-042)* |
| [075](075-identitatea-titularului.md) | Identitatea fiscală a titularului contului; compania proprie se propune, nu se impune | Acceptat — produs, proprietar | 2026-08-31 | „care companie e titularul" *(deschide `OD-107`, `OD-108`)* |
| [076](076-planul-de-control-al-platformei.md) | Planul de control: platforma se administrează pe sine, nu datele clienților; `platform_staff`, gazda `admin.` | Acceptat — produs și tehnic, proprietar | 2026-08-31 | — *(deschide `OD-113`, `OD-114`; precondiție pentru ADR-077)* |
| [077](077-grantul-de-suport.md) | Grantul de suport: cererea e privilegiată, aprobarea e obișnuită, expirarea e în predicat; doar citire | Acceptat — produs și tehnic, proprietar | 2026-08-31 | `DN-18` *(deschide `OD-115`)* |
| [078](078-cine-poate-crea-un-tenant.md) | Cine poate crea un tenant: două canale — autoservire și firmă; invitația e o poartă de lansare, nu un canal | Acceptat — produs, proprietar | 2026-08-31 | `DN-26` *(restrânge `OD-108`; deschide `OD-116`)* |
| [079](079-tenantul-nerevendicat.md) | Tenantul nerevendicat: statutul `unclaimed`, fereastra provizorie în predicat, re-invitarea rămâne a firmei | **Înlocuit de ADR-081** — acceptat și retras în aceeași zi; întrebarea presupunea răspunsul | 2026-08-31 | — *(închiderea lui `DN-27` retrasă)* |
| [080](080-tipul-nu-se-stocheaza.md) | Tipul de cont nu se stochează: se descompune într-o capabilitate și un rând de firmă; poarta de verificare stă pe acțiune, nu pe cont | Acceptat — produs, proprietar | 2026-08-31 | „se poate transforma un tenant în holding sau firmă"; jumătatea din `DN-26` *(deschide `OD-119`)* |
| [081](081-revendicarea-optionala.md) | Revendicarea e opțională, calea de revendicare (`P-11`) nu; mandatul declarat, plătitorul ca fapt cu dată | Acceptat — produs și tehnic, proprietar; **înlocuiește ADR-079** | 2026-08-31 | `DN-27` *(restrânge `DN-03`, `DN-25`; deschide `OD-118`)* |
| [082](082-unitatea-facturabila.md) | Unitatea facturabilă e compania, nu tenantul; grila e date versionate, vocabularul de componente e cod; cantitatea se derivă și se ștampilează | Acceptat — produs, proprietar | 2026-08-31 | compunerea prețului la mai multe companii *(deschide `OD-120`)* |
| [083](083-editarea-companiei.md) | Editarea companiei: două chei, la nivel de companie, și prima impunere reală | Acceptat — produs, proprietar | 2026-08-31 | — *(deschide `OD-121`, `OD-122`; nu închide `OD-108`)* |
| [084](084-rolul-la-provizionare.md) | Rolul scris la provizionare e de nivel companie, altfel nicio cheie de companie nu se poate ține | Acceptat — proprietar, pe recomandarea sesiunii | 2026-08-31 | `OD-124` |
| [085](085-spatiul-apartine-unui-utilizator.md) | Spațiul de lucru aparține unui utilizator, nu unei companii; „compania titularului" e adevărată doar pentru un holding | Acceptat — produs, proprietar | 2026-08-31 | „cum se înregistrează antreprenorul cu mai multe companii" *(restrânge ADR-075; corectează ADR-081 §3.4; deschide `OD-125`)* |
| [086](086-facturarea-pe-companie.md) | Câte o factură pe companie; firma de contabilitate primește una singură, pentru companiile pe care le plătește | Acceptat — produs, proprietar | 2026-08-31 | `OD-107`, partea de destinatar |
| [087](087-decontarea-e-o-alocare.md) | Decontarea e o alocare, nu o postare; un singur modul cu coloană de parte; evenimentul aparține diferenței | Acceptat — tehnic; latura contabilă rămâne | 2026-08-31 | plasarea din `F2.A3` *(deschide `OD-127`, `OD-128`)* |
| [088](088-statutul-fiscal-e-datat-si-stampilat.md) | Statutul fiscal e datat, iar evenimentul poartă ștampila lui — calculată în `emit()`, nu cerută apelantului | Acceptat — proprietar | 2026-08-31 | restrânge `OD-83` *(deschide `OD-130`)* |
| [089](089-tva-pe-documentele-comerciale.md) | TVA pe documentele comerciale: o formulă pe cotă contra 5344 / 2252, cota din nomenclator, statutul decide în amonte; `OD-130` rămâne deschisă | Acceptat — tehnic, varianta reversibilă | 2026-09-02 | prima jumătate a `F2.A6`; rezerva G din ADR-073 §9 *(deschide `OD-131`)* |
| [090](090-registrele-tva-pe-perioada-fiscala.md) | Registrele TVA se citesc pe perioada fiscală și sunt egale cu registrul contabil; perioada cere înregistrare; scriitorul CSV coboară în nucleul documentelor | Acceptat — tehnic, varianta reversibilă | 2026-09-02 | partea structurală a registrelor din `F2.A6` *(deschide `OD-132`)* |
| [091](091-consola-scrie-referinta-din-procesul-web.md) | Consola scrie datele de referință din procesul web, pe conexiunea rolului de referință, cu apelantul verificat în `platform_staff` | Acceptat — tehnic | 2026-09-02 | — *(deschide `OD-133`)* |
| [092](092-consola-citeste-metadate-si-administreaza-personalul.md) | Consola citește metadatele platformei prin funcții enumerate (`rls.console_*`) și își administrează personalul prin `P-12` | Acceptat — tehnic | 2026-09-03 | OD-133 *(deschide `OD-134`)* |

*Indexul se actualizează la fiecare ADR nou. Un ADR care nu apare aici este invizibil.*

*A treia oară în aceeași zi: `083` și `084`, scrise de o sesiune paralelă, lipseau din tabel la
2026-08-31 seara, la fel cum lipsiseră `074` și `075` dimineața. Trei recurențe în douăsprezece ore
nu mai sunt neglijență, sunt un fișier fără gardian — de aici `OD-126`. Nota inițială, păstrată:*

*`074` și `075` lipseau din tabel până la 2026-08-31 — scrise în aceeași zi ca ADR-urile care le-au
descoperit, într-o sesiune paralelă. Aceeași formă ca ciocnirile de numerotare de mai jos: indexul
nu e păzit de nimic automat, deci absența dintr-un tabel nu produce niciun semnal.*

[ADR-010](010-contabilul-practicant.md) închide `OD-32`: rolul de contabil practicant este acoperit
de proprietarul proiectului. **ADR-007 și ADR-008 sunt deci deblocate** — trec în `Acceptat` la
confirmarea lui, nu automat prin acest fișier.

Numărul de ADR-uri în `Propus` **nu mai este** măsura riscului contabil; cu rolurile colapsate, a
doua semnătură nu mai este verificare independentă. Măsura devine acoperirea corpusului de regresie
fiscală — vezi `ADR-010`.
