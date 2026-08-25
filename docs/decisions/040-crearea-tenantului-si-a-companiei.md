# ADR-040 — Crearea unui tenant și a unei companii este cale privilegiată

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Închide:** `OD-53`
- **Modifică:** Spec A §6.2 (lista căilor privilegiate — adaugă `P-9`), §12 (nou)
- **Legate:** [ADR-003](003-rls-tenancy-tables.md), [ADR-004](004-company-context.md),
  [ADR-039](039-valuta-si-perioade.md) §11

## 1. Problema, care nu e de produs

Politica pe `company` cere `rls.has_company_access(id)` **și în `WITH CHECK`**. Un `INSERT` prin
rolul aplicației este deci imposibil: compania nu are cum să aibă acces la ea însăși înainte de a
exista. Măsurat, nu dedus — nicio linie de cod de producție din `backend/evidenta/` nu creează o
companie sau un tenant. Există doar în fixture-uri, ca superuser.

La `tenant` e la fel, dintr-un motiv mai adânc: `tenant` este rădăcina contextului. Politica lui
este `id = app.current_tenant_id() AND rls.has_tenant_access(id)`. Crearea unui tenant se petrece
**înainte să existe un context de tenant** — deci prin construcție nu poate trece prin calea
obișnuită. Aceeași formă ca autentificarea, care precedă contextul ([ADR-026](026-autentificare-inainte-de-context.md)).

Nu e o omisiune de implementare. Este consecința directă a politicilor fail-closed, și e corectă:
alternativa ar fi o politică mai largă pe cele două tabele rădăcină, adică exact fundația slăbită.

## 2. Decizia

**`P-9` — provizionarea unui tenant sau a unei companii.** O cale privilegiată nouă în enumerarea
limitativă din Spec A §6.2, cu aceleași obligații ca celelalte opt: scop îngust, semnătură fără SQL
sau nume de tabele, înregistrare obligatorie în `privileged_access_log` în aceeași tranzacție, și un
test care demonstrează că funcția nu poate fi folosită pentru altceva.

Două funcții, nu una, fiindcă premisele diferă:

| Funcție | Context la apel | Cine poate | Ce verifică SQL-ul |
|---|---|---|---|
| `rls.provision_tenant` | **Niciunul** — precede contextul | Platforma, sau o firmă care creează un tenant client | subdomeniu liber și nerezervat; creatorul e un utilizator existent și activ |
| `rls.provision_company` | Tenantul în care se creează | Un membru cu permisiunea de administrare a tenantului | `rls.has_tenant_access(p_tenant_id)`; IDNO neutilizat în tenant |

### 2.1 Cel care creează primește acces, în aceeași tranzacție

**Da**, cu `granted_via = 'membership'`. Alternativa — companie creată fără acces — produce în chiar
tranzacția de creare o companie pe care creatorul n-o poate vedea, deci nici configura. Ar fi un
sistem care refuză imediat ce tocmai a acceptat.

`rls.provision_company` apelează `engagement.services.provisioning.provision_company_access` în
aceeași tranzacție, astfel încât o companie creată într-un tenant cu engagement
`covers_all_companies = true` să primească pe loc și accesele derivate din engagement. **Fără asta,
`IZ-27` redevine literă moartă**: un engagement care acoperă toate companiile ar acoperi exact
companiile existente la semnare.

### 2.2 Ce nu face `P-9`

Nu creează utilizatori, nu acordă permisiuni în afara celei pe compania nou-creată, nu atinge
companii existente. Un apel care ar putea face oricare dintre acestea n-ar mai avea scop îngust,
adică n-ar mai fi cale privilegiată, ci o poartă.

## 3. De ce nu prin rol separat

Spec A §6.1 lasă deschisă alternativa unui rol cu `BYPASSRLS` folosit de procese dedicate. Nu se
aplică aici: crearea unui tenant sau a unei companii este declanșată de o **cerere de utilizator**,
în procesul care servește cereri. Spec A spune direct ce nu e acceptabil — „același proces care
servește cereri de utilizator să poată comuta la un rol privilegiat".

Funcție `SECURITY DEFINER`, deci, cu judecata în SQL. Aceeași formă ca la revocare
(`rls.revoke_engagement_company_access`) și la notificări: condiția pe care apelantul n-o poate
verifica singur stă acolo unde n-o poate uita.

## 4. Consecință pe care ADR-039 o făcea deja necesară

[ADR-039](039-valuta-si-perioade.md) §11 fixează că **perioada de start a unui tenant este
ireversibilă**: odată postate soldurile inițiale și închisă prima perioadă, nu se mai schimbă.

Decizia aceea presupune un loc unde se ia — iar locul nu exista. `P-9` îl creează, iar Spec A §13
descrie ce se alege acolo și în ce ordine. O alegere ireversibilă care apare ca un dropdown printre
altele într-un formular este o alegere pe care nimeni n-a luat-o conștient.

## 5. Ce rămâne deschis

**`DN-26` — cine poate crea un tenant.** Autoservire deschisă, invitație, sau creare de către o
firmă în numele unui client. Alegerea are consecințe comerciale, nu doar tehnice, și interacționează
cu cele două canale de facturare din Spec A §10.1. `P-9` funcționează pentru oricare dintre ele:
funcția verifică ce i se cere să verifice, iar cine are voie s-o apeleze e o decizie de deasupra ei.
