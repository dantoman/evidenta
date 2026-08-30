# ADR-066 — O rezervă cu declanșator este o decizie deschisă și are rând în registru

- **Status:** **Acceptat** — decizie de proces, a proprietarului, sub
  [ADR-002](002-guvernanta-deciziilor.md)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** `OD-82`
- **Afectează:** forma ADR-urilor, `000-open-decisions.md`,
  `backend/tests/architecture/test_reservations_are_tracked.py` (nou)
- **Legate:** `ADR-002` (regimul de aprobare). *Cazul măsurat — ADR-044 §6 și ADR-065 §3 — e în §1 și
  §5: `Legate:` numește ce depinde, nu ce se citează ca exemplu, iar distincția contează fiindcă
  gardianul din §3.3 o citește*

## 1. Cazul, măsurat

[ADR-044](044-data-de-rezolutie.md) §6 purta o rezervă explicită: *textul anexei nr. 1 la Legea nr.
489/1999 n-a fost citit; procentele vin din Ordinul CNAS nr. 31-A, act care aplică anexa; **de
confirmat înainte de scrierea handlerului de salarii, fiindcă acolo distincția devine cod**.*

[ADR-065](065-schema-salarizarii.md) **este** acel handler. Îl citează pe ADR-044. Și a scăpat rezerva
exact în tabelul de tarife — unde s-a și produs, în aceeași frază, o eroare de mapare punct → cotă
(29% atribuit pct. 1.2 în loc de 1.1).

**Vigilența nu a fost mecanismul lipsă: rezerva fusese scrisă și citită.** Ce a lipsit e altceva, și e
verificabil: **rezerva trăia doar în proza unui ADR.** Nu avea rând în registrul deciziilor deschise,
deci nimic n-o urmărea, nimic n-o scotea la iveală când sarcina pe care o numea a ajuns la rând, și
pierderea ei n-a produs niciun semnal.

*(Contrast util, din același incident: `fiscal/parameters/data/cnas_cnam.toml` purta maparea **corect**
de la început — `provisional_reason` numește pct. 1.1. ADR-ul contrazicea datele încărcate și nimic nu
le compara. Acela e un al doilea mod de eșec, distinct, urmărit separat în `OD-86`.)*

## 2. Opțiuni evaluate

1. **Nimic — se citește mai atent.** *Avantaje:* zero cost. *Dezavantaje:* e exact ce a eșuat; rezerva
   fusese citită. Un mecanism care cere atenție suplimentară la fiecare transcriere nu e mecanism.
   *Cost de schimbare:* —
2. **Regulă de proces plus marcaj auto-declarat și gardian.** *Avantaje:* e tiparul care a funcționat
   de trei ori în acest proiect — `REVERSIBILITY` la migrări, `decizie de domeniu` la ADR-uri,
   `case(*sets, cites=…)` ca unică ușă în corpus. Nimic mecanic nu poate distinge o rezervă de o
   propoziție prudentă; ce se poate impune e **declarația**, exact acolo unde absența ei costă.
   *Dezavantaje:* încă un marcaj de ținut minte la scrierea unui ADR. *Cost de schimbare:* mic.
3. **Gardian care citește proza și deduce rezervele.** *Avantaje:* niciunul realizabil.
   *Dezavantaje:* ar produce fie zgomot ignorat, fie tăcere falsă. *Cost de schimbare:* —

## 3. Decizie

**Opțiunea 2.**

### 3.1 Regula

**O rezervă cu declanșator este o decizie deschisă.** Dacă un ADR spune „X nu s-a verificat, se
confirmă înainte de Y", atunci X **are rând în `000-open-decisions.md`**, cu declanșatorul în coloana
lui — ca `OD-72`, care e forma corectă și exista deja.

### 3.2 Marcajul

În ADR, rezerva se declară cu un marcaj care poartă tokenul:

```
> **REZERVĂ (`OD-85`):** anexa nr. 1 la Legea nr. 489/1999 nu e citită; procentele vin din
> Ordinul CNAS nr. 31-A, act care o aplică. Declanșator: înainte de handlerul de salarii.
```

Iar unde se închide:

```
> **REZERVĂ ÎNCHISĂ (`OD-85`):** anexa obținută la <data>, procentele confirmate verbatim.
```

**Auto-declarat, deliberat** — la fel ca `decizie de domeniu`. Nimic mecanic nu poate ști dacă o frază
e o rezervă; ce se poate impune e ca declarația, odată făcută, să fie urmărită.

### 3.3 Ce impune gardianul

`backend/tests/architecture/test_reservations_are_tracked.py`:

1. **Fiecare marcaj `REZERVĂ` numește un token care există în registru**, într-o secțiune deschisă —
   nu în „Închise". O rezervă care trimite la o decizie închisă e ori rezolvată (și marcajul se
   schimbă), ori tokenul e greșit.
2. **Propagarea:** un ADR care numește în `Legate:` un ADR ce poartă o rezervă deschisă trebuie să
   poarte el însuși ori aceeași rezervă, ori închiderea ei numită. **Aceasta e verificarea care ar fi
   prins cazul din §1.**
3. **Anti-derivă:** dacă niciun marcaj nu mai există nicăieri, testul cade. Un gardian căruia i-a
   dispărut intrarea raportează succes — modul de eșec pe care `test_domain_decisions_cite_sources.py`
   îl numește deja la el.

**Ce nu impune:** că rezerva e adevărată, sau că e completă. Ca la `ADR-002` și la gardianul de citare,
bara e cea pe care nimeni n-o poate contesta.

## 4. Consecințe

- **Devine posibil:** o rezervă supraviețuiește transcrierii dintr-un ADR în următorul, fiindcă nu mai
  depinde de faptul că cineva și-a amintit-o.
- **Devine imposibil:** o rezervă declarată care nu are rând; și un ADR nou care se sprijină pe unul cu
  rezervă deschisă fără s-o propage sau s-o închidă numit.
- **De modificat ca urmare:** `OD-85` **nouă** — prima aplicare a regulii, retroactiv: rezerva lui
  ADR-044 §6 primește rândul care îi lipsea; ADR-044 și ADR-065 primesc marcajul. `OD-82` se închide.
- **Nu acoperă** divergența dintre ce afirmă un ADR și ce spun datele încărcate — al doilea mod de eșec
  din același incident, raportat separat (`OD-86`), fără nimic construit.

## 5. Surse

- [ADR-044](044-data-de-rezolutie.md) §6; [ADR-065](065-schema-salarizarii.md) §3.
- Tiparul: `backend/tests/architecture/test_reverse_migrations.py` (`REVERSIBILITY`),
  `backend/tests/architecture/test_domain_decisions_cite_sources.py` (`decizie de domeniu`),
  `backend/tests/corpus/citations.py` (`case(*sets, cites=…)`).
- `OD-72` — forma corectă a unei amânări cu declanșator, care exista deja în registru.
- Instrucțiunea proprietarului, 2026-08-30.
