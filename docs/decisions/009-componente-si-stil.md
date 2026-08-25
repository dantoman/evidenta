# ADR-009 — Biblioteca de componente și stratul de stil: shadcn/ui + Tailwind

- **Status:** Acceptat — 2026-08-24, de proprietarul proiectului, sub regimul `ADR-002`
  (decizie tehnică, fără conținut contabil)
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `OD-34` din `000-open-decisions.md`. Deblochează `OD-35` (scara de densitate)
- **Afectează:** `frontend/src/shared/`, F0.10, `DataGrid` și `EntryGrid` (`ADR-001`)

## Context

`ADR-001` a stabilit grila, dar TanStack Table este headless: nu randează nimic. Rămânea de ales ce
randează — biblioteca de componente și stratul de stil.

Decizia blochează `OD-35` (scara de densitate), pentru că densitatea nu se poate exprima ca tokeni
înainte să existe un sistem de tokeni. Blochează și F0.10.3.

Orizontul produsului este lung. O aplicație contabilă cu conformitate SNC, TVA și e-Factura se
întreține ani, nu luni; o bibliotecă de UI care face un rewrite major la fiecare doi ani transferă
acel cost în proiect.

## Opțiuni evaluate

1. **shadcn/ui + Tailwind.** Componentele se copiază în repo și devin cod al proiectului; Tailwind
   dă utilitarele.
   *Avantaje:* nicio dependență de UI care să se rupă la o versiune majoră; sursa componentei e
   citibilă și modificabilă, inclusiv de un agent care lucrează în repo; utilitarele fac ieftină
   ajustarea de densitate, care într-un ERP se face constant și pe multe ecrane.
   *Dezavantaje:* fixurile din amonte nu ajung automat; volumul de cod în repo crește.
   *Cost de schimbare ulterioară:* mediu — componentele sunt ale noastre, deci schimbarea e
   rescriere, nu migrare.

2. **Bibliotecă completă (MUI, Mantine, Ant Design).**
   *Avantaje:* acoperire largă imediat, inclusiv componente pe care shadcn nu le are.
   *Dezavantaje:* deține stilul și impune propriul sistem de teme; ajustarea densității se face
   împotriva bibliotecii; un rewrite major în amonte devine problema noastră.
   *Cost de schimbare ulterioară:* mare — atinge fiecare ecran.

3. **Componente proprii peste CSS modules sau CSS-in-JS.**
   *Avantaje:* control total, zero dependențe.
   *Dezavantaje:* rescrie accesibilitatea, focus management și comportamentul de overlay — muncă
   rezolvată, cu multe moduri subtile de a o face greșit.
   *Cost de schimbare ulterioară:* —

## Decizie

**shadcn/ui + Tailwind.** Cinci consecințe se scriu explicit, ca să nu revină ca întrebări:

**1. shadcn se copiază, nu se instalează.** Componentele intră în repo și devin cod al proiectului.
Nu există pachet `shadcn/ui` în manifest. Actualizările din amonte **nu vin automat** — acesta este
în egală măsură avantajul (nu îl rupe o versiune majoră peste trei ani) și costul (fixurile lor nu
ajung la noi; se preiau manual, conștient, dacă se preiau).
*Un agent care vede o componentă shadcn nu trebuie să presupună că e dependență și să încerce să o
„actualizeze".* Nu este. Este cod al proiectului, ca oricare altul.

**2. Componentele copiate se modifică liber.** Nu sunt bibliotecă, deci nu există motiv să rămână
identice cu sursa. **Dar modificarea merge în componenta din `frontend/src/shared/`, niciodată
într-o copie locală per ecran.** O componentă copiată a doua oară ca să fie modificată pentru un
singur ecran este defect, nu adaptare.

**3. Tailwind nu se amestecă cu CSS scris de mână** decât acolo unde utilitarele chiar nu ajung.
Locul acela este cunoscut dinainte: `DataGrid` și `EntryGrid`, unde virtualizarea cere control fin
asupra poziționării și înălțimii rândurilor.
*Excepția este numită aici tocmai ca să rămână excepție, nu precedent.* CSS scris de mână în afara
celor două componente se ridică, nu se adaugă.

**4. Tokenii de design sunt sursa unică.** Culori, spațiere, tipografie — definite ca variabile CSS
în configurația Tailwind și consumate peste tot. Fără valori literale în componente.
Aici se leagă `OD-35`: **scara de densitate devine un set de tokeni, nu o convenție verbală.**
Acesta este motivul pentru care `OD-34` o bloca, iar `C21` din `CLAUDE.md` — „spațierea folosește
scara de densitate, fără valori hardcodate" — devine verificabilă abia acum.

**5. Cifre tabulare pentru orice coloană numerică.** `font-variant-numeric: tabular-nums`, definit
ca token și aplicat de `DataGrid` și `EntryGrid` la coloanele numerice, nu presărat prin ecrane.
Fără el, coloanele de sume se mișcă vizual de la un rând la altul; un contabil observă imediat.
Este o linie de CSS — exact genul de detaliu care, nescris aici, ajunge aplicat pe alocuri.

## Consecințe

- Devine posibil: `OD-35` — scara de densitate se poate exprima acum ca tokeni.
- Devine imposibil, prin regulă: „actualizarea" componentelor shadcn ca și cum ar fi dependență;
  copii locale de componente per ecran; CSS de mână în afara celor două grile.
- De modificat ca urmare:
  - `OD-34` trece în „Închise";
  - `CLAUDE.md` §2.6 primește regulile de mai sus ca `C23`–`C27`;
  - `frontend/src/shared/` devine locul unic al componentelor copiate.
- Se verifică automat: `C25` (fără CSS de mână în afara grilelor) și absența valorilor literale de
  culoare și spațiere se pot prinde cu reguli ESLint și cu un lint de stil. Regulile concrete se
  scriu la F0.10; până atunci sunt convenție, iar acest ADR spune că sunt convenție.

## Surse

- `decisions/001-grila-de-date.md` (TanStack headless — de aici nevoia unui strat de randare).
- `000-open-decisions.md`: `OD-34`, `OD-35`, `OD-19`.
- `CLAUDE.md` §2.6.
- Conversație 2026-08-24.
