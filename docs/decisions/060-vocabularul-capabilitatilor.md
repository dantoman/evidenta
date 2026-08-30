# ADR-060 — Vocabularul capabilităților: listă curatoriată, definită de ce cere inițializare

- **Status:** **Acceptat** — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md).
  Premisa din §4 despre obligația declarativă e **inferență**, marcată ca atare și acceptată explicit
  de proprietar (2026-08-30)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** `DN-10` din `../specs/spec-a-tenancy.md` §11.10
- **Afectează:** `platform/capabilities` (`capability_key`), `accounting_event.capability_snapshot`,
  `F2.P3`, `F2.B0`, `F2.B6`
- **Legate:** Spec A §1.8, §11.10; master planul V2 §8 și §13; `R24`, `R25`, `R26`

## 1. Context

`capability_key` e `TextField` fără constrângere (`platform/capabilities/models.py`); singurele nume
declarate sunt cele trei de conformitate, `COMPLIANCE_CAPABILITIES = ("vat", "efactura",
"statutory_reporting")`, cu un CHECK care le interzice `effective_to` — o capabilitate de
conformitate nu se termină niciodată (`R24`). Restul vocabularului n-a fost niciodată enumerat.

`DN-10` e deschisă din F0.5 și n-a blocat nimic până acum, fiindcă nicio capabilitate
non-conformitate n-a existat ca rând. `F2.P3` o face pe prima — `payroll`, cu inițializare (`R25`) —
iar `F2.B0` o numește la „Blocat de". De aici se pune întrebarea, nu mai devreme.

## 2. Opțiuni evaluate

1. **A — capabilitățile corespund modulelor** din harta spec §4.1. *Avantaje:* previzibil, nimic de
   curatoriat. *Dezavantaje:* obiecția e a specului însuși — `numbering`, `audit` n-au sens ca
   unitate de activare, iar o listă în care jumătate din nume nu se pot activa nu e vocabular, e
   coincidență de denumire. *Cost de schimbare:* mare — numele intră în registru (§5).
2. **B — listă curatoriată, definită de *ce cere inițializare*.** *Avantaje:* criteriul de
   apartenență e verificabil, nu de gust: un nume intră dacă activarea lui cere un pas de pregătire
   cu stare (`initialisation_state`, `initialisation_ref` — care există). Corespunde intenției din
   V2 §8, unde toate exemplele sunt lucruri care cer un pas de inițializare. *Dezavantaje:* lista
   trebuie extinsă deliberat, cu migrare. *Cost de schimbare:* mic la adăugare, mare la redenumire
   (§5).
3. **C — ierarhie** (capabilitate → subcapabilități), pentru „payroll de bază" vs „payroll complet".
   *Avantaje:* grila comercială din V2 §13 o presupune deja. *Dezavantaje:* despicarea unei chei
   existente în două face ambiguu fiecare eveniment ștampilat cu cheia veche; iar azi n-o cere
   niciun cod, doar un tabel de marketing. *Cost de schimbare:* vezi §5 — nu e mare, **fiindcă
   există un mecanism**, și acela e motivul pentru care amânarea e apărabilă.

## 3. Decizie

**Opțiunea B.** Vocabularul închis al lui `capability_key`, peste cele trei de conformitate:

| Cheie | Ce cere inițializarea | Fază |
|---|---|---|
| `payroll` | cumulativele de salarii la activare în cursul anului ([ADR-061](061-cumulativele-de-salarii.md), `F2.B6`) | F2 |
| `inventory` | solduri de cantitate și cost, metoda de evaluare, cutover | F4 |
| `multi_company` | — structurală; intră fiindcă e numită explicit în documente | — |

Vocabularul e **tuplu în cod, materializat ca CHECK în bază** — același tipar ca
`COMPLIANCE_CAPABILITIES`, care e deja tuplu în cod consumat de un `CheckConstraint`. Adăugarea unui
nume e migrare, deliberat: nimic nu trebuie să poată inventa o capabilitate la runtime.

**Ierarhia (C) se amână**, cu declanșator: *prima cerință de produs care are nevoie efectiv de
„payroll de bază" vs „payroll complet"*. Grila din V2 §13 nu e acel declanșator — un tabel de
prețuri nu e cod.

## 4. `payroll` se activează, ieșirile lui declarative nu se dezactivează

