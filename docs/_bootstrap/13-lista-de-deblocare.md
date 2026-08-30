# 13 — Lista de deblocare

- **Scris:** 2026-08-30, la instrucțiunea de continuare („scop și metodă, ambele schimbate")
- **Ce este:** tot ce mi-ar putea opri lucrul de aici până la sfârșitul secvenței de unsprezece pași.
  Proprietarul răspunde o singură dată; după aceea nu mă mai opresc.
- **Regula fișierului, fără excepție:** **fiecare intrare poartă implicitul** — varianta reversibilă
  pe care o iau singur dacă nu primesc răspuns. O intrare fără implicit e o intrare incompletă, și
  ar face din listă chiar blocajul pe care îl elimină.

> **Cum se citește coloana „Implicit":** e ce fac **fără să mai întreb**, nu ce recomand. Un răspuns
> care contrazice implicitul e binevenit oricând **până la declanșatorul scris** — după el, schimbarea
> costă o migrare, și atunci coloana spune cât.

> **Ce NU e în listă:** deciziile deja luate (registrul le are), sarcinile (backlogul le are) și
> constatările de meta-nivel (un rând în registru, apoi mai departe). Aici stă numai ce **oprește**.

---

## A. Decizii pe care doar proprietarul le poate lua — cele ireversibile

Criteriul de intrare în această secțiune: **desfacerea costă o migrare de date sau un artefact deja
depus la o instituție.** Restul a plecat în §D sau nu e în fișier.

| # | Decizia | Unde lovește | **Implicit dacă tac** |
|---|---|---|---|
| **A1** | **Compania-pilot.** Punctele 1 și 2 ale criteriului de ieșire din F2 sunt amânate cu acest declanșator. Fără o companie reală, „diferență explicată" (ADR-064) n-are contra ce | criteriul de ieșire F2; pașii 5–11 se validează pe date inventate | Construiesc tot pe **corpusul intern** (F1.10, `tests/corpus/`), extins la salarii și TVA. Nu aștept. Punctele 1–2 rămân nebifate și **spun asta explicit** în PROGRESS, nu tăcut |
| **A2** | **`IDNP`-ul se stochează sau nu.** Codul personal e obligatoriu în IPC și în declarația nominală CNAS; e și cea mai sensibilă coloană din produs. Alternativa (referință la un depozit extern) nu există azi | pasul 1 (persoana), pașii 4 și 10 (declarațiile) | **Se stochează**, în clar, cu acces auditat prin `platform/audit`, ca orice dată personală de angajat. Fără el declarațiile nu se pot construi deloc. **Reversibil doar spre mai strict** (criptare la coloană): o coloană care există poate fi criptată, una care nu există n-are ce cripta |
| **A3** | **Fluturașul e document legal sau ieșire de produs.** `C38` cere context românesc explicit pentru documente legale; dacă fluturașul e unul, nu poate fi tradus niciodată, în nicio limbă | pasul 3 (fluturaș), `C32`/`C33` | **Document legal.** Se generează în română, prin modulul de document cu convenții `ro-MD` fixe. E ireversibil în direcția asta: un fluturaș deja emis în rusă nu se retrage |
| **A4** | **ADR-007 — perioada în care se înregistrează un storno** (`Propus` din F0). Declanșatorul scris: **prima declarație rectificativă**. Pasul 6 (TVA) îl atinge | pasul 6; corecțiile din pașii 5 și 10 | **Rămâne obligatoriu și fără implicit pe API** — cum e azi. Cine corectează alege data; sistemul nu alege în locul lui. Asta **nu** închide ADR-007, o amână corect |
| **A5** | **Salariul individual pe rapoartele de contabilitate generală** (`OD-84`). Cu detaliul per angajat în registru (ADR-065 §8), fișa contului 531 arată cine cât ia | pașii 3 și 5 (fișa contului, Cartea Mare) | **Se vede**, ca orice altă dimensiune de registru. Restricția pe rol se poate adăuga oricând peste; **a nu scrie dimensiunea** e ireversibil, a o ascunde nu |
| **A6** | **Numerotarea statelor de plată și a ordinelor** — serie per companie, per an, sau continuă | pașii 1 și 3 | **Serie per companie și an**, prin `platform/numbering`, ca la restul documentelor. Schimbarea ulterioară e o serie nouă, nu o renumerotare |
| **A7** | **`DN-18` — nivelul de rol de platformă și accesul de suport.** Neatins de ADR-062, care a decis doar „cine semnează activarea unui parametru" | activarea parametrilor în producție; `privileged_access_log` n-are cititor | **Nu construiesc niciun rol de platformă.** Activarea rămâne comandă de operator, cu aprobator persoană reală (ADR-062). Un rol adăugat mai târziu e aditiv |

---

## B. Reguli care blochează și n-ar trebui — cu îngustarea propusă

Fiecare rând de aici m-a oprit **deja** sau ar fi oprit-o previzibil. Propunerea e **îngustarea**, nu
retragerea: regula rămâne acolo unde apără ceva.

| # | Regula, azi | Ce a costat / ar costa | **Îngustarea propusă** | **Implicit dacă tac** |
|---|---|---|---|---|
| **B1** | **`R1`** — orice modificare a lui `infra/rls/exceptions.toml` e ADR | A oprit `C1(b)` **trei sesiuni la rând** pentru un catalog de trei valori, doar-citire, însămânțat din migrare | Confirmarea proprietarului **numai pentru excepțiile care lărgesc accesul la date**. Un catalog global doar-citire, cu `policy_shape = "global_read_only"` și `writer_role` de migrare, e commit obișnuit — `permission` e precedentul din propriul fișier | **Îngustată** — decizia proprietarului e deja dată în instrucțiunea de continuare. ADR-072, și mai departe |
| **B2** | **`R21`** — modificarea lui `infra/schema/append_only.toml` e ADR | Va opri pasul 3: linia de salariu **nu** intră în listă (`OD-87`), dar registrul de formule și liniile de jurnal generate de salarii ating fișierul | **Adăugarea** unei tabele în listă e **restrictivă** — îngustează ce se poate face cu ea — deci commit obișnuit. **Scoaterea** unei tabele rămâne ADR: aceea lărgește | **Aplic aceeași formă ca la `R1`**, cu rând în registru și motivul scris. Adăugarea e reversibilă prin scoatere; nimic nu s-a pierdut între timp |
| **B3** | **`infra/modules/dependencies.toml`** — modificarea e ADR, prin propriul antet | Va opri pasul 1: `operations/payroll` e **modul nou într-un strat existent**, nu direcție nouă în graf | ADR **numai** pentru: strat nou, direcție nouă între straturi, sau interdicție punctuală ridicată. Un modul nou într-un strat declarat nu schimbă graful | **Adaug modulul fără ADR** dacă fișierul nu cere altfel după citire; dacă gardianul cere o intrare, o scriu cu motivul, nu cu un ADR |
| **B4** | **`C14`** — corpusul de regresie rulează la fiecare modificare de parametru, iar gardianul cere ca fiecare `regression_case_set` din fișierele livrate să numească un set **cu cazuri** | Lovește direct regula 1 a metodei noi: *„cota zilierului necunoscută → rândul există, suma e nulă"*. Un rând fără valoare n-are ce caz de regresie să aibă | Cerința se leagă de **activare**, nu de încărcare. Un parametru `draft` fără valoare stabilită **nu** cere set de cazuri; unul care trece în `active` îl cere | **Încarc rândurile fără valoare ca `draft`**, cu `provisional_reason` scris, și **nu** le dau `regression_case_set` fictiv. Dacă gardianul cade, **el se îngustează** — nu inventez un set gol ca să tacă |
| **B5** | **ADR-002** — *„nu se închide tacit o decizie deschisă; dacă o sarcină cere una, se oprește și se întreabă"* | Sub metoda nouă („reversibil implicit"), fiecare alegere reversibilă ar produce o oprire | Oprirea e pentru **ireversibile** (§A). Pentru restul: alegi varianta reversibilă, scrii rândul în registru cu declanșatorul care ar redeschide-o, continui | **Aplic metoda nouă.** Registrul primește rândul; sarcina nu se oprește |
| **B6** | **ADR-066** — o rezervă cu declanșator e decizie deschisă și **cere** rând în registru plus marcaj | Rândurile de registru devin cost per ADR; sub „structura există, valorile intră ca date" fiecare al doilea ADR are o rezervă | Rândul e obligatoriu **numai când rezerva blochează ceva scriibil azi**. O rezervă care nu blochează stă în ADR-ul ei, cu marcaj `NEATINSĂ` | **Păstrez regula ca azi.** E ieftină și a prins ceva real. Dacă produce zgomot pe trei ADR-uri la rând, o îngustez și scriu de ce |
| **B7** | **`CLAUDE.md` §4** — *„nu se scriu module din F2+ înainte de criteriul de ieșire din faza curentă"* | Nu mai blochează: F1 a ieșit, F2 e pornită prin declarația proprietarului | — | **Consider F2 pornită** și nu mai verific §4 la fiecare modul |
| **B8** | **`C37`** — termenii de model nu apar în interfață, verificat prin grep peste fișierele de resurse | Pasul 1 aduce `employee`, `contract`, `amendment`, `order` — dintre care **niciunul** nu e în harta ADR-017 | Harta se extinde cu termenii de salarizare **în același commit** cu ecranul, nu prin ADR separat | **Extind harta** cu perechile model → interfață pentru salarizare, în ADR-017, la primul ecran. Fără ADR nou |

