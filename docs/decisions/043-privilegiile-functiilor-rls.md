# ADR-043 — Operațiile pe obiectele lui `evidenta_rls` se fac sub rolul lui

- **Status:** Acceptat — decizie tehnică, sub regimul [ADR-002](002-guvernanta-deciziilor.md);
  proprietarul a cerut implementarea după ce defectul a fost măsurat
- **Data:** 2026-08-26
- **Închide:** defectul de privilegii; deschide `OD-64` pentru partea care nu se poate repara
- **Afectează:** `infra/bootstrap/0001_roles.sql` (`NOINHERIT`), fiecare migrare care creează o
  funcție în schema `rls`, `C30`, `C31`
- **Legate:** [ADR-003](003-rls-tenancy-tables.md) (rolul `evidenta_rls`),
  [ADR-012](012-sql-in-django-migrations.md), [ADR-026](026-autentificare-inainte-de-context.md)

## 1. Problema, care are o singură cauză și două fețe

`evidenta_owner` este `NOINHERIT`. Apartenența la `evidenta_rls` **nu îi dă privilegiile** decât
după un `SET ROLE` explicit — și asta e corect: exact de aceea rolul cu `BYPASSRLS` e separat.

Migrările care creează funcții în schema `rls` fac însă așa:

```sql
SET LOCAL ROLE evidenta_rls;
CREATE FUNCTION rls.x() ... SECURITY DEFINER ...;
RESET ROLE;
REVOKE ALL ON FUNCTION rls.x() FROM PUBLIC;   -- emis de OWNER
```

Ultima linie **nu face nimic**. Un `REVOKE` emis de cine nu deține obiectul produce un `WARNING`,
nu o eroare. SQL-ul rulează, migrarea trece, privilegiul rămâne.

Aceeași cauză, a doua față: fișierele `.down.sql` șterg funcțiile ca owner și cad cu
**„must be owner of function"**. `C30` spune că `reverse_sql` nu e opțional — reversul există și nu
rulează.

## 2. Ce s-a măsurat

Pe o bază migrată de la zero, citind `pg_proc.proacl`:

| | |
|---|---|
| funcții în schema `rls` | 25 |
| cu `EXECUTE` pentru PUBLIC | **22** |
| acordate explicit lui `evidenta_app` | 3 |

Printre cele 22: toate cele patru `auth_*` de dinaintea contextului (ADR-026), `resolve_session`,
`resolve_tenant_by_subdomain`, și **ambele căi privilegiate de acces**,
`provision_engagement_company_access` și `revoke_engagement_company_access`.

Demonstrat prin apel, sub rolul aplicației, nu doar din catalog:

- `rls.auth_lookup_user('…')` — **execută**;
- `rls.provision_engagement_company_access('…')` — ajunge la linia 9 din corpul funcției și e oprită
  de garda ei internă, **nu de privilegiu**.

Apărarea era scrisă în migrare, se credea în vigoare, și nu era.

Pentru fețele reversului: `migrate ledger zero` cade. Opt fișiere comise au defectul — `0014`,
`0015`, `0016`, `0023`, `0028`, `0030`, `0032`, `0036`.

## 3. Decizia

**Orice operație asupra unui obiect deținut de `evidenta_rls` — `CREATE`, `DROP`, `GRANT`,
`REVOKE` — se face sub `SET LOCAL ROLE evidenta_rls`.** Nu doar crearea, cum se făcea până acum.

`0041_rls_function_privileges` retrage `EXECUTE` de la PUBLIC pe toate cele 25, de data asta cu
efect, și îl acordă lui `evidenta_app` pe **mulțimea măsurată**: funcțiile apelate din Python
(`grep -r 'rls\.' backend/evidenta/`) reunite cu cele care apar în expresiile politicilor
(`pg_policy`) — o politică se evaluează ca utilizatorul care interoghează. Paisprezece funcții.

Cele unsprezece rămase sunt funcții de trigger sau ajutoare interne. PostgreSQL verifică `EXECUTE`
pe funcția de trigger la `CREATE TRIGGER`, nu la declanșare, deci retragerea nu costă nimic
**triggerelor deja create** — și scoate din raza aplicației opt funcții `SECURITY DEFINER` pe care
n-avea de ce să le poată apela. Pentru triggerele **următoare** costă, și de aici nu se vedea: §4.1.

## 4. Prevenirea stă în gardian, nu în schemă — și asta s-a măsurat

`ALTER DEFAULT PRIVILEGES … REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` pare mecanismul evident. **Nu
funcționează aici.** Încercat în ambele forme — cu `REVOKE` singur și cu `GRANT` explicit către
`evidenta_rls` —, în aceeași tranzacție și într-una nouă după commit: o funcție creată ulterior iese
cu ACL implicit, deci din nou cu `EXECUTE` pentru PUBLIC.

Prevenirea o poartă deci `backend/tests/schema_guard/test_function_privileges.py`, care interoghează
catalogul pe o bază construită de la zero la fiecare rulare. Prima migrare care adaugă o funcție fără
să-i retragă PUBLIC-ul face suita roșie. E idiomul proiectului oricum: un gardian, nu o convenție.

