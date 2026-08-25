# BOOTSTRAP.md — Instrucțiune de inițializare pentru Claude Code

**Proiect:** Evidenta.md — platformă contabilă și ERP pentru Republica Moldova
**Faza curentă:** inițializare. Nu se scrie cod de producție.

---

## 0. Rolul tău în această sesiune

Ești responsabil de transformarea documentelor de strategie și arhitectură într-un repo funcțional, cu toate artefactele de lucru necesare. **Nu implementezi nimic din produs în această fază.** Construiești structura, regulile, agenții, specificațiile și planul de lucru care vor guverna implementarea ulterioară.

Lucrezi în **etape numerotate, cu oprire obligatorie după fiecare.** După fiecare etapă raportezi ce ai creat și aștepți confirmarea umană înainte de a continua. Nu treci la etapa următoare din proprie inițiativă.

---

## 1. Documentele de intrare

Următoarele fișiere există deja în `docs/_input/`. Le citești integral înainte de orice acțiune:

| Fișier | Conținut |
|---|---|
| `master-plan-v2.md` | Viziune, arhitectură, roadmap F0–F5, structură comercială, riscuri |
| `amendment-1.md` | Modifică V2. **Unde există conflict, amendamentul prevalează.** |
| `implementation-spec.md` | Structura modulelor, invarianți, definiții de agenți, etape detaliate F0/F1 |

**Regulă de precedență:** `amendment-1.md` > `master-plan-v2.md`. Dacă găsești o afirmație în V2 care este corectată în amendament, folosești versiunea din amendament și **semnalezi** conflictul în raportul tău, ca să se poată consolida ulterior.

---

## 2. Reguli absolute pentru faza de inițializare

Acestea nu se negociază și nu se interpretează.

1. **Nu scrii cod de producție.** Niciun model Django, nicio migrare, niciun endpoint, nicio componentă React. Configurări, documentație, definiții de agenți și schelete de directoare — da.

2. **Nu inventezi decizii.** Documentele de intrare conțin o listă explicită de decizii deschise. Dacă o sarcină ar necesita închiderea uneia dintre ele, **te oprești și întrebi**. O decizie închisă tacit în cod este cea mai costisitoare eroare posibilă în acest proiect.

3. **Nu completezi golurile din memorie.** Dacă un detaliu lipsește din documentele de intrare — un câmp, o regulă, un termen legal — îl notezi ca întrebare deschisă. Nu îl deduci și nu îl inventezi. Legislația fiscală a Republicii Moldova nu se ghicește.

4. **Te oprești la fiecare checkpoint.** Chiar dacă etapa următoare pare evidentă și rapidă.

5. **Nu reorganizezi documentele de intrare.** `docs/_input/` este read-only. Dacă găsești erori, le raportezi.

6. **Fiecare artefact pe care îl creezi trebuie să fie autosuficient.** Definițiile de agenți nu moștenesc context din conversație. `CLAUDE.md` este citit fără restul documentelor. Scrii ca pentru un cititor care nu a văzut nimic altceva.

---

## 3. Etapele

### ETAPA 0 — Inventar și raport de goluri

**Livrabil:** `docs/_bootstrap/00-inventory.md`

Citești integral cele trei documente de intrare și produci:

1. **Inventarul invarianților** — lista completă, numerotată, a regulilor arhitecturale, cu sursa (document + secțiune). Marchezi care sunt verificabile automat și care necesită review uman.

2. **Inventarul modulelor** — lista completă, cu faza de implementare și faza de modelare pentru fiecare.

3. **Registrul deciziilor** — separat în:
   - decizii închise (cu ce s-a decis și unde)
   - decizii deschise (cu ce blochează și când trebuie luate)

4. **Raport de conflicte** — orice loc unde V2 și amendamentul se contrazic, cu indicarea versiunii care prevalează.

5. **Raport de goluri** — ce este necesar pentru implementare dar nu există în documentele de intrare. Fii exhaustiv și specific. Exemple de tipuri de goluri așteptate: câmpuri de entitate nedefinite, politici RLS descrise doar conceptual, formate de raportare instituțională nespecificate, praguri legislative nedocumentate.

