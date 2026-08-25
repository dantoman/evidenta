-- =============================================================================
-- F0.3.2 — User și Membership: tip, politici, granturi
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §1.5, §1.6, §2.7
--              docs/decisions/003-rls-tenancy-tables.md
--
-- Aici se închide prima cale de acces: din acest punct, `tenant` devine
-- interogabil de un membru activ. A doua cale — firmă cu engagement — vine la
-- F0.3.3.
-- =============================================================================

-- --- tipuri -----------------------------------------------------------------
--
-- Insensibilitatea la majuscule pe e-mail se face de tip, nu prin lower() în
-- interogări: se uită exact la autentificare, unde contează.
ALTER TABLE "user" ALTER COLUMN email TYPE citext;

-- --- user: policy_shape = self_row ------------------------------------------
--
-- Un utilizator își vede propriul rând. Nu al altora, nici măcar al colegilor
-- din același tenant — tabela e globală, deci orice altă formă ar fi o cale de
-- enumerare între tenanți.
--
-- ATENȚIE: aceasta face imposibilă listarea membrilor unei echipe cu nume și
-- e-mail. Este `OD-37`, decizie deschisă, și blochează ecranele de administrare
-- a echipei. Nu se rezolvă prin lărgirea politicii de aici fără ADR.

ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "user" FORCE  ROW LEVEL SECURITY;

CREATE POLICY user_self ON "user"
    FOR ALL TO evidenta_app
    USING      (id = app.current_user_id())
    WITH CHECK (id = app.current_user_id());

-- --- membership: policy_shape = self_row ------------------------------------
--
-- Are `tenant_id`, deci NU este excepție de la R1 — dar politica nu poate fi
-- șablonul: `rls.has_tenant_access` citește chiar această tabelă, iar o politică
-- pe ea care ar apela predicatul ar intra în recursiune. Rândurile proprii se
-- văd direct, fără predicat.

ALTER TABLE membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership FORCE  ROW LEVEL SECURITY;

CREATE POLICY membership_self ON membership
    FOR ALL TO evidenta_app
    USING      (user_id = app.current_user_id())
    WITH CHECK (user_id = app.current_user_id());

-- --- granturi ---------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE ON "user", membership TO evidenta_app;

-- Rolul de rezolvare primește SELECT punctual, nu prin privilegii implicite
-- (0001_roles.sql): are BYPASSRLS, deci fiecare GRANT către el este o decizie.
-- Citește `membership` pentru prima cale de acces din `rls.has_tenant_access`.
GRANT SELECT ON membership TO evidenta_rls;