Al doilea gardian, `tests/architecture/test_reverse_migrations.py`, refuză orice fișier `.down.sql`
**nou** care șterge o funcție `rls.` fără `SET LOCAL ROLE`. Cele opt existente sunt enumerate ca
excepție care **poate doar să scadă**.

### 4.1 Ce a costat, și de aici nu se vedea: tiparul de creare a triggerelor

Măsurat de sesiunea vecină la câteva ore după ce decizia fusese aplicată, dând peste el în timp ce
scria `0042`.

Verificarea lui `EXECUTE` la `CREATE TRIGGER` nu se face pentru rolul care va **declanșa** triggerul.
Se face pentru rolul care **emite** `CREATE TRIGGER`, iar acela este proprietarul tabelei:
`evidenta_owner`. Care e `NOINHERIT` și nu moștenește nimic de la `evidenta_rls`.

Până la `0041`, tiparul „creează funcția sub `evidenta_rls` → `RESET ROLE` → `CREATE TRIGGER`" a
mers în fiecare migrare — **fiindcă PUBLIC avea `EXECUTE` implicit**, iar `evidenta_owner` e în
PUBLIC. Retrăgându-l, `0041` a scos de sub tipar suportul pe care nimeni nu observase că stă.
Triggerele existente nu sunt atinse: verificarea s-a făcut o dată, la crearea lor, înainte de
`0041`. Cad doar cele **noi**, cu „permission denied for function".

Reparația e o linie, și trebuie emisă **sub `evidenta_rls`** ca să aibă efect — un `GRANT` venit de
la un non-proprietar e un WARNING, nu o eroare, exact capcana din §2:

```sql
GRANT EXECUTE ON FUNCTION rls.<f>() TO evidenta_owner;
```

Nu slăbește nimic: `evidenta_app` nu primește nimic în plus, iar proprietarul oricum deține tabela
pe care atașează triggerul.

**Gardianul poartă mesajul, iar mesajul citează ADR-ul.** Prima variantă a acestei secțiuni spunea
că detecția nu e necesară fiindcă eșecul e zgomotos oricum. Proprietarul a corectat raționamentul, și
corectura e mai generală decât cazul: **documentația ajunge la cine caută, mesajul de eroare ajunge
la cine nu știe că trebuie să caute** — exact situația de aici, unde cineva scrie un trigger, primește
un refuz care nu pomenește `NOINHERIT`, și n-are niciun motiv să bănuiască existența unui ADR pe
subiect. Condiția care desființează alternativa în loc s-o aleagă: mesajul conține referința. **Mesajul
e ușa, ADR-ul e camera.**

Gardianul e `backend/tests/architecture/test_trigger_function_grants.py` și citește fișierele, nu
catalogul: pentru fiecare `CREATE TRIGGER … EXECUTE FUNCTION rls.<f>` dintr-un fișier `.up.sql`, dacă
`<f>` e creată în același fișier sub `SET LOCAL ROLE evidenta_rls` și nu primește `GRANT EXECUTE …
TO evidenta_owner` emis tot sub acel rol, migrarea **va** cădea la aplicare. Prinsă înainte de
`make migrate`, nu în timpul lui.

**Ce spune despre §3.** Propoziția „retragerea nu costă nimic" era adevărată pentru ce fusese
măsurat — cele unsprezece funcții existente, cu triggerele lor deja create — și falsă pentru ce nu
fusese măsurat: următoarea funcție de trigger. Diferența dintre a măsura o **stare** și a măsura o
**tranziție**. Măsurătoarea era bună; concluzia era mai largă decât ea.

## 5. Inversele corectate — `OD-64`

### 5.0 Criteriul: nu toate „migrările inverse" sunt același lucru

Cele opt s-au clasificat **înainte** de a fi tratate, iar clasificarea a schimbat sarcina. Criteriul
se scrie aici fiindcă el, nu reparația, e ce previne recidiva în afara gardianului: cele opt sunt
gata, următoarea nu e scrisă încă.

| Categoria | Ce înseamnă | Ce se declară |
|---|---|---|
| **Schemă pură** | adaugă o coloană, un index, o constrângere | reversibilă genuin, permanent — inversul restaurează exact starea |
| **Transformă date** | rescrie valori existente | inversul **aproximează**, nu restaurează. `irreversible` **din clipa în care există date postate** |
| **RLS și roluri** | politici, triggere, funcții `SECURITY DEFINER` | reversibilă, dar cu inversul **rulat** în test, nu declarat |

A treia e cea mai periculoasă, și nu fiindcă ar fi cea mai complicată: **o inversare care lasă o
politică pe jumătate detașată nu produce o eroare, produce acces greșit.** Fail-closed tăcut — exact
modul de eșec găsit la funcțiile `SECURITY DEFINER` din §2. Un invers de schemă care cade, cade
zgomotos; unul de politică reușește și minte.