**Criteriu de calitate:** un inginer care citește doar acest inventar trebuie să știe exact ce e decis, ce nu e decis, și ce lipsește.

**OPREȘTE-TE.** Raportează și așteaptă confirmarea.

---

### ETAPA 1 — Schelet de repo și CLAUDE.md

**Livrabile:**
- structura de directoare conform secțiunii 3 din `implementation-spec.md`
- `CLAUDE.md` în rădăcină
- `README.md`
- `.gitignore`
- `docker-compose.yml` (schelet, servicii: postgres, redis, backend, frontend)
- `Makefile` (comenzi de bază)

**Despre `CLAUDE.md` — cel mai important artefact al acestei etape.**

Conține exclusiv: invarianții (secțiunea 1 din implementation-spec), stack-ul și convențiile (secțiunea 2), regulile de dependență între module (secțiunea 4.3), și lista „ce nu se face" (secțiunea 8).

**Nu conține:** roadmap, justificări, discuție de produs, unit economics, riscuri. Acelea stau în `docs/`.

Constrângeri de formă:
- Reguli imperative, la persoana a doua sau la infinitiv. „Fiecare tabelă business are `tenant_id`", nu „ar fi bine ca tabelele să aibă".
- Fiecare regulă verificabilă. Dacă o regulă nu poate fi verificată de un om sau de un test, reformuleaz-o până devine verificabilă sau scoate-o.
- Fără redundanță. O regulă apare o singură dată.
- Ținta: sub 300 de linii. Este citit la fiecare sesiune, deci fiecare linie costă context.

**Directoarele goale nu se creează.** Structura de module din `implementation-spec.md` secțiunea 4.1 este o hartă de referință, nu un scaffold. Creezi doar directoarele care vor conține fișiere în F0.

**OPREȘTE-TE.** Raportează structura creată și conținutul `CLAUDE.md` și așteaptă confirmarea.

---

### ETAPA 2 — Agenți și comenzi

**Livrabile:**
- `.claude/agents/tenancy-guard.md`
- `.claude/agents/schema-reviewer.md`
- `.claude/agents/accounting-reviewer.md`
- `.claude/agents/fiscal-reviewer.md`
- `.claude/agents/test-author.md`
- `.claude/agents/repo-explorer.md`
- `.claude/commands/new-module.md`
- `.claude/commands/review-migration.md`
- `.claude/commands/isolation-check.md`

Definițiile de agenți există în secțiunea 5.2 din `implementation-spec.md`. Le transferi ca atare, dar le **verifici și le completezi** pentru:

- fiecare `description` conține un declanșator clar, pentru că el determină când se face delegarea
- fiecare agent are setul minim de unelte necesar, nu mai mult
- agenții de review sunt read-only fără excepție
- corpul fiecărui agent este autosuficient: nu presupune că a văzut conversația principală sau `CLAUDE.md`
- fiecare agent are format de ieșire explicit

**Comenzile** din `.claude/commands/` le scrii tu, pe baza fluxurilor descrise în secțiunea 5.3. Fiecare comandă descrie un workflow repetabil, cu pașii și delegările necesare.

**OPREȘTE-TE.** Raportează și așteaptă confirmarea.

---

### ETAPA 3 — Infrastructură de documentație și stare

**Livrabile:**

1. **`docs/` reorganizat:**
```
docs/
├── _input/              (read-only, neatins)
├── _bootstrap/          (rapoartele tale din etapele 0-6)
├── specs/               (Spec A, Spec B — etapele 4-5)
├── decisions/           (ADR-uri)
└── PROGRESS.md          (starea proiectului)
```

2. **`docs/decisions/README.md`** — formatul ADR și indexul. Fiecare decizie primește un fișier numerotat: context, opțiuni evaluate, decizia, consecințe, dată, status.

3. **`docs/decisions/000-open-decisions.md`** — registrul deciziilor deschise din Etapa 0, cu ce blochează fiecare și termenul până la care trebuie luată.

