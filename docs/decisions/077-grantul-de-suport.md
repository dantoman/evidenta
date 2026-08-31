# ADR-077 — Grantul de suport: cererea e privilegiată, aprobarea e obișnuită, expirarea e în predicat

- **Stare:** Acceptat — produs și tehnic, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietar
- **Închide:** `DN-18` din Spec A §6.2 (`P-7`)
- **Deschide:** `OD-115`
- **Atinge:** `infra/bootstrap/0003_access_predicates.sql`, `platform/identity`, `platform/audit`,
  Spec A §6.2 și §6.3
- **Depinde de:** [ADR-076](076-planul-de-control-al-platformei.md) — grantul are nevoie de un
  titular

## 1. Ce se decide

`P-7` este singura cale prin care un angajat al platformei ar putea vedea datele unui client. Spec A
o enumeră de la început, dar fără mecanism: *„vezi `DN-18`"*. Cele trei opțiuni erau (A) nu există,
(B) există cu acordul explicit al tenantului per incident și expirare automată, (C) există fără
acord, cu notificare și audit vizibil clientului.

**Se alege (B).**

(A) se respinge fiindcă face unele incidente irezolvabile, iar costul cade pe client: el trebuie să
exporte, să descrie și să aștepte. (C) se respinge fiindcă mută proprietatea asupra datelor din
`INV-7` într-o promisiune: clientul află *după*. Un audit vizibil este o consolare, nu un drept.

## 2. Forma, în trei mișcări

Ce ține decizia în picioare nu e existența unui tabel de granturi, ci **cine face fiecare pas**:

```
1. cererea       →  cale privilegiată (P-7)      →  angajatul platformei, rol `support`
2. aprobarea     →  cale OBIȘNUITĂ, prin RLS     →  un membru al clientului, cu permisiune
3. accesul       →  ramură în predicat, mărginită de now()
```

Pasul 2 este miezul. **Aprobarea nu trece printr-o cale privilegiată** — trece prin politica
obișnuită a tenantului, ca orice altă scriere a unui membru. Dacă aprobarea ar fi și ea privilegiată,
platforma ar putea să și ceară, și să încuviințeze; consimțământul ar fi o formalitate scrisă de cel
care beneficiază de el.

## 3. `support_grant`

Tabelă **tenant-scoped** — are `tenant_id`, deci `R1` e satisfăcut fără excepție, iar politica e
șablonul din Spec A §2.5. Consecință utilă: clientul își vede propriile granturi cu o interogare
obișnuită, fără nimic special.

| Câmp | Tip | Note |
|---|---|---|
| `id` | uuid | PK |
| `tenant_id` | uuid | NOT NULL |
| `company_id` | uuid | NULL — nul înseamnă tot tenantul; altfel doar compania numită |
| `requested_by_user_id` | uuid | NOT NULL — angajatul platformei, rând viu în `platform_staff` |
| `request_ref` | text | **NOT NULL** — numărul solicitării de suport |
| `justification` | text | NOT NULL — merge în `privileged_access_log` |
| `requested_at` | timestamptz | NOT NULL |
| `approved_by_user_id` | uuid | NULL — un membru al tenantului |
| `approved_at` | timestamptz | NULL |
| `expires_at` | timestamptz | NULL — obligatoriu odată cu aprobarea |
| `revoked_at` | timestamptz | NULL — clientul poate tăia oricând, înainte de expirare |
| `revoked_by_user_id` | uuid | NULL |

Constrângeri:

- `CHECK ((approved_at IS NULL) = (approved_by_user_id IS NULL))` și la fel pentru `expires_at` —
  un grant aprobat fără termen e un grant permanent scris din greșeală;
- `CHECK (expires_at > approved_at)`;
- `CHECK (expires_at <= approved_at + interval '72 hours')` — plafonul stă în bază, nu în serviciu,
  fiindcă serviciul e cel care se schimbă la ora la care se rezolvă incidentele;
- `CHECK (requested_by_user_id <> approved_by_user_id)` — nimeni nu-și aprobă propriul grant, nici
  dacă e din întâmplare și angajat al platformei, și membru al clientului;
- unicitate parțială pe `(tenant_id, requested_by_user_id)` pentru granturile vii, ca o cerere
  nerezolvată să nu se poată multiplica până când cineva apasă din obișnuință.

