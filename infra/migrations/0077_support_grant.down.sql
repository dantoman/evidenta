-- Inversa lui 0077_support_grant.up.sql (ADR-012).
--
-- `rls.resolve_session` revine la forma din 0028 (fara grant), fiindca coloana
-- `user_session.support_grant_id` pleaca odata cu migrarea Django care a adus-o.
-- Tabela o sterge migrarea Django; aici se desfac politicile, privilegiile si functiile.

SET LOCAL ROLE evidenta_rls;

DROP FUNCTION IF EXISTS rls.console_support_grants();
DROP FUNCTION IF EXISTS rls.resolve_session(text);
CREATE FUNCTION rls.resolve_session(p_token_hash text)
RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, actor_firm_id uuid)
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    UPDATE user_session s
       SET last_seen_at = now()
     WHERE s.token_hash = p_token_hash
       AND s.revoked_at IS NULL
       AND s.expires_at > now()
    RETURNING s.id, s.user_id, s.tenant_id, s.actor_firm_id;
$fn$;
REVOKE ALL ON FUNCTION rls.resolve_session(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.resolve_session(text) TO evidenta_app;
DROP FUNCTION IF EXISTS rls.auth_support_grant(uuid, uuid);
DROP FUNCTION IF EXISTS rls.request_support_access(uuid, uuid, text, text);

RESET ROLE;

REVOKE INSERT ON privileged_access_log FROM evidenta_rls;
REVOKE ALL    ON support_grant         FROM evidenta_rls;
REVOKE ALL    ON support_grant         FROM evidenta_app;

DROP POLICY IF EXISTS support_grant_access ON support_grant;

ALTER TABLE support_grant NO FORCE ROW LEVEL SECURITY;
ALTER TABLE support_grant DISABLE  ROW LEVEL SECURITY;
ALTER TABLE support_grant DROP CONSTRAINT IF EXISTS support_grant_window_max;
