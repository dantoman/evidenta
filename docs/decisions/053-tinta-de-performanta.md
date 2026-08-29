# ADR-053 — Ținta de performanță: modelul de volum dă datele, fișa contului agregă pe document

- **Status:** Acceptat — decizie de produs, luată de proprietar prin instrucțiune scrisă,
  2026-08-29 (punctul 7); pragurile numerice din §3.3 sunt **propuse de sesiune**, nu de proprietar,
  și se confirmă sau se corectează fără efect asupra structurii
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** `OD-29`
- **Afectează:** F1.8 (rapoartele contabile), `DataGrid` (F1.G1), read models (Spec A §7),
  `tests/volume/`
- **Legate:** `_bootstrap/11-volume-model.md` (F0.11), [ADR-032](032-cheia-de-partitionare.md),
  [ADR-048](048-formula-si-sloturile-tipizate.md) (`journal_formula` — corespondența pe care se
  face drill-down-ul), [ADR-042](042-scara-de-densitate.md)

---

## 1. Context

`OD-29` cerea „țintele numerice de performanță pentru cele patru scenarii din V2 §12.4": balanța de
verificare pe 5 ani de date, închiderea de perioadă pentru o companie cu volum mare, dashboardul
contabilului cu 100 de clienți, generarea declarației TVA. Registrul o dădea „decizie umană,
înainte de F1"; backlogul F1.8 constata că e „deblocată, nu luată" — modelul de volum există din
F0.11, cu cifre cu sursă și ipoteze declarate, plus măsurători sub rolul aplicației.

Ce lipsea nu erau cifrele de volum, ci **ce vede utilizatorul**: la ce granularitate se citește
fișa unui cont. Un cont 521 cu o factură de patruzeci și una de linii — o factură reală, nu un caz
de test — arată în 1C ca patruzeci și una de rânduri sau ca unul, după configurare, și diferența
decide și indexul, și grila, și ținta.

## 2. Opțiuni evaluate

1. **Praguri numerice fixate acum, fără date.** *Dezavantaj:* cifre inventate, care fie nu
   constrâng nimic, fie constrâng greșit; exact ce `11-volume-model.md` refuză să facă pentru
   partiționare.
2. **Fișa contului pe linie de jurnal, ca implicit.** *Avantaj:* zero agregare. *Dezavantaj:*
   contabilul care deschide 521 vede 41 de rânduri pentru o factură; ecranul e ilizibil înainte să
   fie lent, iar ținta de performanță se pune pe o cantitate pe care nimeni n-o vrea afișată.
3. **Fișa contului agregă implicit pe document, cu drill-down la formule; volumul vine din model;
   ținta se măsoară, nu se declară** — *aleasă*.

## 3. Decizia

### 3.1 Granularitatea

**Fișa contului agregă implicit pe document.** Un rând per document per cont, cu suma și
corespondența; drill-down deschide **formulele** documentului (`journal_formula`, ADR-048), nu
liniile brute — fiindcă fișa se citește „în corespondență cu contul", iar formula e chiar
corespondența. Contabilul care deschide 521 vede un rând per factură, nu 41.

Cartea Mare și balanța agregă deja peste asta; jurnalele (vânzări, cumpărări) sunt pe document prin
definiție. Linia de jurnal rămâne unitatea balanței (`C19`, totalurile pe server) și a exportului.

### 3.2 Datele

Cele patru scenarii se măsoară pe **scenariul „Mare"** din `11-volume-model.md`: o companie
mijlocie, `A3` central — 18.000 de documente pe an, 54.000 de linii, **270.000 de linii pe 5 ani**
per tenant; dashboardul cu 100 de clienți, pe 100 de tenanți micro–mici din același model. La
capătul de sus al intervalelor (×2,7) cifrele se înmulțesc, nu se schimbă forma.

Măsurate **sub `evidenta_app`, cu politicile active**, prin `backend/tests/volume/` — scara mică în
suita obișnuită, scara reală cu `EVIDENTA_VOLUME_ROWS` — și scrise cu mediul lângă ele, ca
raporturi. Când extrasul 1C real (`OD-28`, F1.G0) există, se repetă pe el: modelul dă volumul,
extrasul dă structura.

### 3.3 Pragurile — propuse, nu decise

Cifrele de mai jos sunt ale sesiunii de implementare, ca punct de plecare pentru testul de volum,
și **se confirmă de proprietar**; nimic structural nu depinde de ele:

| Scenariu (V2 §12.4) | Pe ce | Prag propus, server |
|---|---|---|
| Balanța de verificare pe 5 ani | tenant „Mare", 270.000 de linii | ≤ 2 s |
| Fișa contului, un cont cu mișcare bogată, o lună | același tenant, agregat pe document | ≤ 1 s |
| Închiderea de perioadă, companie cu volum mare | lanțul din ADR-050, o lună | ≤ 60 s, ca task |
| Dashboard cu 100 de clienți | read model, 100 de tenanți | ≤ 2 s |
| Declarația TVA, o perioadă fiscală | tenant „Mare" | ≤ 10 s |

## 4. Consecințe

- **Devine posibil:** F1.8 se deblochează — forma fișei contului e decisă, deci și indexul ei:
  `(company, account, accounting_date, entry)`, cu agregarea pe `journal_entry`; `DataGrid` primește
  rânduri de document, cu drill-down în loc de virtualizare peste linii.
- **Devine imposibil sau scump, asumat:** o fișă „pe linie" e o opțiune de afișare, nu implicitul,
  și nu e ținta de performanță; o cifră din §3.3 care cade pe extrasul real e o constatare de
  măsurat, nu un defect al modelului.
- **Ce se modifică:** `08-f1-backlog.md` F1.8 („Blocat de: `OD-29`" se taie; rămâne dependența de
  F1.G1); `000-open-decisions.md`; `tests/volume/` primește scenariul fișei pe document.
- **Ce se verifică automat:** testul de volum pe fiecare rând din §3.3, la scara reală, cu
  rândurile citite (nu absența cuvântului „Seq Scan" — lecția din F0.11); `C19` pe fișă: totalul
  vine de la server.

## 5. Surse

- Instrucțiunea proprietarului, 2026-08-29, punctul 7.
- `docs/_input/evidenta-master-plan-v2.md` §12.4; `docs/_bootstrap/11-volume-model.md` (scenariile,
  ipotezele `A1`–`A5`, măsurătorile); [ADR-048](048-formula-si-sloturile-tipizate.md) §2.1 opțiunea
  1 („fișa contului se citește prin corespondență"); `CLAUDE.md` `C19`, `C20`.
- Benchmark 1C: fișa contului („карточка счёта") arată implicit un rând per înregistrare de
  document, cu expandare — practică, nu temei.
