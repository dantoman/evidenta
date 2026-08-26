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
arhitectură. **Măsurătoarea a îngustat-o.** Toate rezolvatoarele din produs —

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

## 6. Unde cade norma CNAS — și de ce nu se poate spune încă

Ordinul CNAS nr. 31-A/2026 este **act subordonat Legii nr. 489/1999**, ale cărei anexe poartă efectiv
cotele. Prin [ADR-045](045-sursa-de-adevar-pentru-parametri.md), autoritatea unui regulament asupra
**cuantumurilor** este exact ce se neagă; ce rămâne obligatoriu din pct. 8 e partea procedurală — *„se
declară în luna de calcul"*.

> **Nu se afirmă că astfel conflictul dispare.** `legis.md` întoarce 403 și Monitorul Oficial e cu
> plată, deci **textul Legii nr. 489/1999 n-a putut fi citit**. Ce se poate spune e că întrebarea **se
> mută**: din „normă contra invariant" în „ce spune legea, dincolo de ordin". Până când textul legii e
> citit, `R18` se aplică fără excepție, iar dacă legea însăși ancorează calculul în perioada de
> gestiune, atunci excepția se scrie după criteriul de la §5.

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
