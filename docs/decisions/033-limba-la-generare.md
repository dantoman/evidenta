# ADR-033 — Limba la generare: contextul românesc se forțează, nu se moștenește

- **Status:** Acceptat — conținut juridic prin trimitere la art. 7; co-semnătura din
  [ADR-002](002-guvernanta-deciziilor.md) acoperită prin [ADR-010](010-contabilul-practicant.md)
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului, în ambele roluri
- **Închide:** — *(nu închide nicio decizie din registru; operaționalizează
  [ADR-016](016-limba-contabilitatii.md))*
- **Rafinează:** [ADR-016](016-limba-contabilitatii.md), [ADR-014](014-limba-rusa.md)
- **Afectează:** `C33` *(primește mecanism)*, `CLAUDE.md` §2.7 (`C38`), pipeline-ul de documente
  (`C22`), task-urile Celery, F1+

## Context

`ADR-016` stabilește *ce* nu are voie să se întâmple: nicio traducere de interfață nu ajunge
într-un registru, într-o situație financiară sau într-un document generat. `C33` o repetă. Niciunul
nu spune **cine împiedică**, iar mecanismul implicit al Django face exact contrariul: limba activă
este stare de fir de execuție, moștenită de tot ce se randează după ea.

Măsurat pe stack-ul proiectului, înainte de a scrie regula — Django 5.2.17, `LANGUAGE_CODE = "ro"`,
`USE_I18N = True`, **fără `LocaleMiddleware` instalat**:

| Ce s-a măsurat | Rezultat |
|---|---|
| `formats.date_format(date(2026, 3, 7))` cu `ro` activ | `7 Martie 2026` |
| aceeași expresie cu `ru` activ | `7 марта 2026 г.` |
| aceeași expresie cu `en` activ | `March 7, 2026`, cu separator zecimal `.` |
| `translation.activate("ru")`, apoi următoarea unitate de lucru **pe același fir** | limba activă rămâne `ru` |
| aceeași verificare pe un fir nou | `ro` — implicitul din `LANGUAGE_CODE` |
| după `translation.deactivate()` | `ro` |

Trei lucruri decurg din tabel, și niciunul nu e teoretic:

1. **Formatarea unei date pe o factură depinde de cine a activat ultima dată o limbă.** Nu doar
   traducerea șirurilor — și data, și separatorul zecimal.
2. **Nu există restaurare automată.** Limba activată supraviețuiește unității de lucru care a
   setat-o. Un worker care refolosește firele — gunicorn sincron, Celery prefork — o duce în
   următoarea sarcină. De aceea regula numește Celery explicit: `R6` cere deja context de tenant
   pe fiecare task; limba are aceeași formă de defect și nicio gardă.
3. **Riscul nu e activ azi**, fiindcă serverul nu activează nicio limbă și implicitul e `ro`.
   Exact de asta regula costă zero acum și ar costa o rescriere după ce există interfața rusă.

Scenariul concret, în ordinea în care se produce: contabil cu interfața pe rusă → apasă „Tipărește
factura" → pipeline-ul de documente randează în contextul cererii → factură fiscală în rusă.
Nimic nu a eșuat tehnic. Rezultatul este artefact neconform (Legea nr. 287/2017, art. 7 alin. (1)).

## Opțiuni evaluate

1. **Convenția existentă (`C33`), fără mecanism.** *Avantaje:* nimic de scris. *Dezavantaje:*
   regula descrie rezultatul interzis, nu punctul unde se impune; defectul e tăcut și se descoperă
   pe hârtie tipărită, la client. *Cost de schimbare ulterioară:* mare — se descoperă după ce
   documentele au fost deja emise.
2. **Forțare la granița pipeline-ului de generare.** Fiecare cale care produce un document legal
   deschide explicit contextul românesc, indiferent ce a fost activ înainte, iar formatarea de
   document nu consultă limba activă. *Avantaje:* punctul de impunere e unul singur și e vizibil în
   cod; funcționează identic în request și în task. *Dezavantaje:* trebuie ținut minte la fiecare
   pipeline nou — de aceea primește gardă, nu doar regulă. *Cost de schimbare:* mic.