4. **`docs/PROGRESS.md`** — fișierul de stare. Acesta este mecanismul prin care munca supraviețuiește resetării contextului între sesiuni.

Structura minimă a `PROGRESS.md`:

```markdown
# Stare proiect

## Faza curentă
F0 — Fundament

## Ultima sesiune
Data, ce s-a făcut, unde s-a oprit

## Sarcini
- [x] F0.1 Roluri DB și infrastructură RLS
- [ ] F0.2 Suitele de verificare    ← ÎN CURS
- [ ] F0.3 Tenancy și identitate
...

## Blocaje active
Ce împiedică progresul acum

## Decizii luate în această fază
Trimiteri către docs/decisions/

## Întrebări deschise către om
Ce aștept răspuns
```

**Regulă permanentă, de adăugat în `CLAUDE.md`:** `PROGRESS.md` se actualizează la începutul și la sfârșitul fiecărei sesiuni de implementare. O sesiune care nu actualizează starea lasă proiectul într-o poziție din care următoarea sesiune trebuie să reconstruiască contextul ghicind.

**OPREȘTE-TE.** Raportează și așteaptă confirmarea.

---

### ETAPA 4 — Draft Spec A

**Livrabil:** `docs/specs/spec-a-tenancy.md`

Aceasta este specificația blocantă. Fără ea, sarcinile F0.3–F0.7 nu au destul detaliu pentru implementare.

Conținut obligatoriu:

1. **Entități cu câmpuri complete:** `Tenant`, `Company`, `Firm`, `Engagement`, `User`, `Membership`, `CompanyAccess`, `CapabilityActivation`.
   Pentru fiecare: câmpuri, tipuri, constrângeri, indici, relații, reguli de ciclu de viață.

2. **Politicile RLS în formă aproape-SQL.** Nu descriere conceptuală. Forma efectivă a politicii pentru cele două căi de acces (membru al tenantului; engagement activ al firmei), plus comportamentul fail-closed.

3. **Contextul de sesiune:** ce variabile se setează, unde, de către cine, cum se garantează prezența lor în request și în task-uri Celery.

4. **Ciclul de viață al Engagement-ului:** stări, tranziții permise, cine le poate declanșa, ce se întâmplă cu accesul la revocare, ce se păstrează în istoric.

5. **Nivelurile tabelelor:** ce e global, ce e tenant, ce e companie. Lista excepțiilor de la regula `tenant_id`, enumerată limitativ.

6. **Căile privilegiate cross-tenant:** enumerate limitativ, cu justificare, cu mecanismul de audit pentru fiecare.

7. **Read models:** structura, ce agregate conțin, cum se actualizează, de ce sunt singurul loc unde interogarea cross-tenant e permisă.

8. **Cazurile de test de izolare:** enumerate explicit, ca listă din care se pot scrie testele direct. Include cazurile ușor de uitat: engagement expirat, revocat, cu scope restrâns, task fără context.

9. **Restaurare, export, offboarding, retenție:** cele trei concepte separate conform amendamentului, cu limitele explicite ale fiecăruia.

10. **Model de billing:** wholesale și direct, relația cu `CapabilityActivation`, separarea capability set de plan comercial.

**Regula de aur pentru această etapă:** unde documentele de intrare nu îți dau suficient pentru a specifica ceva, **scrii explicit „DECIZIE NECESARĂ" cu opțiunile și implicațiile fiecăreia**, și continui. Nu alegi singur. La final, listezi toate punctele marcate astfel.

**OPREȘTE-TE.** Acest draft necesită review uman atent înainte de a fi considerat valid. Raportează și așteaptă.

---

### ETAPA 5 — Draft Spec B

**Livrabil:** `docs/specs/spec-b-accounting.md`

Conținut obligatoriu:

