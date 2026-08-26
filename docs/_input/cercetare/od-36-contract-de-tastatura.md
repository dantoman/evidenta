# `OD-36` — Contractul de introducere cu tastatura pentru `EntryGrid`

- **Data cercetării:** 2026-08-26
- **Stare:** material pentru ADR. **Doi agenţi încă rulează** (tiparul ARIA `grid`; moduri de eşec în
  grile reale), iar §5 e declarat incomplet de autorul lui. **Nu se scrie ADR-ul până nu se închid.**
- **Sursa primară pentru 1C:** ghidul oficial de utilizare 1C:Предприятие 8.3
  (`instrukciya-po-ehkspluatacii-v8.pdf`, publicat de 1C pe v8.1c.ru), **§4.2 „Поля"** şi **§4.8
  „Таблица"** — descărcat şi citit, nu rezumat de pe bloguri.

---

## 1. Modelul real 1C pentru introducerea în părţi tabelare

| Tastă | Formularea 1C, verbatim | Înseamnă |
|---|---|---|
| **Enter** *(celulă selectată)* | «Чтобы начать редактирование ячейки, следует нажать клавишу **Enter**» | Începe editarea |
| **Enter** *(în editare)* | «Нажатие клавиши Enter после указания значения реквизита **переводит курсор в следующую ячейку**» | Confirmă şi trece la **următoarea celulă din rând** — orizontal, nu în jos |
| **Tab** | «Возможность перехода между ячейками строки… с помощью повторного нажатия Enter **или клавиши Tab**» | La fel ca Enter; configurabil la etapa de configurare |
| **Ins** | «Для ввода в таблицу новой строки следует нажать клавишу **Ins**. Новая ячейка строки автоматически переключается в режим редактирования» | Rând nou, prima celulă **intră singură în editare** |
| **↓ pe ultimul rând** | «новая строка может быть создана автоматически при нажатии клавиши Стрелка вниз в последней строке» | Poate crea rând nou |
| *(rând nou gol)* | «Если при редактировании новой строки не была введена информация ни в одну ячейку, то новая строка будет удалена» | Rândul neatins se aruncă singur |
| **Del** | «**ВНИМАНИЕ!** Удаление строки производится **без дополнительного предупреждения**» | Şterge rândul — **1C însuşi îl marchează ca pericol** |
| **F9** | «выберите… строку, которая будет служить образцом, и следует нажать клавишу **F9**» | Dublează rândul |
| **Shift+F2** | «Для завершения редактирования **строки** таблицы» | Confirmă **rândul** |
| **Ctrl+↓** | «Если для ячейки предусмотрен список значений… чтобы открыть его» | Deschide lista celulei |
| **Ctrl+Home / Ctrl+End** | «перейти на первую строку… на последнюю» | Primul / ultimul rând |
| *(celule sărite)* | «курсор… "перескакивает" через ячейки, значит… установлен **пропуск этих колонок**» | Coloane excluse din traseul Enter |

Câmpuri de alegere, din §4.2.1: **F4** deschide lista; **Shift+F4** curăţă valoarea;
**Ctrl+Shift+F4** deschide forma elementului ales; **F8** creează obiect nou; **Ctrl+↓** dă istoricul
valorilor alese; **Esc** «отмены ввода и возвращения к предыдущему значению»; **Ctrl+Enter** apasă
butonul implicit al formei.

O dezambiguizare pe care ghidul o face explicit (§5.3.1):

> «Следует учитывать **принципиальное отличие** поведения клавиши Enter в формах. В форме **для
> выбора** нажатие клавиши Enter приводит к **выбору**… а в формах **списка** – к **открытию формы**…»

> **Constatarea-titlu: în 1C, Enter şi Tab sunt aceeaşi tastă.** Ambele avansează orizontal. **Enter
> nu coboară.** Ctrl+Enter salvează documentul.

## 2. Cele trei înţelesuri incompatibile ale lui Enter

1. **Enter = avansează o celulă pe rând** — 1C. QuickBooks Online face aceeaşi mişcare cu Tab.
2. **Enter = confirmă celula şi coboară** — Excel, Sheets, Handsontable, MUI X.
3. **Enter = trimite / validează ecranul întreg** — SAP GUI; QuickBooks Desktop: `↵` = *„Record"*.

