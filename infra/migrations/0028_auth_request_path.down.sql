-- Reversul lui 0026_auth_request_path.up.sql.
--
-- Ordinea este inversa celei de la aplicare: intai functiile care citesc
-- tabelele, apoi granturile pe care se sprijina, la urma coloana.

DROP FUNCTION IF EXISTS rls.resolve_session(text);
DROP FUNCTION IF EXISTS rls.auth_spend_backup_code(uuid);
DROP FUNCTION IF EXISTS rls.auth_backup_codes(uuid);
DROP FUNCTION IF EXISTS rls.auth_mfa_methods(uuid);
DROP FUNCTION IF EXISTS rls.auth_lookup_user(citext);

REVOKE ALL ON "user"          FROM evidenta_rls;
REVOKE ALL ON mfa_method      FROM evidenta_rls;
REVOKE ALL ON mfa_backup_code FROM evidenta_rls;
REVOKE ALL ON user_session    FROM evidenta_rls;

DROP INDEX IF EXISTS user_session_token_hash_key;

-- Coloana pleaca odata cu sesiunile care o folosesc: fara token nu exista cale de
-- rezolvare, deci randurile ramase ar fi sesiuni pe care nimeni nu le poate
-- prezenta si nimeni nu le poate inchide.
ALTER TABLE user_session DROP COLUMN IF EXISTS token_hash;
