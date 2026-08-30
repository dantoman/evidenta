# 12 — Linia de salariu: append-only sau nu. Măsurătoare și propunere

- **Data:** 2026-08-30 (sesiunea `evidenta-6e`)
- **Serveşte o singură decizie:** intră tabelele proprii ale salarizării în
  `infra/schema/append_only.toml`? Ridicată de `schema-reviewer` pe
  [ADR-065](../decisions/065-schema-salarizarii.md), care n-o atinge, şi numită acolo precondiţie a
  lui `F2.B1` — nu detaliu al primei migrări.
- **Cerut de proprietar:** *măsoară şi propune; decizia e a mea.* Aceleaşi trei puncte pe care le-a
  cerut: cine ar avea chei străine intrând, ce se întâmplă la recalculare, şi dacă „append-only" aici
  e aceeaşi proprietate ca în registru sau doar acelaşi nume.
- **Metoda:** ca la `11-volume-model.md` — ipotezele se declară, nu se ascund, şi se testează la
  sensibilitate.

---

## 1. Întâi (c), fiindcă decide cum se citesc celelalte două

**„Append-only" e acelaşi nume pentru două cerinţe diferite, şi confuzia e uşoară.** Măsurat în cod:

| Ce | Unde se impune | Ce impune |
|---|---|---|
| Apartenenţa la `append_only.toml` | `platform/rls/schema_audit.py`, constatarea **`IZ-77`** | **doar `R21` şi `R22`**: nicio cheie străină intrând, coloană de partiţionare prezentă şi `NOT NULL` |
| Imutabilitatea postării (`R10`) | triggere proprii — `journal_entry_stays_immutable`, `journal_line_stays_immutable` (`infra/migrations/0036_ledger.up.sql`), `journal_formula_stays_immutable` (`0057`) | refuzul oricărui `UPDATE`/`DELETE` |

**Sunt mecanisme separate.** `journal_line` le are pe amândouă, şi de acolo vine impresia că sunt
unul singur. `privileged_access_log` e în listă **şi** are trigger propriu, construit prin ADR-049 —
tot separat. `audit_event` şi `document_event` sunt în listă din motive de volum.

> **Consecinţa pentru salarizare:** cerinţa **legală** de imutabilitate priveşte **postarea**, nu
> datele-sursă. Ea e deja acoperită: rularea aprobată emite `payroll.run_approved`, postarea intră în
> `journal_line` şi `journal_formula`, iar amândouă sunt imutabile prin trigger şi amândouă sunt deja
> în listă. Linia de salariu e **document sursă**, ca o factură — iar documentele nu sunt în listă.
>
> **Deci pentru linia de salariu singurul motiv candidat e partiţionabilitatea.** Adică o întrebare
> de volum, nu una de conformitate. Aşa se citeşte restul acestui document.

---

## 2. Volumul

Două metode, ca să nu depindă de o singură ipoteză.

### 2.1 De sus în jos, pe cifra BNS

`11-volume-model.md`: **393,0 mii de salariaţi în IMM-uri** (BNS, 2025), din **41,8 mii de
întreprinderi active**. Scenariul optimist al Amendamentului e **15 000 de tenanţi în 10 ani**, deci
≈ **36% din piaţă**.

> 393 000 × 0,36 × 12 luni ≈ **1,70 milioane de linii de salariu pe an**

### 2.2 De jos în sus, pe clasele de mărime

Cu distribuţia din `11-volume-model.md` şi cu numere de salariaţi la mijlocul clasei — **ipoteză
declarată**, fiindcă BNS dă doar pragurile (micro ≤9, mici 10–49, mijlocii 50–249) şi faptul că 68,6%
au 0–4 salariaţi:

| Clasă | Tenanţi | Salariaţi/tenant *(ipoteză)* | Linii de salariu/an |
|---|---|---|---|
| micro | 10 290 | 3 | 370 000 |
| mici | 3 750 | 25 | 1 125 000 |
| mijlocii | 960 | 120 | 1 382 000 |
| **Total** | **15 000** | | **≈ 2,88 milioane/an** |

**Cele două metode dau 1,7 şi 2,9 milioane** — acelaşi ordin de mărime, ceea ce e tot ce se cere de la
o măsurătoare care decide o clasificare. **Se ia cifra mare.**

### 2.3 Proporţia, care e răspunsul