**De ce contează.** Un contabil venit din 1C apasă Enter după fiecare câmp. Sub înţelesul (2) asta
**abandonează un rând pe jumătate completat** şi sare la prima coloană a rândului următor. Sub (3),
**postează documentul**. Ambele sunt tăcute, plauzibile şi produc un document greşit.

**Convergenţa pe care n-o observă nimeni:** idiomul Excel „Tab pe rând, apoi Enter la capăt" şi
idiomul 1C „Enter avansează celula" produc **acelaşi rezultat la hotarul rândului**. Dezacordul e doar
la mijlocul rândului — şi acolo răspunsul 1C e cel care se potriveşte cu felul în care se introduce
efectiv o linie de jurnal.

**Unanim:** `Ctrl+Enter` înseamnă „înregistrează documentul" **şi** în 1C («Записать объект и закрыть
форму»), **şi** în QuickBooks («Record (always)»). E cea mai neambiguă legare disponibilă.

**Implicite de cadru care se ciocnesc cu aşteptarea utilizatorului:** Tab-ul din MUI X **iese din
grilă** implicit; AG Grid lasă editorul **deschis** când grila pierde focusul
(`stopEditingWhenCellsLoseFocus` = `false`); `autoWrapRow`/`autoWrapCol` din Handsontable sunt `false`
din v10.

**Ce supravieţuieşte într-un browser:** Ins, Del, F2, F4, F8, F9, Shift+F2, Shift+F4, Ctrl+Enter,
Ctrl+↓/↑, Ctrl+Home/End, PgUp/PgDn, Alt+↓ sunt **libere**. **Ctrl+F, Ctrl+S, Ctrl+N/O/P, F5, F1, F3,
F11, F12, Ctrl+W/T/Tab sunt luate** de browser. **Ctrl+Shift+F4** (1C: deschide elementul) stă lipit de
Ctrl+F4 = închide fila — riscant.

## 3. Numericul — problema virgulei, măsurată nu presupusă

Tasta zecimală de pe blocul numeric emite un caracter determinat de **aranjamentul de tastatură activ**:

| Aranjament | `VK_DECIMAL` emite |
|---|---|
| **Română (Standard)** `KBDROST` | **virgulă** |
| **Română (Programatori)** `KBDROPR` | **punct** |
| **Rusă** `KBDRU` | **virgulă** |
| **US** `KBDUS` | **punct** |

Un contabil din Chişinău care comută RO ↔ RU ↔ EN în aceeaşi sesiune primeşte **caracter diferit de la
aceeaşi tastă fizică**.

**Capcana specific românească:** româna foloseşte `.` ca separator de **grup** şi `,` ca zecimal
(`1.234,56`). Deci `1.234` e genuin ambiguu — şi bibliotecile greşesc: Handsontable #4396, intrare
`7.000`, aşteptat `7000`, **efectiv `7`**, fiindcă `parseFloat("7.000")` întoarce `7`. Într-o linie de
jurnal e o eroare de 999 de unităţi fără simptom vizibil.

