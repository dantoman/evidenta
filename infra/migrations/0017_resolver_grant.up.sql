-- =============================================================================
-- F0.3.5 — Grantul care lipsea rezolvatorului de subdomeniu
--
-- Fisier nou, nu o editare a lui 0016: acela a fost deja aplicat (ADR-012,
-- regula 2). Corectia este un fisier nou si o migrare noua.
--
-- CE LIPSEA. `rls.resolve_tenant_by_subdomain` este SECURITY DEFINER si apartine
-- lui `evidenta_rls`. Acela are BYPASSRLS — deci nu e oprit de POLITICI — dar nu
-- are niciun privilegiu de TABELA: 0001_roles.sql i le acorda punctual, pentru ca
-- fiecare GRANT catre un rol cu BYPASSRLS este o decizie.
--
-- Cele doua sunt lucruri diferite si se confunda usor: BYPASSRLS spune „politicile
-- nu se aplica", GRANT spune „ai voie sa atingi tabela". Prima fara a doua da
-- exact eroarea de aici: permission denied, din interiorul unei functii care
-- teoretic „ocoleste tot".
-- =============================================================================

GRANT SELECT ON tenant TO evidenta_rls;
