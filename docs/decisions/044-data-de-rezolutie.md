# ADR-044 — Regula se rezolvă după data perioadei, niciodată după data calculului

- **Status:** Acceptat — decizie de domeniu, luată de proprietar (contabil practicant)
- **Data:** 2026-08-26
- **Închide:** `OD-66`
- **Afectează:** `R18`, `C14`, fiecare rezolvator din `fiscal`, calculul salarial (F2)
- **Legate:** [ADR-039](039-valuta-si-perioade.md) `DN-05` §5 (`document_date` versus `posting_date`),
  [ADR-045](045-sursa-de-adevar-pentru-parametri.md), `docs/_input/cercetare/od-22-cnas-cnam.md`

## 1. Întrebarea, după ce s-a îngustat

Cercetarea pe `OD-22` a scos la iveală **Ordinul CNAS nr. 31-A din 18.02.2026, pct. 8**: contribuțiile
calculate în perioada de gestiune pentru **alte** perioade se calculează **conform tarifelor perioadei
de gestiune** — adică ale anului în care se face calculul — și se declară în luna de calcul.

`R18` spune invers: *„Recalcularea unei perioade trecute folosește parametrii și algoritmul valabili
atunci."*

Prima formulare a fost „`R18` e contrazis de o normă în vigoare", ceea ce suna a rescriere de
arhitectură. **Două lucruri au îngustat-o, apoi au desființat-o** — măsurătoarea de mai jos, și apoi
citirea legii (§6), care arată că nu exista niciun conflict.

**Măsurătoarea:** Toate rezolvatoarele din produs —

```
resolve_parameter(parameter_key, effective_date, …)
resolve_logic(logic_key, effective_date)
resolve_handler(name, accounting_date, capabilities)
treatment_for(event_type, accounting_date, snapshot)
active_profile(company_id, on_date)
postable_accounts(company_id, on_date)
```

— **primesc data ca argument, și niciunul nu citește ceasul.** Singurul `datetime.now` din zonă e
`occurred_at`, un moment, nu o zi de rezoluție. Deci mecanismul exprimă deja ambele citiri fără nicio
modificare, iar întrebarea reală era mai mică: **ce dată pasează apelantul.**

## 2. Decizia

> **Data perioadei, nu data calculului.** Rezoluția oricărei reguli fiscale se face după **data
> economică a faptului** — perioada la care se referă calculul. **Data calculului se stochează ca
> metadată de audit și nu intră niciodată în rezoluția regulii.**

## 3. Motivul principal: reproductibilitatea

**Recalcularea lunii martie în iunie trebuie să dea exact același rezultat.**

Dacă rezolvatorul primește data calculului, aceeași perioadă produce rezultate diferite după *când* o
rulezi. Nu e o inconsecvență estetică: **desființează corpusul de regresie.** `C14` cere corpusul rulat
la fiecare modificare de parametru sau algoritm, iar un corpus ale cărui așteptări depind de ziua
rulării nu mai poate afirma nimic stabil — nu mai e corpus, e o măsurătoare.

E același argument ca la `OD-63`, într-un alt strat: acolo un predicat de acces care citea ceasul făcea
accesul **netestabil și neauditabil**; aici un rezolvator care citește ceasul face **rezultatul fiscal**
netestabil, cu aceeași consecință — la o dispută nu se poate reconstitui ce a produs sistemul.

## 4. Motivul secundar: e tiparul deja folosit peste tot

Regulile fiscale sunt date cu `valid_from`/`valid_to` și se rezolvă după **data economică a faptului**,
nu după data operațiunii tehnice. Exact tiparul din [ADR-039](039-valuta-si-perioade.md) `DN-05` §5:
**data economică conduce regula, data tehnică conduce plasarea în registru.**

`document_date` decide ce cotă se aplică; `posting_date` decide în ce perioadă intră înregistrarea.
Data calculului aparține celei de-a doua categorii și nu are ce căuta în prima.

## 5. Criteriul pentru o excepție la `R18`

Consecința decisivă a acestei decizii nu e regula, ci **testul care spune când poate fi încălcată**:

> Se scrie o excepție la `R18` **doar dacă textul legal al regulii se ancorează explicit în momentul
> actului**, nu în perioada la care se referă.

Categoria tipică sunt **majorările de întârziere și penalitățile**, care prin construcție se calculează
la data plății: acolo „momentul actului" *este* faptul generator, nu o convenție de implementare.

**Dacă regula nu e din categoria asta, excepția ar fi o scurtătură de implementare deghizată în cerință
legală.** Și o excepție la un invariant trebuie să fie **vizibilă în cod și în `CLAUDE.md`**, niciodată
implicită într-un apelant — altfel invariantul rămâne scris și nu mai e adevărat.

## 6. Norma CNAS nu era o excepție — era o citire greșită a perioadei