**Fereastra implicită propusă: 24 de ore; maximul, 72.** Cifrele sunt ale proprietarului și se
schimbă printr-o migrare, nu printr-o setare.

### 3.1 Doar citire, și asta nu e o etapă intermediară

Grantul nu are nivel de permisiune. **Nu există grant de scriere.**

Motivul nu e prudența, e `INV-9`: lanțul de trasabilitate spune cine a produs fiecare efect
financiar. Un angajat al platformei care postează în registrul unui client introduce în ledger un
autor care nu aparține niciunei părți ale relației — nici tenantului, nici firmei. Corecția unei
postări greșite se face prin storno (`R10`), de către cine are dreptul să posteze. Suportul
diagnostichează; nu contabilizează.

Un grant de scriere ar fi un ADR nou, cu propriul lui motiv. Absența lui aici e decizie, nu omisiune.

## 4. Ramura din predicat, și de ce nu costă

Predicatele câștigă o a treia cale, **poarta ieftină prima**:

```sql
OR (
    app.current_support_grant_id() IS NOT NULL
    AND EXISTS (
        SELECT 1 FROM support_grant sg
        WHERE sg.id          = app.current_support_grant_id()
          AND sg.tenant_id   = p_tenant_id
          AND sg.approved_at IS NOT NULL
          AND sg.revoked_at  IS NULL
          AND sg.expires_at  > now()
    )
)
```

Patru observații, fiecare fiind un mod de eșec evitat:

1. **Gardul e o variabilă de sesiune, nu o interogare.** Într-o sesiune obișnuită
   `app.current_support_grant_id()` e nul, iar ramura se stinge înainte de orice `EXISTS`. Este
   exact forma căii 2, care se stinge când `app.actor_firm_id` e nul. Costul pe calea fierbinte
   (Spec A §2.8) rămâne cel de azi.