**Implementări care acceptă ambele:** `autoNumeric` cu `decimalCharacterAlternative`; tipul numeric din
Handsontable („A dot (`50.5`) or a comma (`50,5`) can be entered"); opţiunea explicită din LibreOffice
Calc *„Decimal separator key — Same as locale setting"*, care există tocmai fiindcă răspunsul
driverului nu e de încredere; opţiunea Excel *„Use system separators"*.
**Contraexemplul de evitat: SAP** — notaţia zecimală e setare de profil (SU3), iar un utilizator pe
virgulă **trebuie** să tasteze virgulă; un punct tastat e interpretat ca separator de mii şi aruncat.

**`<input type="number">` nu se foloseşte.** GOV.UK enumeră cinci eşecuri concrete: nu se poate dicta
cu Dragon; apare ca *spin button neetichetat* în lista de elemente NVDA; Chrome *„silently discards all
letter input except the letter «e»"* fără să anunţe tehnologia asistivă; rotiţa mouse-ului schimbă tăcut
valoarea; valorile mari se rotunjesc sau devin notaţie exponenţială. Au trecut la
`<input type="text" inputmode="numeric" pattern="[0-9]*">`.

## 4. Accesibilitate — tiparul `grid` din WAI-ARIA APG

- Navigarea cerută: săgeţile mută focusul o celulă şi **la margine „focus does not move"**; `Home` /
  `End` = prima / ultima celulă **din rândul cu focus**; `Ctrl+Home` / `Ctrl+End` = prima celulă a
  primului rând / ultima a ultimului. **APG interzice explicit ciclarea** în grilele de date: ar fi
  *„disorienting… especially for users of assistive technologies"*.
- **Tab nu apare deloc în lista aia.** Ce spune APG: *„Only one of the focusable elements contained by
  the grid is included in the page tab sequence."*
- **APG sancţionează explicit alegerea noastră**, în „Editing and Navigating Inside a Cell": *„If the
  input is a single-line text field, **a subsequent press of Enter may either restore grid navigation
  functions or move focus to an input field in a neighboring cell**."*
- **ARIA 1.2 e citarea mai tare** (normativ): *„Authors **SHOULD** provide a mechanism for changing to
  an interaction or edit mode… pressing Enter again, Tab, Escape, or another key may switch the
  application back to the grid navigation mode."*
- **De ce fiecare celulă trebuie să fie focusabilă:** *„While in application mode, a screen reader user
  hears only focusable elements and content that labels focusable elements."* Asta constrânge direct
  indicatorul de balanţă şi coloanele calculate.
- **Focus:** APG dă ca valabile şi roving tabindex, şi `aria-activedescendant`, dar **toate exemplele
  APG folosesc roving tabindex şi niciunul `aria-activedescendant`** (verificat: 0 apariţii).
- **Atribute:** `aria-invalid`, `aria-required`, `aria-errormessage`, `aria-readonly`, `aria-selected`
  stau pe **`gridcell`**, nu pe grilă — pe `role=grid` sunt **depreciate** în ARIA 1.2.
  `role=grid` are **Accessible Name Required: True**. La virtualizare: `aria-rowcount`/`aria-colcount`
  pe grilă, `aria-rowindex`/`aria-colindex` pe rând/celulă, cu **AVERTISMENTUL** APG: *„Missing or
  inconsistent values of `aria-rowindex` could have devastating effects on assistive technology
  behavior."* `aria-colindextext` e **doar ARIA 1.3**.
- **Trebuie `EntryGrid` să fie deloc `grid`?** Sarah Higley: grilă când *„the primary purpose is to
  enable user interaction… Efficiency is more important than a low barrier to entry."* Adrian Roselli:
  *„you should probably ignore ARIA grid unless you are trying to recreate Excel."*
  > **`EntryGrid` trece ambele teste; `DataGrid` le pică pe amândouă şi trebuie să fie `role="table"`,
  > nu `role="grid"`.** Asta pune despărţirea în două componente din ADR-001 **pe un hotar semantic
  > real**, nu doar de comoditate.

## 5. Ce se strică — cazuri concrete, cu sursă

1. **Clientul web propriu al 1C pierde taste în timpul apelurilor la server.** Limitare documentată:
   «В веб-браузерах… не обрабатываются клавиши, нажатые во время серверного вызова». **Ăsta e motivul
   pentru care o grilă în browser se simte mai lentă decât clientul gros, şi e o constrângere de desen
   dură: nicio tastă nu are voie să aştepte un dus-întors.**
2. **Coruperea numerică tăcută din parsare conştientă de format.** Handsontable #4706: o celulă care
   afişa `7001`, deschisă şi confirmată cu Enter, **a devenit `70005`**; `20,5` într-o celulă goală **a
   devenit `205`**. Rezolvarea: separă formatarea de afişare de parsare.
3. **Ambiguitatea separatorului de grup** — #4396, `7.000` → `7`.
4. **Separatorul de pe blocul numeric respins de-a dreptul** — autoNumeric #602.
5. **`<input type="number">`** — cele cinci eşecuri GOV.UK, dintre care două sunt corupere tăcută.
6. **Virtualizarea distruge ordinea pentru cititorul de ecran.** Higley: *„there is at least one major
   grid library… the visual order does not match the DOM order, and the screen reader accessibility is
   entirely broken."*
7. **`Ctrl+End` minte într-o grilă virtualizată.** Nota APG: *„may move focus to the last row in the DOM
   rather than the last available row in the back-end data."* Un contabil ar conchide că jurnalul are
   mai puţine linii decât are.
8. **Anunţurile assertive taie numele câmpului următor.** Roselli: *„When a live region… is treated as
   assertive, the name of the subsequent field that just received focus is clipped or lost."* Şi: *„The
   virtual cursor is the only certain way to encounter a message associated using `aria-errormessage`"*
   — iar utilizatorii de grilă sunt în mod aplicaţie, nu cursor virtual.
9. **Exemplul de editare din APG e el însuşi defect.** În `dataGrid.js` **F2 nu e implementat deloc**
   (0 apariţii), iar editorul din celulă e `<input class="edit-text-input hidden" tabindex="-1">` —
   **fără nume accesibil**. Nu se copiază.
10. **`aria-readonly` practic nu e suportat** (măsurat de Roselli pe rolurile testate).
11. **Direcţia lui Enter din Excel e globală** — *„affects the whole worksheet, any other open
    worksheets, any other open workbooks, and all new workbooks"*. **Avertisment împotriva
    transformării direcţiei lui Enter în preferinţă de utilizator.**

## 6. Contractul propus pentru `EntryGrid`

Două stări: **Selecţie** (o celulă are focus, fără editor) şi **Editare** (un input din celulă are
focusul DOM). Confirmarea rândului e un **eveniment**, nu o a treia stare.

### 6.1 Cele două axiome

> **A1 — `Enter` ≡ `Tab`.** Peste tot, fără excepţie. Ambele confirmă celula şi avansează la
> următoarea celulă editabilă din rând. E comportamentul documentat 1C, şi face ca obiceiul „Tab" al
> utilizatorului Excel şi obiceiul „Enter" al celui din 1C să producă **rezultate identice**.
>
> **A2 — `Ctrl+Enter` înregistrează documentul.** Niciodată `Enter`. 1C şi QuickBooks sunt de acord.

### 6.2 Modul selecţie

| Tastă | Acţiune |
|---|---|
| `Enter`, `Tab` | Intră în editare, cursor la sfârşit, conţinut **păstrat** |
| `Shift+Tab` | Celula editabilă anterioară, fără editare |
| `F2` | Editare, conţinut păstrat. Al doilea `F2` revine la selecţie |
| orice caracter tipăribil | Editare, **înlocuind** conţinutul cu acel caracter. **Caracterul nu are voie să se piardă** |
| `←` `→` | Celula anterioară / următoare din rând. **Nu ciclează** (APG) |
| `↑` `↓` | Rând anterior / următor, aceeaşi coloană. **Nu ciclează**, excepţie: `↓` pe ultimul rând îl confirmă şi adaugă unul nou |
| `Home` / `End` | Prima / ultima celulă editabilă a rândului |
| `Ctrl+Home` / `Ctrl+End` | Prima celulă a primului rând / ultima a ultimului |
| `PgUp` / `PgDn` | Un ecran de rânduri |
| `Delete` | Curăţă valoarea, rămâne în selecţie |
| `Backspace` | Curăţă valoarea **şi** intră în editare |
| `Insert`, `Ctrl+Insert` | Rând nou **sub** cel curent; prima celulă editabilă **în editare** |
| `Ctrl+Delete` | Şterge rândul. **Fără modal**; reversibil cu `Ctrl+Z` |
| `F9` | Dublează rândul dedesubt, cu valori |
| `Shift+F2` | Confirmă rândul acum, fără să mute |
| `Ctrl+Z` / `Ctrl+Y` | Anulează / reface în documentul neconfirmat |
| `Ctrl+C` / `Ctrl+V` | Bloc dreptunghiular; lipirea sparge pe `\t` şi `\n`, adaugă rânduri, trece fiecare valoare prin parserul celulei |
| `Escape` | Rând murdar: revine la ultima stare confirmată. Rând nou neatins: îl elimină şi **scoate focusul din grilă**. Altfel: scoate focusul |
| `Ctrl+Enter` | Confirmă rândul, apoi **înregistrează documentul** |

### 6.3 Modul editare

| Tastă | Acţiune |
|---|---|
| `Enter`, `Tab` | Confirmă celula; **următoarea celulă editabilă din rând**, în **selecţie**. La ultima celulă editabilă: confirmă **rândul**, adaugă rând nou şi îi pune prima celulă **în editare** |
| `Shift+Enter`, `Shift+Tab` | Confirmă; celula editabilă anterioară. La prima celulă: ultima celulă a rândului precedent |
| `Escape` | Revine la valoarea dinaintea editării; înapoi în selecţie. **Nu părăseşte niciodată rândul** |
| `F2` | Înapoi în selecţie, **păstrând** valoarea tastată |
| `←` `→` `Home` `End` | Mută **cursorul** în text. Niciodată între celule |
| `↑` `↓` | Popup deschis: mută opţiunea evidenţiată. Altfel: confirmă şi mută un rând |
| `Delete` / `Backspace` | Un caracter după / înainte de cursor |
| `Alt+Enter` | Întrerupere de rând — **doar** în celule declarate multi-linie |
| `Ctrl+Enter` | Confirmă celula, confirmă rândul, **înregistrează documentul** |

### 6.4 Celule de alegere *(cont, contrapartidă, centru de cost, articol)*

| Tastă | Acţiune |
|---|---|
| `F4`, `Alt+↓`, `Ctrl+↓` | Deschide popup fără să mute focusul din celulă |
| tastare | Filtrează pe măsură ce se tastează. **Listă locală de candidaţi; nu blochează niciodată pe server** |
| `↑` `↓` | Mută opţiunea evidenţiată |
| `Enter` | Acceptă opţiunea, închide popup-ul **şi avansează la celula următoare** — o tastă, nu două. *(Abatere deliberată de la APG combobox; vezi 6.7)* |
| `Escape` | Închide popup-ul, celula rămâne în editare cu textul anterior. Al doilea `Escape` revine |
| `Shift+F4` | Curăţă valoarea |
| `F8` | „Creează nou" pentru entitatea referită; la salvare umple celula |
| `Ctrl+Alt+Enter` | Deschide înregistrarea referită. *(1C foloseşte `Ctrl+Shift+F4`, lipit de închiderea filei din Chrome)* |

### 6.5 Celule numerice

1. **Acceptă `.` şi `,` interschimbabil.** **Nu se consultă locale-ul, aranjamentul sau
   `navigator.language` la introducere** — s-a măsurat că aceeaşi tastă fizică emite ambele.
2. **Separatorii de grup se resping la introducere.** Cifre, semn opţional, **cel mult un** separator.
   Al doilea separator nu se acceptă — tasta e respinsă, fără trunchiere tăcută. **Asta elimină din
   rădăcină clasa `7.000 → 7`.**
3. **În editare, celula arată valoarea brută:** fără grupare, cu separatorul pe care l-a tastat
   utilizatorul. La confirmare se normalizează la şir zecimal cu `.` şi se formatează prin **modulul
   unic** (`C18`).
4. **`<input type="text" inputmode="decimal">`.** Niciodată `type="number"`.
5. Acceptă `-` în faţă şi în spate. Notaţia contabilă e **doar afişare**.
6. **Fără aritmetică în client dincolo de comoditatea introducerii.** Dacă se adoptă calculul inline,
   rezultatul e **intrare**, niciodată cifră contabilă calculată — `C19` rămâne în picioare.
7. Indicatorul de balanţă e `role="status"` cu `aria-live="polite"` — **niciodată `assertive`**, care
   ar tăia numele celulei următoare la fiecare confirmare. E o comoditate, nu un control: **`R11`
   rămâne verificare de bază de date.**

### 6.6 Rânduri şi document

- Numerele de rând într-o coloană needitabilă din stânga, atribuite automat — dublura vizibilă a lui
  `aria-rowindex`.
- Un rând nou lăsat **fără nicio valoare** se aruncă la ieşirea focusului *(regula 1C, verbatim)*.
- Rândul se confirmă la ieşirea focusului, pe `Shift+F2`, sau pe `Ctrl+Enter`.
- **Grila nu postează niciodată.** `Ctrl+Enter` invocă acţiunea de salvare a documentului, care poartă
  `Idempotency-Key` (`C9`); un al doilea `Ctrl+Enter` cât o salvare e în zbor **se ignoră, nu se pune la
  coadă**.

### 6.7 Reguli care nu sunt taste

- **R-K1 — Nicio tastă nu aşteaptă reţeaua.** Validarea care cere serverul e optimistă: valoarea se
  acceptă local, celula arată stare în aşteptare, iar **rândul** nu se poate confirma până nu se
  rezolvă. Tastele apăsate în timpul unei cereri se pun la coadă şi se aplică în ordine, **niciodată nu
  se pierd**. *(Consecinţă directă a limitării proprii a clientului web 1C.)*
- **R-K2 — Primul caracter nu se pierde niciodată.** Editarea intrată printr-o tastă tipăribilă trebuie
  să însămânţeze acel caracter **sincron, în acelaşi eveniment**, nu după un dus-întors de stare React.
- **R-K3 — Ecranele nu adaugă handlere de taste.** Deja în `CLAUDE.md` §2.8; aici devine verificabil.
- **R-K4 — `EntryGrid` e `role="grid"` cu roving tabindex; `DataGrid` e `role="table"`.** Fiecare celulă
  e focusabilă sau conţine un element focusabil. `aria-invalid` / `aria-required` / `aria-errormessage`
  stau pe `gridcell`. **Editorul din celulă primeşte nume accesibil derivat din antetul coloanei** —
  omisiunea din exemplul APG e defect, nu model.
- **R-K5 — Listă de coloane sărite.** Coloanele needitabile şi cele completate automat se exclud din
  traseul Enter/Tab, declarat per coloană *(1C: «пропуск этих колонок»)*. **Săgeţile ajung totuşi la
  ele**, ca utilizatorii de cititor de ecran în mod aplicaţie să le audă.

### 6.8 Cele patru alegeri genuin contestate

| Alegere | S-a ales | Împotrivă | De ce |
|---|---|---|---|
| Direcţia lui Enter | **orizontal** (1C) | Excel/Sheets/Handsontable/MUI coboară | Utilizatorul-ţintă e migrant din 1C; rândul pe jumătate completat e chiar clasa de eroare de prevenit; `↑`/`↓` rămân pentru vertical; idiomul Excel converge oricum la hotarul rândului. **Nu se face preferinţă de utilizator** — setarea globală a Excel e chiar avertismentul |
| Ştergerea rândului | **`Ctrl+Delete`**; `Delete` gol curăţă celula | 1C foloseşte `Del` gol | Manualul 1C însuşi îl semnalează: «без дополнительного предупреждения». Excel/Sheets/Handsontable folosesc toate `Delete` pentru curăţare. `Ctrl+Z` e mitigarea, nu un modal |
| `Enter` în popup | **acceptă + avansează** | APG combobox: acceptă + închide | Viteza de introducere. Consemnat ca abatere; `Escape` dă varianta în doi paşi |
| `Shift+Enter` | **celula anterioară** | Excel/Handsontable: în sus; editorul 1C: rând nou | Dacă `Enter ≡ Tab`, oglinda lui trebuie să fie `Shift+Tab`. Rândul nou se mută pe `Alt+Enter` |

---

## 7. Ce nu s-a putut verifica

**Citat din sursă primară:** fiecare legare 1C din §1 (ghidul oficial, §4.2 şi §4.8, citit integral);
fiecare legare Excel, AG Grid, Handsontable şi MUI X marcată ca documentată; tot textul APG şi ARIA 1.2
(preluat live de pe w3.org); maparea `VK_DECIMAL` per aranjament (kbdlayout.info); opţiunea LibreOffice;
tabelul complet de scurtături QuickBooks Desktop (PDF-ul propriu Intuit); Handsontable #4396 şi #4706,
autoNumeric #602.

**Inferat, secundar sau neverificabil — nu se citează ca documentat:**

1. **Google Sheets e aproape integral nesursat.** Pagina oficială de scurtături **nu listează deloc Tab,
   Shift+Tab, Enter, Shift+Enter, Esc, Page Up/Down, Delete sau Backspace.** Cele două pagini Google
   chiar **se contrazic** pe `Ctrl+Enter` („Fill range" vs „add another line within a cell").
2. **„Excel revine la coloana de unde a început şirul de Tab"** — Microsoft spune doar *„the selection
   moves to the start of the next row"*. Rafinarea pe care se bazează toată lumea **nu e în documentaţie**.
3. **Excel: un caracter tipăribil înlocuieşte conţinutul** — nicăieri afirmat explicit. La fel pentru
   săgeţile care mută cursorul în editare.
4. **Excel Table: Tab în ultima celulă adaugă un rând** — real în produs, **absent din pagina oficială**,
   citită integral.
5. **`Ins`/`Del`/`F9`/`Tab` din 1C în *formele gestionate* anume.** Ghidul citit documentează elementul
   de tabel al platformei. Dacă o configuraţie 1C:Бухгалтерия activează Tab-între-celule e **setare per
   configuraţie**, prin recunoaşterea proprie a 1C — deci **„ce ţine memoria musculară a contabilului"
   variază de la o configuraţie la alta**. Nicio instalare 1C vie n-a fost testată.
6. **Comportamentul 1C la blocul numeric** — ghidul nu spune nimic. Inferat din aranjamentele Windows,
   **nemăsurat în 1C**.
7. **SAP.** `help.sap.com` a expirat la fiecare încercare. Rândul SAP vine din fire de comunitate şi
   material de instruire terţ, **nu din documentaţia SAP**. De tratat ca direcţional corect, precis
   neverificat.
8. **Limitările de tastatură ale clientului web 1C** — citatul e de pe un sit de specialişti care
   reproduce documentaţia ITS; `its.1c.ru` e în spatele unui login. Încredere mare în fond, **oglindă, nu
   sursă**.
9. **Tastele rezervate de browser** — de pe pagina de ajutor Chrome. **Care dintre ele se pot
   `preventDefault` nu s-a verificat aici**, iar Firefox şi Safari n-au fost verificate deloc.
10. **`aria-readonly` pe `gridcell`** — Roselli a măsurat suport aproape absent, dar **n-a testat `grid`
    sau `gridcell`**; „bănuiesc că nu e mult mai bun" e o bănuială. Dacă contractul depinde de el, e o
    măsurătoare pe care ne-o datorăm.
11. **Nu există implementare de referinţă APG pentru cazul nostru.** Pagina „Advanced Data Grid" spune
    verbatim *„This example has not yet been developed."* „Virtualizarea" din Exemplul 3 e `display:none`,
    nu ferestruire reală — APG o recunoaşte. **Pe Tab-în-grile, focus virtualizat şi `aria-readonly`
    luăm decizii pe care nicio sursă nu le ia în locul nostru.**
12. **§5 e incomplet prin construcţie** — agentul pe moduri de eşec (înghiţirea primului caracter în AG
    Grid/MUI, pierderea focusului la virtualizare, IME şi taste moarte, interferenţa cu autofill) încă
    rula. Cele unsprezece cazuri de mai sus sunt sursate, dar **detaliul la nivel de issue pentru
    punctele 1–3 din brief nu e încă în mână.**

## 8. Două lucruri de ridicat înainte ca asta să devină ADR

- **ADR-001 spune că `EntryGrid` e „Zeci de rânduri. Nevirtualizată."** Dar `_bootstrap/07-f1-grile.md`
  cere aceleiaşi componente să servească **potrivirea extrasului bancar** şi **maparea conturilor la
  importul din 1C** — niciuna nu e de zeci de rânduri. **Ori constrângerea de nevirtualizare, ori
  criteriul de generalitate trebuie să cedeze**, iar răspunsul decide dacă `OD-41` se redeschide.
  Costul de accesibilitate e asimetric: **un `EntryGrid` nevirtualizat evită din start clasa 6 şi 7 de
  eşecuri de la §5.**
- **Frontend-ul e schelet gol** (`main.tsx`; TanStack Table 8.21 + React 19 instalate, fără
  virtualizator). **Nimic nu trebuie desfăcut** — contractul se poate scrie şi implementa curat.
