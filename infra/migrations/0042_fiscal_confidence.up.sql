-- Istoricul increderii in sursa unui parametru fiscal — ADR-046.
--
-- Confirmarea unei valori nu schimba valoarea. De-aia tranzitia e usor de
-- inregistrat gresit: arata ca o editare a unei coloane, iar o editare sterge
-- exact starea pe care s-a bazat un calcul trecut. Din momentul in care SFS
-- publica, o interogare pe o data din martie spune ca nimic n-a fost provizoriu,
-- desi calculul din martie chiar s-a facut pe o deductie.
--
-- Tabela e in aceeasi clasa cu `fiscal_parameter` si `fiscal_parameter_source`:
-- globala, citibila de oricine, scriibila prin calea privilegiata P-4. Motivul e
-- identic — cand SFS publica nota anuala, faptul e acelasi pentru toti tenantii.
-- Un istoric de incredere per tenant ar insemna ca doi tenanti pot da raspunsuri
-- diferite aceluiasi control despre acelasi act normativ.
--
-- Citirea e deschisa deliberat: un tenant care recalculeaza 2026 in 2030 trebuie
-- sa poata arata nu doar sub ce act s-a calculat, ci si cat de ferm era atasat
-- numarul de act la momentul depunerii.

ALTER TABLE fiscal_parameter_confidence_event ALTER COLUMN confidence TYPE text COLLATE "C";

ALTER TABLE fiscal_parameter_confidence_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter_confidence_event FORCE  ROW LEVEL SECURITY;
CREATE POLICY fiscal_parameter_confidence_event_read ON fiscal_parameter_confidence_event
    FOR SELECT TO evidenta_app USING (true);

-- --- Istoricul e append-only, ca registrul si din acelasi motiv ---------------
--
-- Starea la un moment trecut trebuie sa ramana recuperabila dupa ce starea
-- prezenta se schimba. Un UPDATE sau un DELETE aici nu corecteaza istoria, o
-- rescrie — iar o istorie rescriibila nu raspunde intrebarii pentru care exista.
-- Corectia se face printr-un eveniment nou, cu `note` care spune ce se corecteaza.

-- Sub rolul care detine obiectele din `rls`, si cu REVOKE emis tot de el:
-- ADR-043 a masurat ca un REVOKE de la cine nu detine functia produce un WARNING,
-- nu o eroare — migrarea trece si privilegiul ramane.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.refuse_confidence_event_rewrite()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'fiscal_parameter_confidence_event is append-only (ADR-046): % refused on %',
        TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$;

REVOKE ALL ON FUNCTION rls.refuse_confidence_event_rewrite() FROM PUBLIC;

-- Masurat, si e o consecinta a lui ADR-043 pe care merita s-o stie oricine mai
-- scrie un trigger de acum inainte:
--
--   `CREATE TRIGGER` verifica EXECUTE pe functie *la creare*, nu la declansare,
--   iar `CREATE TRIGGER` se emite ca proprietar al tabelei — `evidenta_owner`,
--   care e NOINHERIT si nu mostenește nimic din `evidenta_rls`.
--
-- Toate migrarile de pana la 0041 au mers fiindca PUBLIC avea EXECUTE implicit.
-- 0041 a retras acel privilegiu, corect. Efectul secundar: tiparul folosit peste
-- tot — creeaza functia sub `rls`, `RESET ROLE`, `CREATE TRIGGER` — nu mai merge
-- pentru functii noi, si cade cu „permission denied for function".
--
-- Grantul de mai jos e emis tot sub `evidenta_rls`, deci are efect (ADR-043).
-- Nu slabeste nimic: functia doar ridica o exceptie, si proprietarul oricum
-- detine tabela.
GRANT EXECUTE ON FUNCTION rls.refuse_confidence_event_rewrite() TO evidenta_owner;

RESET ROLE;

-- `evidenta_app` nu primeste EXECUTE si nu se rupe nimic: verificarea e la
-- crearea triggerului, nu la declansarea lui.

CREATE TRIGGER fiscal_confidence_event_append_only
    BEFORE UPDATE OR DELETE ON fiscal_parameter_confidence_event
    FOR EACH ROW EXECUTE FUNCTION rls.refuse_confidence_event_rewrite();
