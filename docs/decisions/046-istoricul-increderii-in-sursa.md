# ADR-046 — Încrederea în sursă are istoric, fiindcă o confirmare nu schimbă valoarea

- **Status:** Acceptat — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md); golul a
  fost găsit de proprietar în designul livrat
- **Data:** 2026-08-26
- **Afectează:** `fiscal_parameter`, `infra/rls/exceptions.toml` (`R1`), `R15`
- **Legate:** [ADR-044](044-data-de-rezolutie.md), [ADR-045](045-sursa-de-adevar-pentru-parametri.md),
  [ADR-043](043-privilegiile-functiilor-rls.md), `OD-22`, `OD-56`

## 1. Golul

`fiscal_parameter` primise o coloană `source_confidence` — `confirmed` sau `provisional` — plus motivul
deducției. Cazul care a cerut-o: **cuantumurile scutirilor pe 2026 nu se pot cita.** SFS publică
valorile abia în comunicatul retrospectiv anual, deci pentru 2026 încă nu există niciuna; ce există e
valoarea din 2025 plus două liste exhaustive de modificări care nu ating art. 33–35. Destul de solid ca
să calculezi, nu destul ca să aperi la un control — **și astea sunt afirmații diferite.**

Coloana singură răspunde însă doar la *„e dedusă acum?"*. Întrebarea unui control e cealaltă:

> **La data la care ați depus, pe ce vă bazați?**

**Confirmarea unei valori nu schimbă valoarea.** Deci nu e o versiune nouă cu `valid_from` nou — e o
editare în loc a unei singure coloane. Iar editarea **șterge exact faptul cerut**: din momentul în care
SFS publică, `provisional_in_force` pe o dată din martie întoarce zero rânduri, deși calculul din martie
chiar s-a făcut pe o deducție.

## 2. Decizia

**Încrederea devine append-only.** Fiecare stare prin care trece un parametru se scrie ca eveniment în
`fiscal_parameter_confidence_event`, cu:

- starea (`confirmed` / `provisional`) și motivul deducției **fotografiat la acel moment** — formularea
  se poate edita ulterior, iar rostul rândului e ce se credea atunci;
- `note`, obligatorie: *„SFS a publicat nota anuală la 30.03.2027"* e un răspuns, *„confirmat"* nu e;
- `effective_at`, **furnizat de apelant**, nu implicit `now()` — retrodatarea unei tranziții petrecute
  înainte ca tabela să existe e un caz real, iar o coloană care poate spune doar „acum" nu-l poate
  exprima.

Starea curentă rămâne pe parametru, pentru interogarea frecventă; evenimentul e ce face trecutul
recuperabil. Serviciul le scrie pe amândouă într-o tranzacție, ca să nu se poată face jumătate.

`provisional_in_force` capătă a doua axă: `effective_date` e **fereastra fiscală**, `as_known_at` e
**momentul despre care se întreabă**. Fără a doua, funcția raportează convingerile de azi despre o
perioadă trecută — adevărat despre acum, fals despre depunere.

## 3. Aceasta este varianta mai slabă din două, și merită spus

Cealaltă, propusă de proprietar, e ca **însuși calculul să-și ștampileze la postare versiunea de
parametru și încrederea de atunci** — aceeași disciplină ca *„suma postată e autoritativă, nu
recalculată"*.

Ea e mai robustă, și motivul e precis. Reconstituirea din tabela asta presupune că rezoluția e
reproductibilă. [ADR-044](044-data-de-rezolutie.md) chiar garantează asta — dar garanția acoperă
**regula**, nu o corecție ulterioară a **rândului**. Dacă cineva repară mai târziu o greșeală de
introducere într-un parametru, re-rezolvarea dă alt răspuns decât cel folosit efectiv, iar istoricul de
încredere nu semnalează nimic: el spune cât de ferm era atașat numărul, nu care era numărul.

**Ștampila aparține motorului de postare**, deci altui modul. Tabela asta e ce poate livra `fiscal` pe
cont propriu — și e chiar ce ar înregistra ștampila.

## 4. Append-only impus de bază, nu de convenție

Un trigger refuză `UPDATE` și `DELETE`. Motivul e același ca la registru: **starea la un moment trecut
trebuie să rămână recuperabilă după ce starea prezentă se schimbă**, iar o istorie rescriibilă nu
răspunde întrebării pentru care există — și rescrierea n-ar lăsa urmă, ceea ce e chiar modul de eșec.
Corecția e un eveniment nou, cu `note` care spune ce corectează.

Triggerul ține și împotriva căii privilegiate: testul îl exercită sub administratorul de test, care
ocolește RLS și **e refuzat oricum**.

## 5. Clasificarea RLS — și de ce e ADR

`R1` cere ca modificarea lui `infra/rls/exceptions.toml` să fie ADR. Tabela intră în aceeași clasă cu
`fiscal_parameter` și `fiscal_parameter_source`: **globală, citibilă de oricine, scriibilă prin `P-4`**.

Motivul nu e simetria, ci conținutul: **când SFS publică nota anuală, faptul e același pentru toți
tenanții.** Un istoric de încredere per tenant ar însemna că doi tenanți pot da răspunsuri diferite
aceluiași control despre același act normativ.

## 6. Ce nu se poate exercita azi, spus explicit

**`P-4` nu are mecanism.** `fiscal_parameter` are `INSERT`/`UPDATE` retrase de la `evidenta_app`, iar
politica admite doar `SELECT` — deci nici scrierea parametrilor, nici tranziția de încredere nu se pot
executa end-to-end. **Este exact același gol ca `OD-56`** pentru încărcarea planului de conturi, pe altă
tabelă.

Serviciul primește de aceea conexiunea **explicit**, prin `using`, în loc s-o aleagă singur: un serviciu
care ar întinde tăcut mâna după o conexiune privilegiată ar fi o cale privilegiată pe care n-a declarat-o
nimeni.

Ce se testează azi: **refuzurile**, care se produc înainte de orice scriere, și **garanțiile bazei**
asupra rândurilor odată ce există. Ce nu se testează: dubla scriere, până există `P-4`.

## 7. Ce s-a respins

**`db_default` pentru `source_confidence`.** Măsurat: `default=` din Django se aplică în Python și
migrarea scoate defaultul din bază, deci un `INSERT` brut care omite coloana **cade tare**. E rezultatul
dorit — parametrii intră prin SQL privilegiat, și cine încarcă o cotă trebuie să spună dacă a fost citită
în act. Un `db_default` ar schimba comportamentul tăcut, motiv pentru care există un test care fixează
exact acest eșec.

**Un eveniment care repetă starea curentă.** Refuzat: ar adăuga un rând care nu schimbă nimic, dar ar
face istoria să pară că s-a întâmplat ceva — iar un cititor ar data tranziția la momentul greșit.

**Un `PROVISIONAL` implicit când istoria nu ajunge înapoi până la momentul cerut.** Arată a prudență, și
tocmai de-aia e rău: rămâne o afirmație despre pe ce s-a bazat cineva, în direcția care nu se verifică
fiindcă se citește ca grijă. `confidence_at` ridică eroare.
