-- =============================================================================
-- F0.3.7c — Autentificarea pe calea de request: token de sesiune si functiile
--            care preced contextul
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §3.2 (secventa cererii), §6.1
--              (mecanismul cailor privilegiate), ADR-021 (MFA obligatoriu)
--              CLAUDE.md C8, R3, R4
--
-- PROBLEMA, in aceeasi forma ca la 0016. Spec A §3.2 numeroteaza doi pasi
-- inaintea tranzactiei: (1) rezolva subdomeniul, (2) autentifica utilizatorul.
-- Amandoi preced contextul, iar `app.current_user_id()` este fail-closed: nu
-- intoarce NULL cand contextul lipseste, ci ridica eroare. Prin urmare NICIO
-- politica `self_row` nu poate raspunde inainte de autentificare — nici macar
-- pentru a citi randul propriu, fiindca „propriu" este exact ce nu se stie inca.
--
-- Pasul 1 are deja calea lui: `rls.resolve_tenant_by_subdomain` (0016). Fisierul
-- de fata da pasul 2 aceeasi forma.
--
-- CE ESTE SI CE NU ESTE AICI. Sunt aici doar interogarile care preced identitatea
-- verificata: cautarea contului dupa e-mail, factorii lui de autentificare, si
-- rezolvarea unei sesiuni dintr-un token. NU sunt aici — pentru ca nu au ce cauta
-- — emiterea sesiunii, marcarea ultimei autentificari si revocarea: dupa ce
-- parola SI al doilea factor au fost verificate, identitatea este cunoscuta,
-- contextul se poate deschide, iar politica `user_session_self` scrie randul
-- prin ORM ca orice alt rand al utilizatorului. O functie privilegiata in plus
-- acolo ar fi fost o gaura deschisa fara sa fie nevoie.
--
-- DE CE NU SE DESCHIDE CONTEXTUL DUPA PAROLA. Ar simplifica trei functii intr-una
-- singura. Ar insemna insa un context de baza de date obtinut cu parola singura,
-- adica exact ce ADR-021 interzice la nivelul aplicatiei, mutat cu un strat mai
-- jos unde nu se mai vede.
--
-- TOKENUL. `user_session` era identificata pana acum doar prin cheia primara. O
-- cheie primara nu este un secret: apare in loguri, in mesaje de eroare si in
-- referinte. Coloana `token_hash` separa cele doua roluri — identificatorul
-- ramane vizibil, secretul este pastrat doar ca SHA-256, deci un dump al bazei
-- nu contine nicio sesiune folosibila. `COLLATE "C"` fiindca este cod, nu
-- denumire (C34): se compara pe egalitate, niciodata lingvistic.
-- =============================================================================

ALTER TABLE user_session ADD COLUMN token_hash text COLLATE "C";

-- Sesiunile existente preced modelul de token, deci nu au unul si nu il pot
-- primi: nimeni nu detine secretul care le-ar corespunde. Sunt inchise explicit,
-- cu motiv, in loc sa fie sterse — istoricul sesiunilor ramane citibil, iar
-- valoarea pusa in `token_hash` nu poate fi produsa de niciun SHA-256 (are alta
-- lungime si alt alfabet), deci nu se poate potrivi niciodata cu o cautare.
UPDATE user_session
   SET token_hash        = 'pre-token-session:' || id::text,
       revoked_at        = COALESCE(revoked_at, now()),
       revocation_reason = COALESCE(revocation_reason, 'session token model introduced')
 WHERE token_hash IS NULL;

ALTER TABLE user_session ALTER COLUMN token_hash SET NOT NULL;

-- Unic: doua sesiuni cu acelasi token ar face „care sesiune" o intrebare fara
-- raspuns determinat, iar raspunsul ales de planificator ar fi al altui
-- utilizator.
CREATE UNIQUE INDEX user_session_token_hash_key ON user_session (token_hash);

-- -----------------------------------------------------------------------------
-- Caile privilegiate. Aceeasi disciplina ca 0016: scop ingust, semnatura care nu
-- accepta SQL sau nume de tabele, niciun camp de business intors.
-- -----------------------------------------------------------------------------

SET LOCAL ROLE evidenta_rls;

