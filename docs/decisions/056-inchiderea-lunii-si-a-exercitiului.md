# ADR-056 — Închiderea: luna nu postează nimic, exercițiul postează lanțul într-o singură înregistrare, în perioada lui deschisă

- **Status:** Acceptat — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md), care
  **implementează** deciziile contabile deja luate ([ADR-039](039-valuta-si-perioade.md) §10,
  [ADR-050](050-lantul-de-inchidere-ca-roluri.md) §3.2, [ADR-054](054-importul-e-distributie-corpusul-e-intern.md)
  §4); nu decide niciun cont și nicio corespondență nouă
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului (sarcina F1.5.4, prima din ordinea fixată)
- **Închide:** — *(deschide `OD-73`, §5)*
- **Afectează:** `accounting/posting/services/closing.py` (nou), `accounting/periods/services/lifecycle.py`
  (invariantul clasei 8 pe primitivă; cititorul exercițiului), `accounting/periods/errors.py`,
  `accounting/events` (`source_module = "periods"`, migrarea `0002`), `tests/isolation/test_closing.py`

---

## 1. Context

F1.5.4 era blocată pe o definiție greșită (conturile lanțului ca parametri fiscali) și s-a deblocat
prin ADR-050; ordinea lanțului e aprobată, rolurile sunt în catalog. Ce rămânea de decis e
**inginerie**: câte evenimente, câte înregistrări, în ce perioadă cade postarea, ce verifică
închiderea lunii, ce se întâmplă cu pașii pe care actul nu-i datează.

Măsurat înainte: registrul de evenimente n-avea niciun tip `period.*` — verificarea mecanică pe
care proprietarul a numit-o; `close_period` schimba starea fără nicio validare; `close_fiscal_year`
bloca perioadele fără să posteze nimic; motorul avea contractul pe formule (ADR-048) și
`entry_type = "closing"` nefolosit.

## 2. Opțiuni evaluate

