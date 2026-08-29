# ADR-051 — Cheile de context ale legării condiționate sunt enumerate în cod; valorile sunt date

- **Status:** Acceptat — decisă de proprietar prin instrucțiune scrisă, 2026-08-29
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului
- **Închide:** `OD-55` (deschisă prin [ADR-036](036-forma-postarii.md) §6.2)
- **Afectează:** `accounting/slots` (`AccountRoleBinding`, `resolve_role`), F1.4.2, Spec B §3.3,
  [ADR-037](037-conventii-de-platforma.md) §3.5 (nota de reconciliere)
- **Legate:** [ADR-036](036-forma-postarii.md) §2 opțiunea 1, §6.2, §10;
  [ADR-048](048-formula-si-sloturile-tipizate.md) §3.4 (`bind_roles`)

---

## 1. Context

[ADR-036](036-forma-postarii.md) §6.2 lasă un rol de cont să se lege diferit după o **cheie de
context** — grupă de nomenclator, depozit, tip de contraparte, cotă TVA — echivalentul „conturilor
de evidență" din 1C. Versiunea 1 a acelui document declara mulțimea cheilor închisă și definită în
cod; versiunea 2 nu mai afirma nimic, iar formularea „legare condiționată" singură nu decide.
`OD-55` a fost deschisă exact pentru golul acesta, cu termen „înainte de F1.4".

Ce s-a livrat între timp restrânge întrebarea: [ADR-048](048-formula-si-sloturile-tipizate.md) a
adus rolurile ca **catalog al platformei** (`accounting/slots/catalogue.py`, derivat din planul de
conturi livrat cu produsul) și legarea **necondiționată** (`AccountRoleBinding`, cu
`valid_from`/`valid_to`, per companie). Motorul le consumă prin `posting.formula.bind_roles`; un rol
nelegat refuză cu `slots.role_not_bound`. Ce lipsește e a doua dimensiune a legării — condiția — și
forma ei depinde de răspunsul de aici.

## 2. Opțiuni evaluate

1. **Chei definibile de client.** Tenantul declară o cheie nouă („zona de vânzare", „linia de
   produs") și o expresie care o extrage din evenimentul postat. *Avantaj:* acoperă orice practică
   moștenită din 1C fără muncă de produs. *Dezavantaje:* o cheie definită de client cere un
   **evaluator de expresii peste `payload`** — exact DSL-ul respins în ADR-036 §2, opțiunea 1 — și
   reproduce configurabilitatea nelimitată care face incumbentul imposibil de întreținut: o
   modificare legislativă ar trebui verificată împotriva a o mie de expresii necunoscute, câte una
   per tenant. *Cost de schimbare ulterioară:* maxim — expresiile trăiesc în tenanți și nu se pot
   retrage.
2. **Chei enumerate în cod, valori în date** — *aleasă*. Vocabularul cheilor e o enumerare a
   platformei; ce *valoare* a cheii leagă la ce cont e rând per companie. Aceeași formă ca la
   catalogul de roluri: **vocabularul e cod, valorile sunt date**. *Avantaj:* motorul știe static
   de unde citește fiecare cheie (grupa articolului, depozitul liniei, tipul partenerului, cota
   liniei), deci legarea se verifică o singură dată, în produs. *Dezavantaj:* o cheie nouă e o
   **versiune de platformă**, nu o setare de tenant — un client cu o practică neacoperită așteaptă
   ore–zile, nu configurează. *Cost de schimbare:* mic — o cheie se adaugă în enumerare cu testele
   ei; niciuna nu se scoate cât are legări.
3. **Fără legare condiționată; contul se alege în document.** *Avantaj:* zero structură.
   *Dezavantaj:* mută pe utilizator, la fiecare linie, o alegere pe care 1C o face din configurare;
   exact frecarea de migrare pe care ADR-036 §7.3 o refuză. Respinsă.

## 3. Decizie

**Cheile de context sunt enumerate în cod. Valorile lor și legările sunt date, per companie.**

Concret, pentru F1.4.2:

- **Vocabularul** trăiește în `accounting/slots`, ca enumerare cu teste: `item_group`, `warehouse`,
  `partner_type`, `vat_rate` — cele patru numite în ADR-036 §6.2. Fiecare cheie declară din ce câmp
  al formulei sau al evenimentului își citește valoarea; motorul nu evaluează nimic la runtime.
- **Legarea** — `AccountRoleBinding` primește `context_key` (din vocabular; `NULL` = legare
  necondiționată, cea de azi) și `context_value` (identificatorul valorii; `COLLATE "C"`). Unicitatea
  parțială de azi devine unicitate peste `(company, role, context_key, context_value)` pe interval de
  valabilitate, cu `NULLS NOT DISTINCT`.
- **Rezoluția**, în `resolve_role`, în ordinea: legarea condiționată care se potrivește → legarea
  necondiționată → `slots.role_not_bound`. Fără cont de rezervă (ADR-036 §5.1). O cheie prezentă în
  formulă fără legare condiționată **nu e eroare** — cade pe cea necondiționată.
- **O cheie nouă** se adaugă în enumerare, cu handlerul care o populează și testele lui — deployment,
  pentru toți tenanții (`R23`). Nu există cale prin care un tenant să declare o cheie.

## 4. Consecințe

- **Devine posibil:** F1.4.2 se deblochează — forma tabelei de legare e fixată. Echivalentul
  „conturilor de evidență" din 1C există fără evaluator de expresii, iar o schimbare legislativă se
  verifică peste un vocabular de patru chei, nu peste expresii per tenant.
- **Devine imposibil sau scump, asumat:** o practică de client care cere o axă de legare
  neenumerată e muncă de produs (ADR-036 §9.1, ultima linie). Aceasta e chiar granița pe care
  ADR-036 §11.1 o numește test de falsificare: dacă apare cazul, se mută granița **acum**, nu se
  strecoară un evaluator.
- **Ce se modifică:** [ADR-036](036-forma-postarii.md) §6.2 și §13 (rândul `OD-55`), C7 din §11;
  [ADR-037](037-conventii-de-platforma.md) §3.5, nota de reconciliere, care trimitea la `OD-55`;
  `08-f1-backlog.md` F1.4.2 („Blocat de") și tabelul de blocaje; Spec B §3.3 primește forma de aici
  la implementare.
- **Ce se verifică automat, la F1.4.2:** un test per cheie (valoare legată → contul condiționat;
  valoare nelegată → contul necondiționat; nimic → `slots.role_not_bound`); un test că legarea
  condiționată respectă `valid_from`/`valid_to` fără să atingă postările existente (ADR-036 §6.4);
  gardianul de model peste noua formă a unicității.

## 5. Surse

- Instrucțiunea proprietarului, 2026-08-29, punctul 4.
- [ADR-036](036-forma-postarii.md) §1.1 (registrele de „conturi de evidență" din 1C), §2 opțiunea 1,
  §6.2, §10.
- [ADR-048](048-formula-si-sloturile-tipizate.md) §3.4 — `bind_roles`, `slots.role_not_bound`.
- `docs/decisions/000-open-decisions.md`, rândul `OD-55`.
- `CLAUDE.md` — `R23`, `C3`, §4 („nu se pornesc … DSL").