-- Pasul 2a: contul, dupa e-mail. Intoarce exact materialul necesar verificarii
-- parolei si nimic altceva — fara nume, fara locale, fara data crearii. Contul
-- inactiv nu apare deloc: „dezactivat" si „inexistent" trebuie sa dea acelasi
-- raspuns apelantului, altfel formularul de autentificare devine o lista de cine
-- are cont.
CREATE OR REPLACE FUNCTION rls.auth_lookup_user(p_email citext)
RETURNS TABLE (user_id uuid, password_hash text, mfa_enabled boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    SELECT u.id, u.password_hash, u.mfa_enabled
      FROM "user" u
     WHERE u.email = p_email
       AND u.is_active;
$fn$;

-- Pasul 2b: factorii confirmati. Neconfirmate nu autentifica (o inrolare
-- abandonata nu trebuie sa blocheze si nici sa deschida contul), deci filtrul
-- este aici, nu in apelant: un apelant care il uita ar accepta un factor pe care
-- nimeni nu a dovedit ca il poseda.
CREATE OR REPLACE FUNCTION rls.auth_mfa_methods(p_user_id uuid)
RETURNS TABLE (method_id uuid, method_type text, secret_encrypted bytea)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    SELECT m.id, m.method_type, m.secret_encrypted
      FROM mfa_method m
     WHERE m.user_id = p_user_id
       AND m.confirmed_at IS NOT NULL;
$fn$;

-- Pasul 2c: codurile de rezerva nefolosite. Se intorc ca hash-uri, cate unul pe
-- rand, fiindca fiecare are sarea lui — nu exista cautare dupa valoare, si
-- aceeasi proprietate face un dump inutilizabil.
CREATE OR REPLACE FUNCTION rls.auth_backup_codes(p_user_id uuid)
RETURNS TABLE (code_id uuid, code_hash text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    SELECT c.id, c.code_hash
      FROM mfa_backup_code c
     WHERE c.user_id = p_user_id
       AND c.used_at IS NULL;
$fn$;

-- Pasul 2d: consumarea unui cod. `used_at IS NULL` in WHERE, nu in apelant:
-- conditia si scrierea trebuie sa fie aceeasi instructiune, altfel doua cereri
-- paralele cheltuiesc acelasi cod de doua ori. Intoarce NULL daca nu a cheltuit
-- nimic — apelantul trateaza NULL ca refuz.
CREATE OR REPLACE FUNCTION rls.auth_spend_backup_code(p_code_id uuid)
RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    UPDATE mfa_backup_code
       SET used_at = now()
     WHERE id = p_code_id
       AND used_at IS NULL
    RETURNING true;
$fn$;

-- Fiecare cerere ulterioara: sesiunea, dupa token. Verificarea vietii sesiunii
-- este in WHERE, nu in apelant, din acelasi motiv ca mai sus — o sesiune expirata
-- sau revocata nu intoarce niciun rand, deci nu exista cale prin care apelantul
-- sa o accepte din greseala.
--
-- `last_seen_at` se scrie aici fiindca aceasta ESTE folosirea sesiunii. O a doua
-- functie „touch" ar fi insemnat inca o cale privilegiata pentru un fapt deja
-- cunoscut in aceasta.
CREATE OR REPLACE FUNCTION rls.resolve_session(p_token_hash text)
RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, actor_firm_id uuid)
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    UPDATE user_session s
       SET last_seen_at = now()
     WHERE s.token_hash = p_token_hash
       AND s.revoked_at IS NULL
       AND s.expires_at > now()
    RETURNING s.id, s.user_id, s.tenant_id, s.actor_firm_id;
$fn$;

RESET ROLE;

-- BYPASSRLS spune „politicile nu se aplica"; GRANT spune „ai voie sa atingi
-- tabela". Lectia lui 0017: prima fara a doua da permission denied din interiorul
-- unei functii care teoretic ocoleste tot.
GRANT SELECT                 ON "user"          TO evidenta_rls;
GRANT SELECT                 ON mfa_method      TO evidenta_rls;
GRANT SELECT, UPDATE         ON mfa_backup_code TO evidenta_rls;
GRANT SELECT, UPDATE         ON user_session    TO evidenta_rls;

REVOKE ALL ON FUNCTION rls.auth_lookup_user(citext)      FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.auth_mfa_methods(uuid)        FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.auth_backup_codes(uuid)       FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.auth_spend_backup_code(uuid)  FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.resolve_session(text)         FROM PUBLIC;

GRANT EXECUTE ON FUNCTION rls.auth_lookup_user(citext)     TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.auth_mfa_methods(uuid)       TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.auth_backup_codes(uuid)      TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.auth_spend_backup_code(uuid) TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.resolve_session(text)        TO evidenta_app;
