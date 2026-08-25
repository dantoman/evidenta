# ADR-034 — Nomenclatoarele au denumire legală și denumire internă

- **Status:** Acceptat — conținut contabil; co-semnătura din
  [ADR-002](002-guvernanta-deciziilor.md) acoperită prin [ADR-010](010-contabilul-practicant.md)
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului, în ambele roluri
- **Închide:** — **`OD-40` rămâne deschisă.** Această decizie nu răspunde la întrebarea juridică;
  o face nedistructivă în ambele sensuri
- **Rafinează:** [ADR-014](014-limba-rusa.md), secțiunea „Datele introduse de tenant: valoare unică"
- **Afectează:** `masterdata/items`, `masterdata/partners`, F0.7, documentele de la F1,
  `CLAUDE.md` §2.7 (`C39`)

## Context

`ADR-016` a stabilit că rusa este strat de prezentare exclusiv, și a lăsat o singură întrebare
deschisă — `OD-40`: dacă denumirea unui articol tastată în rusă de un tenant, ajunsă pe o factură
fiscală emisă de el, este conformă. Art. 11 din Legea nr. 287/2017 nu prescrie limba pentru
documentele **întocmite** de entitate; singura prevedere de limbă, alin. (11), privește documentele
**primite din străinătate** și acceptă româna, engleza și rusa fără traducere.

Între timp produsul nu restricționează nimic — decizia explicită din `ADR-016`, corectă atunci.
Problema este că **tăcerea nu e neutră**: un utilizator rusofon tastează în chirilice denumiri de
produse și de parteneri, ele ajung pe documente fiscale, iar sistemul produce un artefact
posibil neconform fără să greșească nimic tehnic. Iar greșeala e reversibilă doar într-un sens —
datele deja tastate rămân. Un nomenclator se tastează o dată și se folosește de o mie de ori; dacă
răspunsul la `OD-40` vine peste un an și e „nu", corecția e retastarea nomenclatorului fiecărui
client rusofon.

Starea de azi a schemei, verificată în cod:

| Tabelă | Coloane de denumire | Cine tastează |
|---|---|---|
| `item` | `name` — una singură | tenantul |
| `partner` | `legal_name`, `short_name` *(prescurtare, nu limbă)* | tenantul |
| `counterparty_registry` | `legal_name` | **nimeni** — se alimentează din surse publice |
| `unit_of_measure`, planul de conturi | denumire unică, română | **noi**, ca date de referință |

Deci discuția atinge exact două tabele: `item` și `partner`. Registrul global nu e „contrapartea pe
care o tastează utilizatorul" — el conține ce spune statul; datele de referință livrate de noi rămân
în română prin `ADR-016`, inclusiv simbolul de unitate de măsură care se tipărește pe factură.

## Opțiuni evaluate

1. **Avertisment la detectarea chirilicelor** în câmpurile care ajung pe documente fiscale.
   *Avantaje:* zero schemă, se poate adăuga oricând, nu blochează pe nimeni. *Dezavantaje:* pune
   utilizatorul într-o alegere pe care nu o poate face — ori tastează în română o denumire pe care
   nu o folosește zilnic, ori ignoră avertismentul; iar la a doua sută de articole îl ignoră.
   *Cost de schimbare:* mic, dar nu rezolvă nomenclatorul.
2. **Câmp dublu pentru nomenclatoare:** denumirea care ajunge pe document, plus o denumire internă
   liberă. *Avantaje:* utilizatorul lucrează în limba lui fără ca ieșirea să depindă de asta;
   răspunsul la `OD-40` nu mai poate cere retastare, în niciunul dintre sensuri. *Dezavantaje:* o
   coloană în plus pe două tabele și o regulă de afișare de ținut minte. *Cost de schimbare:* mic
   acum, mare după ce există date reale — exact argumentul din `ADR-014` pentru planul de conturi,
   pe al doilea front.
3. **Se așteaptă `OD-40`.** *Avantaje:* nicio decizie luată prematur. *Dezavantaje:* întrebarea e
   contabilă și nu are termen, iar datele se acumulează între timp. *Cost de schimbare:*
   asimetric — dacă răspunsul e „conform", nu s-a pierdut nimic; dacă e „neconform", se retastează.

