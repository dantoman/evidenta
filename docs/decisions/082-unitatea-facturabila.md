# ADR-082 — Unitatea facturabilă e compania, nu tenantul; cantitatea se derivă și se ștampilează

- **Stare:** Acceptat — produs, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Închide:** cum se compune prețul când un tenant are mai multe companii
- **Deschide:** `OD-120`
- **Atinge:** `plan`, `subscription`, Spec A §10.1–10.4
- **Legate:** [ADR-047](047-stampila-parametrului-la-postare.md),
  [ADR-060](060-vocabularul-capabilitatilor.md), [ADR-080](080-tipul-nu-se-stocheaza.md),
  [ADR-081](081-revendicarea-optionala.md)

## 1. Ce a impus decizia

O firmă de contabilitate poate crea un tenant cu mai multe companii — un grup, pentru un client de-al
ei. Fiecare companie în plus costă, **indiferent cine plătește**: tenantul sau firma.

Din propoziția asta rezultă că prețul nu poate fi o proprietate a tenantului. Azi `subscription` are
`plan_code` și `price_amount` și nicio cantitate — adică un tenant cu o companie și un tenant cu opt
plătesc la fel, deși costul real al platformei e per companie: fiecare are ledger propriu, închideri
proprii, declarații proprii, perioade proprii.

## 2. Opțiuni evaluate

1. **Preț fix pe tenant.** *Avantaje:* cel mai simplu de explicat și de implementat; `subscription`
   rămâne cum e. *Dezavantaje:* factura nu urmărește costul, iar grupul cu opt companii e exact
   segmentul care consumă cel mai mult și plătește cel mai puțin per unitate. *Cost de schimbare:*
   mare — schimbarea de la un preț fix la unul pe cantitate se face pe abonamente vii, adică pe
   clienți care au semnat altceva.
2. **Preț pe companie, peste o bază de plan.** *Avantaje:* factura urmărește costul; se aplică identic
   pe ambele canale de facturare; nu cere nicio noțiune nouă în afara unei cantități.
   *Dezavantaje:* cantitatea trebuie să fie reconstituibilă pentru orice perioadă facturată, ceea ce
   `company.status` singur nu poate (§4). *Cost de schimbare:* mic.
3. **Preț pe utilizator.** *Avantaje:* modelul dominant în SaaS. *Dezavantaje:* **facturează exact
   invers față de cost** în piața asta: un contabil, șaizeci de companii. Firma cu un singur om ar
   plăti cât un client cu o companie și zece angajați. *Cost de schimbare:* —

## 3. Decizia

**Opțiunea 2.** Prețul unui abonament se compune din componente: baza planului, plus cantitatea de
companii facturabile din perioadă înmulțită cu prețul unitar.

### 3.1 Grila e date, și se schimbă fără deployment

Cerința proprietarului: *modelul prețurilor stă la nivel de date, care se pot modifica oricând.* Deci
componentele **nu** sunt două coloane pe `plan`.

`plan_price_component`, tabelă globală, versionată ca toate datele de referință din acest sistem:

| Câmp | Note |
|---|---|
| `plan_code` | planul căruia i se aplică |
| `component_key` | din vocabularul închis de mai jos |
| `unit_price`, `currency` | prețul unitar |
| `valid_from`, `valid_to` | grila se schimbă; abonamentele existente trebuie să știe ce grilă li s-a aplicat (Spec A §10.2) |

Se scrie pe calea datelor de referință, sub rolul ei, cu rând în `privileged_access_log`
([ADR-049](049-rolul-de-date-de-referinta.md)) — o grilă schimbată pe conexiunea aplicației e o
schimbare de preț fără autor.

### 3.2 Ce e date și ce e cod — aceeași linie ca peste tot

Împărțirea nu e nouă, e `R15` / `R16` aplicat facturării: **valorile sunt date, vocabularul e cod.**

- **Date, schimbabile oricând, fără deployment:** prețurile, planurile, componentele active pe fiecare
  plan, marginile lor de valabilitate, diferența de grilă wholesale, ce plan propune ce capabilități.
- **Cod, schimbat printr-o migrare, deliberat:** `component_key` — vocabular curatoriat, cu `CHECK`,
  pornind de la `base` și `company`.

Motivul pentru care vocabularul nu e liber e același ca la `capability_key` în
[ADR-060](060-vocabularul-capabilitatilor.md): **fiecare componentă are nevoie de un numărător.**
`company` se numără; `user`, `document` sau `declaration` s-ar număra doar dacă cineva scrie ce se
numără și pe ce interval. O componentă scrisă liber într-un rând ar produce o linie de factură care
nu poate fi calculată — sau, mai rău, care se calculează ca zero și nu spune nimănui.

Deci: **orice preț se schimbă cu un `INSERT`. Un fel nou de a măsura cere cod, fiindcă e cod.**

**Nu se schimbă nimic în raport cu cine plătește.** Canalul (`direct` sau `wholesale`) și plătitorul
sunt o atribuire cu dată, decisă în [ADR-081](081-revendicarea-optionala.md) §5. Prețul se compune la
fel pe ambele; ce diferă sunt rândurile de grilă, nu formula.

## 4. Cantitatea se derivă, apoi se ștampilează

Cantitatea **nu** se ține într-un contor pe `subscription`. Un contor incrementat de serviciul care
creează companii divergează de tabela pe care o numără la prima creare care eșuează după commit-ul
contorului, și nimic nu semnalează divergența.

