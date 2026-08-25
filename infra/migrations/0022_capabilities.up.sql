-- =============================================================================
-- F0.5.1 — CapabilityActivation: nesuprapunere si politica
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §1.8
--              CLAUDE.md R24, R25, R26
--
-- CONSTRANGEREA DE NESUPRAPUNERE, si de ce cheia e COALESCE.
--
-- O capabilitate poate fi la nivel de tenant (company_id NULL) sau de companie.
-- Forma evidenta — EXCLUDE pe (company_id, capability_key, interval) — este
-- gresita exact pentru primul caz: intr-o constrangere de excludere, NULL nu este
-- egal cu NULL, deci doua randuri la nivel de tenant nu intra niciodata in
-- conflict. Ar trece tacut, si tocmai capabilitatile de tenant sunt cele care
-- controleaza facturarea.
--
-- COALESCE(company_id, tenant_id) da o singura cheie de scope care acopera ambele
-- cazuri: randurile de companie se compara intre ele, cele de tenant intre ele,
-- si niciodata unele cu altele.
-- =============================================================================

ALTER TABLE capability_activation
    ADD CONSTRAINT capability_activation_no_overlap
    EXCLUDE USING gist (
        COALESCE(company_id, tenant_id) WITH =,
        capability_key WITH =,
        daterange(effective_from, effective_to, '[)') WITH &&
    );

ALTER TABLE capability_activation ENABLE ROW LEVEL SECURITY;
ALTER TABLE capability_activation FORCE  ROW LEVEL SECURITY;

-- Tenant-scoped. Nu se ingusteaza pe app.current_company_id(): profilul de
-- capabilitati este input al Posting Engine (R26), iar acela are nevoie sa vada
-- si capabilitatile de tenant cand posteaza pentru o companie.
CREATE POLICY capability_activation_access ON capability_activation
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id));

GRANT SELECT, INSERT, UPDATE, DELETE ON capability_activation TO evidenta_app;