3. **Serverul nu activează niciodată nicio limbă.** Toată traducerea rămâne în client (`C32`,
   fără bibliotecă i18n). *Avantaje:* elimină problema la rădăcină; este, de fapt, starea de azi.
   *Dezavantaje:* nu se susține — notificările prin e-mail se compun pe server și vor avea nevoie
   de limba destinatarului, iar atunci opțiunea 3 devine opțiunea 1 fără să observe nimeni.

## Decizie

**Opțiunea 2, cu opțiunea 3 păstrată cât timp e adevărată** — și ea este azi, ceea ce face garda
ieftină.

### Regula

Orice cale care produce un **document legal** — document tipărit, registru, situație financiară,
declarație, payload e-Factura, descriere de înregistrare contabilă generată de sistem — deschide
explicit contextul lingvistic românesc la intrarea ei (`translation.override("ro")` sau
echivalent) și nu se bazează pe starea moștenită. Se aplică identic în request și în task Celery.
Intră în `CLAUDE.md` ca **`C38`**.

### Formatarea

Numerele, datele și sumele în litere de pe documente vin dintr-un **modul de formatare de
document**, cu convenții `ro-MD` fixate, care **nu consultă limba activă**. `C18` cere un singur
modul de formatare în client, pentru afișare; acesta este perechea lui pe server, pentru documente.
Nu sunt același modul și nu au aceeași sursă de adevăr: unul urmează utilizatorul, celălalt
jurisdicția.

### Cele două straturi, enumerate ca să nu se rediscute

**Exclusiv în română, ca date stocate:**

- denumirile din planul de conturi SNC — nomenclatură legală, nu text de interfață
  ([ADR-016](016-limba-contabilitatii.md))
- formularele de tipar, declarațiile, registrele, payload-ul e-Factura
- descrierile înregistrărilor contabile generate de sistem
- formatarea de numere și date **pe documente**

**Strat de afișare, traductibil:** meniuri, butoane, mesaje de eroare, ajutor, ecrane de
configurare, notificări către utilizator. Inclusiv o **etichetă de afișare pentru denumirile de
conturi**: contabilul rusofon vede „Материалы" în listă și tipărește „Materiale". Eticheta este
resursă de interfață **cheiată pe codul contului**, niciodată coloană în tabela de conturi —
`ADR-016` o spunea deja ca ipoteză; aici devine forma de implementat.

### Glosarul rusesc se construiește din 1C, nu din română

Consemnat acum, se aplică în ziua în care interfața rusă se programează: termenii se iau din
terminologia 1C pe care contabilii moldoveni o folosesc deja, nu prin traducerea etichetelor
românești. Nu e preferință de stil — este singura parte a lucrării care scade costul de
recalificare, deci singura care contează comercial. O traducere corectă gramatical și străină de
1C costă la fel de mult de produs și nu cumpără nimic.

## Consecințe

- **Devine posibil:** interfața rusă, fără risc de conformitate pe ieșire. Cele două straturi se
  ating într-un singur punct, iar punctul e numit.
- **Devine imposibil (deliberat):** randarea documentelor prin aceleași șabloane ca interfața,
  „ca să nu duplicăm". Duplicarea este aici separarea, nu accidentul.
- **De modificat:** `CLAUDE.md` §2.7 primește `C38`. Când apare primul pipeline de generare, tot
  atunci apare și proba lui: randare cu `ru` activ, ieșire în română.
- **Se verifică automat, azi:** `backend/tests/architecture/test_document_language.py` —
  `LANGUAGE_CODE` este `ro` și serverul nu activează nicio limbă (`LocaleMiddleware`,
  `translation.activate`). Testul **nu** demonstrează că documentele sunt în română; nu există încă
  document generat. Demonstrează că terenul pe care stă regula nu se mută tăcut, și cade cu un
  mesaj care spune ce trebuie scris înainte de a-l lărgi. Probă că poate eșua: rulat cu un
  `translation.activate("ru")` plantat în `platform`, testul cade și numește fișierul și linia.

## Surse

- Măsurători pe mediul de dezvoltare al proiectului, 2026-08-25: Django 5.2.17,
  `config.settings.dev`, `django.utils.formats` și `django.utils.translation`.
- Legea nr. 287 din 15.12.2017, art. 7 alin. (1) — prin [ADR-016](016-limba-contabilitatii.md).
- [ADR-014](014-limba-rusa.md) §„Trei lucruri care se fac acum, cu cost zero"; `C22`, `C32`, `C33`.