---

## C. Surse neobținute — ce blochează fiecare, și dacă rândul gol ajunge

Coloana care contează e ultima: **„rândul gol cu motiv e suficient?"**. Unde e *da*, sursa nu mă
oprește niciodată — oprește doar o bifă.

| # | Sursa | Blochează | Rândul gol ajunge? | **Implicit dacă tac** |
|---|---|---|---|---|
| **C1** | **Cuantumul taxei fixe a zilierului** (anexa nr. 1 pct. 1.9). **Lacună constatată în act**, nu sursă neobținută: legea BASS nu-l numește, L22/2018 n-are cuantum | pasul 8 (zilieri) | **Da** | Rândul de parametru există, `value` nul, `provisional_reason` = enumerarea celor trei surse verificate. Calculul **refuză** cu cod stabil, nu presupune zero |
| **C2** | **Catalogul HG 941/2020** — duratele de funcționare utilă | pasul 9 (amortizare fiscală) | **Da** | Registrul de active și amortizarea contabilă merg întregi; durata fiscală e coloană nulă cu motiv. Amortizarea fiscală **nu se calculează**, nu se aproximează |
| **C3** | **Anexa nr. 4¹ la IRM19** (validările) și **clasificatorul funcțiilor** (col. 11) | pasul 1 — **numai depunerea**, nu construcția | **Da** | Câmpurile există și se completează; validarea la depunere rămâne nebifată. Funcția se ține ca text liber până la clasificator, cu coloana pregătită pentru cod |
| **C4** | **Structura declarației IPC** (boxele adoptate) | pasul 4 | **Parțial** — structura raportului nu se poate inventa | Construiesc **registrul de sume raportabile** (per persoană, per tip, per lună) — el e ce cere calculul. Randarea în formular se face când textul e citit; până atunci, export tabelar |
| **C5** | **Structura declarației TVA** (boxele) — identitățile MO obținute, textele nu (`F2.X2 (c)`) | pasul 6 | **Parțial**, ca C4 | Registrele de vânzări și cumpărări întregi, cu toate sumele pe care declarația le cere; formularul, când textul e citit |
| **C6** | **Numerele MO pentru parametrii încărcați** (`OD-22`) și **marginile `valid_from`** (`OD-92`) | activarea oricărui parametru | **Da** — e chiar forma impusă de `C1(a)` | Parametrii stau `draft`/`provisional`, cu observația în `observed_in` și marginea NULL. Calculul pe ei **spune** că e provizoriu |
| **C7** | **Canalele instituționale**: SFS (`OD-24`, `OD-75`), CNAS/CNAM/BNS (`OD-25`), BNM (`OD-26`), băncile (`OD-27`) | depunerea (pașii 4, 6, 10), cursul (pasul 5), extrasele | **Da** | Toate ieșirile se generează **ca fișier**, verificabil. Depunerea automată e strat peste, adăugat când canalul există. Cursul se introduce manual până la BNM |
| **C8** | **HG 764/1992** (registrul de casă) — statut incert, nicio formă în vigoare găsită | pasul 5 (casa) | **Da** | Casa funcționează contabil; **registrul tipărit** al casei nu se generează până la text. Am scris deja că lipsește |
| **C9** | **Legea nr. 287/2017 din publicația proprie** și categoriile de entități | pasul 10 (situații financiare) | **Nu, la sfârșit** — categoria decide ce situații se depun | Construiesc situațiile pentru **o singură categorie** (entitate mijlocie, setul complet) și declar asta. Restul, la text |
| **C10** | **Redacția intermediară a anexei nr. 1** (dovedită prin pct. 1.9, LP318 — vezi ADR-068 §8) | marginile pct. 1.5, 1.8, 1.9 (`OD-85`) | **Da** | Valorile intră cu `observed_in`, fără margine. Nicio margine fabricată — regula e deja impusă în bază |
| **C11** | **Actele indemnizațiilor** (concedii medicale, HG-uri, plafoane) | pasul 7 | **Da** | Structura (cerere, tip, zile, bază de calcul, sumă) există; cotele și plafoanele sunt rânduri nule cu motiv. Calculul refuză, nu inventează |