Rândurile de componente (`EmployerCharge`, `EmployeeWithholding` — ADR-065 §2) sunt ~4 per
angajat-lună, deci ~4× liniile.

| Tabelă | Pe an | Cumulat la 5 ani | Faţă de `journal_line` |
|---|---|---|---|
| `audit_event` | ≈ 172 mln | ≈ 860 mln | 167% — **primul candidat la partiţionare**, spune modelul |
| `journal_line` | ≈ 103 mln | ≈ 515 mln | 100% |
| componentele salarizării | ≈ 11,5 mln | ≈ 58 mln | **11%** |
| **linia de salariu** | **≈ 2,9 mln** | **≈ 14,4 mln** | **2,8%** |

**Linia de salariu e de ~35 de ori mai mică decât `journal_line` pe an şi de ~60 de ori mai mică decât
`audit_event`.** `11-volume-model.md` conchide deja că *„nu există problemă de volum per tenant"* şi
că prima tabelă care s-ar partiţiona e `audit_event`, nu `journal_line`. Linia de salariu e cu două
tabele mai jos în aceeaşi listă.

**Sensibilitate:** ar trebui un factor de **35×** faţă de ipoteze ca linia de salariu să ajungă la
volumul lui `journal_line` de azi. Modelul îşi declară propria incertitudine la „cel mult un factor de
doi".

---

## 3. Ce ar avea chei străine intrând, şi dinspre ce

Lista trebuie completă **înainte**, fiindcă direcţia e ireversibilă în practică: o tabelă cu chei
străine intrând nu se repartiţionează, se redesenează (`R21`).

| Dinspre | Ce ar pointa | Fază | Evitabil? |
|---|---|---|---|
| **`EmployerCharge` / `EmployeeWithholding`** | fiecare componentă calculată, spre linia din care derivă | **F2.B0**, deja decis | **Nu, natural.** Alternativa e ca fiecare rând de componentă să poarte `(company, employee, period)` denormalizat şi să se lege prin ele |
| **Raportul rulării în paralel** (`F2.B5`) | perechea *rezultatul nostru ↔ rezultatul celuilalt sistem*, per angajat şi componentă | F2.B5 | Greu — o pereche care nu poate pointa spre una dintre laturi nu e pereche |
| **Fluturaşul arhivat** (`F2.B4` + `F2.P1`) | documentul generat per angajat şi rulare | F2.B4 | Da — poate pointa spre **rulare**, nu spre linie |
| **Certificatul medical / concediul** (`F2.B3`) | „ce rulare a plătit indemnizaţia" | F2.B3 | Da — legătura naturală e linie → certificat, adică **ieşind** |
| **Generaţiile de recalculare** (§4) | `supersedes_line_id`, auto-referenţial | — | Depinde de §4 |
| **Cumulativele** (`F2.B6`) | — | — | **Niciuna.** `opening_balance_payroll_cumulative` e poziţie de pornire, citită de salarizare; nu arată spre linii |

**Bilanţ: cel puţin două chei străine intrând sunt naturale şi greu de evitat**, iar una dintre ele —
componentele — e chiar structura pe care ADR-065 tocmai a fixat-o. A o interzice ar însemna
denormalizarea fiecărui rând de componentă, plătită acum pentru o nevoie de partiţionare pe care
cifrele n-o arată.

---

## 4. Ce se întâmplă la recalculare

**O rulare de salarii se recalculează mult mai des decât se corectează o factură** — o zi de concediu
introdusă târziu, un spor uitat. Şi asta se întâmplă **înainte de aprobare**, cât rularea e în
`draft` / `calculated`.

- **Dacă linia e append-only:** fiecare recalculare lasă o generaţie. La 2–3 recalculări per rulare,
  volumul din §2.3 se triplează — ≈ 8,7 mln/an —, iar două treimi sunt stări intermediare **pe care
  nu s-a sprijinit nimeni**. Nu e urmă de audit; e gunoi cu formă de urmă.
- **Dacă nu e:** trebuie spus ce ţine locul urmei.

**Ce ţine locul urmei, şi există deja ca tipar în acest repo:**

1. **Îngheţare la schimbarea de stare.** `infra/migrations/0039_opening_balances.up.sql` are
   `rls.opening_balance_line_frozen`: liniile lotului de solduri iniţiale sunt modificabile cât lotul
   e `draft` şi **refuzate la scriere după ce iese din el**. Aceeaşi formă pentru salarizare: linia e
   mutabilă în `draft` / `calculated`, **îngheţată la `approved`**.
