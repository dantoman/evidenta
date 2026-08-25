# Suita 2 — gardian de model

Enumeră **toate** tabelele din schemă și eșuează dacă vreuna:

- nu are coloană de context de tenant
- nu are politică RLS activă
- nu are `FORCE ROW LEVEL SECURITY`

Excepțiile sunt o **listă versionată**, ținută în acest director. Lista limitativă completă este
decizie deschisă (Spec A) — vezi `docs/decisions/000-open-decisions.md`. Cunoscute până acum:
registrul global de contrapărți, parametrii fiscali, cursul BNM, tabelele de sistem Django.

Suita 1 prinde bug-urile de azi. Suita 2 prinde tabela pe care cineva o adaugă peste trei ani fără
să știe regula. A doua este mai valoroasă pe termen lung.

Rulează sub rolul de aplicație, la fiecare commit. Se scrie la F0.2.
