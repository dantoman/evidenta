# ADR-050 — Conturile lanțului de închidere sunt roluri de cont, nu parametri fiscali

- **Status:** Acceptat — decizie de domeniu contabil, luată de proprietar prin instrucțiune scrisă,
  2026-08-29 (punctul 2); consemnată de sesiunea de implementare
- **Data:** 2026-08-29
- **Decide:** proprietarul proiectului, contabil practicant ([ADR-010](010-contabilul-practicant.md))
- **Închide:** jumătate din `OD-22` — partea „mapări de conturi"; `OD-22` rămâne deschisă strict
  pentru cote, praguri, plafoane, scutiri, termene
- **Afectează:** F1.5.4 (închiderea), `accounting/slots` (catalogul de roluri), `08-f1-backlog.md`
  F1.5.4 și tabelul de blocaje, `000-open-decisions.md` rândul `OD-22`
- **Legate:** [ADR-036](036-forma-postarii.md) §5.1, §6.1 (roluri și legare),
  [ADR-048](048-formula-si-sloturile-tipizate.md) (catalogul livrat, legarea necondiționată),
  [ADR-045](045-sursa-de-adevar-pentru-parametri.md) (actul de rang potrivit dă valoarea)

---

## 1. Context

Backlogul F1.5.4 spunea: *„conturile concrete din lanț sunt mapări de conturi, deci parametri
fiscali (`R15`): se încarcă din `fiscal_parameter` cu act normativ, nu se scriu în handler"*, și
bloca închiderea pe `OD-22` — care, la rândul ei, e blocată pe numerele de Monitorul Oficial ale
actelor modificatoare din Codul fiscal.

Definiția era greșită, și greșeala ținea două sarcini blocate pe un act care nu le privește.
Conturile 351, 731, 333, 334, 332 vin din **Planul general de conturi** — Ordinul MF nr. 119 din
06.08.2013 — act propriu, cu autoritate proprie și cadență proprie. Nu se schimbă printr-o
modificare de Cod fiscal, deci nu sunt parametri fiscali în sensul `R15`, ci exact ce
[ADR-036](036-forma-postarii.md) §6.1 numește **rol de cont**: un slot semantic al handlerului,
legat la un cont concret, cu implicitul din plan. Catalogul cu 37 de roluri și legarea
necondiționată există de la [ADR-048](048-formula-si-sloturile-tipizate.md) și a fost livrat cu
`CHELTUIALA_IMPOZIT_VENIT → 731` deja în el.

## 2. Opțiuni evaluate

1. **Conturile lanțului ca `fiscal_parameter`** (varianta din backlog). *Avantaj:* aparent aceeași
   rigoare ca la cote. *Dezavantaje:* pune un act contabil sub rezolvatorul de parametri fiscali —
   aceeași confuzie pe care `OD-56` a numit-o pentru planul de conturi; cere numere de MO pentru
   acte modificatoare ale Codului fiscal care n-au nicio legătură cu 351; și dublează mecanismul de
   legare rol → cont cu un al doilea, pentru aceleași conturi. *Cost de schimbare:* mare — două
   locuri pentru același fapt.