1. **Lanțul ca două evenimente** — rezultatele la 351, apoi 351 la 333 după contabilizarea
   impozitului. *Avantaj:* pasul 2 (impozitul) cade natural între ele. *Dezavantaje:* contrazice
   ADR-039 §10 („două `event_type`, nu trei"); și mută în motor o secvențiere pe care contabilul o
   face oricum înainte de a închide anul — impozitul se calculează din rulajele claselor 6 și 7, nu
   din soldul postat al lui 351.
2. **Un eveniment, o înregistrare, cu 731 ca corespondență proprie** — *aleasă*. Pașii 1, 3 și 4 din
   ADR-050 §3.2 sunt formule distincte în aceeași înregistrare: clasele 6 și 7 la 351 (fără 731), 731
   la 351, 351 la 333. Profitul până la impozitare rămâne lizibil în formule și în situație — motivul
   pentru care proprietarul a ținut 731 deoparte. Impozitul (pasul 2) e **precondiție**: postarea
   contabilului sau a modulului fiscal, înainte de a închide anul.
3. **Postarea de închidere admisă într-o perioadă `closed`** (excepție de la `R12` pentru
   `entry_type = "closing"`). *Avantaj:* decembrie poate fi închis lunar fără redeschidere.
   *Dezavantaj:* o excepție la un invariant, luată în cod, pe care proprietarul n-a cerut-o.
   Respinsă: **ultima perioadă trebuie să fie deschisă**; un decembrie închis pentru raportarea lunară
   se redeschide cu motiv, iar auditul arată că s-a întâmplat.

## 3. Decizia

### 3.1 Luna — `period.month_closed`

Închiderea lunii **nu postează nimic**. `periods.services.lifecycle.close_period` — primitiva —
validează **invariantul clasei 8**: la data raportării, conturile de gestiune au sold zero
(ADR-039 §10.1); un sold nenul refuză cu `periods.class8_not_settled`, numind conturile. Validarea
stă pe primitivă, nu pe ușă, ca niciun apel să n-o ocolească. Ușa motorului,
`posting.services.closing.close_month`, face tranziția și **înregistrează evenimentul** — `posted`,
fără înregistrare de jurnal — ca vocabularul a ce s-a întâmplat cu registrul să fie complet (R13).
O lună redeschisă și reînchisă e un al doilea eveniment, nu o reluare: `reopened_count` e în cheia
de idempotență.

Clasa e a codului, nu a coloanei `account_class`: „clasa 8" din normă e primul caracter al codului.

### 3.2 Exercițiul — `period.year_closed`

`posting.services.closing.close_year`, o tranzacție, în ordinea:

1. exercițiul e `open`; toate perioadele în afara ultimei sunt `closed`; **ultima e `open`**
   (`periods.last_period_not_open` altfel);
2. soldurile claselor 6 și 7 se citesc prin `ledger.services.trial_balance` — aceeași agregare ca
   raportul — pe fereastra exercițiului; **un cont de rezultat cu sold la intrarea în exercițiu
   refuză** (`periods.result_accounts_not_at_zero`): exercițiul precedent n-a fost închis aici;
3. cele trei roluri se rezolvă la data închiderii (`REZULTAT_FINANCIAR_TOTAL`,
   `CHELTUIALA_IMPOZIT_VENIT`, `PROFIT_NET_PERIOADA`); soldurile și conturile rezolvate intră în
   **payload** — evenimentul spune pe ce a stat închiderea, iar o recalculare peste ani închide
   aceleași numere (R18);
4. handlerul, **pur** (ADR-036 §5.1): citește payload-ul, întoarce formule; nu citește registrul.
   Conturile 6/7 sunt ale companiei, selectate după primul caracter al codului; contul lui
   `CHELTUIALA_IMPOZIT_VENIT` și subconturile lui (după prefixul de cod) formează pasul 3;
   direcția fiecărei formule vine din semnul soldului, iar 351 pleacă la 333 în direcția care îl
   lasă pe zero — profit `Dt 351 / Ct 333`, pierdere `Dt 333 / Ct 351`;
5. `post_formulas(entry_type = "closing")`, datată în ultima zi a exercițiului, cu `rule_ref` al
   tratamentului; niciun calcul, nicio rotunjire — sumele sunt ale registrului, la a patra zecimală;
6. `close_month` pe ultima perioadă (cu invariantul clasei 8), apoi `close_fiscal_year`, care
   blochează toate perioadele.

Un exercițiu fără nimic de închis se închide fără înregistrare: eveniment `posted`, `journal_entry`
absent — legitim, și testat.

### 3.3 Numele evenimentelor

ADR-039 §10 le-a scris `period.month.closed` și `period.year.closed`, înainte să existe registrul.
Registrul impune forma din Spec B §1.4 — `<domeniu>.<acțiune>`, două segmente, `snake_case` — și a
refuzat al treilea segment la prima înregistrare. Numele înregistrate sunt **`period.month_closed`**
și **`period.year_closed`**; sunt aceleași evenimente. `accounting_event.source_module` primește
valoarea `periods`: nimeni n-a tastat lanțul (`manual` ar minți), iar documentul sursă e perioada.

## 4. Consecințe

- **Devine posibil:** F1.5.4 e livrată în structură; `period.month_closed` apare în registru —
  verificarea mecanică a proprietarului e pozitivă; criteriul de ieșire „postarea într-o perioadă
  închisă e refuzată" își păstrează demonstrația și capătă perechea: lanțul se refuză dacă ultima
  lună nu poate închide.
- **Devine imposibil sau scump, asumat:** un decembrie închis lunar cere redeschidere cu motiv
  înainte de închiderea anului; reformarea bilanțului (pasul 5) nu se postează până la `OD-73`;
  nicio cale HTTP nu apelează încă `close_month`/`close_year` — ecranul de închidere e al fazei
  ecranelor, și inventarul „fiecare rută are un apelant" a fost respectat în sens invers: fără rută
  fără ecran.
- **Ce se verifică automat:** `tests/isolation/test_closing.py` — luna: eveniment `posted` fără
  înregistrare; refuz pe clasa 8 și pe primitivă și pe ușă; reînchiderea e al doilea eveniment.
  Exercițiul: cele patru corespondențe în ordine (1000 / 600 / 80 / 320), 351 la zero, 333 cu
  rezultatul, `entry_type = "closing"`, `rule_ref`, payload-ul cu solduri și conturile rolurilor,
  toate perioadele `locked`; pierderea în sens invers; exercițiul gol; refuzurile (lună deschisă
  la mijloc, ultima închisă, sold la intrare, al doilea închis); lanțul derulat înapoi când ultima
  lună nu poate închide.

## 5. Ce se raportează, nu se decide

- **`OD-73` — reformarea bilanțului.** Pasul 5 din ADR-050 §3.2 („334 se decontează, 333 la 332")
  poartă în act un moment — *la reformarea bilanțului* — pe care actul nu-l definește
  ([`od-22-planul-de-conturi.md`](../_input/cercetare/od-22-planul-de-conturi.md) §4). Trei variante:
  (a) în aceeași înregistrare cu închiderea exercițiului, la 31.12; (b) la aprobarea situațiilor
  financiare, în exercițiul următor, ca eveniment propriu; (c) la blocarea exercițiului
  (Spec B §6.2: `closed → locked` „după depunerea situațiilor"). ADR-039 §10 spune „două
  `event_type`, nu trei", ceea ce apasă spre (a) sau (c). **Nu se alege în cod.**
- **Impozitul pe venit (pasul 2)** e postarea contabilului sau a modulului fiscal, înainte de
  închidere; motorul nu-l poate verifica — un an cu rezultat zero n-are impozit.
- **Rulările fără ecran.** Serviciile există; ruta și ecranul vin cu F1.8/F2.

## 6. Surse

- [ADR-039](039-valuta-si-perioade.md) §8, §10, §10.1; [ADR-050](050-lantul-de-inchidere-ca-roluri.md)
  §3.1–3.2; [ADR-054](054-importul-e-distributie-corpusul-e-intern.md) §4; [ADR-048](048-formula-si-sloturile-tipizate.md)
  §3.4; [ADR-036](036-forma-postarii.md) §5.1.
- Spec B §1.4 (forma `event_type`), §6.2–6.3; `08-f1-backlog.md` F1.5.4.
- Planul general de conturi, cap. III — clasa 6, clasa 7, 351, 333 (`od-22-planul-de-conturi.md` §2, §4).
- `CLAUDE.md` — `R9`, `R10`, `R12`, `R13`, `R18`, `C10`, `D6`.