2. **Variabila nu acordă nimic singură.** Ca și la firmă („apartenența se verifică, nu se
   presupune", Spec A §2.4), un atacant care setează `app.support_grant_id` nu obține nimic: rândul
   trebuie să existe, să fie aprobat, neexpirat și **al tenantului cerut**.
3. **`now()`, nu `current_date`.** [ADR-041](041-ziua-ca-argument.md) §1 o spune direct: `now()`
   compară *momente*, nu *zile*, deci e corect în orice fus. O fereastră de suport se măsoară în
   ore; o fereastră măsurată în zile ar da acces până la miezul nopții unei zile pe care nimeni n-a
   ales-o. Regula „niciun predicat nu citește ceasul" e despre ziua de calendar, iar rescrierea
   amânată din ADR-041 §6 **nu atinge această ramură** — parametrul `p_on_date` nu o traversează.
4. **Expirarea nu depinde de niciun job.** Aceeași proprietate ca la engagement (Spec A §4.4): un
   job care nu rulează nu are voie să lase acces deschis.

`rls.has_company_access` primește ramura simetrică, cu condiția în plus că `company_id` al grantului
e nul sau egal cu compania cerută.

## 5. Cererea (`P-7`) și ecranul de consimțământ

`rls.request_support_access(p_tenant_id, p_company_id, p_request_ref, p_justification)` —
`SECURITY DEFINER`, deținută de `evidenta_rls`, cu scop îngust ca celelalte căi. Verifică în SQL,
acolo unde apelantul n-o poate uita:

- apelantul are rând viu în `platform_staff` cu `staff_role = 'support'`;
- tenantul există și nu e `archived`;
- `p_request_ref` și `p_justification` sunt nevide — un `''` nu e o justificare;
- scrie rândul `support_grant` **neaprobat** și rândul din `privileged_access_log` cu
  `path_code = 'P-7'`, `subject_tenant_id`, `justification` și `request_id`, în aceeași tranzacție.

Cererea nu dă acces. Ce dă acces e aprobarea, iar aprobarea o scrie clientul, prin politica lui.

Ecranul de consimțământ e cel din [ADR-017](017-terminologie.md), verbatim, cu numărul real:

> „Echipa Evidenta solicită acces temporar la datele companiei pentru rezolvarea solicitării #1234."

`request_ref` e `NOT NULL` tocmai fiindcă propoziția asta nu se poate scrie fără el. Un ecran care ar
spune „platforma solicită acces la datele dumneavoastră" cere aprobare pentru orice, oricând — și
`ADR-017` a numit deja concretețea drept cerință, nu stil.

**Cine aprobă:** un membru al tenantului cu o cheie nouă în catalogul din
[ADR-020](020-roluri-ca-date.md), `tenant.approve_support_access`, ținută implicit doar de rolul de
administrare creat cu tenantul. Cheia e nouă fiindcă ceva o impune — condiția pe care ADR-020 o pune
pentru orice cheie.

## 6. Ce se întâmplă în jur

- **Notificare** către contactul administrativ la cerere, la aprobare, la revocare și la expirare.
  Cele patru, nu doar prima: un client care a aprobat trebuie să vadă și când s-a închis.
- **Sesiunea de suport** se creează pe gazda tenantului, nu pe `admin.` — contextul de tenant vine
  din subdomeniu (`C8`), și pentru suport la fel. Ce diferă e `app.support_grant_id`, setat la
  deschidere și niciodată mai târziu.
- **Bara de context** spune, în interfața obișnuită, că sesiunea rulează pe un grant de suport și
  până când. Nu există „modul discret".
- **Revocarea instantanee** e a clientului, oricând, fără motivare — aceeași formă ca revocarea unui
  contract de deservire (Spec A §4.3, `INV-7`). Sesiunile deschise pe grantul revocat se invalidează
  în aceeași tranzacție, din același motiv ca la §4.3: RLS taie oricum, dar interfața rămasă deschisă
  produce erori în loc de un mesaj.

## 7. Consecințe

- **Devine posibil:** diagnosticul pe date reale, mărginit, enumerabil și consimțit; un raport de
  conformitate în care fiecare atingere a datelor unui client are un număr de solicitare.
- **Devine imposibil:** accesul tăcut al platformei; accesul care supraviețuiește incidentului;
  scrierea platformei în registrul unui client.
- **Rămâne posibil și trebuie spus:** un angajat al platformei cu drepturi de bază de date atinge
  orice. Spec A §2.7.1 numește deja asta — RLS apără de aplicație compromisă și de erori de cod, nu
  de administratorul bazei. Acest ADR nu schimbă modelul de amenințare; îl respectă.
- **De modificat ca urmare:** Spec A §6.2 (`P-7` primește mecanism), §6.3 (`justification`
  obligatoriu la `P-7` — deja scris, acum are cine să-l scrie), §11 (`DN-18` trece în „decis").
- **Ce se verifică automat**, trei teste noi în suita de penetrare (`C13`, `T1` — sub rolul
  aplicației):
  1. grant neaprobat, `app.support_grant_id` setat → zero rânduri;
  2. grant aprobat dar `expires_at` în trecut → zero rânduri, **fără să fi rulat vreun job**;
  3. grant aprobat pe tenantul A, sesiune pe tenantul B → zero rânduri.

## 8. Ce rămâne deschis

**`OD-115` — clauza contractuală.** Alegerea are consecințe contractuale, nu doar tehnice: termenii
de utilizare trebuie să spună că platforma nu accesează datele fără aprobare per solicitare, și ce
se întâmplă când clientul refuză. Textul e juridic, deci nu se scrie aici — [ADR-002](002-guvernanta-deciziilor.md)
cere co-semnătură pentru conținut juridic, iar acest ADR se limitează la mecanism. **Mecanismul nu
așteaptă textul; textul nu are voie să descrie altceva decât mecanismul.**

## Surse

- Spec A §2.4 (predicatele), §2.7.1 (ce nu apără RLS), §2.8 (costul politicilor), §4.3 (revocarea),
  §4.4 (expirarea în predicat), §6.1–6.3 (`P-7`, `privileged_access_log`), §11 (`DN-18`).
- [ADR-017](017-terminologie.md) (textul ecranului de consimțământ),
  [ADR-020](020-roluri-ca-date.md), [ADR-041](041-ziua-ca-argument.md) §1 și §6,
  [ADR-076](076-planul-de-control-al-platformei.md).
- `CLAUDE.md` `R1`, `R10`, `C8`, `C13`, `T1`.
- Conversație 2026-08-31.
