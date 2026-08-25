# Suita 1 — penetrare

Autentificat ca Tenant A, se încearcă accesul la **fiecare tip de resursă** a lui Tenant B:
facturi, înregistrări contabile, payroll, atașamente, obiecte API, read models.
Rezultat așteptat: **acces zero, în toate cazurile.**

Cazuri obligatorii, ușor de uitat:

- engagement expirat
- engagement revocat
- engagement cu scope restrâns
- task Celery fără context setat

**Rulează sub rolul de aplicație**, niciodată ca superuser sau owner de tabelă. Un test rulat ca
owner ocolește RLS și nu demonstrează nimic.

Se scrie la F0.2, înaintea oricărui model. Rulează la fiecare commit.
