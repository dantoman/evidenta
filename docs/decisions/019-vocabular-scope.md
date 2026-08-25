# ADR-019 — Vocabularul de `module_key` și de drepturi în scope

- **Status:** Acceptat — decizie de model, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `DN-07` (Spec A §1.4)
- **Afectează:** `engagement_module_scope`, predicatul de acces al firmei, cazul obligatoriu
  „engagement cu scope restrâns" (`T2`), F0.3.3, F0.2.4

## Context

V2 §9.1 descrie scope-ul ca „ce companii, ce module, ce drepturi", fără să enumere niciunul.
Consecința practică: cazul de test „engagement cu scope restrâns", obligatoriu prin `T2` din
`CLAUDE.md`, nu poate fi scris — nu există ce să restrângi.

Decizia devine urgentă odată cu [ADR-018](018-engagementuri-multiple.md): dacă două firme se separă
prin module, modulele trebuie să aibă nume înainte ca separarea să existe.

## Opțiuni evaluate

1. **A — `module_key` = numele modulului din harta modulelor**, cu două niveluri de drept
   (`read`, `write`). Direct verificabil, scriibil azi, nu depinde de nicio altă decizie deschisă.
   Granularitate grosieră: acces la `payroll` înseamnă și vizualizarea salariilor individuale.
2. **B — catalog de permisiuni separat de module** (`payroll.view_salaries`, `payroll.run`,
   `accounting.post`). Granularitate reală, rezolvă din start confidențialitatea salariilor. Cere un
   catalog menținut și verificat mecanic, plus `DN-08` (vocabularul de roluri) închisă înainte —
   deci ar bloca F0.3.3 până la a treia decizie.
3. **C — scope pe capabilități**, reutilizând cheile din `CapabilityActivation`. Evită un al doilea
   vocabular, dar suprapune două concepte ortogonale: ce a activat tenantul, față de ce are voie
   firma să vadă. Când cele două diverg — și vor diverge — nu există loc unde să stea diferența.

## Decizie

**Opțiunea A.** `module_key` este numele modulului de business din harta modulelor
(`_input/evidenta-implementation-spec.md` §4.1), iar `permission_level` rămâne `read` sau `write`,
așa cum e deja în Spec A §1.4.

- **Cheile sunt modulele de business, nu cele de platformă.** `platform/*` — tenancy, identity,
  rls, audit, documents, numbering — este infrastructură; nu se deleagă unei firme și nu primește
  chei de scope.
- **Lista trăiește într-un singur loc**, în `platform/engagement`, și este impusă prin `CHECK`.
  Adăugarea unui modul este migrare, deliberat: un `module_key` scris liber într-un rând ar produce
  scope care nu refuză nimic, fiindcă nu s-ar potrivi cu nimic.
- **`write` include `read`.** Nivelurile sunt ordonate, nu independente.

Motivul alegerii nu este că granularitatea grosieră ar fi suficientă — nu este, iar limita e numită
mai jos. Este că A se extinde spre B **fără migrare de date**: cheile fine se adaugă peste aceleași
coloane, cu numele modulului ca prefix (`payroll` → `payroll.run`), iar rândurile existente rămân
valide ca „tot modulul". B ales acum ar fi cerut, în plus, închiderea lui `DN-08`.

## Ce rămâne în afara deciziei

**Confidențialitatea salariilor individuale nu este rezolvată de această decizie.** Cu vocabularul
de aici, o firmă cu `payroll` vede salariile individuale ale angajaților clientului. Este limita
cunoscută și acceptată a opțiunii A, nu o scăpare: dacă piața o cere înainte de F2, extinderea este
adăugarea cheii fine, nu rescrierea modelului.

`DN-08` (vocabularul de roluri pentru `Membership` și `CompanyAccess`) rămâne deschisă. Este o
decizie diferită: aici se decide ce poate vedea **firma** la client, acolo ce poate face **omul**
în interiorul unei organizații. Nu se închid una prin cealaltă.

## Consecințe

- Devine scriibil cazul obligatoriu din `T2`: engagement cu scope restrâns, se cere un modul din
  afara scope-ului, rezultat zero acces (IZ-28).
- Predicatul de acces al firmei primește un al doilea argument: nu „are engagement activ?", ci „are
  engagement activ **care acoperă modulul cerut**?".
- Fiecare modul de business viitor își declară cheia la intrarea în F0.3.3 sau printr-o migrare
  ulterioară; niciunul nu o inventează la runtime.
- Costul acceptat: o firmă cu acces la `payroll` vede tot ce ține de salarizare, inclusiv sumele
  individuale.
