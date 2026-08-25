-- =============================================================================
-- F0.3.7a — corecție: catalogul avea un singur strat de apărare, nu două
--
-- Autoritate:  docs/decisions/020-roluri-ca-date.md
--              infra/bootstrap/0001_roles.sql (privilegii implicite)
--
-- CE ERA GREȘIT. `0019_roles.up.sql` scria `GRANT SELECT ON permission TO
-- evidenta_app` și comenta că aplicația doar citește. Instrucțiunea era însă
-- fără efect: `ALTER DEFAULT PRIVILEGES` din bootstrap acordă deja CRUD complet
-- pe orice tabelă creată de owner, iar GRANT nu poate îngusta ceva — doar adaugă.
--
-- Aplicația chiar nu putea scrie, dar exclusiv prin politica RLS. Comentariul
-- descria două straturi acolo unde exista unul, iar diferența s-ar fi văzut abia
-- în ziua în care o migrare viitoare adaugă din greșeală o politică permisivă.
-- =============================================================================

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON permission FROM evidenta_app;
