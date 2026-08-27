-- 0044 — scrierea datelor de referinta ale planului de conturi, sub owner
--
-- Context:     infra/rls/exceptions.toml — `coa_template` si `coa_template_account`
--                  sunt `global_read_only`: rolul aplicatiei citeste, nu scrie
--              CLAUDE.md R2 (FORCE ROW LEVEL SECURITY), C30
--
-- De ce exista: `FORCE ROW LEVEL SECURITY` se aplica SI proprietarului tabelei.
-- Cele doua tabele nu aveau nicio politica de scriere, deci incarcatorul rulat ca
-- `evidenta_owner` primea „new row violates row-level security policy" — masurat,
-- nu presupus. Fara aceasta politica, continutul planului de conturi nu poate
-- intra in baza pe nicio cale in afara de superuser.
--
-- Ce NU face: nu creeaza un rol nou si nu atinge rolul aplicatiei. `evidenta_app`
-- ramane exact cu ce avea — SELECT si atat. Scrierea e a proprietarului schemei,
-- care oricum poate face ALTER TABLE pe ele; politica doar nu-l mai contrazice.
--
-- Cele doua tabele sunt globale: nu au `tenant_id`, deci nu exista predicat de
-- tenant de scris aici. `USING (true)` nu largeste nimic pentru nimeni altcineva:
-- politica e legata de rol prin `TO evidenta_owner`.

CREATE POLICY coa_template_owner_write ON coa_template
    FOR ALL TO evidenta_owner
    USING (true) WITH CHECK (true);

CREATE POLICY coa_template_account_owner_write ON coa_template_account
    FOR ALL TO evidenta_owner
    USING (true) WITH CHECK (true);
