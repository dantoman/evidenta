# ADR-026 — Autentificarea precede contextul, deci trece prin căi privilegiate înguste

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Afectează:** `platform/identity`, Spec A §3.2 și §6, `infra/migrations/0026_auth_request_path.up.sql`

## Context

Spec A §3.2 numerotează doi pași înaintea tranzacției: (1) rezolvă subdomeniul → tenant,
(2) autentifică utilizatorul. Amândoi preced contextul, prin definiție.

Pasul 1 avea deja răspunsul: `rls.resolve_tenant_by_subdomain`, funcție `SECURITY DEFINER` îngustă
(F0.3.5). Pasul 2 nu îl avea, iar consecința nu era teoretică: serviciile de autentificare livrate
la F0.3.7b existau, dar nu puteau fi apelate de pe nicio cerere. Testele le exercitau deschizând
manual un context — adică presupunând rezolvat exact ce autentificarea trebuie să producă.

Motivul e `app.current_user_id()`, care este **fail-closed**: fără context ridică excepție, nu
întoarce `NULL`. Deci nicio politică `self_row` — `user`, `mfa_method`, `mfa_backup_code`,
`user_session` — nu poate răspunde înainte de autentificare. Nici măcar pentru rândul propriu:
„propriu" este tocmai ce nu se știe încă.

## Opțiuni evaluate

**A. Funcții `SECURITY DEFINER` înguste, una per operațiune.** *Avantaje:* aceeași disciplină ca
pasul 1 și ca Spec A §6.1 — scop îngust, semnătură care nu acceptă SQL, niciun câmp de business
întors. Judecata (filtrul `confirmed_at`, viața sesiunii, consumarea unui cod într-o singură
instrucțiune) stă în SQL, deci un apelant nu poate uita o condiție de care depinde securitatea.
*Dezavantaje:* patru funcții în plus, fiecare o suprafață care trebuie justificată.
*Cost de schimbare:* mic.

**B. Un al doilea rol de bază de date cu granturi doar pe tabelele de identitate.** *Avantaje:* o
singură graniță, explicită. *Dezavantaje:* Spec A §6.1 o exclude cu propriile cuvinte — „nu este
acceptabil ca același proces care servește cereri de utilizator să poată comuta la un rol
privilegiat". Procesul care servește cereri este exact cel care autentifică. *Cost de schimbare:*
mare — granița se mută la nivel de proces.

**C. Deschiderea contextului după verificarea parolei**, apoi ORM pentru restul. *Avantaje:* ar
reduce totul la o singură funcție privilegiată. *Dezavantaje:* un context de bază de date obținut cu
parola singură. Este exact ce `ADR-021` interzice la nivel de aplicație, mutat cu un strat mai jos,
unde nu se mai vede. *Cost de schimbare:* —

## Decizie

**Opțiunea A**, cu o graniță trasată explicit:

**Trec prin cale privilegiată** doar interogările care preced identitatea verificată:
`rls.auth_lookup_user`, `rls.auth_mfa_methods`, `rls.auth_backup_codes`,
`rls.auth_spend_backup_code` și `rls.resolve_session`.

**Nu trec** — și nu au voie să treacă — emiterea sesiunii, marcarea ultimei autentificări și
revocarea proprie. După ce parola **și** al doilea factor au fost verificate, identitatea este
cunoscută, contextul se poate deschide, iar `user_session_self` scrie rândul prin ORM ca orice alt
rând al utilizatorului. O funcție privilegiată acolo ar fi o gaură deschisă fără să fie nevoie.

## Relația cu enumerarea limitativă din Spec A §6.2

Lista `P-1`…`P-8` enumeră limitativ căile **cross-tenant**. Niciuna dintre funcțiile de mai sus nu
este cross-tenant: fiecare răspunde despre un singur cont sau o singură sesiune, iar `resolve_session`
întoarce tenantul sesiunii, nu date ale vreunui tenant. Sunt căi *anterioare contextului*, categoria
lui `rls.resolve_tenant_by_subdomain` — mecanismul din §6.1, nu o intrare în §6.2.

Prin urmare lista rămâne neschimbată. Ce se schimbă este că §6.1 are acum două utilizări, nu una, și
ADR-ul de față este locul unde a doua e consemnată.

## Consecințe

- `authenticate()` cere `tenant_id`: sesiunea se emite pentru tenantul gazdei, iar una fără tenant
  n-ar autentifica nimic.
- Verificarea accesului la emitere se face **întrebând baza**, prin vizibilitatea rândului din
  `tenant` — aceeași `rls.has_tenant_access` pe care o folosește orice interogare ulterioară. O
  reimplementare în Python ar fi a doua copie a regulii de acces, liberă să se abată de la cea care
  apără efectiv datele.
- Sesiunea are `token_hash`: cheia primară identifică, tokenul autentifică, și nu mai sunt aceeași
  valoare. Un dump al bazei nu conține nicio sesiune folosibilă.
- Rămâne deschis, și **nu** este închis aici: înrolarea MFA a unui utilizator care nu are încă un al
  doilea factor nu are cale de request. Nu poate obține sesiune (`ADR-021`), deci nu poate ajunge la
  ecranul de înrolare. Vezi `OD-46`.
