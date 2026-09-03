# ADR-093 — Paginile consolei fără server se desenează, ca pagini „de implementat"

- **Stare:** Acceptat — produs, proprietar
- **Data:** 2026-09-03
- **Decis de:** proprietar, prin instrucțiune directă după livrarea ADR-092: *„creează paginile, să se
  știe că trebuie implementat"*
- **Închide:** nimic din registru
- **Restrânge:** [ADR-092](092-consola-citeste-metadate-si-administreaza-personalul.md) §4, teza
  „nu se desenează intrări pentru ele"
- **Atinge:** `frontend/src/app/console/PlannedScreen.tsx`, bara laterală a consolei, Spec A §14

## 1. Ce se decide

[ADR-076](076-planul-de-control-al-platformei.md) §4.3 enumeră nouă obiecte pe care le administrează
consola. Șase au server și pagină (ADR-091, ADR-092). Trei nu au server: **abonamentele și planurile**
(modulul de facturare nu există), **granturile de suport** (ADR-077 acceptat, neconstruit) și
**incidentele** (niciun job cu stare persistată). Întrebarea e ce vede un angajat al platformei în
locul lor.

## 2. Opțiuni evaluate

1. **Nu se desenează nimic; un rând în subsolul barei laterale spune ce lipsește** — alegerea din
   ADR-092 §4. *Avantaje:* bara laterală conține doar ce funcționează; nimeni nu ia o intrare drept
   funcționalitate. *Dezavantaje:* ce rămâne de construit nu se vede acolo unde va trăi; un rând de
   subsol e citit o dată și uitat, iar lista din ADR-076 §4.3 rămâne cunoscută doar celor care citesc
   ADR-uri.
2. **Intrări dezactivate în bara laterală.** *Dezavantaje:* un control desenat și oprit e exact
   forma pe care ADR-074 și antetul aplicației o refuză („un control care arată viu și nu răspunde
   învață oamenii să nu creadă interfața"); nu spune nici ce lipsește, nici de ce.
3. **O pagină per obiect, marcată „de implementat", care spune ce va face, ce lipsește, de ce
   decizie depinde și când se construiește.** *Avantaje:* harta drumului stă unde va trăi
   funcționalitatea; textul e ridicat din ADR-urile care o guvernează, deci nu inventează nimic;
   marcajul stă și în bara laterală, și în antetul paginii, deci intrarea nu poate fi luată drept
   funcționalitate. *Dezavantaje:* trei intrări în bara laterală care nu fac nimic încă.
   *Cost de schimbare:* zero — pagina se înlocuiește cu cea reală când apare serverul.

## 3. Decizia

**Opțiunea 3.** Trei rute pe consolă — `abonamente`, `granturi-de-suport`, `incidente` — servite de
o singură componentă, `PlannedScreen`, care nu cere nimic serverului. Fiecare pagină are patru
secțiuni fixe: *ce va face*, *ce lipsește*, *deciziile care o guvernează*, *când se construiește*.
Textele stau în fișierul de resurse (`console.planned`) și citează ADR-076, ADR-077, ADR-082,
ADR-086, Spec A §6.2 și §10.2, `R6` — nimic ce nu e deja decis. Marcajul „de implementat" apare
lângă eticheta din bara laterală și în antetul paginii.

Când unul dintre cele trei obiecte primește server, pagina „de implementat" se înlocuiește cu pagina
reală pe aceeași adresă, și textul ei se șterge din resurse. O pagină „de implementat" care
supraviețuiește implementării e un defect.

## 4. Consecințe

- **Devine posibil:** un angajat al platformei vede întreaga listă din ADR-076 §4.3 și știe, pentru
  fiecare intrare, dacă e funcțională sau nu, și de ce.
- **Se restrânge:** ADR-092 §4 — teza „nu se desenează intrări pentru ele" nu mai e valabilă; restul
  ADR-092 rămâne.
- **Ce se verifică automat:** `console.test.tsx` — pagina „Abonamente și planuri" arată marcajul,
  secțiunea „Ce lipsește" și decizia citată.
- **Spec A §14** își actualizează paragraful paginilor.

## Surse

- [ADR-074](074-sistemul-de-design-evidenta.md) (controale desenate și oprite),
  [ADR-076](076-planul-de-control-al-platformei.md) §4.3,
  [ADR-092](092-consola-citeste-metadate-si-administreaza-personalul.md) §4.
- Conversație 2026-09-03: „Abonamente și planuri: tabelele de facturare nu există… creează paginile
  să se știe că trebuie implementat".
