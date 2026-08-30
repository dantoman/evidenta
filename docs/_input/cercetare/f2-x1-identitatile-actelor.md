# `F2.X1` — Identitățile actelor: numărul Monitorului Oficial, data publicării, intrarea în vigoare

- **Data cercetării:** 30 august 2026
- **Pentru:** `OD-22` (numerele MO pe care `R15` le cere pentru fiecare parametru), `F2.X1`
  (`provisional_reason` al rândurilor încărcate `draft`)
- **Completează:** [`od-22-tva.md`](od-22-tva.md) („Ce nu s-a putut verifica", pct. 2),
  [`od-22-cnas-cnam.md`](od-22-cnas-cnam.md), [`od-22-impozitul-pe-venit.md`](od-22-impozitul-pe-venit.md)
- **Descărcări:** scratchpad-ul sesiunii, `x2/acte/` — paginile de ediție MO (`mo-<id>.html`),
  PDF-urile de pe `gov.md`, textele `.doc` de pe `old.mf.gov.md`, instantaneele Wayback

---

> ## Statutul sursei — de citit înainte de a folosi orice identitate de aici
>
> **Canalul oficial care a mers pentru metadatele MO este `monitorul.gov.md`, pagina de ediție**
> `https://monitorul.gov.md/ro/monitor/<id>`. Textul actelor e în spatele paywall-ului, dar **cuprinsul
> fiecărei ediții e public**: numărul ediției, data, și pentru fiecare act **poziția, denumirea,
> numărul și data adoptării**. Exact câmpurile cerute de `R15`. Căutarea sitului
> (`/ro/search?keywords=…&from=…&to=…`) indexează fiabil edițiile din ~2020 încoace; pentru 2018 și
> mai devreme a întors zero rezultate, iar edițiile s-au găsit **sondând id-urile** (care nu sunt
> cronologice: `monitor/1` e 25.04.2014, `monitor/1300` e 20.06.2002, `monitor/2016` e 05.01.2018).
> Edițiile din **1997, 2000 și 2003** n-au fost localizate prin sondaj.
>
> **`legis.md` a rămas inaccesibil pe toate căile:** 403 Cloudflare la pagină, la căutare și la
> `downloadpdf`; instantaneele Wayback ale paginilor `getResults?doc_id=` există, dar sunt **carcase
> JavaScript** („Conținutul se încarcă...") — textul vine prin AJAX și nu e arhivat; niciun PDF
> `downloadpdf/<id>` al actelor de aici nu e în arhivă (verificat prin CDX pentru 15 id-uri).
> `parlament.md`, `sfs.md`, `cnam.md` — 403 (și prin `curl`, și prin WebFetch). Wayback a servit o
> singură pagină utilă: știrea SFS din 2023 despre cota HoReCa. `mf.gov.md`, `gov.md`, `cnas.gov.md`
> — accesibile; `old.mf.gov.md` e parțial „în mentenanță", dar fișierele `.doc` ale Legilor
> nr. 1164/1997 și nr. 1417/1997 s-au descărcat.
>
> **Consecință:** numerele MO există acum pentru **toate actele modificatoare** și pentru HG-uri și
> ordin — confirmate pe pagina de ediție. **Clauzele de intrare în vigoare** s-au citit verbatim doar
> pentru titlurile I–II și III ale Codului fiscal (textele MF ale legilor de punere în aplicare); pentru
> restul, data e **afirmată** de MF, SFS sau de proiectul aprobat de Guvern, nu **citită** din lege.
> Actele de bază din 1997–2003 au identitatea MO doar din **citările din actele oficiale de pe `gov.md`**
> (preambulul proiectelor de lege citează „(Monitorul Oficial al Republicii Moldova, 2000, nr. 1–4,
> art. 2)"), nu de pe pagina de ediție.
>
> **O corecție de identitate, găsită pe cuprinsul MO:** actul care aprobă salariul mediu prognozat
> pentru 2025 **nu este „HG nr. 966/2024"**, cum stă în `od-22-cnas-cnam.md` §3. **966 e poziția în
> MO nr. 533-535 din 19.12.2024; actul e HG nr. 845 din 18.12.2024.** Numărul de poziție a fost luat
> drept număr de act. Se corectează în fișierul CNAS și în orice TOML care l-ar cita.

**Filtrul România a fost aplicat.** Fiecare cifră de identitate de aici vine de pe `monitorul.gov.md`,
`gov.md`, `mf.gov.md`/`old.mf.gov.md`, `cnas.gov.md` sau dintr-un instantaneu Wayback al `sfs.md`.
Aruncate explicit din rezultate: `legislatie.just.ro`, `mfinante.gov.ro`, `cnas.ro`, `anaf.ro`,
`lege5.ro`, `monitoruljuridic.ro`, `mmuncii.gov.ro`, `gov.ro`. Folosite **doar ca indiciu** spre
număr/dată, niciodată ca sursă a unei cifre: `contabilsef.md`, `monitorul.fisc.md`, `contabilitate.md`,
`lex.md`, `lege.md`, `legalbadger.org`, `sindicate.md`, `wipo.int`. Textul `legis.md` care apare în
rezumatele motorului de căutare (de ex. „LP187/2025 … publicat 18.07.2025") a fost tratat ca indiciu și
confirmat pe pagina de ediție MO.

---

## Tabelul identităților

Fiecare rând: data preluării **30.08.2026** pentru toate URL-urile. „poz." = numărul de ordine al
actului în cuprinsul ediției (ceea ce citările numesc „art."). **Clauză** = text citit; **afirmat** =
data spusă de o instituție, fără textul legii; **inferență** = marcată ca atare.

| Act — titlul complet, cum apare în cuprinsul MO | Monitorul Oficial | Intrarea în vigoare | Sursa (URL, 30.08.2026) | Justifică în `od-22-*` |
|---|---|---|---|---|
| **Codul fiscal nr. 1163-XIII din 24.04.1997** | Publicare inițială: **MO nr. 62 din 18.09.1997** — *neconfirmat oficial*: numărul ediției apare în rezumate neoficiale (`wipo.int`, `anta.gov.md`), iar antetul textului MF al Legii nr. 1164/1997 dă pentru acea lege „nr.62/524 din 18.09.1997"; **art. 522 pentru Cod e inferență** din numerotarea vecină. **Republicat: MO ediție specială din 08.02.2007** — citat oficial în proiectul de lege aprobat de Guvern: „Codul fiscal nr. 1163/1997 (republicat în Monitorul Oficial al Republicii Moldova, ediție specială din 8 februarie 2007)". Ediția din 1997 nu e localizată în arhiva `monitorul.gov.md` | **Titlurile I și II: 01.01.1998** — Legea nr. 1164-XIII din 24.04.1997, art. „Intrarea în vigoare": *„(1) Titlurile I şi II ale Codului fiscal intră în vigoare la 1 ianuarie 1998. (2) Prezenta lege intră în vigoare la data publicării, cu excepţia art.1-20 care intră în vigoare la 1 ianuarie 1998."* (antet: MO nr. 62/524 din 18.09.1997; republicată MO ed. specială 08.02.2007, pag. 105). **Titlul III (TVA): 01.07.1998** — Legea nr. 1417-XIII din 17.12.1997, art. 1: *„Titlul III al Codului fiscal intră în vigoare la 1 iulie 1998."* (antet: MO nr. 40-41/290 din 07.05.1998; republicată MO ed. specială 08.02.2007, pag. 110) | republicare: `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2025-06/NU-394-MF-2025_0.pdf` (Art. I); L1164: `https://old.mf.gov.md/common/actnorm/taxes/laws/02.03.11/Legea_pentru_punerea_aplic._a_titl._I_si_II_ale_Codului_fiscal.doc`; L1417: `https://old.mf.gov.md/common/actnorm/taxes/laws/02.03.11/Legea_pentru_punerea_in_aplicare_a_titlului_III_al_Codului_fiscal.doc`; paginile MF: `https://mf.gov.md/en/node/105671` (Cod, `legis.md` doc_id 138569), `https://mf.gov.md/ro/content/lege-pentru-punerea-în-aplicare-titlului-iii-al-codului-fiscal-nr1417-xiii` (doc_id 138615) | tot ce e pe titlul II (art. 15, 33–35, 83, 88–92, cap. 7¹, 10², 10⁴) și titlul III (art. 96, 103, 104, 112, 114, 115) |
| **Legea nr. 489-XIV din 08.07.1999 privind sistemul public de asigurări sociale** | **MO 2000, nr. 1–4, art. 2, din 06.01.2000** — citat oficial de două ori: proiectul de lege al MMPS: „Legea nr. 489/1999 privind sistemul public de asigurări sociale (Monitorul Oficial al Republicii Moldova, 2000, nr. 1–4, art. 2)"; anexa la Ordinul CNAS nr. 38-A/2025: „(Monitorul Oficial nr.1-4 din 06.01.2000)". Pagina de ediție **nelocalizată** | **Neobținută.** Nici clauza, nici data. **Forma în vigoare a anexei nr. 1:** neobținută; conform `od-22-cnas-cnam.md` (Ordinul CNAS 31-A/2026), pentru 2026 anexa poartă pct. 1.10 (L. 228/2025) și modificările L. 187/2025 și L. 318/2025 — **de verificat pe textul ordinului**, necitit aici | `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2026-02/102-MMPS-2026.pdf` (Art. I); `https://cnas.gov.md/sites/default/files/Dispoziţii/public_publications_7102514_md_particularitat.pdf` (pct. 1) | cotele CAS din anexa nr. 1 (24 / 29 / 39 / 32 / 18 / 6%), excluderile din anexa nr. 3, majorarea art. 28 |
| **Legea nr. 1593-XV din 26.12.2002 cu privire la mărimea, modul și termenele de achitare a primelor de asigurare obligatorie de asistență medicală** | **MO 2003, nr. 18–19, art. 57** — citat oficial în proiectul de lege aprobat de Guvern (Art. V: „Legea nr. 1593/2002 … (Monitorul Oficial al Republicii Moldova, 2003, nr. 18-19, art. 57)"). **Data ediției neconfirmată** (sondajul id-urilor 1178–1189 din 2003 n-a găsit-o) | **Neobținută.** Anexele nr. 1 și nr. 2 — necitite (vezi `od-22-cnas-cnam.md`, „Ce nu s-a putut verifica" pct. 2) | `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2025-05/nu-665-mded-2024.pdf` (Art. V); pagina MF: `https://www.mf.gov.md/ro/content/legea-cu-privire-la-mărimea-modul-și-termenele-de-achitare-primelor-de-asigurare-obligatorie` (`legis.md` doc_id 121301) | prima CNAM 9% (anexa nr. 1), prima în sumă fixă (anexa nr. 2), termenele art. 17 și 22 |
| **Legea contabilității și raportării financiare nr. 287 din 15.12.2017** | **MO nr. 1-6 din 05.01.2018, poz. 22** — confirmat pe cuprins: „22. Legea contabilității și raportării financiare (nr. 287, 15 decembrie 2017)"; și citarea oficială MF: „(Monitorul Oficial al Republicii Moldova, 2018, nr.1–6, art.22)" | **Neobținută.** 01.01.2019 apare doar în surse neoficiale (`contabilsef.md`) — **nu se preia** | `https://monitorul.gov.md/ro/monitor/2016`; `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2026-02/134-MF-2026.pdf` (Art. I); pagina MF `https://mf.gov.md/ro/content/legea-contabilității-și-raportării-financiare-nr-287` (doc_id 120938) | `C33` (art. 7 alin. (1), limba română); categoriile de entități — nu e parametru fiscal |
| **Codul muncii al Republicii Moldova nr. 154-XV din 28.03.2003** | **MO 2003, nr. 159–162, art. 648** — citat oficial în proiectul de lege al MMPS: „Codul muncii al Republicii Moldova nr. 154/2003 (Monitorul Oficial al Republicii Moldova, 2003, nr. 159–162, art. 648)". **Data 29.07.2003 — doar din surse neoficiale** (`sindicate.md`); sondajul id-urilor 1140–1149 n-a găsit ediția | **Neobținută oficial.** „Art. 391 — 1 octombrie 2003" apare doar pe `lege.md` — **nu se preia** | `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2025-06/432-MMPS_0.pdf` (Articol unic); pagina MF `https://mf.gov.md/ro/content/codul-muncii-nr-154-xv` | baza calculului salarial (`F2.B`) — nu e parametru fiscal |
| **Legea nr. 178 din 26.07.2018 cu privire la modificarea unor acte legislative** | **MO nr. 309-320 din 17.08.2018, poz. 496** — confirmat pe cuprins (era citat din nota SFS; acum verificat independent — închide pct. 8 din `od-22-impozitul-pe-venit.md`) | **Neobținută.** 01.10.2018 pentru cota unică de 12% — afirmat de SFS/BGPF în `od-22-impozitul-pe-venit.md`, clauza necitită | `https://monitorul.gov.md/ro/monitor/2061` | cota unică 12%, art. 15 lit. a) |
| **Legea nr. 60 din 23.04.2020 privind instituirea unor măsuri de susținere a activității de întreprinzător și modificarea unor acte normative** | **MO nr. 108-109 din 25.04.2020, poz. 186** — confirmat pe cuprins (verifică citarea din `od-22-cnas-cnam.md`) | **Neobținută.** 01.01.2021 pentru anularea contribuției individuale de 6% — afirmat în `od-22-cnas-cnam.md`, clauza necitită | `https://monitorul.gov.md/ro/monitor/2204` | contribuția individuală CAS 0% din 2021; dispariția plafonului de 5 salarii medii |
| **Legea nr. 212 din 20.07.2023 pentru modificarea unor acte normative (ce vizează politica bugetar-fiscală)** | **MO nr. 297-301 din 10.08.2023, poz. 514** — confirmat pe cuprins | **31.12.2023 pentru HoReCa 8%** — afirmat oficial de SFS, cu articolul citat: *„La data de 10 august 2023 în Monitorul Oficial … au fost publicate modificările … urmare a intrării în vigoare a Legii pentru modificarea unor acte normative nr.212/2023. Potrivit art. II pct.22 a Legii menționate supra, cota TVA pentru … HORECA …"* și *„începând cu data de 31 decembrie 2023 … se va aplica cota TVA de 8%, urmare a expirării la data de 30 decembrie 2023 a stării de urgență"*. Clauza legii — necitită | `https://monitorul.gov.md/ro/monitor/2758`; SFS prin Wayback: `https://web.archive.org/web/20240102123043/https://sfs.md/ro/stiri/incepand-cu-31-decembrie-2023-se-va-aplica-cota-tva-de-8-pentru-domeniul-horeca` | HoReCa 12% → 8% de la 31.12.2023 (`od-22-tva.md` §7.1) |
| **Legea nr. 214 din 31.07.2024 pentru modificarea unor acte normative (ce vizează politica bugetar-fiscală și vamală)** | **MO nr. 355-357 din 15.08.2024, poz. 545** — confirmat pe cuprins (verifică citarea din `od-22-impozitul-pe-venit.md`) | **Neobținută.** 01.01.2025 pentru scutirile +10% — afirmat de SFS; clauza necitită | `https://monitorul.gov.md/ro/monitor/2946` | scutirile art. 33–35 pentru 2025; politica fiscală 2025 (TVA §7.2) |
| **Legea nr. 311 din 26.12.2024 pentru modificarea unor acte normative (ce vizează politica fiscală și vamală)** | **MO nr. 556-559 din 27.12.2024, poz. 770** — confirmat pe cuprins | **Neobținută** | `https://monitorul.gov.md/ro/monitor/3010` | citată în `od-22-tva.md` pct. 2 fără parametru atribuit — **rămâne fără atribuire** |
| **Legea nr. 139 din 13.06.2025 pentru modificarea unor acte normative (Codul fiscal și Legea nr. 1417/1997 pentru punerea în aplicare a titlului III din Codul fiscal)** | **MO nr. 340-342 din 28.06.2025, poz. 389** — confirmat pe cuprins și în citarea oficială din HG-ul MF: „(Monitorul Oficial al Republicii Moldova, 2025, nr. 340-342, art. 389)" | **01.01.2026 — afirmat de MF** (articolul „Modificările efectuate în Codul fiscal pentru anul 2026", 03.02.2026); clauza necitită | `https://monitorul.gov.md/ro/monitor/3114`; `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2025-12/NU-920-MF-2025.pdf` (preambul); `https://www.mf.gov.md/ro/content/modificările-efectuate-în-codul-fiscal-pentru-anul-2026-privind-impozitul-pe-venit-tva` | taxarea inversă produse energetice, art. 101⁷ (`od-22-tva.md` §7.4) |
| **Legea nr. 187 din 10.07.2025 pentru modificarea unor acte normative** | **MO nr. 379-380 din 18.07.2025, poz. 491** — confirmat pe cuprins | **01.01.2026 — afirmat de MF** (același articol). Proiectul aprobat de Guvern în iunie 2025 („Lege pentru modificarea Codului fiscal nr.1163/1997 și a altor acte normative") are Art. XIII: *„Prin derogare de la prevederile art. 56 alin. (2) din Legea nr. 100/2017 cu privire la actele normative, prezenta lege intră în vigoare la 1 ianuarie 2026, cu excepția: a) … care intră în vigoare la data publicării …; b) Art. I pct.17 … se aplică începând cu perioada fiscală 2025; c) … care intră în vigoare la 1 ianuarie 2027."* — **e proiect, nu textul promulgat, iar atribuirea lui Legii nr. 187 e inferență** (titlu și calendar) | `https://monitorul.gov.md/ro/monitor/3126`; proiect: `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2025-06/NU-394-MF-2025_0.pdf` (Art. XIII) | extinderea dispozitivelor medicale la 8%; anexa nr. 3 pct. 10¹ la L. 489/1999 |
| **Legea nr. 228 din 10.07.2025 pentru modificarea unor acte normative (privind activitatea economică independentă a persoanelor fizice)** | **MO nr. 452-455 din 29.08.2025, poz. 623** — confirmat pe cuprins | **Neobținută.** 01.01.2026 — afirmat de SFS (`od-22-impozitul-pe-venit.md` §6) | `https://monitorul.gov.md/ro/monitor/3147` | cap. 10⁴ antreprenor independent (15% / 35%); pct. 1.10 anexa nr. 1 L. 489/1999 |
| **Legea nr. 318 din 29.12.2025 pentru modificarea unor acte normative (domeniul fiscal)** | **MO nr. 659-661 din 31.12.2025, poz. 792** — confirmat pe cuprins (verifică citarea din `od-22-impozitul-pe-venit.md` §7) | **01.01.2026 — afirmat de MF** (același articol); clauza necitită | `https://monitorul.gov.md/ro/monitor/3204` | baza impozabilă la reduceri de preț; abrogarea TAXI de la 01.07.2026; plafonul 360 000; art. 35² |
| **Legea bugetului asigurărilor sociale de stat pe anul 2026 nr. 320 din 29.12.2025** | **MO nr. 659-661 din 31.12.2025, poz. 796** — confirmat pe cuprins (verifică integral citarea din `od-22-cnas-cnam.md`) | **Neobținută.** 01.01.2026 — natura actului (lege bugetară anuală); clauza necitită | `https://monitorul.gov.md/ro/monitor/3204` | taxele fixe (22 878 / 30 966 / 5 827 lei), majorarea 0,1%/zi |
| **Legea fondurilor asigurării obligatorii de asistență medicală pentru anul 2026 nr. 321 din 29.12.2025** | **MO nr. 659-661 din 31.12.2025, poz. 798** — confirmat pe cuprins | **Neobținută.** 01.01.2026 — natura actului; clauza necitită | `https://monitorul.gov.md/ro/monitor/3204` | 9,0% angajat / 0% angajator; 12 636 lei; reducerile art. 4 |
| **Legea nr. 12 din 19.02.2026 pentru modificarea articolului 112 din Codul fiscal nr. 1163/1997** | **MO nr. 96-99 din 26.02.2026, poz. 60** — confirmat pe cuprins. **Titlul confirmă obiectul**: e actul pragului de înregistrare TVA | **01.03.2026 — afirmat de SFS** (comunicat, `od-22-tva.md` §7.3); clauza necitită | `https://monitorul.gov.md/ro/monitor/3234` | pragul art. 112 alin. (1): 1,5 → 1,7 mln lei |
| **HG nr. 845 din 18.12.2024 privind aprobarea cuantumului salariului mediu lunar pe economie, prognozat pentru anul 2025** *(citată greșit ca „HG nr. 966/2024")* | **MO nr. 533-535 din 19.12.2024, poz. 966** — confirmat pe cuprins: „966. Hotărâre privind aprobarea cuantumului salariului mediu lunar pe economie, prognozat pentru anul 2025 (nr. 845, 18 decembrie 2024)" | **Neobținută** | `https://monitorul.gov.md/ro/monitor/3004` | salariul mediu prognozat 2025 — 16 100 lei (`od-22-cnas-cnam.md` §3) |
| **HG nr. 773 din 17.12.2025 privind aprobarea cuantumului salariului mediu lunar pe economie, prognozat pentru anul 2026** | **MO nr. 620-622 din 18.12.2025, poz. 785** — confirmat pe cuprins (închide pct. 7 din `od-22-cnas-cnam.md`) | Proiectul aprobat de Guvern are un singur punct și **nicio clauză de intrare în vigoare**: *„Se aprobă cuantumul salariului mediu lunar pe economie, prognozat pentru anul 2026, în mărime de 17400 de lei, pentru utilizare în modul stabilit de legislație."* — deci la data publicării, **inferență** din regula generală, nu citare | `https://monitorul.gov.md/ro/monitor/3193`; proiect: `https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2025-12/NU-916-MMPS-2025_0.pdf` | salariul mediu prognozat 2026 — 17 400 lei; venitul asigurat IT (68%); plafonul pct. 12 anexa nr. 3 |
| **HG nr. 697 din 22.08.2014 pentru aprobarea Regulamentului cu privire la reţinerea impozitului pe venit din salariu şi din alte plăţi efectuate de către patron în folosul angajatului, precum şi din plăţile achitate în folosul persoanelor fizice care nu practică activitate de întreprinzător pentru serviciile prestate şi/sau efectuarea de lucrări** | **MO nr. 256-260 din 29.08.2014, poz. 745** — confirmat pe cuprins (verifică „256-260/745" din `od-22-impozitul-pe-venit.md`) | **Neobținută** | `https://monitorul.gov.md/ro/monitor/36` | procedura reținerii (cererea de scutiri, anexele 6–8, metoda cumulativă) — **doar procedură**, ADR-045 |
| **Ordinul CNAS nr. 31-A din 18.02.2026 cu privire la aprobarea Particularităţilor calculării şi achitării contribuţiilor de asigurări sociale de stat obligatorii în anul 2026** | **MO nr. 100-103 din 27.02.2026, Partea III, poz. 157** — confirmat pe cuprins | **Neobținută.** Textul ordinului n-a fost descărcat aici: PDF-ul de pe `cnas.gov.md` găsit prin căutare e **anexa Ordinului nr. 38-A din 03.03.2025** (anul 2025), iar pagina `cnas.gov.md/ro/node/585` nu leagă niciun PDF | `https://monitorul.gov.md/ro/monitor/3235` | reproducerea anexei nr. 1 (pct. 9, 13), pct. 8 (tariful perioadei de gestiune — conflictul cu `R18`), pct. 41 |

---

## Ce nu s-a putut verifica

Fiecare poziție e un blocaj real, cu ce s-a încercat.

1. **Nicio clauză de intrare în vigoare a actelor modificatoare n-a fost citită din textul legii.**
   Încercat: `legis.md` (403 direct, 403 la `downloadpdf`, Wayback — carcase JS fără conținut, CDX
   fără PDF pentru id-urile 149593, 150415, 152066, 121301, 152357, 152322, 138462, 146462, 120938,
   120073, 129313, 140625, 138615, 155185, 8238); `parlament.md` (403; Wayback are pagini
   `LegislativId`, dar fără o hartă act → id, neexplorat în buget); MO — text cu plată. Ce există în
   loc: data **afirmată** de MF (L. 139, 187, 318 — 01.01.2026), de SFS (L. 212 — 31.12.2023, cu
   art. II pct. 22 citat; L. 12/2026 — 01.03.2026) sau clauza din **proiectul** aprobat de Guvern
   (L. 187, cu atribuire inferată). **`valid_from` se încarcă din aceste afirmații cu `confidence`
   sub `verified`, nu peste.**
2. **Codul fiscal — publicarea inițială (MO nr. 62/522 din 18.09.1997)** e neconfirmată oficial:
   numărul ediției vine din rezumate neoficiale, art. 522 e inferență din antetul textului MF al Legii
   nr. 1164/1997 (art. 524, aceeași ediție). Republicarea din 08.02.2007 e citată oficial. Căutarea MO
   pentru 18.09.1997 a întors zero; ediția nu e localizată prin sondaj.
3. **Legea nr. 489/1999 — pagina de ediție MO și clauza de intrare în vigoare.** Identitatea
   (2000, nr. 1–4, art. 2, 06.01.2000) stă pe două citări oficiale concordante, nu pe cuprinsul ediției.
   Căutarea MO pentru 06.01.2000 — zero; sondajul n-a atins anul 2000. **Anexa nr. 1 în forma 2026**
   — necitită.
4. **Legea nr. 1593/2002 — data ediției MO nr. 18–19/2003** e necunoscută; `cnam.md` întoarce 403 și
   prin `curl`; anexele nr. 1 și nr. 2 rămân necitite.
5. **Codul muncii — data ediției (29.07.2003) și art. 391** apar doar în surse neoficiale; sondajul
   id-urilor 1140–1149 (august 2003 e la `monitor/1150`) n-a găsit ediția 159–162.
6. **Legea nr. 287/2017 — 01.01.2019** e doar în surse neoficiale; pagina MF nu spune nimic despre
   intrarea în vigoare.
7. **Ordinul CNAS nr. 31-A/2026 — textul.** PDF-ul găsit pe `cnas.gov.md` e cel din 2025 (Ordinul
   38-A/2025); linkul spre anexa din 2026 nu a fost găsit pe `cnas.gov.md/ro/node/585`. Citatele din
   `od-22-cnas-cnam.md` (pct. 8, 9, 13, 41) **nu au fost reverificate aici**.
8. **Legea nr. 311/2024** are acum identitatea, dar **niciun parametru atribuit** în cele trei fișiere
   — a fost listată în `od-22-tva.md` fără să i se atribuie o modificare. Rămâne de citit ce schimbă.
9. **HG nr. 697/2014, HG nr. 845/2024, L. 60/2020, L. 178/2018, L. 214/2024, L. 228/2025, L. 320/2025,
   L. 321/2025** — identitate MO completă, clauză de intrare în vigoare neobținută (aceleași căi ca la
   pct. 1).
10. **Atribuirea proiectului `NU-394-MF-2025` Legii nr. 187/2025 e inferență.** Avizul Guvernului
    `IL-232-2025` din iulie 2025 privește o **altă** inițiativă (nr. 232 din 18.06.2025, a unui grup de
    deputați) cu aceeași sferă (Codul fiscal + L. 489/1999) și spune și el „1 ianuarie 2026" — fără
    textul promulgat, nu se poate spune care a devenit Legea nr. 187.
11. **Datele intrării în vigoare și titlurile din cuprinsul MO nu spun ce articole modifică fiecare
    lege.** Atribuirea parametru → act din ultima coloană e cea din fișierele `od-22-*`, nu o
    verificare nouă.
