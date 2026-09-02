# ADR-091 — Consola scrie datele de referință din procesul web, pe conexiunea rolului de referință, cu apelantul verificat

- **Stare:** Acceptat — tehnic (arhitectură delegată); proprietarul confirmă sau răsturnă, cu
  declanșatorul din §6
- **Data:** 2026-09-02
- **Decis de:** sesiunea de implementare (`evidenta-82`), la cererea proprietarului: *„mă aștept ca
  partea asta să fie setată în setările sistemului… dacă se schimbă TVA-ul?"*, apoi alegerea
  explicită a planului de control al platformei drept loc al ecranului
- **Închide:** nimic din registru — decizie descoperită la construirea primei pagini a consolei
  ([ADR-076](076-planul-de-control-al-platformei.md) §4.3, „Parametri fiscali")
- **Deschide:** `OD-133`
- **Atinge:** Spec A §6.1–§6.2 (nota de sub listă), Spec A §14 (nouă),
  `fiscal/parameters/console_views.py`, `fiscal/parameters/services/authoring.py`,
  `platform/api/permissions.py`

## 1. Contextul: două propoziții care par să se contrazică

[ADR-076](076-planul-de-control-al-platformei.md) a decis consola și a enumerat pagina „Parametri
fiscali" printre obiectele ei. Până azi, un parametru fiscal se scria dintr-un fișier TOML, prin
două comenzi de shell (`load_fiscal_parameters`, `activate_fiscal_parameters`), sub rolul
`evidenta_refdata`, prin `privileged_run` (`P-4`, [ADR-049](049-rolul-de-date-de-referinta.md)).
Proprietarul a cerut ca aceeași operațiune să existe în interfață.

Spec A §6.1 spune însă: *„Ce nu este acceptabil: același proces care servește cereri de utilizator
să poată comuta la un rol privilegiat."* Iar nota de sub §6.2 închide `DN-17` parțial „pe criteriul
«cine apelează»": `P-9` rămâne funcție `SECURITY DEFINER` **fiindcă e apelată dintr-o cerere de
utilizator**, pe când `P-3`, `P-4`, `P-5`, `P-10` rulează sub `evidenta_refdata` fiindcă le rulează
un operator din shell. Un buton „Activează" pe consolă e o cerere HTTP care apelează `P-4`. După
criteriul literal, calea ar trebui să devină funcție `SECURITY DEFINER` sau să plece din proces.

**Ce s-a măsurat înainte de a decide.** `config/settings/base.py` declară `DATABASES["refdata"]`
necondiționat, cu credențialele din mediu: **fiecare** proces care încarcă setările — serverul web,
workerul Celery, orice comandă `manage.py` — are conexiunea de referință la dispoziție. Izolarea pe
care propoziția din §6.1 o descrie nu există azi *ca proprietate a procesului*; există ca proprietate
a **codului** — nimic în afara lui `privileged_run` nu deschide conexiunea, iar `privileged_run` cere
un cod de cale și scrie rândul de jurnal. Deci ce protejează azi datele de referință nu e granița de
proces, e ușa unică și jurnalul ei.

## 2. Opțiuni evaluate

1. **Job Celery, într-un worker care are credențialele de referință, serverul web fără ele.**
   *Avantaje:* singura variantă în care propoziția din §6.1 devine adevărată la nivel de proces.
   *Dezavantaje:* interfața devine asincronă pentru o operațiune de o secundă (ciornă scrisă,
   „așteptați"); cere două deployment-uri cu medii diferite, care azi nu există — în dezvoltare nu
   rulează niciun worker; și **nu schimbă ce poate face un proces web compromis**: poate pune în
   coadă exact același job. Mută unde se execută scrierea, nu cine o poate cere.
   *Cost de schimbare ulterioară:* mic, dacă ușa rămâne serviciul (vezi §4).
2. **Funcție `SECURITY DEFINER` per operațiune, deținută de `evidenta_rls`**, ca `P-9`.
   *Avantaje:* consecvent cu criteriul literal „cine apelează". *Dezavantaje:* contrazice motivul
   pentru care există `evidenta_refdata` — ADR-049 a scos scrierile de referință **din** funcțiile cu
   `BYPASSRLS`, ca „ce rulează privilegiat" să fie o proprietate a rolului, nu a unei liste de
   funcții; semnătura ar purta un `jsonb` de valoare, un act cu publicările lui și o margine — adică
   logica de validare din `authoring.py` rescrisă în PL/pgSQL, a doua copie a aceleiași reguli.
   *Cost de schimbare:* mare — o funcție privilegiată acordată e presupusă de tot ce se scrie după.
3. **Procesul web, pe conexiunea `evidenta_refdata`, prin `privileged_run`, cu apelantul verificat
   în `platform_staff` și ștampilat ca `actor_user_id`.** *Avantaje:* aceeași ușă, același rând de
   jurnal, aceeași regulă ca pentru comenzi — și, în plus faţă de comenzi, **un apelant identificat**
   (comanda are doar login-ul de sistem de operare, `default_actor()`); pe gazda `admin.` nu există
   context de tenant, deci scrierea nu poate amesteca date de client; sincron, ceea ce e forma
   corectă pentru „scrie o ciornă, apoi activează". *Dezavantaje:* propoziția din §6.1 rămâne
   neadevărată la nivel de proces — cum e și azi — și se spune. *Cost de schimbare:* mic: ușa e
   serviciul, nu vederea (§4).

## 3. Decizia

**Opțiunea 3.** Consola apelează `P-4` din procesul web, pe conexiunea rolului de referință, prin
`privileged_run`, după ce clasa de permisiune a verificat — în contextul cererii, prin politica
`platform_staff_self` — că apelantul e un `operator` viu. Rândul din `privileged_access_log` poartă
`actor = "console:operator"`, `actor_user_id` al persoanei și `request_id` al cererii.

Criteriul „cine apelează" din nota de sub §6.2 se **precizează**, nu se abandonează: `P-9` rămâne
`SECURITY DEFINER` fiindcă apelantul ei e **un utilizator al unui tenant**, care acționează asupra
propriului spațiu și nu trebuie să vadă nimic altceva; consola apelează `P-4` ca **angajat al
platformei**, pe o gazdă fără tenant, asupra unor tabele care nu sunt ale nimănui. Sunt două
categorii de apelant, nu două transporturi.

## 4. Consecințe mecanice

- **Ușa e serviciul, nu comanda și nu vederea.** Regulile scrierii (actul cu `effective_from`,
  ciorna, marginea cu temeiul ei, valoarea activă needitată, activarea refuzată fără margine) s-au
  mutat din `load_fiscal_parameters` în `fiscal/parameters/services/authoring.py`; comenzile și
  consola îl apelează amândouă. O a doua copie a regulii „o valoare activă nu se editează" ar fi
  divergat la primul câmp nou.
- **Cine poate apăsa e verificat în cod, nu afirmat într-un ADR.** `platform/api/permissions.py`
  refuză unui `support` ușa `P-4` — ceea ce `OD-113` consemna ca lipsă. `OD-113` rămâne deschisă
  pentru catalog (când lista de acțiuni crește), nu pentru verificare.
- **Ce nu face consola.** Versiunile de logică (`[[logic]]`) rămân ale încărcătorului: numesc cod
  care trebuie desfășurat, ceea ce niciun ecran nu poate face. Parametrii cu `scope = company` nu se
  oferă: consola administrează platforma, nu statutul unui client (ADR-076 §2).
- **`platform_staff` se scrie azi dintr-o comandă, sub rolul de instalare.** Primul `admin` precede
  orice sesiune de consolă, deci nu poate fi acordat din consolă; e același act ca `create_tenant` și
  e scris la fel, fără rând de jurnal — shell-ul e propriul lui audit, ca la migrări. Calea prin care
  un `admin` acordă și retrage din consolă, cu rând de jurnal, e `OD-133`.
- **Spec A** primește nota de sub §6.2 completată și §14 (consola), conform ADR-076 §5.
- **Ce se verifică automat:** `tests/isolation/test_console.py` — un `support` primește 403 la
  scriere; un `operator` scrie o ciornă și rândul de jurnal îl numește; activarea fără margine e
  refuzată cu cod; activarea cu margine ștampilează aprobatorul o singură dată; o valoare activă nu
  se editează.

## 5. Ce devine posibil, imposibil, scump

- **Posibil:** răspunsul la „dacă se schimbă TVA-ul?" e un ecran: o versiune nouă cu data și actul,
  apoi „Activează", de către un operator identificat.
- **Imposibil prin construcție:** ca ecranul să scrie o valoare fără act sau să activeze una fără
  margine — refuzurile sunt ale serviciului, nu ale formularului.
- **Scump, deliberat:** orice altă scriere de referință din consolă (cursuri, plan de conturi) trece
  prin aceeași formă — un serviciu de autorat, o vedere care îl apelează sub `privileged_run` — sau nu
  trece.

## 6. Ce rămâne deschis și când se revine

- **Declanșatorul de revenire la opțiunea 1:** ziua în care deployment-ul de producție dă serverului
  web și workerului credențiale diferite. Atunci `DATABASES["refdata"]` dispare din procesul web,
  vederile consolei pun în coadă un task care apelează același `authoring.py`, iar ecranul așteaptă.
  Nimic din regulă nu se rescrie; se schimbă doar cine ține conexiunea.
- **`OD-133`** — calea privilegiată a administrării `platform_staff` din consolă.

## Surse

- Spec A §6.1, §6.2 (nota de sub listă), §6.3; [ADR-049](049-rolul-de-date-de-referinta.md);
  [ADR-076](076-planul-de-control-al-platformei.md) §2, §4.1–§4.3, §5.
- `CLAUDE.md` `R4`, `R15`, `C8`, `C10`, `D1`; §4 — „datele de referință se scriu sub rolul de date
  de referință, prin `privileged_run`, cu rând în `privileged_access_log`".
- Măsurat: `backend/config/settings/base.py`, `DATABASES["refdata"]` — declarat necondiționat.
- Conversație 2026-09-02.
