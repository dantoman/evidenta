# ADR-016 — Limba contabilității: cerință legală, nu preferință de produs

- **Status:** Acceptat — conținut juridic; co-semnătura din `ADR-002` acoperită prin `ADR-010`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului, în ambele roluri
- **Închide:** `OD-38` *(ca **nu se face**)*; partea rămasă deschisă din `DN-01` / `OD-13`
- **Rafinează:** [ADR-014](014-limba-rusa.md), secțiunea „Datele de referință livrate de noi"
- **Afectează:** F0.6, F0.7, F1.1, F0.10.3

## Temeiul legal

**Legea contabilității și raportării financiare nr. 287 din 15.12.2017, art. 7:**

> **Articolul 7. Limba şi moneda în care se ţine contabilitatea**
> (1) Contabilitatea se ţine în limba română şi în monedă naţională.
> (2) Contabilitatea faptelor economice efectuate în valută străină se ţine atît în monedă
> naţională, cît şi în valută străină, în conformitate cu standardele de contabilitate.

Limba de stat este româna, cu grafie latină (Constituția, art. 13, după înlocuirea sintagmelor prin
legea din martie 2023, menținută de Curtea Constituțională în martie 2024). Rusa nu are statut
oficial.

## Decizie

**Rusa este exclusiv strat de prezentare.**

Nu poate fi altceva: registrele contabile și situațiile financiare se țin în română prin lege. Un
mecanism de traducere care ar produce un registru în rusă ar produce un artefact **neconform** — nu
o funcționalitate incompletă, ci un defect de conformitate.

Trei consecințe directe:

**1. `OD-38` (ieșire bilingvă) se închide ca „nu se face".** Nu este funcționalitate amânată. Pentru
documentele contabile, este ceva ce nu poate exista. Dacă cerința reapare din piață, răspunsul este
explicația legală, nu o intrare în backlog.

**2. Denumirile din planul de conturi rămân valoare unică, în română.** Aceasta **anulează** partea
deschisă din `ADR-014`: nu mai există un „caz scump" de propagat per companie, pentru că nu se
adaugă niciodată a doua limbă în instanță. `DN-01` se închide complet.

Dacă vreodată se dorește o etichetă de afișare în rusă pentru un cont, ea este **resursă de
interfață cheiată pe codul contului** — la fel ca orice alt șir de interfață (`C32`), niciodată
valoare stocată per companie. Distincția nu e cosmetică: prima nu poate ajunge într-un registru, a
doua poate.

**3. Regula din `CLAUDE.md` capătă temei legal.** Nu „nimic din traducerea interfeței nu ajunge în
documente" ca preferință, ci cu trimitere la art. 7. Un agent care vede o justificare legală are mai
puține șanse să ocolească regula decât unul care vede o convenție.

## Beneficiu colateral: art. 7 alin. (2)

Modelul de sumă din Spec B §7.1 — sumă în valută, valuta, cursul, suma în monedă națională, toate
patru stocate — nu mai este alegere de proiectare justificată prin imutabilitate. Este **cerință
legală**: „se ţine atît în monedă naţională, cît şi în valută străină".

Se consemnează în Spec B, pentru că o cerință legală nu se optimizează la o revizuire ulterioară de
performanță.

## Ce rămâne deschis, cu forma întrebării schimbată

Întrebarea era: acoperă art. 7 și conținutul documentelor primare, sau doar registrele și
raportarea?

**Art. 11 („Documentele primare") nu conține nicio cerință de limbă pentru documentele întocmite de
entitate.** Alin. (7) enumeră elementele obligatorii — denumire, număr, dată, IDNO, conținutul
faptelor economice, etaloane, semnături — fără să prescrie limba. Singura prevedere de limbă din tot
articolul este:

> (11) Documentele primare primite din străinătate şi întocmite în altă limbă decît română, engleză
> sau rusă sînt traduse în limba română.

Ea privește documentele **primite din străinătate**, iar rusa apare explicit printre limbile care
**nu** cer traducere.

Aceasta nu răspunde la întrebare — o restrânge. Ce rămâne de stabilit, și rămâne decizie contabilă:
dacă denumirea unui articol tastată în rusă de un tenant, ajunsă pe o factură fiscală emisă de el,
este conformă. → **`OD-40`**.

Produsul **nu restricționează nimic** până la răspuns. Restricția tăcută ar fi la fel de greșită ca
permisiunea tăcută, iar aici greșeala e reversibilă doar într-un sens: datele deja tastate rămân.

## Trei constatări din art. 11 care nu țin de limbă

Găsite citind articolul pentru întrebarea de mai sus. Nu sunt decizii; sunt intrări pentru F0.6 și
pentru Spec A, unde documentul core se proiectează:

| Alineat | Text | Unde atinge |
|---|---|---|
| (5) | documentele primare pe hârtie și în formă electronică au **aceeași putere juridică** | F0.6 — forma electronică nu e un compromis |
| (9) | la documentele electronice, cu excepția celor cu regim special, **semnătura nu e obligatorie**; identificarea persoanelor se stabilește prin **proceduri interne** | F0.6, F0.4 — auditul *este* procedura internă de identificare, deci nu e opțional |
| (14), (15) | corectările sunt **interzise** pe documentele de casă și de plată; pe restul se fac cu dată, nume și semnătură | F1 — regimul de corecție diferă pe tip de document, ceea ce Spec B §9 nu distinge încă |

Ultima este cea care merită atenție: modelul de storno din Spec B tratează uniform corecția, iar
legea nu.

## Consecințe

- `CLAUDE.md`: `C32` capătă temeiul legal; se adaugă `C33`.
- Spec B §2.2: nota despre `name_ro` se simplifică — valoare unică, în română, fără „aici va veni rusa".
- Spec B §7.1: modelul de sumă primește temeiul din art. 7 alin. (2).
- `ADR-014` rămâne valid; partea lui deschisă se închide aici.
- Registrul: `OD-38` → închisă („nu se face"); `OD-13` / `DN-01` → închise complet; `OD-40` nouă.

## Surse

- Legea nr. 287 din 15.12.2017 a contabilității și raportării financiare, art. 7, art. 11 —
  text extras din PDF-ul publicat de USMF, verificat împotriva rezumatului de pe
  [contabilitate.md](https://www.contabilitate.md/ro/always-at-hand/baza-juridica/reglementarea-normativ-legislativa-a-contabilitatii/translate-to-rom-zakon-o-bukhgalterskom-uchete-i-finansovoi-otchetnosti-no-287/2017).
  **De reconfirmat împotriva textului consolidat de pe [legis.md](https://www.legis.md/) înainte de
  a intra în corpusul de regresie** — copia consultată datează din 2020 și art. 11 a fost completat
  prin Legea nr. 302 din 30.11.2018.
- Constituția RM, art. 13; hotărârea Curții Constituționale, martie 2024.
- [ADR-014](014-limba-rusa.md), [ADR-010](010-contabilul-practicant.md)
