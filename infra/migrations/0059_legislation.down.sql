REVOKE ALL ON normative_act, official_publication, normative_act_publication FROM evidenta_refdata;
DROP POLICY IF EXISTS normative_act_publication_refdata_write ON normative_act_publication;
DROP POLICY IF EXISTS normative_act_publication_read ON normative_act_publication;
ALTER TABLE normative_act_publication NO FORCE ROW LEVEL SECURITY;
ALTER TABLE normative_act_publication DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS official_publication_refdata_write ON official_publication;
DROP POLICY IF EXISTS official_publication_read ON official_publication;
ALTER TABLE official_publication NO FORCE ROW LEVEL SECURITY;
ALTER TABLE official_publication DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS normative_act_refdata_write ON normative_act;
DROP POLICY IF EXISTS normative_act_read ON normative_act;
ALTER TABLE normative_act NO FORCE ROW LEVEL SECURITY;
ALTER TABLE normative_act DISABLE ROW LEVEL SECURITY;
-- Tabelele le sterge Django, in aceeasi migrare inversa.
