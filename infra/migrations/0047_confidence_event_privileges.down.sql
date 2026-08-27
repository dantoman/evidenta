-- Inversul lui 0047: reacorda privilegiile de scriere, adica starea de dinainte.
--
-- Reversibil, cu invers testat, si cu consecinta scrisa: derularea inapoi pune la
-- loc niste privilegii pe care RLS oricum nu le lasa sa produca efect. Nu
-- redeschide nimic azi — dar daca intre timp cineva adauga o politica de scriere
-- pe aceasta tabela, le redeschide pe amandoua deodata.

GRANT INSERT, UPDATE, DELETE ON fiscal_parameter_confidence_event TO evidenta_app;
