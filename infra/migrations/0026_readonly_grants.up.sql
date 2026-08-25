-- =============================================================================
-- Retragerea scrierii de pe tabelele globale declarate „doar citire"
--
-- Fisier nou, nu o editare a lui 0023: acela a fost deja aplicat (ADR-012).
--
-- CE S-A GASIT. `0001_roles.sql` acorda privilegii implicite de INSERT, UPDATE si
-- DELETE catre `evidenta_app` pentru fiecare tabela creata de owner. Este exact
-- ce trebuie pentru tabelele de business — si gresit pentru cele globale, unde
-- singurul lucru care oprea scrierea era absenta unei politici de INSERT.
--
-- Absenta unei politici nu e o interdictie, e o omisiune care se comporta ca una.
-- O migrare viitoare care adauga o politica de scriere din alt motiv ar fi
-- deschis tacit scrierea — iar `feature_flag` si `release_ring` descriu codul,
-- deci un tenant care le-ar putea scrie ar schimba comportamentul pentru toti.
--
-- Gasit pentru ca un test astepta „permission denied" si a primit „row-level
-- security policy". Refuzul era corect; stratul care refuza, nu.
-- =============================================================================

REVOKE INSERT, UPDATE, DELETE ON feature_flag  FROM evidenta_app;
REVOKE INSERT, UPDATE, DELETE ON release_ring  FROM evidenta_app;