2. **Conturile scrise în handler.** *Dezavantaj:* exact ce interzice ADR-036 §5.1 („fără cont de
   rezervă", rolul, nu contul) și ce backlogul numea pe drept „un rezultat pe care nimeni nu-l poate
   apăra la un control".
3. **Extinderea catalogului de roluri** — *aleasă*. Rolurile lanțului intră în
   `roles_snc_2020.csv` cu subcontul implicit din plan și sursa citată; handlerele de închidere le
   referă ca pe orice rol; legarea per companie e cea existentă. *Cost de schimbare:* zero
   structură — e date peste ce există.

## 3. Decizia

### 3.1 Rolurile

| Rol | Cont implicit | Denumire din Planul general de conturi |
|---|---|---|
| `REZULTAT_FINANCIAR_TOTAL` | 351 | Rezultat financiar total |
| `CHELTUIALA_IMPOZIT_VENIT` | 731 | Cheltuieli privind impozitul pe venit *(exista)* |
| `PROFIT_NET_PERIOADA` | 333 | Profit net (pierdere netă) al perioadei de gestiune |
| `PROFIT_UTILIZAT_PERIOADA` | 334 | Profit utilizat al perioadei de gestiune |
| `PROFIT_NEREPARTIZAT_ANI_PRECEDENTI` | 332 | Profit nerepartizat (pierdere neacoperită) al anilor precedenți |

Clasele 6 și 7 nu primesc câte un rol: lanțul le închide **integral**, ca mulțime de conturi de
venituri și cheltuieli ale perioadei, citite din plan după clasă — nu ca sloturi individuale.

### 3.2 Ordinea lanțului — aprobată, obligatorie

1. **Clasele 6 și 7 la 351, fără 731.** Veniturile și cheltuielile perioadei se închid la
   rezultatul financiar total; 731 **nu** se închide odată cu restul clasei 7.
2. **Se contabilizează impozitul pe venit pe 731.**
3. **731 la 351.**
4. **351 la 333.**
5. **La reformarea bilanțului:** 334 se decontează, 333 la 332.

Motivul pentru care 731 stă separat e de raportare, nu de gust: dacă 731 s-ar închide odată cu
restul clasei 7, **profitul până la impozitare din Situația de profit și pierdere iese greșit**.
Ordinea de mai sus e regula; un handler care o abate produce o situație financiară greșită, nu o
variantă.

### 3.3 Ce rămâne în `OD-22`

Strict ce e parametru fiscal în sensul `R15`: cote de TVA, cote CNAS și CNAM, plafoane, scutiri
personale, cote de impozit pe venit, praguri de înregistrare, termene de raportare, coeficienți de
amortizare fiscală — unde numerele de Monitorul Oficial chiar lipsesc. Pentru acestea nimic nu se
schimbă.

## 4. Consecințe

- **Devine posibil:** F1.5.4 se deblochează — `period.year.closed` are conturile din catalog și
  ordinea de aici; nu așteaptă niciun număr de Monitorul Oficial. Impozitul pe venit din pasul 2
  cere cota (parametru fiscal, `OD-22`) — dar handlerul se scrie și se testează cu o cotă de test,
  iar cota reală intră ca date, pe calea din [ADR-049](049-rolul-de-date-de-referinta.md).
- **Devine imposibil sau scump, asumat:** o companie care vrea alt cont pentru rezultatul total
  reface legarea (stratul 2), nu configurează lanțul; ordinea pașilor nu e configurabilă.
- **Ce se modifică:** `roles_snc_2020.csv` (patru roluri noi, sursa: Planul general de conturi,
  Ordinul MF nr. 119/2013), `tests/isolation/test_account_roles.py` (numărul fixat: 41),
  backlogul F1.5.4 și tabelul de blocaje, rândul `OD-22` din registru.
- **Ce se verifică automat:** testul de catalog (numărul și legarea implicită a fiecărui rol la un
  cont existent în planul livrat); la F1.5.4, testele lanțului — după închiderea clasei 7 fără 731,
  soldul lui 731 e nenul până la pasul 3; după pasul 4, 351 e zero; `accounting-reviewer` pe
  handler.

## 5. Surse

- Instrucțiunea proprietarului, 2026-08-29, punctul 2 — inclusiv ordinea lanțului, verbatim.
- Planul general de conturi contabile, Ordinul MF nr. 119 din 06.08.2013 (conturile 332, 333, 334,
  351, 731 — `snc_2020.csv`, transcris din PDF-ul MF).
- [ADR-036](036-forma-postarii.md) §5.1, §6.1; [ADR-048](048-formula-si-sloturile-tipizate.md);
  `08-f1-backlog.md` F1.5.4 (formularea corectată); `CLAUDE.md` `R15`, `R9`.
