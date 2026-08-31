# ADR-088 — Statutul fiscal e datat, iar evenimentul poartă ștampila lui

- **Stare:** Acceptat — proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar, cu raționamentul reprodus în §2
- **Restrânge:** `OD-83` *(partea portantă se închide aici; forma rezolvării în handlere rămâne)*
- **Legate:** [ADR-038](038-vocabularul-de-evenimente.md), [ADR-047](047-stampila-parametrului-la-postare.md),
  [ADR-060](060-vocabularul-capabilitatilor.md), [ADR-071](071-tipurile-de-raport-ca-tabela.md) §7
- **Deschide:** `OD-130`

## 1. Ce era blocat, și de ce blocajul era pus greșit

`OD-83`: motorul selectează un tratament după `(event_type, accounting_date, capability_snapshot)`,
iar `HandlerVersion.requires` se compară exclusiv cu setul de capabilități. Un **statut fiscal** —
plătitor de TVA, rezident de parc IT, regim de impozitare — nu e capabilitate: `ADR-060` pune
criteriul de apartenență pe *ce cere inițializare cu stare*, iar un statut nu se vinde și nu se
activează.

Sesiunea de implementare a citit asta ca pe un zid și s-a oprit înaintea pasului 6. **Greșit ca
proces**: exista o variantă reversibilă, iar regula e s-o iei și să scrii un rând, nu să te oprești.
Consemnat aici fiindcă tiparul se repetă altfel.

## 2. Ce a decis proprietarul, cu raționamentul lui

> **Partea portantă nu e unde se ramifică, e ca statutul fiscal să fie datat.** O companie devine
> plătitor de TVA la o dată. Fără o tabelă de statut cu margini, nicio variantă nu funcționează — nici
> ștampilarea, nici rezolvarea la postare — fiindcă n-ai de unde ști ce era valabil atunci.
>
> Cu ea, ambele variante sunt recuperabile: coloana se poate adăuga mai târziu prin backfill din tabela
> de statut, iar rezolvarea prin dată se poate înlocui cu ștampilă oricând.
>
> **Diferența reală dintre ele:** dacă nu ștampilezi, o corecție ulterioară a statutului schimbă tăcut
> rapoartele deja emise. Cu ștampilă, evenimentul poartă ce era adevărat atunci; o corecție de statut
> e vizibilă ca diferență, nu se propagă în tăcere.

Deci: **tabela de statut datat, ștampila pe eveniment, forma rezolvării în handlere amânată până la al
treilea caz.** Tiparul din [ADR-071](071-tipurile-de-raport-ca-tabela.md) §7 — vocabularul acum,
legarea când există consumator real; proiectată azi, rezolvarea pe două dimensiuni ar fi o schemă
validată de nimic.

## 3. Ce exista deja, măsurat

**Marginile pentru TVA există.** `company_vat_registration` (Spec A §1.2) poartă `vat_code`,
`valid_from`, `valid_to` și sursa, cu docstring-ul care spune exact de ce: *„o companie se
înregistrează și poate fi radiată în cursul anului. Recalcularea unei perioade trecute trebuie să
folosească statutul valabil atunci (`R18`) — ceea ce un boolean nu poate exprima."*

**Parcul IT nu are tabelă.** `OD-81` o numește ca rămânând „ca să existe ce se citește", dar
`company_it_park_residency` nu există în cod — verificat, zero potriviri. Nu se creează aici: nu are
încă niciun cititor, iar acesta e ADR-ul care tocmai a decis să nu proiecteze scheme fără consumator.

Deci ce lipsea nu era o tabelă, ci **profilul** — un singur răspuns la *ce era adevărat despre această
companie la data asta* — și **ștampila**.

## 4. Forma

`accounting_event` primește `tax_status_snapshot`, `jsonb`, lângă `capability_snapshot`. Versionat de
la primul rând, ca și profilul de capabilități: un instantaneu fără versiune nu spune nimic despre ce
citea cine l-a scris.

**Se calculează în `emit()`, nu se cere apelantului**, și aici forma se abate deliberat de la
`capability_snapshot`:

| | de unde vine | de ce |
|---|---|---|
| `capability_snapshot` | de la apelant | e **input** al motorului (`R26`): apelantul poate avea motiv să-l suprascrie |
| `tax_status_snapshot` | calculat în `emit` din `(company_id, accounting_date)` | e **fapt** despre companie la o dată; un apelant care îl uită ar produce un eveniment fără ștampilă, iar lipsa unei ștampile e chiar eșecul tăcut pe care ADR-ul îl evită |

`null` rămâne posibil și înseamnă un singur lucru: eveniment scris înainte ca această coloană să
existe. Nu înseamnă „fără statute" — distincția contează la prima recalculare.

## 5. Ce **nu** se decide aici

- **`OD-130` — forma rezolvării în handlere.** Cum ajunge statutul să selecteze un tratament:
  a doua dimensiune în `HandlerVersion.requires`, un predicat peste ștampilă, sau altceva. Se ia
  **la al treilea caz**: primul au fost parcurile IT (`OD-81`, rezolvat prin refuz), al doilea e TVA.
  Ștampila nu prejudecă niciuna — poartă informație corectă oricare ar fi răspunsul.
- **Dacă statutul e de fapt o diferență de date** — cotă zero plus alt cont de deducere — și nu de
  formă. Proprietarul o numește explicit: dacă se dovedește așa, ștampila rămâne informație corectă pe
  eveniment și nu încurcă.
- **Tabela de rezidență de parc IT.** Când are cititor.

## 6. Consecințe

- **Devine posibil:** pasul 6 (TVA) poate începe — statutul la data postării e cunoscut și păstrat.
- **Devine imposibil:** o corecție de statut care schimbă tăcut un raport deja emis. Evenimentul
  poartă ce era adevărat atunci; diferența se vede.
- **Rămâne recuperabil, în ambele sensuri:** dacă rezolvarea se face prin dată, ștampila e redundantă
  și inofensivă; dacă se face prin ștampilă, ea e deja acolo pentru evenimentele scrise de acum.
- **Ce se verifică automat:**
  1. evenimentul poartă statutul valabil **la data contabilă**, nu la data scrierii;
  2. o înregistrare de TVA adăugată *după* postare nu schimbă ștampila unui eveniment deja scris;
  3. o companie fără nicio înregistrare de TVA primește o ștampilă care spune **asta**, nu una goală.

## Surse

- Spec A §1.2 (`company_vat_registration`), `R18`, `R26`.
- [ADR-047](047-stampila-parametrului-la-postare.md) *(ce a stat la baza unei postări se ștampilează)*,
  [ADR-071](071-tipurile-de-raport-ca-tabela.md) §7 *(vocabularul acum, legarea la consumator)*.
- Măsurat la 2026-08-31: `company_vat_registration` există și e datată; `company_it_park_residency` nu
  există; `emit()` primește `capability_snapshot` de la apelant.
- Instrucțiunea proprietarului, 2026-08-31, reprodusă în §2.
