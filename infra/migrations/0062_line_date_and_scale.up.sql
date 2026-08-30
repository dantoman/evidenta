-- Linia poarta data inregistrarii, nu una a ei — ADR-059.
--
-- `journal_line.accounting_date` e cheia de partitionare (ADR-032) si, prin
-- ADR-039 §9, „data postarii" — una singura per inregistrare. Pana azi motorul
-- cerea doar ca liniile sa cada in aceeasi perioada cu antetul, iar nota manuala
-- lasa o linie sa poarte alta zi din aceeasi luna. Nimic contabil nu cerea asta:
-- data economica are coloana ei, `document_date`. Costul aparea in rapoarte —
-- fisa contului data un rand dupa linie si registrul dupa antet, iar Cartea Mare
-- putea taia o nota in doua la marginea ferestrei.
--
-- Motorul refuza primul (`posting.line_date_differs`); triggerul e a doua
-- bariera, pentru importul si migrarile de date care nu trec prin motor —
-- acelasi tipar ca `journal_entry_needs_open_period` din 0036.
--
-- Scara sumelor sta in `Meta` (Django o poate exprima): `debit`, `credit` si
-- `amount` la doua zecimale, conventia aprobata in ADR-037 §3.2. Aici e doar ce
-- Django nu poate spune.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_line_date_is_the_entrys() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    entry_date date;
BEGIN
    SELECT accounting_date INTO entry_date FROM journal_entry WHERE id = NEW.journal_entry_id;

    IF entry_date IS NULL THEN
        RAISE EXCEPTION 'journal_line names entry % which does not exist', NEW.journal_entry_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF NEW.accounting_date <> entry_date THEN
        RAISE EXCEPTION 'journal_line dated % belongs to entry % dated %; a line carries '
                        'the posting date of its entry (ADR-039 §9, ADR-059)',
            NEW.accounting_date, NEW.journal_entry_id, entry_date
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION rls.journal_line_date_is_the_entrys() FROM PUBLIC;
-- ADR-043 §4.1: CREATE TRIGGER verifica EXECUTE la creare, ca `evidenta_owner`.
GRANT EXECUTE ON FUNCTION rls.journal_line_date_is_the_entrys() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER journal_line_carries_the_entry_date
    BEFORE INSERT ON journal_line
    FOR EACH ROW EXECUTE FUNCTION rls.journal_line_date_is_the_entrys();
