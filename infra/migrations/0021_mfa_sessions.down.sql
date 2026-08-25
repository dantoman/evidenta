-- Inversa lui 0021_mfa_sessions.up.sql (ADR-012).

REVOKE ALL ON mfa_method, mfa_backup_code, user_session FROM evidenta_app;

DROP POLICY IF EXISTS user_session_self ON user_session;
DROP POLICY IF EXISTS mfa_backup_code_self ON mfa_backup_code;
DROP POLICY IF EXISTS mfa_method_self ON mfa_method;

ALTER TABLE user_session     NO FORCE ROW LEVEL SECURITY;
ALTER TABLE user_session     DISABLE ROW LEVEL SECURITY;
ALTER TABLE mfa_backup_code  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE mfa_backup_code  DISABLE ROW LEVEL SECURITY;
ALTER TABLE mfa_method       NO FORCE ROW LEVEL SECURITY;
ALTER TABLE mfa_method       DISABLE ROW LEVEL SECURITY;
