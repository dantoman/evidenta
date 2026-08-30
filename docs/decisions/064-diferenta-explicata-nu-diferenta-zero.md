# ADR-064 — Punctul 3 al criteriului de ieșire din F2: diferență explicată, nu diferență zero

- **Status:** **Acceptat** — decizie de **scop**, a proprietarului, sub regimul
  [ADR-002](002-guvernanta-deciziilor.md)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** — *(rescrie un punct al criteriului de ieșire din F2; punctele 1 și 2 rămân, amânate
  cu declanșator — §5)*
- **Afectează:** criteriul de ieșire din F2 (`_bootstrap/09-f2-backlog.md`), `F2.B5` (rularea în
  paralel)
- **Legate:** [ADR-054](054-importul-e-distributie-corpusul-e-intern.md),
  [ADR-010](010-contabilul-practicant.md)

## 1. Context

Criteriul de ieșire din F2, din spec §6, are trei puncte, toate externe. Al treilea:

> Rulare payroll în paralel cu **diferență zero** pe cel puțin trei companii-pilot

Raportul pe fiecare punct — blochează construcția sau doar validarea — e în
`_bootstrap/09-f2-backlog.md`, §„Întrebarea reformulată". Concluzia lui: niciunul dintre cele trei
nu blochează construcția; toate trei blochează câte o bifă; două au echivalent intern verificabil în
CI.

Proprietarul a amânat rescrierea criteriului până la alegerea companiei-pilot — **cu o excepție,
punctul 3**, care se rescrie acum.

## 2. De ce punctul 3 nu poate aștepta pilotul

**„Diferență zero contra 1C" presupune că 1C are dreptate.**

Un Evidenta corect contra unui 1C greșit n-ar atinge niciodată zero. Formulat ca bifă, criteriul
**obligă produsul să fie la fel de greșit ca incumbentul** ca să poată fi declarat gata — exact
inversul a ce validează rularea în paralel.

Nu e nevoie de pilot ca să se știe asta. E o proprietate a formulării, nu a datelor; se vede citind
criteriul, iar amânarea lui până la pilot ar însemna descoperirea în momentul cel mai scump: pe date
reale, cu clientul de față, cu răspunsul „criteriul e greșit" în loc de „iată diferența și de ce".

## 3. Decizie

Punctul 3 al criteriului de ieșire din F2 devine:

> Rulare payroll în paralel pe cel puțin trei companii-pilot, cu, pentru fiecare, **fie diferență
> zero, fie fiecare diferență explicată una câte una**, cu motiv.

„Explicată" înseamnă atribuită unei cauze numite — parametru diferit, interpretare diferită a unei
reguli, defect al unuia dintre cele două sisteme — nu tolerată.

**Starea de produs nu se decide aici.** Raportul de diferențe are nevoie de o stare „diferență
explicată", cu motiv, în tiparul lui `unassigned` din Cartea Mare: o diferență cinstită între două
citiri, purtată vizibil, nu ascunsă. **Forma ei e a lui `F2.B5`** — model, ecran, export — și se
decide în sarcina care o construiește. Aici se fixează doar ce trebuie să poată fi bifat.

## 4. Ce nu se schimbă

Punctele 1 și 2 rămân cum sunt scrise. Verificarea internă care se poate face înaintea pilotului
rămâne cea din `09-f2-backlog.md`: trei luni consecutive închise pe o companie sintetică de servicii,
fiecare raport generat sub contextul românesc și validat contra formularului citit, diferență zero
între registrele TVA și fișa conturilor de TVA, între IPC21 și rulări, între situații și balanță.

**Ce rămâne al pilotului rămâne al pilotului:** divergența dintre înțelegerea noastră și practica
instituției — exact ce corpusul intern nu poate prinde, și același loc unde
[ADR-054](054-importul-e-distributie-corpusul-e-intern.md) a lăsat divergența pentru F1.

## 5. Ce rămâne deschis, cu declanșator

- **Rescrierea punctelor 1 și 2** — despicarea punctului 2 în „generat și validat contra
  formularului" (intern) și „depus și acceptat" (extern), cum s-a făcut la F1. **Declanșator:
  alegerea companiei-pilot.** Atunci consecința de calendar devine reală și „ce înseamnă acceptat"
  încetează să fie ipotetic.
- **Ce se construiește în trimestrul de pilot** (F3?) — întrebare de planificare de fază, nu de
  criteriu. Merge cu descompunerea F3.

**Consecința de calendar, consemnată ca să nu fie o surpriză:** cât timp punctul 1 rămâne scris așa,
F2 nu se poate închide mai devreme de trei luni după începutul pilotului, oricât de gata ar fi codul.

## 6. Consecințe

- **Devine posibil:** bifarea cinstită a punctului 3. Înainte era imposibilă în cazul în care
  produsul e mai corect decât incumbentul — adică exact în cazul pe care produsul îl urmărește.
- **Devine imposibil:** raportarea unei rulări în paralel ca „reușită" cu diferențe nenumite.
- **De modificat ca urmare:** criteriul de ieșire din `_bootstrap/09-f2-backlog.md`; `F2.B5` primește
  starea „diferență explicată" în obiectivul lui.
- **Se verifică intern, înainte de pilot:** raportul arată zero pe cazurile interne, găsește o
  diferență plantată la angajatul și componenta corecte, **și o poate purta ca explicată**.

## 7. Surse

- Spec §6 (criteriul de ieșire din F2, text original).
- `_bootstrap/09-f2-backlog.md`, §„Întrebarea reformulată" — raportul pe fiecare punct, 2026-08-30.
- [ADR-054](054-importul-e-distributie-corpusul-e-intern.md) — tiparul: ce se verifică intern se
  separă de ce cere o instituție.
- Instrucțiunea proprietarului, 2026-08-30.