1. **Structura ledgerului:** `AccountingEvent`, `JournalEntry`, `JournalLine`, cu câmpuri, constrângeri, dimensiuni analitice.
2. **Planul de conturi SNC** ca date versionate: template global, instanță per companie, conturi de sistem vs. subconturi, politica de propagare a modificărilor legislative.
3. **Posting Engine:** structura regulilor, rezoluția, condiționarea pe capabilități, datele efective.
4. **Maparea document → postare:** formatul regulilor, cu exemple.
5. **Motorul de reguli fiscale:** separarea parametri (date) / logică (cod versionat), registrul de selecție după dată efectivă.
6. **Perioade:** stări, închidere, redeschidere, blocare la postare.
7. **Multi-valută:** modelul de sumă, cursuri, diferențe, reevaluare.
8. **Solduri inițiale:** structura pentru GL, parteneri, stocuri, active, angajați.
9. **Storno și lineage:** structura corecției, cele două legături, coerența drill-down-ului.
10. **Idempotență și deduplicare:** unde stau cheile, ce constrângeri le impun.

Aceeași regulă: „DECIZIE NECESARĂ" unde lipsește informație. Nu inventezi.

**OPREȘTE-TE.**

---

### ETAPA 6 — Backlog F0

**Livrabil:** `docs/_bootstrap/06-f0-backlog.md`

Descompui Faza 0 în sarcini de dimensiunea unei sesiuni Claude Code. Pentru fiecare:

- identificator (F0.1, F0.2, ...)
- obiectiv într-o propoziție
- fișiere care se creează sau se modifică
- dependențe față de alte sarcini
- agenții de review care trebuie invocați la final
- criteriu de terminare, verificabil
- decizii deschise care o blochează, dacă există

**Constrângere de dimensionare:** o sarcină care atinge mai mult de un modul sau care nu poate fi verificată printr-un criteriu clar este prea mare. O descompui.

**Ordinea din `implementation-spec.md` secțiunea 6.1 este obligatorie.** În special: rolurile de bază de date (F0.1) și suitele de verificare (F0.2) preced orice model. Nu se rearanjează.

**OPREȘTE-TE.** După confirmarea acestei etape, inițializarea e completă și începe implementarea.

---

## 4. Cum raportezi la fiecare checkpoint

Format fix, scurt:

```
ETAPA N — terminată

Creat:
- cale/fisier.md — ce conține, în câteva cuvinte

Decizii pe care NU le-am luat (necesită răspuns uman):
- întrebarea, cu opțiunile și implicațiile

Conflicte sau erori găsite în documentele de intrare:
- ce am găsit, unde

Următoarea etapă: N+1 — titlul
Aștept confirmarea.
```

Nu repeți conținutul fișierelor create în raport. Omul le poate deschide.

---

## 5. Ce faci când întâlnești ambiguitate

Ordinea de acțiune, strictă:

1. **Caută în documentele de intrare.** Poate răspunsul există într-o secțiune pe care nu ai corelat-o.
2. **Verifică amendamentul.** Poate V2 spune un lucru și amendamentul îl corectează.
3. **Dacă tot lipsește:** notezi ca „DECIZIE NECESARĂ" sau „GOL DE INFORMAȚIE", cu opțiunile identificate și implicațiile fiecăreia, și **continui cu restul**. Nu blochezi întreaga etapă pentru un punct.
4. **La checkpoint, raportezi toate punctele deschise.**

Ce nu faci niciodată: alegi o variantă „rezonabilă" și mergi mai departe fără să spui. Într-un sistem contabil, o presupunere tăcută despre o regulă fiscală, un termen de raportare sau o structură de cont devine un defect care se descoperă la un client, nu în teste.

---

## 6. Ce nu faci în această fază

- Nu scrii modele Django, migrații, endpoint-uri sau componente React
- Nu creezi directoare goale pentru module din faze viitoare
- Nu instalezi dependențe și nu rulezi `pip install` sau `npm install` dincolo de ce cere scheletul
- Nu modifici `docs/_input/`
- Nu treci la etapa următoare fără confirmare
- Nu închizi decizii marcate ca deschise
- Nu deduci reguli fiscale, praguri, cote sau formate de raportare din memorie
- Nu comprimi și nu rescrii documentele de intrare — sunt referință, nu material de prelucrat

---

## 7. Primul lucru pe care îl faci

Citește integral cele trei documente din `docs/_input/`. Apoi execută Etapa 0.

Nu confirma că ai înțeles. Începe.