---

## D. Alegeri de produs care afectează modelul

Astea nu sunt juridice și nu sunt ireversibile — dar fiecare **se scrie în schemă**, deci un răspuns
acum e mai ieftin decât o migrare peste trei săptămâni.

| # | Alegerea | **Implicit dacă tac** | Ce costă schimbarea după |
|---|---|---|---|
| **D1** | **Granularitatea pontajului:** ore pe zi, sau zile lucrate + ore total pe lună | **Ore pe zi.** Zilele se deduc din ore; invers nu. Art. 22 alin. (1) cere proporția timpului lucrat, iar la timp parțial cere raportul la salariul minim — ambele au nevoie de ore | O migrare aditivă dacă se merge de la zile spre ore și trebuie recompletat; nimic dacă invers |
| **D2** | **Clauzele contractului: câmpuri structurate sau text.** Art. 49 alin. (1) enumeră 19 clauze | **Structurate doar cele consumate de calcul** (funcție, salariu, timp de muncă, dată de început, dată de încetare, condiții speciale), restul text pe actul adițional | Aditiv: o clauză care devine structurată se adaugă, cu backfill din text — manual, dar posibil |
| **D3** | **Rularea de salarii: per companie sau per tenant** | **Per companie.** Perioadele contabile, planul de conturi și registrul sunt deja per companie; o rulare per tenant ar traversa companii | Mare. Cheia rulării e în fiecare linie de salariu și în fiecare formulă |
| **D4** | **Scara sumelor de salarii:** 2 zecimale (ca linia de jurnal, ADR-059) sau 4 (ca `amount_scale`) | **2 zecimale pe rezultat, 4 pe intermediar.** Fluturașul și declarația arată bani; proporțiile art. 22 nu se rotunjesc la mijloc | Recalcularea perioadelor deja închise |
| **D5** | **Ce se activează prin capabilitatea `payroll`** (ADR-060): doar calculul, sau și ieșirile declarative | **Calculul se activează; ieșirile declarative nu se dezactivează niciodată** (`R24`, cum spune chiar ADR-060) | Nimic — e deja decis, îl reafirm aici ca să nu fie recitit ca deschis |
| **D6** | **Segmentul-țintă la pasul 1:** câți angajați trebuie să meargă bine | **Până la 50 pe companie.** Modelul de volum e măsurat pe asta (`12-volumul-salarizarii.md`); ecranele se proiectează pentru listă, nu pentru grilă de introducere în masă | Ecranele, nu schema |
| **D7** | **Ecranul de introducere a pontajului:** `EntryGrid` sau formular pe angajat | **`EntryGrid`** — e grilă de introducere repetitivă, exact ce descrie ADR-052. `OD-36` nu blochează: contractul de tastatură e scris | Refacerea unui ecran |
| **D8** | **Livrarea fluturașului:** descărcare, e-mail, sau portal al angajatului | **Descărcare din interfața contabilului.** E-mailul n-are transport (`OD-50`), portalul angajatului e produs nou | Aditiv |
| **D9** | **Persoana e entitate proprie sau e „angajatul".** ADR-069 a arătat că populația asigurată e mai largă decât angajații | **Persoană fizică ca entitate**, cu raporturi (contract de muncă, contract civil, raport de serviciu) ca serii peste ea. Interfața largă de la început — lărgirea unei interogări scrise pe `employee` e rescrierea fiecărui apelant | Foarte mare. E chiar defectul măsurat în ADR-069 |
| **D10** | **Se importă istoric de salarii la punerea în funcțiune** (cumulativele anului, `OD-04` / ADR-061) | **Da, prin soldurile inițiale de salarii** — tabela există deja și are constrângerea de semn. Fără ele, o punere în funcțiune la mijloc de an calculează greșit scutirile | Aditiv, dar o companie pusă în funcțiune fără ele are un an fiscal greșit |

---

## Ce fac mai departe, fără să aștept

1. **§A** — iau implicitul scris, pe fiecare rând, și marchez în PROGRESS care implicit a fost luat.
2. **§B1** e deja decisă de proprietar; **B2**–**B8** le aplic în forma din coloana „Implicit".
3. **§C** — fiecare sursă lipsă devine **un rând cu motiv**, niciodată un blocaj și niciodată o
   valoare inventată.
4. **§D** — implicitul intră în schemă la primul commit care îl atinge, cu rând în registru.

**Un răspuns care contrazice un implicit e binevenit oricând.** Coloana „ce costă schimbarea după"
din §D spune exact cât — ca decizia să se ia pe cifră, nu pe impresie.