**Opțiunea respinsă înainte de a fi listată:** `CHECK` care refuză chirilicele pe coloana legală.
Denumirea juridică a unui furnizor ucrainean **este** în chirilice, iar art. 11 alin. (11) o
acceptă. O constrângere de alfabet ar refuza date corecte.

## Decizie

**Opțiunea 2 pentru nomenclatoare, opțiunea 1 pentru text liber. Ambele, nu una.**

### Nomenclatoare — `item` și `partner`

- Coloana existentă rămâne **denumirea legală**: `item.name`, `partner.legal_name`. `NOT NULL`.
  Ea este singura care ajunge pe un document, într-un registru sau într-un export.
- Se adaugă `internal_name text NULL` pe ambele. Alfabet liber, limba utilizatorului. Apare în
  liste, în căutare și în importuri. **Niciodată** pe un document generat.
- Afișarea preferă `internal_name` când există și cade pe denumirea legală când nu. Căutarea
  acoperă ambele coloane.
- `partner.short_name` **rămâne ce este** — prescurtare, nu denumire în altă limbă. Suprapunerea
  celor două ar fi economisit o coloană și ar fi produs o semantică pe care nimeni n-o poate
  reconstitui peste doi ani.
- Colația: coloane de denumire, deci implicita bazei (`ro-x-icu`). `C34` privește coloanele de cod.

### Text liber — descrieri, note, denumiri de pe liniile de document

Avertisment la detectarea chirilicelor, **nu refuz**. Este singura formă potrivită: descrierea unei
linii se scrie o dată, pentru un document, iar `OD-40` este exact întrebarea la care produsul nu are
voie să răspundă tacit — nici prin restricție, nici prin permisiune tăcută. Textul avertismentului
stă în fișierele de resurse (`C32`).

### Ce nu intră în scop

Celelalte coloane de denumire — `item_category.name`, denumirile de categorii și grupări — nu ajung
pe un document fiscal. Nu primesc a doua coloană. Dacă vreuna ajunge acolo, decizia se redeschide
pentru ea, cu motiv scris; „pentru simetrie" nu este motiv.

## Consecințe

- **Devine posibil:** contabilul rusofon își ține nomenclatorul în limba lui, iar factura iese în
  română, fără ca nimeni să aleagă între cele două.
- **Devine imposibil (deliberat):** ca răspunsul la `OD-40` — oricare ar fi — să ceară retastarea
  nomenclatoarelor.
- **`OD-40` rămâne deschisă și nu mai blochează nimic.** Rândul din registru se actualizează cu
  această trimitere.
- **`ADR-014` rămâne valid** pentru tot restul datelor tastate de tenant: valoare unică. Excepția
  este limitativă și este enumerată aici — două tabele, o coloană fiecare.
- **De implementat:** migrare aditivă (`C5`) pe `item` și `partner`, cu lanțul de review din
  `review-migration`. **Nu este scrisă în această sesiune** — este sarcina `F0.7.7` din backlog.
  Până atunci decizia este consemnată, nu aplicată.
- **Se verifică automat:** proba care contează nu este existența coloanei, ci că documentul nu o
  citește. Ea aparține gărzii de pipeline din [ADR-033](033-limba-la-generare.md) și se scrie odată
  cu primul document generat: denumirea tipărită este cea legală, chiar când `internal_name` există
  și diferă. Până atunci regula trăiește ca `C39`, fără gardă — și `CLAUDE.md` o spune așa.

## Surse

- Legea nr. 287 din 15.12.2017, art. 7 alin. (1), art. 11 alin. (7) și (11) — prin
  [ADR-016](016-limba-contabilitatii.md), unde textul e citat și marcat pentru reconfirmare pe
  legis.md.
- `000-open-decisions.md`: `OD-40`.
- Schema în vigoare: `backend/evidenta/masterdata/items/models.py`,
  `backend/evidenta/masterdata/partners/models.py`,
  `backend/evidenta/masterdata/counterparties/models.py`.