Se derivă la facturare, din companiile tenantului. Dar derivarea singură nu e suficientă, și motivul
e deja scris în acest repo, la trei rânduri distanță: `CompanyVatRegistration` există fiindcă
*„o companie se înregistrează și poate fi radiată în cursul anului; recalcularea unei perioade
trecute trebuie să folosească starea validă atunci (`R18`) — ceea ce un boolean nu poate exprima."*
`company.status` e exact acel boolean cu trei valori: `active`, `suspended`, `closed`, fără interval.
O companie închisă în martie nu mai poate fi numărată pentru februarie.

**Deci: se derivă la emitere și se ștampilează pe factură** — lista companiilor facturate, cu prețul
unitar aplicat. Este forma din [ADR-047](047-stampila-parametrului-la-postare.md): *calculul își
ștampilează baza la postare; parametrul nu-și amintește pe ce s-a calculat.* O perioadă trecută se
citește din ștampilă, niciodată re-derivată.

Consecința utilă: `company.status` nu are nevoie de istoric datat pentru facturare. Dacă îi va trebui
unul din alt motiv, acela va fi propriul lui ADR.

## 5. Cine poate mări factura altcuiva

Adăugarea unei companii e, în tabelul din [ADR-081](081-revendicarea-optionala.md) §3.2, muncă de
contabil — permisă fără revendicare. Dar **mărește factura plătitorului**, iar plătitorul poate fi
cealaltă parte.

Regula, aceeași simetrie ca la mutarea plătitorului:

> **Cine adaugă o companie și nu e plătitorul, cere confirmarea plătitorului.**

Pe cazul normal — firma plătește și firma adaugă — actorul *este* plătitorul, deci nu există nicio
fricțiune. Fricțiunea apare exact acolo unde trebuie: clientul care adaugă a patra companie pe un cont
plătit de firmă, sau firma care adaugă pe un cont plătit de client. Nimeni nu aruncă o obligație de
plată în curtea altcuiva.

Confirmarea se cere **înainte** de creare, cu suma arătată. O companie creată și apoi refuzată la
plată ar fi o companie cu ledger care trebuie desființată, iar ștergerea fizică nu există în această
specificație.

## 6. Relația cu `multi_company`

Capabilitatea **permite**; prețul **măsoară**. Sunt două lucruri, și rămân două:
`CapabilityActivation` n-are cheie străină către plan (Spec A §10.1), iar `multi_company` e o cheie
din vocabularul curatoriat ([ADR-060](060-vocabularul-capabilitatilor.md) §3), nu o linie de factură.

Pe ecran, a doua companie face amândouă lucrurile într-un singur pas — activarea și efectul comercial,
arătate împreună înainte de confirmare ([ADR-080](080-tipul-nu-se-stocheaza.md) §3). În schemă rămân
separate, fiindcă se schimbă independent: grila se rescrie fără să atingă activările, iar o activare
se poate face din migrare fără să emită o factură.

## 7. Consecințe

- **Devine posibil:** o firmă care aduce un grup de opt companii plătește proporțional, pe oricare
  canal; o factură din 2027 se poate explica linie cu linie în 2031, din ștampila ei.
- **Devine imposibil:** un contor de companii care divergează de tabela de companii; o factură
  retroactivă recalculată din starea de azi.
- **De modificat ca urmare:** `plan_price_component` (globală, versionată, scrisă prin calea datelor
  de referință); linia de factură poartă componenta, compania și prețul unitar aplicat; Spec A §10.2
  primește componentele, §10.3 notează că prețul măsoară iar capabilitatea permite.
- **Ce se verifică automat:** (a) o companie închisă după emiterea facturii nu schimbă factura emisă;
  (b) adăugarea unei companii de către o parte care nu e plătitorul e refuzată fără confirmare, cu cod
  stabil (`C10`); (c) suma facturată e egală cu suma liniilor ștampilate — verificare aritmetică, nu
  de intenție; (d) un `component_key` din afara vocabularului e refuzat de `CHECK`, nu de serviciu.

## 8. Ce rămâne deschis

**`OD-120` — cifrele grilei și regula de proporționalitate.** Baza per plan, prețul per companie,
diferența wholesale: sunt rânduri de date și se scriu când proprietarul le decide — nu blochează
construcția. Ce **nu** e date și de aceea stă aici: dacă o companie adăugată la jumătatea lunii se
facturează proporțional sau integral. Proporționalitatea e o regulă de calcul, deci cod (`R16`), și
schimbarea ei retroactivă ar schimba facturi emise. **Emiterea** facturii rămâne `OD-107`
(vendorul e rezident RM, deci factura intră ea însăși în e-Factura, cu TVA și serie) — acest ADR
spune **ce** se facturează, nu **cum** se emite.

## Surse

- Spec A §10.1 (capability set ≠ plan comercial), §10.2 (`plan`, `subscription`), §10.3, §10.4
  (wholesale).
- [ADR-047](047-stampila-parametrului-la-postare.md) (ștampila la postare, forma reutilizată aici),
  [ADR-060](060-vocabularul-capabilitatilor.md) §3, [ADR-080](080-tipul-nu-se-stocheaza.md) §3,
  [ADR-081](081-revendicarea-optionala.md) §5.
- Măsurat în cod la 2026-08-31: `platform/tenancy/models.py` — `CompanyStatus` are trei valori și
  niciun interval; `CompanyVatRegistration` poartă motivul pentru care o stare fără dată nu răspunde
  despre trecut.
- [ADR-049](049-rolul-de-date-de-referinta.md) (calea de scriere a datelor de referință).
- `CLAUDE.md` `R15`, `R16`, `R18`, `R25`, `C10`.
- Conversație 2026-08-31.