**Prima lectură a acestui ADR spunea că întrebarea „se mută" spre textul Legii nr. 489/1999, necitit.
Textul a fost între timp citit de proprietar, și rezultatul e mai bun: nu e nevoie de nicio excepție.**

> **REZERVĂ (`OD-85`):** textul anexei nr. 1 la Legea nr. 489/1999 **nu e citit**; tarifele de mai jos
> vin din Ordinul CNAS nr. 31-A, act care aplică anexa. *Declanşator: înainte de handlerul de salarii,
> unde distincţia devine cod.* — marcaj adăugat retroactiv 2026-08-30 prin
> [ADR-066](066-rezerva-e-decizie-deschisa.md); rezerva exista din prima redactare, dar fără rând în
> registru, şi s-a pierdut exact la handler.

**Tarifele sunt în lege, nu în ordin.** Anexa nr. 1 la Legea nr. 489/1999 reglementează categoriile de
plătitori, **tarifele**, baza de calcul și termenele de virare. Ordinul CNAS nu inventează un cuantum —
repetă o regulă care are deja rang de lege. Iar legea ancorează explicit **în momentul acumulării**, în
două locuri:

> **Art. 20 alin. (5)** — plătitorii sunt obligați să calculeze și să vireze, în mărimea și termenele
> din anexa nr. 1, contribuțiile **aferente salariilor calculate** și altor recompense.
>
> **Anexa nr. 1** — contribuția datorată lunar de angajator se calculează prin aplicarea tarifului
> corespunzător la suma salariilor și recompenselor **calculate lunar** pentru toți angajații.

Iar sinteza practicii spune direct: contribuțiile se calculează **conform contabilității de
angajamente**.

### 6.1 De ce asta desființează întrebarea în loc s-o rezolve

Confuzia nu era „normă contra invariant". Era despre **ce înseamnă *perioada* pentru CAS.**

Sub contabilitate de angajamente, **un salariu calculat în iunie pentru muncă din martie se acumulează
în iunie.** Nu e o recalculare a lui martie — e un **fapt economic al lunii iunie**. Perioada lui
economică este iunie, deci parametrii lui sunt cei din iunie. `R18` nu e atins.

Două situații arată identic și nu sunt:

| Situație | Perioadă economică | Tarif |
|---|---|---|
| **Corectarea unei erori** în acumularea din martie | martie | martie |
| **Plată suplimentară calculată în iunie** pentru muncă din martie | **iunie** | **iunie** |

Prima e recalculare, a doua e **eveniment nou**. `R18` le tratează corect pe amândouă — **cu condiția
ca rezolvatorul să primească data de angajament, nu perioada de muncă.**

### 6.2 Consecința pentru modelul de salarii

Linia de salariu are nevoie de **două date**, exact ca linia de jurnal:

- **perioada de muncă** — pentru declarația nominală și pentru drepturi;
- **data de angajament** — pentru rezoluția tarifului.

Același tipar ca `document_date` / `posting_date` din [ADR-039](039-valuta-si-perioade.md) `DN-05` §5.
Ceea ce e o confirmare utilă în sine: **al treilea loc în care aceeași distincție apare independent**,
descoperită de fiecare dată din alt capăt. Când o distincție se redescoperă singură de trei ori, nu mai
e o convenție de proiect — e forma domeniului.

> **Rezerva proprietarului, purtată ca atare:** textul integral al anexei nr. 1 **nu a fost citit**, ci
> doar sinteze care îl citează. **De confirmat înainte de scrierea handlerului de salarii**, fiindcă
> acolo distincția de la §6.2 devine cod.

## 7. Ce s-a respins

**Data calculului ca dată de rezoluție.** Ar fi urmat litera ordinului CNAS, dar cu trei costuri: pierde
reproductibilitatea și odată cu ea corpusul de regresie (§3); rupe tiparul `document_date` /
`posting_date` folosit peste tot altundeva (§4); și ar fi generalizat de la un act subordonat la toate
regulile fiscale, ceea ce nici ordinul nu cere.

**Un comutator de configurație** — „rezolvă după perioadă sau după calcul, la alegere". Respins din
același motiv pentru care s-a respins alinierea sesiunii de bază la `OD-63`: funcționează, și face
corectitudinea să depindă de o setare pe care nimic n-o verifică.

## 8. Ce nu se schimbă în cod

**Nimic.** Rezolvatoarele primesc deja data ca argument; docstring-ul lui
`fiscal/parameters/services/resolution.py` afirmă deja că *„a resolver that could fall back to «today»
would make recalculating a closed period return this year's answer, and the mistake would be silent and
correct-looking"*. Decizia confirmă mecanismul existent și îi dă temeiul; ce se adaugă e criteriul de la
§5, care înainte nu exista.