Tensiunea e reală și se numește aici în loc să fie ocolită: Spec A §1.8 pune „payroll în măsura
obligațiilor declarative" la conformitate (`R24`, nu se dezactivează niciodată), iar V2 §13 îl vinde
pe planuri.

**Linia trasă:** `payroll` **nu** intră în `COMPLIANCE_CAPABILITIES`. Capabilitatea se activează, are
inițializare și poate lipsi. Dar odată activată, **ieșirile ei declarative nu se pot dezactiva și nu
se pot factura separat** — `R24` se ține **pe ieșiri, în cod**, nu pe rândul de capabilitate.

> **Inferență, marcată ca atare.** Că obligația declarativă apare *când există angajați, nu când
> există plan* este o **citire** a lui `R24`, nu un citat din el și nu o prescripție a vreunui act.
> Ce e citabil e doar că obligația există: darea de seamă lunară a angajatorului (IPC21) e impusă de
> art. 92 din Codul fiscal și aprobată prin Ordinul Ministerului Finanțelor nr. 94 din 30.07.2020
> (Monitorul Oficial nr. 199-204 din 07.08.2020, art. 687). Că din asta decurge că platforma nu are
> voie să o condiționeze de plan e alegerea proprietarului, acceptată la 2026-08-30, nu o consecință
> logică a actului.

## 5. De ce amânarea lui C e ieftină — și condiția care o face așa

**Numele ajung în registru.** Măsurat: `accounting_event.capability_snapshot` e `JSONField`
obligatoriu, scris pe **fiecare** eveniment contabil, iar docstring-ul din
`platform/capabilities/services/profile.py` declară forma drept contract:

> *„adding a key is safe, changing the meaning of one is not, and this is how a reader tells which
> meaning it is holding"*

Deci: **adăugarea unui nume e sigură; redenumirea sau re-semnificarea lui, după primul eveniment
postat, nu e.** `R18` citește snapshot-ul înapoi la recalcularea unei perioade trecute.

Amânarea lui C ar fi fost o pariere pe noroc dacă despicarea lui `payroll` în două chei ar fi cerut
rescrierea evenimentelor. Nu o cere: `SNAPSHOT_VERSION` există (`= 1`), definit exact pentru asta.
B → C se face cu o versiune nouă de snapshot, în care cheia veche înseamnă reuniunea celor două noi.

**Consemnat fiindcă schimbă răspunsul, nu doar îl justifică:** fără `SNAPSHOT_VERSION`, alegerea
proprietarului ar fi fost alta (2026-08-30). O amânare care își numește condiția de siguranță nu e
aceeași lucrare cu una care se sprijină pe noroc.

## 6. Consecințe

- **Devine posibil:** `F2.P3` (capabilitatea `payroll` cu inițializare), și prin el `F2.B0` și
  `F2.B6`.
- **Devine imposibil:** un `capability_key` inventat la runtime; și, după primul eveniment postat sub
  o cheie, redenumirea ei fără versiune nouă de snapshot.
- **De modificat ca urmare:** `DN-10` trece în „Închise" în registru; Spec A §11.10 primește
  răspunsul; `09-f2-backlog.md` — `F2.P3` și rândul din tabelul de blocaje.
- **Nu se verifică automat** dincolo de CHECK: că un nume nou merită să fie capabilitate rămâne
  judecată, iar criteriul scris („cere inițializare cu stare") e ce o face revizuibilă.

## 7. Surse

- `../specs/spec-a-tenancy.md` §1.8 (conformitatea nu e capabilitate plătibilă), §11.10 (`DN-10`, cele
  trei opțiuni), tabelul lui `capability_activation`.
- Master planul V2 §8 (exemplele de capabilități), §13 (grila comercială).
- `CLAUDE.md` `R24`, `R25`, `R26`.
- Măsurat în cod la 2026-08-30: `platform/capabilities/models.py` (`capability_key` fără CHECK,
  `COMPLIANCE_CAPABILITIES`), `platform/capabilities/services/profile.py` (`SNAPSHOT_VERSION`,
  contractul formei), `accounting/events/models.py` (`capability_snapshot` obligatoriu).
- Codul fiscal art. 92; Ordinul Ministerului Finanțelor nr. 94 din 30.07.2020 (IPC21), prin
  `../_input/cercetare/f2-x2-formularele-sfs.md`.
- Instrucțiunea proprietarului, 2026-08-30 (răspunsul la cele opt întrebări din
  `../_bootstrap/09-f2-backlog.md`).
