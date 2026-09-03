-- Reverse of 0080: the default privileges back, the collation back to the database's.
ALTER TABLE settlement ALTER COLUMN currency TYPE varchar(3);

GRANT UPDATE, DELETE ON settlement TO evidenta_app;
GRANT UPDATE, DELETE ON revaluation_item TO evidenta_app;
GRANT UPDATE, DELETE ON revaluation TO evidenta_app;
