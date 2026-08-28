-- Inversul lui 0056. Doar constrangerile: coloanele pleaca odata cu operatiile
-- Django de deasupra, iar colatia pleaca odata cu coloana.

ALTER TABLE company_account DROP CONSTRAINT IF EXISTS company_account_required_within_slots;
ALTER TABLE coa_template_account
    DROP CONSTRAINT IF EXISTS coa_template_account_required_within_slots;
