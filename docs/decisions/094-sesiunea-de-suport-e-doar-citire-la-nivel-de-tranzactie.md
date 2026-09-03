# ADR-094 — Sesiunea de suport e doar-citire la nivel de tranzacție, nu de serviciu

- **Stare:** Acceptat — tehnic (arhitectură delegată); proprietarul confirmă sau răsturnă
- **Data:** 2026-09-03
- **Decis de:** sesiunea de implementare (`evidenta-82`), la construirea lui ADR-077 sub instrucțiunea
  proprietarului: *„încearcă să implementezi ce este posibil"*
- **Închide:** nimic din registru; **construiește** [ADR-077](077-grantul-de-suport.md) integral
  (`DN-18`, `P-7`), cu excepția notificării de expirare (§4)
- **Atinge:** `platform/rls/context.py`, `platform/rls/middleware.py`, `infra/bootstrap/0002`,
  `infra/bootstrap/0003`, `infra/migrations/0077`, `platform/support`, Spec A §6.2 și §14

## 1. Problema: „doar citire" era o proprietate fără mecanism

[ADR-077](077-grantul-de-suport.md) §3.1 decide că grantul de suport **nu are nivel de permisiune**
și că **nu există grant de scriere**: suportul diagnostichează, nu contabilizează (`INV-9`, `R10`).
Dar mecanismul decis — ramura a treia a predicatelor `rls.has_tenant_access` și
`rls.has_company_access` — deschide **politica**, și politicile din acest sistem sunt `FOR ALL`, cu
același predicat în `USING` și în `WITH CHECK`. O sesiune pe grant ar fi putut, la nivel de politică,
să scrie orice poate citi. Ce ar fi oprit-o erau verificările de permisiune din servicii — acolo unde
există; nu toate serviciile verifică o cheie, și niciuna n-a fost scrisă gândindu-se la un apelant
care nu e membru.

## 2. Opțiuni evaluate

1. **Predicatul se despică**: un `rls.has_tenant_read_access` cu ramura de grant, folosit în
   `USING`, și predicatul vechi, fără ramură, în `WITH CHECK`. *Dezavantaje:* toate politicile
   existente — zeci de migrații, append-only (`C31`) — ar trebui rescrise printr-o migrare nouă
   fiecare; iar gardianul de model verifică forma declarată a politicii, care s-ar schimba peste tot.
   *Cost:* mare, și riscul e exact în locul unde o greșeală deschide totul.
2. **Verificare în servicii**: fiecare serviciu care scrie refuză când contextul poartă un grant.
   *Dezavantaje:* disciplinară, nu structurală — următorul serviciu scris fără verificare scrie.
   E clasa de apărare pe care Spec A §2.7.1 o numește insuficientă singură.
3. **Tranzacția e doar-citire**: `tenant_context` execută `SET TRANSACTION READ ONLY` când
   contextul poartă `support_grant_id`; PostgreSQL refuză orice `INSERT`, `UPDATE`, `DELETE` din
   tranzacție, prin orice politică, orice serviciu, orice scăpare. Deasupra, middleware-ul refuză
   metodele nesigure ale unei sesiuni pe grant **înainte** de vedere, cu cod stabil
   (`support.read_only`, 403), ca refuzul să se poată spune în cuvinte și nu ca eroare de bază.
   *Măsurat pe PostgreSQL 18:* `SET TRANSACTION READ ONLY` e acceptat după interogările
   `set_config(...)` care deschid contextul și refuză scrierea următoare. *Dezavantaje:* două
   excepții enumerate — emiterea sesiunii de suport (scrie `user_session`) și `logout` (o revocă) —
   trec cu `read_only=False`, respectiv pe lista `SUPPORT_WRITABLE_PATHS`. *Cost de schimbare:* mic.

## 3. Decizia

**Opțiunea 3, cu opțiunea 2 ca strat de mesaj.** Doar-citirea e a bazei; middleware-ul o spune
înainte. Nicio politică nu se rescrie, niciun serviciu nu are de știut ce e un grant.

Trei alegeri de implementare, consemnate fiindcă ar invalida cod dacă s-ar schimba:

