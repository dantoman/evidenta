-- Inversul lui 0062: triggerul, apoi functia, sub rolul care o detine (ADR-043 §5).

DROP TRIGGER IF EXISTS journal_line_carries_the_entry_date ON journal_line;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.journal_line_date_is_the_entrys();
RESET ROLE;
