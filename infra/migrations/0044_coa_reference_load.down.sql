-- Inversul lui 0044. Sterge doar cele doua politici adaugate acolo; nimic altceva
-- din forma tabelelor nu s-a schimbat, deci nu e nimic altceva de intors.
--
-- Reversibil, cu invers testat: derularea inapoi lasa tabelele exact cum erau —
-- globale, citibile de aplicatie, nescriibile de nimeni prin politica. Consecinta
-- operationala: incarcatorul de plan de conturi nu mai poate rula pana la o noua
-- aplicare a lui 0044.

DROP POLICY IF EXISTS coa_template_owner_write ON coa_template;
DROP POLICY IF EXISTS coa_template_account_owner_write ON coa_template_account;
