-- 0058 — jurnalul cailor privilegiate (spec-a §6.3), scris de rolul de date de referinta
--
-- Context:     docs/specs/spec-a-tenancy.md §6.1, §6.3
--              docs/decisions/049-rolul-de-date-de-referinta.md (ADR-049)
--              infra/rls/exceptions.toml — `privileged_access_log`, `policy_shape = "platform_log"`
--              infra/schema/append_only.toml — `occurred_at` ca coloana de partitionare
--
-- Tabela era declarata in contract din F0 si nu exista in nicio baza: fiecare cale
-- privilegiata „se auditeaza" intr-o tabela pe care nimeni n-o crease. Se creeaza
-- odata cu primul rol care are ce scrie in ea.
--
-- Cine o scrie: `evidenta_refdata`, rand per rulare, in aceeasi tranzactie cu
-- incarcarea (§6.1). Cine o citeste: administrarea platformei — un rol care nu
-- exista inca (`DN-18`, `P-7`). Pana atunci NIMENI prin aplicatie: rolul
-- aplicatiei nu primeste nici SELECT, fiindca tabela contine identificatori de
-- tenant ai altor tenanti, iar „citire libera" ar fi o interogare cross-tenant in
-- afara stratului de read models (R7).
--
-- Ordinea C30: tabela e creata de Django in aceeasi migrare; aici ENABLE → FORCE →
-- POLICY → GRANT.

ALTER TABLE privileged_access_log ALTER COLUMN path_code TYPE text COLLATE "C";
ALTER TABLE privileged_access_log ALTER COLUMN request_id TYPE text COLLATE "C";

ALTER TABLE privileged_access_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE privileged_access_log FORCE  ROW LEVEL SECURITY;

-- Scriitorul vede ce a scris (idempotenta unui incarcator se citeste din propriile
-- rulari) si poate insera. UPDATE si DELETE nu au politica si nu au privilegiu —
-- si peste asta sta triggerul de mai jos.
CREATE POLICY privileged_access_log_refdata_read ON privileged_access_log
    FOR SELECT TO evidenta_refdata USING (true);
CREATE POLICY privileged_access_log_refdata_insert ON privileged_access_log
    FOR INSERT TO evidenta_refdata WITH CHECK (true);

-- Privilegiile implicite din 0001 au dat aplicatiei INSERT/UPDATE/DELETE/SELECT
-- la crearea tabelei. Se retrag toate: nici citirea nu e a ei (vezi sus).
REVOKE ALL ON privileged_access_log FROM evidenta_app;
GRANT SELECT, INSERT ON privileged_access_log TO evidenta_refdata;

-- --- Append-only, ca registrul si din acelasi motiv ---------------------------
--
-- Un jurnal de acces care se poate rescrie nu e jurnal. Corectia e un rand nou.
-- Tiparul din 0042: functia sub `evidenta_rls`, grantul catre owner emis tot de
-- el (ADR-043 §4.1), apoi triggerul ca owner.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.refuse_privileged_log_rewrite()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'privileged_access_log is append-only (spec-a 6.3, ADR-049): % refused on %',
        TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$;

REVOKE ALL ON FUNCTION rls.refuse_privileged_log_rewrite() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.refuse_privileged_log_rewrite() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER privileged_access_log_append_only
    BEFORE UPDATE OR DELETE ON privileged_access_log
    FOR EACH ROW EXECUTE FUNCTION rls.refuse_privileged_log_rewrite();
