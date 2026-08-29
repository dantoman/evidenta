-- 0059 — registrul actelor normative si al publicarilor lor (OD-65, ADR-049)
--
-- Context:     docs/decisions/049-rolul-de-date-de-referinta.md §OD-65
--              infra/rls/exceptions.toml — cele trei tabele, `global_read_only`,
--                  `writer_role = "evidenta_refdata"`
--              CLAUDE.md R15 (sursa cu numar de Monitorul Oficial), C34
--
-- Doua fapte, nu unul, verificate din PDF-urile Ministerului Finantelor
-- (2026-08-28): un act are doua publicari, si o singura pozitie din Monitorul
-- Oficial (nr. 233-237 art. 1534 din 22.10.2013) acopera doua acte (OMF 118/2013
-- si OMF 119/2013). Al doilea fapt face „inca un set de coloane" imposibil: o
-- coloana nu se imparte intre doua randuri de act. De aici trei tabele: actul,
-- publicarea (pozitia din Monitor), si legatura M:N intre ele.
--
-- Globale, ca parametrii: aceeasi lege pentru toti. Citire libera aplicatiei;
-- scriere exclusiv sub rolul de date de referinta.

-- Codurile se ordoneaza pe octeti (C34): numarul de act, numarul de Monitor si
-- articolul sunt coduri, nu denumiri.
ALTER TABLE normative_act ALTER COLUMN act_type   TYPE text COLLATE "C";
ALTER TABLE normative_act ALTER COLUMN act_number TYPE text COLLATE "C";
ALTER TABLE official_publication ALTER COLUMN gazette_number TYPE text COLLATE "C";
ALTER TABLE official_publication ALTER COLUMN article        TYPE text COLLATE "C";

ALTER TABLE normative_act ENABLE ROW LEVEL SECURITY;
ALTER TABLE normative_act FORCE  ROW LEVEL SECURITY;
CREATE POLICY normative_act_read ON normative_act
    FOR SELECT TO evidenta_app USING (true);
CREATE POLICY normative_act_refdata_write ON normative_act
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);

ALTER TABLE official_publication ENABLE ROW LEVEL SECURITY;
ALTER TABLE official_publication FORCE  ROW LEVEL SECURITY;
CREATE POLICY official_publication_read ON official_publication
    FOR SELECT TO evidenta_app USING (true);
CREATE POLICY official_publication_refdata_write ON official_publication
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);

ALTER TABLE normative_act_publication ENABLE ROW LEVEL SECURITY;
ALTER TABLE normative_act_publication FORCE  ROW LEVEL SECURITY;
CREATE POLICY normative_act_publication_read ON normative_act_publication
    FOR SELECT TO evidenta_app USING (true);
CREATE POLICY normative_act_publication_refdata_write ON normative_act_publication
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);

-- Privilegiile implicite din 0001 dau aplicatiei si scrierea; se retrage
-- explicit (OD-47: declaratia si baza spun acelasi lucru). Fara DELETE pentru
-- nimeni: un act citat de un parametru nu dispare.
GRANT SELECT ON normative_act, official_publication, normative_act_publication TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE
    ON normative_act, official_publication, normative_act_publication FROM evidenta_app;
GRANT SELECT, INSERT, UPDATE
    ON normative_act, official_publication, normative_act_publication TO evidenta_refdata;
