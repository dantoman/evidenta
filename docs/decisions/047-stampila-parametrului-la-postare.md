# ADR-047 — Calculul își ștampilează baza, fiindcă parametrul nu și-o amintește

- **Status:** Acceptat — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md); cerută
  explicit de proprietar, ca ultimul gol din modelul de parametri
- **Data:** 2026-08-26
- **Închide:** `OD-68`
- **Afectează:** `journal_entry` (tabelă nouă atârnată de el), `accounting/ledger/services/writing.py`,
  `R10`, `R13`, `R18`
- **Legate:** [ADR-046](046-istoricul-increderii-in-sursa.md) §3, [ADR-044](044-data-de-rezolutie.md),
  [ADR-039](039-valuta-si-perioade.md) `DN-05`, `OD-67`

## 1. Golul, în forma în care rămăsese

[ADR-046](046-istoricul-increderii-in-sursa.md) a dat parametrului istoric: fiecare stare prin care a
trecut `source_confidence` și de când. Răspunde la *cât de ferm era parametrul în martie*.

Nu răspunde la *pe ce a stat postarea din martie*, și sunt întrebări diferite — pentru motivul care a
produs și ADR-046: **confirmarea nu schimbă valoarea.** Din clipa în care SFS publică nota anuală,
nimic din parametru nu mai arată că un calcul s-a făcut pe o deducție. Contabilul care deschide
martie în 2030 vede un număr confirmat și un act citat, și nu are de unde ști că în martie niciunul
din cele două nu exista în forma aceea.

ADR-046 §3 numea deja varianta tare și spunea de ce n-o poate livra: **aparține motorului de
postare.** Aceasta e ea.

## 2. Decizia

**La postare, calculul înregistrează ce a folosit: care versiune de parametru și ce încredere avea
atunci.** Într-o tabelă proprie, `entry_parameter_stamp`, un rând pe parametru pe înregistrare.

Trei alegeri fac diferența dintre o ștampilă și o notiță:

**Încrederea se copiază, nu se referă.** O referință se rezolvă la ce spune lumea *acum*, adică
exact ce se pierde. `confidence` e valoarea de la momentul calculului, scrisă în rând.

**`resolved_at` ține instantul**, deci `fiscal.confidence_at(parameter_id, resolved_at)` reproduce
încrederea ștampilată din istoricul lui ADR-046. O ștampilă care nu se poate re-deriva e o afirmație;
una care se poate e o probă — iar la un control diferența asta se plătește. Testul o verifică în
ambele sensuri: același apel la instantul ștampilei dă `provisional`, la instantul publicării dă
`confirmed`.

**`parameter_id` e versiunea.** Fiecare versiune e rândul ei, deci id-ul identifică versiunea; nu
există o coloană separată care să ajungă să spună altceva decât el.

`parameter_key` se copiază deliberat, denormalizat: ștampila trebuie să rămână citibilă când
parametrul e înlocuit, iar cititorul poate să n-aibă acces la modulul fiscal.

## 3. Tabelă, nu `jsonb` pe înregistrare

`capability_snapshot` de pe evenimentul contabil e `jsonb`, și tiparul ar fi fost la îndemână. Nu e
același caz.

Profilul de capabilități se citește **înapoi**, pentru o singură înregistrare, când reconstitui de ce
s-a contabilizat așa. Ștampila se citește **înainte, peste toate înregistrările**: *SFS a publicat —
ce am postat pe o deducție și trebuie reexaminat?* Aia e o interogare cu filtru pe încredere și un
index, nu o expresie de cale peste un blob. Cu `jsonb` ar fi fost o scanare secvențială și o expresie
scrisă de mână, la fiecare publicare.

Indexul invers există din același motiv: *versiunea asta s-a dovedit greșită — ce stă pe ea?*

**Fără FK spre `fiscal_parameter`** — `D6`: modulele vorbesc prin servicii și evenimente, nu prin
import de modele. Se păstrează id-ul, joinul e un apel de serviciu, iar `accounting` continuă să nu
cunoască numele de tabele ale lui `fiscal`.

**FK-ul spre `journal_entry` e permis**, și merită spus fiindcă `R21` pare să-l interzică: în
`append_only.toml` e `journal_line`, nu antetul. Linia e cea care se repartiționează.

## 4. Aceeași tranzacție, și de ce nu e detaliu

Ștampilele se scriu în `post_entry`, între linii și trecerea în `posted`. Dacă ar fi putut fi scrise
după, ar fi putut lipsi — iar cazul pentru care există tabela e exact acela: o postare a cărei bază
n-a consemnat-o nimeni. Testul o arată prin refuz: o ștampilă respinsă ia înregistrarea cu ea.

## 5. Imutabilă, prin două mecanisme, și unul dintre ele a fost măsurat

Ce a stat sub o postare e la fel de imutabil ca postarea (`R10`).

Aplicația nu are `UPDATE` și nu are `DELETE`. **Asta a cerut o corecție de la prima scriere:** un
`GRANT SELECT, INSERT` restrâns nu *retrage* nimic, iar tabela ajunsese la `evidenta_app` cu toate
patru privilegiile, din cele implicite pe care le primește orice tabelă nouă. Comentariul din
migrare spunea că privilegiul oprește aplicația; catalogul spunea altceva. `REVOKE`-ul explicit
există fiindcă măsurătoarea a contrazis comentariul, nu din prudență.

Triggerul acoperă restul — o migrare, o reparație de date, orice rulează ca proprietar. Testul îl
exercită pe rânduri semănate, nu scrise prin ORM: rândurile ORM trăiesc în tranzacția testului, deci
un `UPDATE` de pe altă conexiune nu prinde nimic și un trigger `FOR EACH ROW` nu se declanșează
niciodată. Un test scris așa trece și cu trigger, și fără.

## 6. Ce nu livrează

**Nimic nu scrie încă ștampile**, fiindcă niciun handler nu rezolvă încă un parametru fiscal —
F1.4.4 e blocată pe cazurile `C1`–`C5` din [ADR-036](036-forma-postarii.md) §11. Mecanismul există
înaintea primului producător, deliberat și la cererea proprietarului: **e ieftin acum și scump după
ce există calcule postate**, fiindcă o coloană adăugată ulterior e goală pentru toată istoria, iar
istoria e singurul lucru pentru care tabela există.

`OD-67` nu blochează: ștampila **citește** parametri, nu îi scrie.
