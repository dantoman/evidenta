-- Metadate de atasament — Spec A §5.3, ADR-030.
--
-- La nivel de COMPANIE, nu de tenant. Argumentul care decide nu e consecventa,
-- ci accesul: documentele stau la nivel de companie, iar accesul se acorda per
-- companie (`company_access`). Un atasament tinut la nivel de tenant ar avea o
-- granita de acces MAI LARGA decat documentul pe care il insoteste — un contabil
-- cu acces la o singura companie a unui holding ar vedea atasamentele
-- celorlalte.
--
-- Si atasamentele sunt cazul cel mai prost in care poate aparea: un PDF de
-- factura contine tot ce e in document si de obicei mai mult. Nu e o coloana, e
-- o pagina.

ALTER TABLE attachment_metadata ALTER COLUMN storage_key      TYPE text        COLLATE "C";
ALTER TABLE attachment_metadata ALTER COLUMN checksum_sha256  TYPE varchar(64) COLLATE "C";
ALTER TABLE attachment_metadata ALTER COLUMN content_type     TYPE text        COLLATE "C";

ALTER TABLE attachment_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachment_metadata FORCE  ROW LEVEL SECURITY;

-- Aceeasi forma ca pentru orice tabela ingustata pe companie: contextul de
-- tenant DECIDE tenantul, iar `rls.has_company_access` decide compania. Ambele,
-- nu una: contextul singur ar lasa orice membru al tenantului sa vada orice
-- companie a lui, iar predicatul singur n-ar lega randul de contextul curent.

CREATE POLICY attachment_metadata_access ON attachment_metadata
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id));

GRANT SELECT, INSERT, UPDATE, DELETE ON attachment_metadata TO evidenta_app;