2. **După aprobare, urma e registrul.** Aprobarea emite `payroll.run_approved`, postarea e imutabilă
   (`R10`, prin trigger), iar o corecţie de după e **rulare nouă sau storno** — nu o editare. Aceasta
   e urma care contează la un control, şi e deja imutabilă.
3. **Cât e `draft`, urma e `platform/audit`.** `F2.B1` cere oricum audit pe datele personale; cine a
   schimbat ce înainte de aprobare e exact ce răspunde auditul, fără să umple cea mai mare tabelă a
   modulului cu generaţii moarte.

---

## 5. Propunerea sesiunii

> **Linia de salariu şi componentele ei NU intră în `infra/schema/append_only.toml`.**

Pe cele trei puncte:

1. **Volumul nu o cere.** 2,8% din `journal_line`, cu două tabele mai jos decât primul candidat pe
   care modelul îl numeşte. Ar trebui un factor de 35× ca să conteze.
2. **Cheile străine intrând sunt naturale, şi cel puţin două sunt greu de evitat** — una fiind chiar
   structura fixată de ADR-065. `R21` le-ar interzice pe toate, iar preţul se plăteşte acum pentru o
   partiţionare pe care nimic nu o cere.
3. **Cerinţa legală e deja acoperită în altă parte.** `R10` priveşte postarea, iar postarea e în
   `journal_line` şi `journal_formula` — amândouă imutabile prin trigger, amândouă deja în listă.
   Numele comun nu e cerinţă comună.

**Ce se construieşte în loc, şi nu e opţional:**

- `payroll_line` **îngheţată la `approved`**, prin trigger, pe tiparul lui
  `rls.opening_balance_line_frozen`. Fără el, decizia de aici devine „linia se poate edita oricând",
  ceea ce nu e ce se propune.
- **Cheie primară `UUID`** (`C6`), fiindcă `bigint` e rezervat tabelelor din listă — măsurat:
  `journal_line` e singura din `ledger` cu `BigAutoField`, restul sunt `UUID`.

> **De ce contează că se decide acum:** tipul cheii primare **încorporează** decizia. `UUID` pentru o
> tabelă din afara listei, `bigint` pentru una din listă. Schimbarea lui după ce există rânduri şi
> chei străine nu e migrare, e rescriere — exact motivul pentru care ADR-065 a numit-o precondiţie a
> lui `F2.B1`, nu detaliu al primei migrări.

## 6. Ce ar răsturna propunerea

Consemnat ca să fie verificabil, nu ca precauţie.

> **Care dintre ele are declanşator, deci rând în registru** (regula [ADR-066](../decisions/066-rezerva-e-decizie-deschisa.md)),
> verificat la închiderea `OD-87`:
>
> - **Păstrarea generaţiilor de recalculare → `OD-88`.** E o **rezervă**: „niciun act n-o cere" e o
>   afirmaţie despre ce **nu s-a citit**, nu despre ce s-a verificat, iar declanşatorul e o căutare
>   ţintită. Rând deschis.
> - **Un client cu mii de angajaţi → fără rând.** Nu e rezervă: nimic nu e neverificat. E un **prag de
>   sensibilitate** — condiţia în care decizia se schimbă, cunoscută şi calculată. Monitorizare, nu
>   decizie deschisă.
> - **Distribuţia reală pe clase → fără rând nou.** E deja declarată ca ipoteză în
>   `11-volume-model.md`, sub `OD-01`, cu acelaşi tabel BNS numit acolo. Un al doilea rând ar dubla-o.

- **Un client cu mii de angajaţi.** La 5 000 de salariaţi într-un singur tenant, linia de salariu
  ajunge la 60 000/an pentru acel tenant — încă sub `journal_line`-ul lui, dar profilul iese din
  „IMM", care e chiar definiţia pieţei-ţintă.
- **Păstrarea generaţiilor de recalculare ca cerinţă**, dacă un control cere să vadă calculele
  intermediare, nu doar rezultatul aprobat. **Nu s-a citit niciun act care să o ceară** — şi nu s-a
  căutat: ar fi `F2.X2`. Dacă apare, §4 se schimbă şi §2.3 se triplează.
- **Distribuţia reală pe clase**, din tabelul BNS `ANT030040`, dacă diferă de ipoteza din §2.2 cu mai
  mult decât factorul de doi pe care modelul îl declară.
