-- =============================================================================
-- F0.3.7b — MFA si sesiuni: politici si granturi
--
-- Autoritate:  docs/decisions/021-mfa-obligatoriu.md
--              docs/specs/spec-a-tenancy.md §1.5, §2.7
--
-- Toate trei tabelele sunt legate de utilizator, nu de tenant: un contabil are un
-- singur cont pentru toti clientii (ADR-003, identitate globala), deci si un
-- singur al doilea factor. Politica este `self_row`, ca la `user`.
--
-- CE NU FACE POLITICA. Nu impiedica un administrator de tenant sa reseteze MFA
-- altcuiva — pentru ca nu exista o astfel de operatiune prin ORM, si nu trebuie
-- sa existe. Recuperarea trece printr-un al doilea administrator, pe o cale
-- explicita, cand se construieste (ADR-021). Un suport care poate reseta MFA este
-- un MFA optional cu pasi in plus.
-- =============================================================================

ALTER TABLE mfa_method ENABLE ROW LEVEL SECURITY;
ALTER TABLE mfa_method FORCE  ROW LEVEL SECURITY;

CREATE POLICY mfa_method_self ON mfa_method
    FOR ALL TO evidenta_app
    USING      (user_id = app.current_user_id())
    WITH CHECK (user_id = app.current_user_id());

ALTER TABLE mfa_backup_code ENABLE ROW LEVEL SECURITY;
ALTER TABLE mfa_backup_code FORCE  ROW LEVEL SECURITY;

CREATE POLICY mfa_backup_code_self ON mfa_backup_code
    FOR ALL TO evidenta_app
    USING      (user_id = app.current_user_id())
    WITH CHECK (user_id = app.current_user_id());

-- Sesiunile: proprii, la citire si la scriere. Revocarea sesiunilor altcuiva —
-- la revocarea unui engagement — nu trece pe aici: e o operatiune administrativa
-- asupra randurilor altor utilizatori, deci trece prin aceeasi disciplina ca
-- revocarea accesului la companie (0014), pe o cale privilegiata ingusta.
ALTER TABLE user_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_session FORCE  ROW LEVEL SECURITY;

CREATE POLICY user_session_self ON user_session
    FOR ALL TO evidenta_app
    USING      (user_id = app.current_user_id())
    WITH CHECK (user_id = app.current_user_id());

GRANT SELECT, INSERT, UPDATE, DELETE
    ON mfa_method, mfa_backup_code, user_session
    TO evidenta_app;