- **Grantul călătorește cu sesiunea, nu cu cererea.** `user_session.support_grant_id` se scrie la
  emitere și niciodată mai târziu (ADR-077 §6); `rls.resolve_session` îl întoarce și **refuză să
  rezolve o sesiune al cărei grant a fost revocat sau a expirat**. Așa se face „invalidarea sesiunilor
  în aceeași tranzacție" fără o a doua funcție: următoarea cerere a suportului primește 401.
- **Suportul intră pe gazda clientului cu contul lui obișnuit.** Aceeași parolă, același al doilea
  factor; abia după ce politicile clientului nu-l admit ca membru sau ca firmă, autentificarea
  întreabă `rls.auth_support_grant` și, dacă există un grant viu, emite sesiunea cu el. Un membru care
  are și un grant intră ca membru; sesiunea lui nu e doar-citire.
- **Notificarea cererii se scrie în funcția `P-7`.** Dispatch-ul Python trece prin
  `rls.notify_tenant_members`, care cere `rls.has_tenant_access` — un context de tenant pe care
  consola nu-l are prin construcție (măsurat: a refuzat). Funcția scrie aceleași rânduri, cu același
  proprietar. Aprobarea și revocarea notifică din contextul clientului, pe calea obișnuită.

## 4. Ce s-a construit și ce nu

- **Construit:** `support_grant` (ADR-077 §3, cu toate constrângerile, plafonul de 72 h în bază);
  ramura a treia în ambele predicate (`infra/bootstrap/0003`) și variabila `app.support_grant_id`
  (`0002`); `rls.request_support_access` (`P-7`, cu rândul de jurnal și notificarea);
  `rls.auth_support_grant`; `rls.resolve_session` cu grantul; cheia `tenant.approve_support_access`
  (identity/0011, în rolul de administrare); aprobarea și revocarea din spațiul clientului, cu
  propoziția de consimțământ din ADR-017 verbatim; pagina consolei (listă pentru toți, cerere pentru
  `support`); bara sesiunii de suport în interfața obișnuită; notificări la cerere, aprobare,
  revocare.
- **Neconstruit, cu motivul:** notificarea la **expirare** — expirarea nu e un eveniment, e o
  comparație cu `now()` în predicat (ADR-077 §4, pct. 4), deci n-are cine s-o trimită fără un job;
  grantul **pe o singură companie** din consolă — consola nu poate lista companiile unui client (ADR-076
  §2), deci nu le poate numi; coloana și ramura există, calea de cerere pe companie nu.
- **Ce se verifică automat:** `tests/isolation/test_support_grants.py` — cele trei teste din ADR-077
  §7, plus: variabila singură nu deschide nimic; grantul pe o companie deschide o companie; `P-7` doar
  de pe consolă și doar pentru `support`; aprobarea cere cheia și plafonul; sesiunea de suport citește,
  primește `support.read_only` la scriere, e refuzată pe alt spațiu și moare la revocare; sub context
  de grant baza refuză un `UPDATE` cu „read-only transaction".

## 5. Consecințe

- **Devine posibil:** diagnosticul pe date reale, consimțit, mărginit, enumerabil — și doar-citire
  printr-o proprietate a tranzacției, nu prin disciplina serviciilor.
- **Devine imposibil prin construcție:** ca o sesiune de suport să scrie ceva, oriunde, chiar și
  printr-o vedere care n-a auzit de granturi.
- **Scump, deliberat:** orice viitor „grant de scriere" — ADR-077 §3.1 spune că ar fi un ADR nou; acum
  ar trebui să și ridice `READ ONLY`, adică să atingă exact linia de aici.

## Surse

- [ADR-077](077-grantul-de-suport.md) §3.1, §4, §5, §6, §7; [ADR-017](017-terminologie.md) (textul
  consimțământului); [ADR-076](076-planul-de-control-al-platformei.md) §2, §4.2;
  [ADR-041](041-ziua-ca-argument.md) §1.
- Spec A §2.7.1, §2.8, §6.1–§6.3; `CLAUDE.md` `R10`, `C8`, `C13`, `T1`, `T2`.
- Măsurat: `SET TRANSACTION READ ONLY` după `set_config`, PostgreSQL 18; `rls.notify_tenant_members`
  sub context de consolă → `notifications.no_access_to_tenant`.
- Conversație 2026-09-03.
