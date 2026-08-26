-- Ce a stat sub un calcul, la momentul calculului — OD-68, ADR-047.
--
-- ADR-046 a dat istoricul increderii: fiecare stare prin care a trecut
-- `source_confidence` si de cand. Raspunde la „cat de ferm era parametrul in
-- martie". Nu raspunde la „pe ce a stat postarea din martie", si sunt intrebari
-- diferite — fiindca *confirmarea nu schimba valoarea*. Din momentul in care SFS
-- publica, nimic din parametru nu mai arata ca s-a calculat pe o deductie.
--
-- De-aia stampila e a calculului, nu a parametrului, si se pune la postare.
-- Increderea se **copiaza**, nu se refera: o referinta se rezolva la ce spune
-- lumea acum, adica exact ce se pierde.
--
-- Verificabila, nu doar declarata: `resolved_at` tine instantul, deci
-- `fiscal.confidence_at(parameter_id, resolved_at)` reproduce increderea
-- stampilata din istoric. O stampila care nu se poate re-deriva e o afirmatie;
-- una care se poate e o proba, iar la un control diferenta asta se plateste.
--
-- Fara FK spre `fiscal_parameter`: `D6` — modulele vorbesc prin servicii si
-- evenimente, niciodata prin import de modele. Se pastreaza id-ul, joinul e un
-- apel de serviciu. FK-ul spre `journal_entry` e permis: `journal_line` e cea
-- din `append_only.toml`, nu antetul (`R21`).

ALTER TABLE entry_parameter_stamp ALTER COLUMN parameter_key TYPE text COLLATE "C";
ALTER TABLE entry_parameter_stamp ALTER COLUMN confidence    TYPE text COLLATE "C";

ALTER TABLE entry_parameter_stamp ENABLE ROW LEVEL SECURITY;
ALTER TABLE entry_parameter_stamp FORCE  ROW LEVEL SECURITY;

CREATE POLICY entry_parameter_stamp_access ON entry_parameter_stamp
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id)
                AND (app.current_company_id() IS NULL
                     OR company_id = app.current_company_id()))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id)
                AND (app.current_company_id() IS NULL
                     OR company_id = app.current_company_id()));

-- Fara UPDATE si fara DELETE: ce a stat sub o postare e la fel de imutabil ca
-- postarea (`R10`). Privilegiul opreste aplicatia; triggerul de mai jos opreste
-- restul, inclusiv o migrare care crede ca repara date.
GRANT SELECT, INSERT ON entry_parameter_stamp TO evidenta_app;

-- REVOKE explicit, si e masurat, nu defensiv: un GRANT restrans nu *retrage*
-- nimic. Tabela ajunge la `evidenta_app` cu UPDATE si DELETE prin privilegiile
-- implicite pe care le primeste orice tabela noua, deci fara linia asta
-- comentariul de mai sus ar fi fost fals — verificat pe catalog, unde aplicatia
-- aparea cu toate patru.
REVOKE UPDATE, DELETE ON entry_parameter_stamp FROM evidenta_app;

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.refuse_parameter_stamp_rewrite()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'entry_parameter_stamp is append-only (ADR-047): % refused on %',
        TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$;

REVOKE ALL ON FUNCTION rls.refuse_parameter_stamp_rewrite() FROM PUBLIC;

-- ADR-043 §4.1, aplicat: `CREATE TRIGGER` verifica EXECUTE pe functie la creare,
-- nu la declansare, si se emite ca proprietar al tabelei — `evidenta_owner`, care
-- e NOINHERIT. Fara linia asta cade cu „permission denied for function", mesaj
-- care nu spune nimic despre cauza. Emisa sub `evidenta_rls` ca sa aiba efect.
GRANT EXECUTE ON FUNCTION rls.refuse_parameter_stamp_rewrite() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER entry_parameter_stamp_append_only
    BEFORE UPDATE OR DELETE ON entry_parameter_stamp
    FOR EACH ROW EXECUTE FUNCTION rls.refuse_parameter_stamp_rewrite();
