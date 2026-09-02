# ADR-089 — TVA pe documentele comerciale: forma postării, iar statutul decide în amonte

- **Stare:** Acceptat — tehnic (arhitectură delegată), pe **varianta reversibilă** (lista de deblocare
  §B5); **valorile fiscale nu se decid aici** — cotele rămân `draft` (`OD-22`) și calculul refuză cât
  timp nu sunt activate
- **Data:** 2026-09-02
- **Decis de:** sesiunea de implementare (`evidenta-5f`); proprietarul confirmă sau răstoarnă alegerile
  din §6, fiecare cu declanșatorul ei
- **Închide:** prima jumătate a lui `F2.A6` — *TVA pe document ajunge în registru*; rezerva `G` din
  [ADR-073](073-forma-postarii-documentelor-comerciale.md) §9 (*„TVA — fără, un singur tratament
  înregistrat"*), în forma din §2
- **Nu închide, deliberat:** `OD-130` (forma rezolvării pe statut în handlere) — al doilea caz se ia
  aici pe varianta reversibilă, decizia rămâne la al treilea; `OD-22`; proratarea (art. 102 alin. (4));
  registrele și declarația
- **Deschide:** `OD-131`
- **Atinge:** `accounting/posting` (familia `commercial`), `platform/documents` (`vat_breakdown`),
  `fiscal/parameters` (`regime_rate`, prima ușă HTTP a lui `fiscal`), `operations/sales`,
  `operations/purchases`, `platform/tenancy` (înregistrarea în scopuri de TVA), trei ecrane
- **Legate:** [ADR-073](073-forma-postarii-documentelor-comerciale.md),
  [ADR-088](088-statutul-fiscal-e-datat-si-stampilat.md), [ADR-048](048-formula-si-sloturile-tipizate.md)
  (`vat_rate` pe formulă), [ADR-037](037-conventii-de-platforma.md) §3.1, [ADR-044](044-data-de-rezolutie.md),
  [ADR-087](087-decontarea-e-o-alocare.md)

> **REZERVĂ (`OD-83`), purtată mai departe din [ADR-073](073-forma-postarii-documentelor-comerciale.md)
> și [ADR-087](087-decontarea-e-o-alocare.md):** motorul selectează tratamentul doar pe capabilități,
> iar statutul TVA nu e una. **Nu se stinge aici, deși tratamentul cu TVA e livrat:** felia lasă
> statutul să decidă în amonte (§2) și motorul cu un singur tratament per eveniment; forma prin care
> un statut datat ar selecta un tratament rămâne `OD-130`, la al treilea caz. Rezerva iese cu acela.

> **REZERVĂ NEATINSĂ (`OD-85`):** [ADR-044](044-data-de-rezolutie.md) e citat pentru principiul datei
> de rezoluție, nu pentru tarifele anexei nr. 1; nicio valoare din acea rezervă nu apare aici.

> **REZERVĂ (`OD-22`):** nicio cotă nu apare în acest ADR și nici în cod. `vat.standard` și
> `vat.reduced` sunt `draft` pe baza de dezvoltare; o linie cu regim impozabil **refuză** cu
> `fiscal.no_parameter`, numind cheia, până la activarea din act citabil. Rezerva iese cu activarea, nu
> cu acest ADR.

## 1. Ce se decide: forma, cu TVA

Aceleași patru familii ca în ADR-073 §1; ce se adaugă e **o formulă pe cotă** contra contului de TVA,
cu cota și cheia parametrului ștampilate pe formulă (ADR-048), iar creanța sau datoria poartă totalul.

| Eveniment | Formule | Sumă |
|---|---|---|
| `sales.invoice_issued` | `CREANTE_*` / `VENIT_*` | **net** |
| | `CREANTE_*` / `TVA_COLECTATA` (5344), câte una pe cotă | TVA la cota aceea |
| `sales.return_issued` | `RETUR_REDUCERI` / `CREANTE_*` | net |
| | `TVA_COLECTATA` / `CREANTE_*`, câte una pe cotă | TVA la cota aceea |
| `purchases.invoice_recorded`, **deductibil** | rolul de cost / `DATORII_*` | net |
| | `TVA_DEDUCTIBILA` (2252) / `DATORII_*`, câte una pe cotă | TVA la cota aceea |
| `purchases.invoice_recorded`, **nedeductibil** | rolul de cost / `DATORII_*` | **total** |
| `treasury.*` | neschimbate | — |

Conturile nu sunt alegere: 5344 și 2252 sunt în Planul general de conturi și în catalogul de roluri din
ADR-048, nelegate de nimic până azi. **Faptul poartă `net`, `vat`, `total` și `vat_by_rate`**, iar
handlerul verifică trei identități înainte să scrie ceva — `total = net + vat`, cotele însumează `vat`,
netele lor însumează `net` — și refuză, nu repară: un fapt care le încalcă a fost asamblat din două
citiri ale aceluiași document, și a-l posta pe cel care se echilibrează ascunde care.

## 2. Statutul decide în amonte, nu în motor — `OD-130` rămâne deschisă

ADR-073 a refuzat al doilea tratament fiindcă motorul selectează pe capabilități, iar statutul TVA nu
e una. ADR-088 a închis partea portantă — statutul e datat și ștampilat pe eveniment — și a amânat la
al treilea caz **cum ajunge statutul să selecteze un tratament** (`OD-130`). Acesta e al doilea caz, și
se ia **fără să selecteze nimic în motor**:

| Unde | Ce decide statutul | Cum |
|---|---|---|
| stratul documentar, la vânzare | ce poate spune o linie | statutul **la data documentului**: neînregistrat → doar `fara_tva`; înregistrat → un regim din nomenclator, `fara_tva` refuzat |
| emiterea, la vânzare | dacă documentul legal poate purta TVA | același statut, la aceeași dată, verificat din nou la validare — înregistrarea se poate corecta între tastare și emitere |
| `operations/purchases`, la contabilizare | dacă TVA-ul furnizorului e al nostru de dedus | `vat_deductible` pe fapt, citit din statutul **la data contabilă** — discriminator pe tiparul lui `partner_resident` (ADR-073 §2) |
| motor, la contabilizare | că faptul n-a mințit | `vat_deductible` contra ștampilei scrise de `emit()` din aceeași dată (ADR-088); dezacordul e refuz, `purchases.vat_status_mismatch` |

**Handlerul citește sume și booleeni; nu întreabă niciodată cine e compania.** Un singur
`HandlerVersion` per eveniment, ca înainte. De ce e reversibil: dacă `OD-130` decide a doua dimensiune
în `requires` sau un predicat peste ștampilă, câmpul de pe fapt pleacă sau rămâne ca verificare, iar
înregistrările scrise între timp sunt corecte oricum — ștampila e deja acolo, pe fiecare eveniment.

**Nu s-a luat:** un al doilea `HandlerVersion` selectat pe statut — ar fi însemnat să decid `OD-130`
la al doilea caz, exact ce ADR-088 §5 amână, cu o schemă validată de un singur consumator.

## 3. Cota vine din nomenclator, nu din cod — și `fara_tva` nu e regim

`vat.regimes` (parametru `table`, `draft`) primește `rates`: **regim → cheia parametrului de cotă**
(`taxable_standard` → `vat.standard`). Codul știe doar că un regim absent din `rates` nu poartă cotă;
nicio valoare nu apare în repository. `fiscal.regime_rate(code, on)` rezolvă în doi pași — regimul din
tabel, cota din cheia lui, ambele la data faptului (ADR-044) — și refuză regimul necunoscut
(`fiscal.vat_regime_unknown`) sau cota inactivă (`fiscal.no_parameter`), **numind cheia**. Un refuz
care numește ce lipsește e diferența dintre „produsul nu face TVA" și „cota nu e activată din act".

**Ordinea verificărilor e statutul, apoi nomenclatorul** — și e deliberată: `write_lines` citește
întâi statutul companiei la data documentului și abia pentru o companie care *poate* spune un regim
cere nomenclatorului cota. Invers, un neplătitor cu parametrii `draft` ar primi
`fiscal.no_parameter` — o propoziție corectă despre lucrul greșit. *(Măsurat de sesiunea paralelă pe
seeder, 02.09: apelul direct al lui `service_line` sărea peste statut și refuza pe nomenclator;
seeder-ul trece acum prin `write_lines`, ușa ecranului.)*

`fara_tva` **nu e în nomenclator**: e statutul emitentului — *nu sunt plătitor la data asta* —, nu un
tratament al livrării. De aceea o companie înregistrată nu-l poate folosi (`sales.vat_regime_required`),
iar la achiziții e admisibil oricând: furnizorul neplătitor emite fără TVA, indiferent de statutul
nostru.

**Prima ușă HTTP a lui `fiscal`:** `GET /api/v1/fiscal/vat/regimes?on=` — codurile, cheia și cota
fiecăruia, sau `unavailable` cu codul fiscal când cota nu se rezolvă. Ecranul nu ține nomenclatorul;
îl cere pentru data documentului. Doar citire: valorile intră prin încărcătorul privilegiat (ADR-049).

## 4. Calculul: pe linie, o singură implementare

`line_amounts` — regula decisă de proprietar și scrisă la ADR-037 §3.1: **TVA se calculează și se
rotunjește pe fiecare linie, pe netul rotunjit; totalul documentului e suma liniilor** — se apelează
pentru **toate** regimurile, cu cota zero pentru `fara_tva`, ca să existe o singură aritmetică și nu
una pe regim. Măsurat în test: trei linii de 33,33 la 20% dau 20,01; pe baza totală ar da 20,00.

`platform.documents.vat_breakdown` adună liniile pe `(regim, cheie, cotă)`; faptul le împăturește pe
`(cheie, cotă)` — registrului îi pasă de regim, registrului contabil de cotă — și fiecare parte devine
o formulă cu `vat_rate` și `vat_rate_key` (ADR-048, `R18`): fișa lui 5344 se citește pe cote fără să
se întoarcă la documente.

## 5. Înregistrarea în scopuri de TVA are o ușă

`company_vat_registration` exista din F0 și era scrisă doar de teste și de mână: statut datat, fără
ușă, deci nicio companie creată prin produs n-a putut fi vreodată plătitor. Acum:
`tenancy.services.vat_registration.register_for_vat` (suprapunerea refuzată — două înregistrări peste o
zi ar da două răspunsuri la o întrebare; cheia `company.edit`, per companie, ca la fișă — ADR-083),
`POST/GET /api/v1/companies/<id>/vat-registrations`, `GET .../tax-status?on=` (ziua e obligatorie,
ADR-044), și zona *Înregistrarea în scopuri de TVA* pe fișa companiei: istoric, nu bifă.

**Radierea nu se face de aici, și nu e scăpare:** art. 114 alin. (2) face perioada fiscală finală din
două date, iar aceea stă în `accounting/periods`, pe care `platform` nu-l importă. Data de sfârșit se
poate înregistra; perioada finală e al doilea apel, neconstruit în felia asta — ca la companie și
exercițiu.

## 6. Ce a fost alegere, enumerat — fiecare cu declanșatorul care o redeschide

| # | Alegerea | Ce s-a luat | Ce ar răsturna-o |
|---|---|---|---|
| **A** | data la care se citește dreptul de deducere | **data contabilă** — ziua în care intră în registru și ziua ștampilei (ADR-088), ca motorul să poată confrunta cele două | textul art. 102 citit, dacă leagă deducerea de altă zi (primirea facturii, plata) → `OD-131` |
| **B** | TVA nedeductibilă la cumpărătorul neînregistrat | **în cost, o formulă pe total, fără cotă** — SNC „Stocuri" pct. 15 spune *cuprinde* impozitele nerecuperabile pentru stocuri (`c1-c3-c5-stocuri.md`); pentru servicii e **inferență prin analogie**, marcată | un text care cere prezentarea separată a TVA-ului nerecuperabil → `OD-131` |
| **C** | compania înregistrată **spune un regim** pe fiecare linie; `fara_tva` refuzat | ales: `fara_tva` e statut, nu tratament | o livrare în afara sferei (art. 95 alin. (2)) primește cod propriu în `vat.regimes`, cu articolul citit |
| **D** | data statutului la vânzare | **data documentului** — factura e documentul legal, ce poate purta se decide după ziua pe care o poartă | textul art. 108/117 citit, dacă spune altfel |
| **E** | unde stă legarea regim → cheie de cotă | **date**, în `vat.regimes.rates` | — nimic anticipat; o cotă nouă e un rând, nu un deploy |
| **F** | a doua dimensiune de selecție în motor | **nu** — discriminator pe fapt + verificare contra ștampilei | `OD-130`, la al treilea caz |
| **G** | regim implicit pe ecran | **niciunul** — nici standardul; e răspunsul obișnuit și tot un răspuns pe care îl dă cineva | — |
| **H** | perioadele TVA la înregistrare | **nu se deschid aici** — n-au consumator până la registre | felia următoare (registrele pe `VatPeriod`) |

## 7. Ce **nu** se decide aici

- `OD-130` — forma rezolvării pe statut în handlere. Al treilea caz decide.
- Proratarea (art. 102 alin. (4)), dreptul de deducere al scutirilor (art. 103 contra art. 104) —
  `vat.regimes` le distinge ca vocabular, nimic nu le consumă încă.
- Registrele de livrări și procurări pe `VatPeriod`, declarația (Ordinul IFPS 1164/2012, text necitit —
  `F2.X2 (c)`), termenul (parametru, `draft`).
- `OD-128` — ajustarea bazei la contractul în valută; intră pe ușa decontării.
- Sfera cotei reduse — nu e parametru scalar, nu e aici.

## 8. Consecințe

- **Devine posibil:** o companie înregistrată emite facturi cu TVA și le contabilizează pe 5344; o
  factură primită cu TVA ajunge pe 2252 sau în cost, după statut; jurnalul documentelor are coloana de
  TVA nenulă și egală cu rulajul lui 5344 pe lună (primul punct din criteriul `F2.A6`, măsurat în test).
- **Devine imposibil:** factură cu TVA de la un neplătitor; TVA la o cotă neactivată; un fapt care
  afirmă deducerea pe o zi în care ștampila spune altceva.
- **De modificat ca urmare:** `commercial.py` (fapte, handlere, roluri cerute), `documents/services/
  lines.py`, `fiscal/parameters/services/vat.py` + `views.py` + `urls.py`, `operations/{sales,purchases}/
  services/lines.py` (semnătura lui `service_line` primește `vat_regime_code`; `write_lines` e ușa
  ecranului), `issuing.py`, `recording.py`, `tenancy/services/vat_registration.py`, `tva.toml`
  (`rates`), trei ecrane, `ro.ts`.
- **Măsurat pe baza de dezvoltare, 2026-09-02:** `vat.*` toate `draft`; `accounting.unit_price_scale`
  activ (4); zero înregistrări TVA; 85 de linii `fara_tva` pe trei companii neînregistrate — rămân
  valide sub regula din §3.
- **Seeder-ul** primește a șaptesprezecea situație — vânzare cu `taxable_standard` — ca să fie refuzată
  pe nume: compania nu e înregistrată, iar refuzul spune care ușă deschide asta.

## Surse

- **Planul general de conturi**, Ordinul MF nr. 119 din 06.08.2013 — 5344, 2252 (prin
  `roles_snc_2020.csv`, ADR-048).
- **SNC „Stocuri" pct. 15** — costul de intrare *cuprinde* impozitele și taxele nerecuperabile
  (`_input/cercetare/c1-c3-c5-stocuri.md`); analogia la servicii e a acestui ADR, nu a actului.
- **Codul fiscal, Titlul III** — art. 96 (cotele), art. 102 (deducerea; alin. (4) proratarea), art. 103,
  art. 104, art. 114 alin. (2) — prin reproducerea SFS din `od-22-tva.md` și
  `f2-x2-prorata-tva-si-amortizarea-fiscala.md`; **textul din MO necitit**.
- ADR-037 §3.1, decizia proprietarului privind rotunjirea pe linie (`amounts.py`).
- Măsurat: `backend/tests/isolation/test_vat_on_documents.py`, 15 teste sub rolul aplicației.