**Întrebarea care decide, pentru fiecare migrare, e una singură: atinge date deja postate?**

- **Nu** → reversibilă, cu test care rulează inversarea și verifică starea, nu doar că n-a aruncat.
- **Da** → `IrreversibleError` explicit. **Niciodată `noop`.**

Un `noop` pe o migrare care a transformat date e o minciună consemnată în cod: rulează, nu eșuează,
și lasă baza într-o stare pe care n-a descris-o nimeni. Într-un registru append-only e mai rău decât
o eroare, fiindcă descoperirea vine mult mai târziu — și `R10` înseamnă că nu există `UPDATE` cu care
s-o repari.

Simetric, și la fel de dăunător: **`IrreversibleError` pe ceva reversibil de drept.** Ambele îl fac
pe cel care citește codul peste un an să creadă altceva decât adevărul, doar în direcții opuse. De
aceea gardianul acceptă ambele declarații și nu forțează niciuna.

Cele opt fișiere nu se repară prin editare: `C31` le face append-only din clipa aplicării. Corecția
sunt **opt fișiere noi**, `0042`–`0049`, iar `run_sql_file` primește un `down_name` care le indică.
Direcția de dus nu se schimbă deloc — același fișier, aceeași amprentă. Se schimbă doar din ce fișier
se citește inversul, iar acel invers **nu rulase niciodată**, deci nu se falsifică niciun istoric.

Patru lucruri sunt parte din contract, nu detalii de stil:

- **Ordinea: triggere, apoi politici, apoi funcții.** Verificată de test, fiindcă la patruzeci de
  linii nu se mai vede la review și se manifestă abia când cineva chiar derulează înapoi.
- **Fără `CASCADE`.** Un `CASCADE` nu se oprește la ce a creat migrarea: poate șterge obiecte
  atașate între timp de altă migrare, tăcut, raportând succes. Dacă un `DROP` cade pe dependență,
  eroarea e informație.
- **Rotația se testează sub rolul care o va rula** — `evidenta_owner`, prin conexiunea de migrare.
  Rulată ca superuser ar trece întotdeauna și ar eșua în producție: verde din motivul greșit.
- **Rotație, nu inversare:** `down`, apoi `up` din nou, cu catalogul comparat înainte și după. „N-a
  aruncat" nu e afirmația; „baza e unde a plecat" este. A doua aplicare prinde funcția rămasă,
  numele de politică ciocnit, triggerul orfan.

Plus proba că reparația era necesară: un test asertează că inversul **original** încă eșuează cu
„must be owner of function". Fără el, nimic n-ar distinge „am reparat un defect" de „am rescris un
fișier care mergea".

### 5.1 De ce `0028` e reversibil, și de ce motivul evident e greșit

`0028_auth_request_path` e singura dintre cele opt care transformă date: adaugă `token_hash` și umple
rândurile existente. Argumentul tentant — *„șterge doar datele pe care el le-a creat"* — e adevărat
azi și **se rupe tăcut**: din clipa în care producția scrie token-uri reale, inversul șterge date pe
care nu le-a creat el. Cine aplică peste un an raționamentul „date auto-create" unei coloane care nu
e efemeră ajunge la concluzia greșită.

Motivul real este **regenerabilitatea**: o amprentă de token e efemeră prin natură. Nu se pierde
informație, se pierd sesiuni. Consecința operațională e scrisă în fișier fiindcă cine derulează
înapoi în producție trebuie s-o știe dinainte: **toată lumea se deloghează.**

### 5.2 Recidiva

Orice migrare care atinge `journal_entry`, `journal_line` sau perioadele declară
`REVERSIBILITY = "reversible-tested"` sau `"irreversible"`. **Niciodată niciuna, niciodată `noop`** —
un `noop` rulează, nu eșuează, și lasă baza într-o stare pe care n-a descris-o nimeni; într-un
registru append-only e mai rău decât o eroare, fiindcă descoperirea vine mult mai târziu.

Gardianul acceptă **ambele** declarații: ireversibilitatea forțată acolo unde ceva e reversibil de
drept e o minciună la fel de dăunătoare ca `noop`-ul pe ceva ireversibil, doar în direcția opusă. Iar
`"reversible-tested"` nu e o etichetă: gardianul cere ca fișierul să fie în lista rotită efectiv.

## 6. Ce rămâne deschis

`OD-64` este **închisă** prin §5. Ce rămâne din ea e doar constatarea generală care a produs-o: o
migrare inversă nu e exercitată de nimic, iar `C30` cerea existența fișierului, nu funcționarea lui.

## 7. De ce nu s-a văzut

Aceeași formă ca restul constatărilor din 25–26 august: **SQL-ul a rulat, nimic n-a strigat, efectul
n-a existat.** Gardianul de model verifică tabele și politici, nu setări de privilegii; harness-ul
construiește baza de la zero, deci reproduce fidel aceeași stare greșită la fiecare rulare; iar
migrările inverse nu sunt exercitate niciodată — o derulare înapoi e lucrul de care ai nevoie în ziua
în care restul a mers deja prost.
