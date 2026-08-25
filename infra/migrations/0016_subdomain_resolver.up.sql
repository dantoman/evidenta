-- =============================================================================
-- F0.3.5 — Rezolvarea tenantului din subdomeniu
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §1.1, §3.2, §6
--              CLAUDE.md C8
--
-- PROBLEMA. Contextul de tenant vine exclusiv din subdomeniu (C8). Dar ca sa afli
-- ce tenant e, trebuie sa citesti tabela `tenant` — a carei politica cere deja
-- `app.current_tenant_id()`. Rezolvarea subdomeniului este, prin natura ei,
-- anterioara contextului.
--
-- SOLUTIA. O cale privilegiata ingusta, in sensul spec-a §6.1: o functie SECURITY
-- DEFINER care primeste un subdomeniu si intoarce identificatorul si starea
-- tenantului. Nimic altceva. Nu primeste nume de tabele, nu accepta SQL, si nu
-- intoarce niciun camp de business.
--
-- CE DIVULGA, si de ce e acceptabil: existenta unui subdomeniu. Aceea este oricum
-- observabila din exterior — numele DNS se rezolva sau nu. Functia nu adauga nimic
-- ce nu se poate afla cu un ping. Ce NU divulga: denumirea juridica, contactul,
-- numarul de companii, nimic din ce ar face dintr-un subdomeniu ghicit o sursa de
-- informatie.
--
-- Raspunsul HTTP ramane 404 si pentru subdomeniu inexistent, si pentru tenant
-- inactiv (IZ-37) — distinctia se face in aplicatie, nu se divulga apelantului.
-- =============================================================================

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.resolve_tenant_by_subdomain(p_subdomain citext)
RETURNS TABLE (tenant_id uuid, status text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    SELECT t.id, t.status FROM tenant t WHERE t.subdomain = p_subdomain;
$fn$;

RESET ROLE;

REVOKE ALL ON FUNCTION rls.resolve_tenant_by_subdomain(citext) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.resolve_tenant_by_subdomain(citext) TO evidenta_app;
