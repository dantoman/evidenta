# OD-23 — Nomenclatorul Planului general de conturi contabile

**Data cercetării:** 2026-08-26

**Sursa:** <https://mf.gov.md/sites/default/files/legislatie/Planul%20general%20de%20conturi%20contabile.pdf>
— PDF consolidat publicat de Ministerul Finanţelor, **63 de pagini, toate citite**. Extras cu
`pdftotext` în trei moduri (`-layout`, implicit, `-raw`); rezultatele celor trei extrageri concordă.

**Actul:** Ordinul Ministerului Finanţelor **nr. 119 din 06.08.2013**, Monitorul Oficial
**nr. 177-181, art. 1225, din 16.08.2013**; anexa publicată în Monitorul Oficial
**nr. 233-237, art. 1534, din 22.10.2013**. Nomenclatorul este în redacţia Ordinului
Ministerului Finanţelor **nr. 100 din 28.06.2019, în vigoare 01.01.2020**.

Antetul actului, aşa cum apare în PDF: `nr. 119 din 06.08.2013 (în vigoare 01.01.2014)`,
`Monitorul Oficial nr.233-237 art.1534 din 22.10.2013`,
`Monitorul Oficial nr.177-181 art.1225 din 16.08.2013`.

Capitolul II ocupă paginile 4–11; capitolul III, paginile 11–63.

Acest fişier este consemnare de sursă primară. Denumirile sunt transcrise litera cu litera din act,
inclusiv formele cu „î" („dobînzi", „pînă", „vînzări", „sfîrşitul") şi inclusiv erorile materiale
ale actului publicat. Nu s-a normalizat şi nu s-a corectat nimic.

---

## 1. Structura de codificare

Citat din capitolul I, verbatim:

> Simbolizarea conturilor are la bază sistemul zecimal potrivit căruia:
> − clasele de conturi sînt simbolizate cu o singură cifră de la 1 la 9;
> − grupele de conturi sînt simbolizate cu două cifre, din care: prima indică codul (simbolul) clasei în care este inclusă grupa respectivă, iar a doua – numărul grupei;
> − conturile de gradul I sînt simbolizate cu trei cifre, din care: primele două formează codul grupei, la care se referă contul respectiv, iar a treia cifră – numărul contului de gradul I;
> − conturile de gradul II sînt simbolizate cu patru cifre, din care: primele trei cifre indică codul contului de gradul I, iar a patra cifră – numărul contului de gradul II al contului sintetic respectiv.

**Abatere reală de la această regulă:** clasa 9 **nu are nivel de grupă**. Conturile 911–925 atârnă
direct de clasă, în ambele capitole — capitolul III nu conţine niciun titlu `GRUPA 9x`. În tabelul
din secţiunea 7 aceste conturi au `părinte = 9`.

---

## 2. Obligatoriu vs. recomandare. Ce poate adăuga o entitate

Citat din capitolul I, verbatim:

> Conturile de gradul I din clasele 1-7 sînt obligatorii pentru toate entităţile, iar conturile de gradul I din clasele 8-9 şi conturile de gradul II din toate clasele au un caracter de recomandare şi se aplică, după caz, în funcţie de particularităţile activităţii entităţii şi cerinţele de prezentare a informaţiilor, precum şi în scopuri de analiză şi control.

Citat din capitolul I, verbatim:

> Entităţile pot să introducă conturi suplimentare de gradul II în clasele 1-7 şi conturi de gradul I şi II în clasele 8-9 în conformitate cu necesităţile informaţionale proprii, fără dublarea şi denaturarea Planului general de conturi contabile.

---

## 3. Clasele de activ şi de pasiv

Citat din capitolul I, verbatim:

> Planul general de conturi contabile cuprinde conturi de activ şi de pasiv. Conturile din clasele 1, 2, 7 şi 8 (cu excepţia conturilor rectificative) sînt conturi de activ, iar conturile din clasele 3-6 (cu excepţia conturilor rectificative) sînt conturi de pasiv.

Clasa 9 nu este clasificată activ/pasiv în această frază. Despre ea actul spune separat, verbatim:

> Conturile din clasa 9 funcţionează în partidă simplă, conform căreia înregistrările se efectuează în debitul sau creditul unui singur cont, fără corespondenţă cu alte conturi.

---

## 4. Conturile rectificative

Marcajul **nu apare în capitolul II**. El există exclusiv în capitolul III, în text narativ, sub
forma `este un cont de activ (rectificativ)` / `este un cont de pasiv (rectificativ)`.

Lista de mai jos este completă şi exhaustivă: cuprinde toate cele 20 de apariţii ale şirului
`(rectificativ)` din document.

| cod | sens declarat | denumire (Cap. II) |
|---|---|---|
| 113 | pasiv | Amortizarea imobilizărilor necorporale |
| 114 | pasiv | Deprecierea imobilizărilor necorporale |
| 117 | pasiv | Deprecierea fondului comercial pozitiv |
| 124 | pasiv | Amortizarea mijloacelor fixe |
| 126 | pasiv | Amortizarea şi deprecierea resurselor minerale |
| 127 | pasiv | Deprecierea imobilizărilor corporale în curs de execuţie |
| 128 | pasiv | Deprecierea terenurilor |
| 129 | pasiv | Deprecierea mijloacelor fixe |
| 133 | pasiv | Amortizarea şi deprecierea activelor biologice imobilizate |
| 143 | pasiv | Deprecierea investiţiilor financiare pe termen lung |
| 152 | pasiv | Amortizarea şi deprecierea investiţiilor imobiliare |
| 214 | pasiv | Uzura obiectelor de mică valoare şi scurtă durată |
| 218 | pasiv | Ajustări pentru deprecierea stocurilor |
| 222 | pasiv | Corecţii (provizioane) privind creanţele compromise |
| 253 | pasiv | Provizioane pentru pierderi din împrumuturi neachitate la termen |
| 254 | pasiv | Ajustări pentru deprecierea investiţiilor financiare curente |
| 313 | activ | Capital nevărsat |
| 315 | activ | Capital retras |
| 334 | activ | Profit utilizat al perioadei de gestiune |
| 831 | pasiv | Adaos comercial |

Exemplu de formulare, verbatim:
`Contul 124 “Amortizarea mijloacelor fixe” este un cont de pasiv (rectificativ).`

**Observaţie asupra semnului soldului:** marcajul este exact inversul sensului clasei, fără excepţie
în acest act. Toate cele 16 conturi rectificative din clasele 1–2 sunt declarate **de pasiv**, deşi
stau în clase de activ. Conturile 313, 315 şi 334 sunt declarate **de activ** în clasa 3, care este
de pasiv. Contul 831 este declarat **de pasiv** în clasa 8, care este de activ.

---

## 5. Notele de modificare

### 5.1 Note de bloc, la finalul capitolului II

Capitolul II **nu conţine note inline per cont**. Nomenclatorul a fost înlocuit integral în 2019, iar
la finalul capitolului stau doar trei note de bloc, verbatim:

```
[Nomenclatorul în redacţia Ordinului Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020]
[Cap.II completat prin Ordinul Ministerului Finanţelor nr.26 din 04.03.2015, în vigoare
13.03.2015]
[Cap.II modificat prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare
01.01.2015]
```

Imediat sub ele, înainte de capitolul III, verbatim:

```
Notă: Pe tot parcursul textului capitolului III contul “312” se exclude conform Ordinului
     Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020
```

### 5.2 Note per cont, în capitolul III

Toate cele 33 de note per-cont din document se află în capitolul III, nu în capitolul II. Contul
**336** are nota cerută, dar ea este tot în capitolul III:
`[Contul 336 introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015]`

| cont | notă |
|---|---|
| 114 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 115 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 116 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 117 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 127 | completat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 141 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 142 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 143 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 162 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020, **contul 162 devine 163** |
| 162 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 218 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 253 | introdus prin Ordinul Ministerului Finanţelor nr.26 din 04.03.2015, în vigoare 13.03.2015 |
| 254 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| **312** | **abrogat** prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 314 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 316 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 317 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| **336** | **introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015** |
| 341 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 342 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 343 | introdus prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020, **contul 343 devine 344** |
| 344 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| **413** | **abrogat** prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |
| 414 | introdus prin Ordinul Ministerului Finanţelor nr.26 din 04.03.2015, în vigoare 13.03.2015 |
| 513 | introdus prin Ordinul Ministerului Finanţelor nr.26 din 04.03.2015, în vigoare 13.03.2015 |
| 616 | introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015 |
| 617 | introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015 |
| 618 | introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015 |
| 715 | introdus prin Ordinul Ministerului Finanţelor nr.26 din 04.03.2015, în vigoare 13.03.2015 |
| 716 | introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015 |
| 717 | introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015 |
| 718 | introdus prin Ordinul Ministerului Finanţelor nr.188 din 30.12.2014, în vigoare 01.01.2015 |
| 721 | modificat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020 |

Notele de renumerotare `contul 162 devine 163` şi `contul 343 devine 344` explică de ce nomenclatorul
actual are 163 „Avansuri acordate pe termen lung" şi 344 „Alte elemente de capital propriu".

---

## 6. Nomenclatorul conturilor contabile (capitolul II)

**517 rânduri: 9 clase, 32 de grupe, 156 conturi de gradul I, 320 conturi de gradul II.**

Ordinea este cea din act. Denumirile sunt transcrise litera cu litera, fără normalizare.

| cod | denumire | nivel | părinte |
|---|---|---|---|
| 1 | ACTIVE IMOBILIZATE | clasa | — |
| 11 | IMOBILIZĂRI NECORPORALE | grupa | 1 |
| 111 | Imobilizări necorporale în curs de execuţie | gradul I | 11 |
| 112 | Imobilizări necorporale în exploatare | gradul I | 11 |
| 1121 | Concesiuni, licenţe şi mărci | gradul II | 112 |
| 1122 | Drepturi de autor şi titluri de protecţie | gradul II | 112 |
| 1123 | Programe informatice | gradul II | 112 |
| 1124 | Alte imobilizări necorporale | gradul II | 112 |
| 113 | Amortizarea imobilizărilor necorporale | gradul I | 11 |
| 1131 | Amortizarea concesiunilor, licenţelor şi mărcilor | gradul II | 113 |
| 1132 | Amortizarea drepturilor de autor şi titlurilor de protecţie | gradul II | 113 |
| 1133 | Amortizarea programelor informatice | gradul II | 113 |
| 1134 | Amortizarea altor imobilizări necorporale | gradul II | 113 |
| 114 | Deprecierea imobilizărilor necorporale | gradul I | 11 |
| 115 | Fond comercial pozitiv | gradul I | 11 |
| 116 | Fond comercial negativ | gradul I | 11 |
| 117 | Deprecierea fondului comercial pozitiv | gradul I | 11 |
| 12 | IMOBILIZĂRI CORPORALE, TERENURI, MIJLOACE FIXE ŞI RESURSE MINERALE | grupa | 1 |
| 121 | Imobilizări corporale în curs de execuţie | gradul I | 12 |
| 1211 | Construcţii în curs de execuţie | gradul II | 121 |
| 1212 | Utilaj destinat instalării | gradul II | 121 |
| 1213 | Imobilizări corporale pînă la punerea în utilizare | gradul II | 121 |
| 1214 | Costuri ulterioare în curs de execuţie | gradul II | 121 |
| 122 | Terenuri | gradul I | 12 |
| 1221 | Terenuri în curs de pregătire pentru utilizare prestabilită | gradul II | 122 |
| 1222 | Terenuri fără construcţii | gradul II | 122 |
| 1223 | Terenuri cu construcţii | gradul II | 122 |
| 1224 | Terenuri cu zăcăminte | gradul II | 122 |
| 1225 | Terenuri cu plantaţii perene | gradul II | 122 |
| 1226 | Terenuri primite în gestiune economică | gradul II | 122 |
| 1227 | Alte terenuri | gradul II | 122 |
| 123 | Mijloace fixe | gradul I | 12 |
| 1231 | Clădiri | gradul II | 123 |
| 1232 | Construcţii speciale | gradul II | 123 |
| 1233 | Maşini, utilaje şi instalaţii tehnice | gradul II | 123 |
| 1234 | Mijloace de transport | gradul II | 123 |
| 1235 | Inventar şi mobilier | gradul II | 123 |
| 1236 | Costuri ulterioare aferente obiectelor neînregistrate în bilanţ | gradul II | 123 |
| 1237 | Mijloace fixe primite în leasing financiar | gradul II | 123 |
| 1238 | Mijloace fixe primite în gestiune economică | gradul II | 123 |
| 1239 | Alte mijloace fix | gradul II | 123 |
| 124 | Amortizarea mijloacelor fixe | gradul I | 12 |
| 1241 | Amortizarea clădirilor | gradul II | 124 |
| 1242 | Amortizarea construcţiilor speciale | gradul II | 124 |
| 1243 | Amortizarea maşinilor, utilajelor şi instalaţiilor tehnice | gradul II | 124 |
| 1244 | Amortizarea mijloacelor de transport | gradul II | 124 |
| 1245 | Amortizarea inventarului şi mobilierului | gradul II | 124 |
| 1246 | Amortizarea costurilor ulterioare aferente obiectelor neînregistrate în bilanţ | gradul II | 124 |
| 1247 | Amortizarea mijloacelor fixe primite în leasing financiar | gradul II | 124 |
| 1248 | Amortizarea mijloacelor fixe primite în gestiune economică | gradul II | 124 |
| 1249 | Amortizarea altor mijloace fixe | gradul II | 124 |
| 125 | Resurse minerale | gradul I | 12 |
| 126 | Amortizarea şi deprecierea resurselor minerale | gradul I | 12 |
| 127 | Deprecierea imobilizărilor corporale în curs de execuţie | gradul I | 12 |
| 128 | Deprecierea terenurilor | gradul I | 12 |
| 129 | Deprecierea mijloacelor fixe | gradul I | 12 |
| 13 | ACTIVE BIOLOGICE IMOBILIZATE | grupa | 1 |
| 131 | Active biologice imobilizate în curs de execuţie | gradul I | 13 |
| 132 | Active biologice imobilizate în exploatare | gradul I | 13 |
| 133 | Amortizarea şi deprecierea activelor biologice imobilizate | gradul I | 13 |
| 1331 | Amortizarea activelor biologice imobilizate | gradul II | 133 |
| 1332 | Deprecierea activelor biologice imobilizate | gradul II | 133 |
| 14 | INVESTIŢII FINANCIARE PE TERMEN LUNG | grupa | 1 |
| 141 | Investiţii financiare pe termen lung în părţi neafiliate | gradul I | 14 |
| 1411 | Valori mobiliare | gradul II | 141 |
| 1412 | Cote de participaţie | gradul II | 141 |
| 1413 | Depozite | gradul II | 141 |
| 1414 | Împrumuturi acordate | gradul II | 141 |
| 1415 | Alte investiţii financiare | gradul II | 141 |
| 142 | Investiţii financiare pe termen lung în părţi afiliate | gradul I | 14 |
| 1421 | Acţiuni şi cote de participaţie deţinute în părţile afiliate | gradul II | 142 |
| 1422 | Împrumuturi acordate părţilor afiliate | gradul II | 142 |
| 1423 | Împrumuturi acordate aferente intereselor de participare | gradul II | 142 |
| 1424 | Alte investiţii financiare în părţi afiliate | gradul II | 142 |
| 143 | Deprecierea investiţiilor financiare pe termen lung | gradul I | 14 |
| 1431 | Deprecierea investiţiilor financiare pe termen lung în părţi neafiliate | gradul II | 143 |
| 1432 | Deprecierea investiţiilor financiare pe termen lung în părţi afiliate | gradul II | 143 |
| 15 | INVESTIŢII IMOBILIARE | grupa | 1 |
| 151 | Investiţii imobiliare | gradul I | 15 |
| 152 | Amortizarea şi deprecierea investiţiilor imobiliare | gradul I | 15 |
| 1521 | Amortizarea investiţiilor imobiliare | gradul II | 152 |
| 1522 | Deprecierea investiţiilor imobiliare | gradul II | 152 |
| 16 | CREANŢE ŞI AVANSURI ACORDATE PE TERMEN LUNG | grupa | 1 |
| 161 | Creanţe pe termen lung | gradul I | 16 |
| 1611 | Creanţe comerciale pe termen lung | gradul II | 161 |
| 1612 | Creanţe pe termen lung privind leasingul | gradul II | 161 |
| 1613 | Alte creanţe pe termen lung | gradul II | 161 |
| 162 | Creanţe ale părţilor afiliate pe termen lung | gradul I | 16 |
| 1621 | Creanţe aferente intereselor de participare | gradul II | 162 |
| 1622 | Alte creanţe ale părţilor afiliate | gradul II | 162 |
| 163 | Avansuri acordate pe termen lung | gradul I | 16 |
| 1631 | Avansuri acordate pentru imobilizări necorporale | gradul II | 163 |
| 1632 | Avansuri acordate pentru imobilizări corporale | gradul II | 163 |
| 1633 | Avansuri acordate pentru stocuri | gradul II | 163 |
| 1634 | Alte avansuri acordate pe termen lung | gradul II | 163 |
| 17 | ALTE ACTIVE IMOBILIZATE | grupa | 1 |
| 171 | Cheltuieli anticipate pe termen lung | gradul I | 17 |
| 172 | Alte active imobilizate | gradul I | 17 |
| 2 | ACTIVE CIRCULANTE | clasa | — |
| 21 | STOCURI | grupa | 2 |
| 211 | Materiale | gradul I | 21 |
| 2111 | Materii prime şi materiale de bază | gradul II | 211 |
| 2112 | Materiale auxiliare | gradul II | 211 |
| 2113 | Piese de schimb | gradul II | 211 |
| 2114 | Combustibil | gradul II | 211 |
| 2115 | Ambalaje | gradul II | 211 |
| 2116 | Anvelope şi acumulatoare procurate separat de mijloacele de transport | gradul II | 211 |
| 2117 | Materiale cu destinaţia agricolă | gradul II | 211 |
| 2118 | Materiale transmise temporar terţilor | gradul II | 211 |
| 2119 | Alte materiale | gradul II | 211 |
| 212 | Active biologice circulante | gradul I | 21 |
| 213 | Obiecte de mică valoare şi scurtă durată | gradul I | 21 |
| 2131 | Obiecte de mică valoare şi scurtă durată în stoc | gradul II | 213 |
| 2132 | Obiecte de mică valoare şi scurtă durată în exploatare | gradul II | 213 |
| 2133 | Construcţii şi dispozitive provizorii | gradul II | 213 |
| 2134 | Obiecte de mică valoare şi scurtă durată transmise temporar terţilor | gradul II | 213 |
| 214 | Uzura obiectelor de mică valoare şi scurtă durată | gradul I | 21 |
| 2141 | Uzura obiectelor de mică valoare şi scurtă durată | gradul II | 214 |
| 2142 | Uzura construcţiilor şi dispozitivelor provizorii | gradul II | 214 |
| 215 | Producţia în curs de execuţie | gradul I | 21 |
| 2151 | Produse în curs de execuţie | gradul II | 215 |
| 2152 | Servicii în curs de execuţie | gradul II | 215 |
| 2153 | Lucrări în curs de execuţie | gradul II | 215 |
| 216 | Produse | gradul I | 21 |
| 2161 | Produse finite | gradul II | 216 |
| 2162 | Semifabricate din producţie proprie | gradul II | 216 |
| 2163 | Produse secundare | gradul II | 216 |
| 2164 | Produse transmise temporar terţilor | gradul II | 216 |
| 217 | Mărfuri | gradul I | 21 |
| 2171 | Bunuri procurate în vederea revînzării | gradul II | 217 |
| 2172 | Produse transmise spre vînzare magazinelor proprii | gradul II | 217 |
| 2173 | Active imobilizate deţinute pentru vînzare | gradul II | 217 |
| 2174 | Mărfuri transmise temporar terţilor | gradul II | 217 |
| 218 | Ajustări pentru deprecierea stocurilor | gradul I | 21 |
| 2181 | Ajustări pentru deprecierea materialelor | gradul II | 218 |
| 2182 | Ajustări pentru deprecierea activelor biologice circulante | gradul II | 218 |
| 2183 | Ajustări pentru deprecierea obiectelor de mică valoare şi scurtă durată | gradul II | 218 |
| 2184 | Ajustări pentru deprecierea producţiei în curs de execuţie | gradul II | 218 |
| 2185 | Ajustări pentru deprecierea produselor | gradul II | 218 |
| 2186 | Ajustări pentru deprecierea mărfurilor | gradul II | 218 |
| 22 | CREANŢE COMERCIALE ŞI CALCULATE | grupa | 2 |
| 221 | Creanţe comerciale | gradul I | 22 |
| 2211 | Creanţe comerciale din ţară | gradul II | 221 |
| 2212 | Creanţe comerciale din străinătate | gradul II | 221 |
| 2213 | Alte creanţe comerciale | gradul II | 221 |
| 222 | Corecţii (provizioane) privind creanţele compromise | gradul I | 22 |
| 223 | Creanţe ale părţilor afiliate | gradul I | 22 |
| 2231 | Creanţe aferente intereselor de participare | gradul II | 223 |
| 2232 | Alte creanţe ale părţilor afiliate | gradul II | 223 |
| 224 | Avansuri acordate curente | gradul I | 22 |
| 2241 | Avansuri acordate pentru imobilizări necorporale | gradul II | 224 |
| 2242 | Avansuri acordate pentru imobilizări corporale | gradul II | 224 |
| 2243 | Avansuri acordate pentru stocuri | gradul II | 224 |
| 2244 | Alte avansuri acordate curente | gradul II | 224 |
| 225 | Creanţe ale bugetului | gradul I | 22 |
| 2251 | Creanţe privind impozitul pe venit | gradul II | 225 |
| 2252 | Creanţe privind taxa pe valoarea adăugată | gradul II | 225 |
| 2253 | Creanţe privind accizele | gradul II | 225 |
| 2254 | Creanţe privind alte impozite şi taxe | gradul II | 225 |
| 2255 | Alte creanţe ale bugetului | gradul II | 225 |
| 226 | Creanţe ale personalului | gradul I | 22 |
| 2261 | Creanţe ale titularilor de avans | gradul II | 226 |
| 2262 | Creanţe privind recuperarea prejudiciului material | gradul II | 226 |
| 2263 | Creanţe privind împrumuturile acordate personalului | gradul II | 226 |
| 2264 | Alte creanţe ale personalului | gradul II | 226 |
| 23 | ALTE CREANŢE CURENTE | grupa | 2 |
| 231 | Creanţe privind veniturile din utilizarea de către terţi a activelor entităţii | gradul I | 23 |
| 2311 | Creanţe privind leasingul | gradul II | 231 |
| 2312 | Creanţe privind dobînzile şi redevenţele calculate | gradul II | 231 |
| 2313 | Creanţe privind dividendele calculate | gradul II | 231 |
| 2314 | Alte creanţe privind veniturile | gradul II | 231 |
| 232 | Creanţe preliminate | gradul I | 23 |
| 2321 | Creanţe preliminate privind decontările cu bugetul | gradul II | 232 |
| 2322 | Creanţe preliminate privind leasingul | gradul II | 232 |
| 2323 | Alte creanţe preliminate | gradul II | 232 |
| 233 | Creanţe curente privind asigurările | gradul I | 23 |
| 234 | Alte creanţe curente | gradul I | 23 |
| 2341 | Creanţe privind ieşirea activelor imobilizate | gradul II | 234 |
| 2342 | Creanţe privind ieşirea altor active circulante | gradul II | 234 |
| 2343 | Creanţe privind subvenţiile | gradul II | 234 |
| 2344 | Creanţe privind finanţările şi încasările cu destinaţie specială | gradul II | 234 |
| 2345 | Creanţele aferente parteneriatului public-privat | gradul II | 234 |
| 2346 | Creanţe privind reclamaţiile înaintate şi recunoscute | gradul II | 234 |
| 2347 | Creanţe privind alte operaţiuni | gradul II | 234 |
| 24 | NUMERAR | grupa | 2 |
| 241 | Casa | gradul I | 24 |
| 2411 | Casa în monedă naţională | gradul II | 241 |
| 2412 | Casa în valută străină | gradul II | 241 |
| 2413 | Numerar în casierie legat | gradul II | 241 |
| 242 | Conturi curente în monedă naţională | gradul I | 24 |
| 2421 | Numerar la conturi nelegat | gradul II | 242 |
| 2422 | Numerar la conturi legat | gradul II | 242 |
| 243 | Conturi curente în valută străină | gradul I | 24 |
| 2431 | Numerar la conturi în ţară | gradul II | 243 |
| 2432 | Numerar la conturi în străinătate | gradul II | 243 |
| 2433 | Numerar la conturi legat | gradul II | 243 |
| 244 | Alte conturi bancare | gradul I | 24 |
| 2441 | Acreditive | gradul II | 244 |
| 2442 | Carduri bancare | gradul II | 244 |
| 2443 | Numerar la alte conturi bancare | gradul II | 244 |
| 245 | Transferuri de numerar în expediţie | gradul I | 24 |
| 246 | Documente băneşti | gradul I | 24 |
| 25 | INVESTIŢII FINANCIARE CURENTE | grupa | 2 |
| 251 | Investiţii financiare curente în părţi neafiliate | gradul I | 25 |
| 2511 | Valori mobiliare | gradul II | 251 |
| 2512 | Cote de participaţie | gradul II | 251 |
| 2513 | Depozite | gradul II | 251 |
| 2514 | Împrumuturi acordate | gradul II | 251 |
| 2515 | Alte investiţii financiare curente | gradul II | 251 |
| 252 | Investiţii financiare curente în părţi afiliate | gradul I | 25 |
| 2521 | Acţiuni şi cote de participaţie deţinute în părţile afiliate | gradul II | 252 |
| 2522 | Împrumuturi acordate părţilor afiliate | gradul II | 252 |
| 2523 | Împrumuturi acordate aferente intereselor de participare | gradul II | 252 |
| 2524 | Alte investiţii financiare în părţi afiliate | gradul II | 252 |
| 253 | Provizioane pentru pierderi din împrumuturi neachitate la termen | gradul I | 25 |
| 254 | Ajustări pentru deprecierea investiţiilor financiare curente | gradul I | 25 |
| 2541 | Ajustări pentru deprecierea investiţiilor financiare curente în părţi neafiliate | gradul II | 254 |
| 2542 | Ajustări pentru deprecierea investiţiilor financiare curente în părţi afiliate | gradul II | 254 |
| 26 | ALTE ACTIVE CIRCULANTE | grupa | 2 |
| 261 | Cheltuieli anticipate curente | gradul I | 26 |
| 262 | Alte active circulante | gradul I | 26 |
| 3 | CAPITAL PROPRIU | clasa | — |
| 31 | CAPITAL SOCIAL, NEÎNREGISTRAT ŞI PRIME DE CAPITAL | grupa | 3 |
| 311 | Capital social | gradul I | 31 |
| 313 | Capital nevărsat | gradul I | 31 |
| 3131 | Capital nevărsat privind părţile sociale neachitate de proprietari | gradul II | 313 |
| 3132 | Capital nevărsat privind acoperirea pierderilor anilor precedenţi | gradul II | 313 |
| 314 | Capital neînregistrat | gradul I | 31 |
| 3141 | Acţiuni neînregistrate emise la înfiinţarea societăţii | gradul II | 314 |
| 3142 | Părţi sociale depuse pînă la înregistrarea de stat a majorării capitalului social | gradul II | 314 |
| 315 | Capital retras | gradul I | 31 |
| 316 | Patrimoniul primit de la stat cu drept de proprietate | gradul I | 31 |
| 317 | Prime de capital | gradul I | 31 |
| 32 | REZERVE | grupa | 3 |
| 321 | Capital de rezervă | gradul I | 32 |
| 322 | Rezerve statutare | gradul I | 32 |
| 323 | Alte rezerve | gradul I | 32 |
| 33 | PROFIT NEREPARTIZAT (PIERDERE NEACOPERITĂ) | grupa | 3 |
| 331 | Corecţii ale rezultatelor anilor precedenţi | gradul I | 33 |
| 332 | Profit nerepartizat (pierdere neacoperită) al anilor precedenţi | gradul I | 33 |
| 333 | Profit net (pierdere netă) al perioadei de gestiune | gradul I | 33 |
| 334 | Profit utilizat al perioadei de gestiune | gradul I | 33 |
| 335 | Rezultat din tranziţia la noile reglementări contabile | gradul I | 33 |
| 336 | Excedent net (deficit net) al perioadei de gestiune | gradul I | 33 |
| 34 | ALTE ELEMENTE DE CAPITAL PROPRIU | grupa | 3 |
| 341 | Fonduri | gradul I | 34 |
| 3411 | Aporturi iniţiale ale fondatorilor fundaţiilor | gradul II | 341 |
| 3412 | Fondul de active imobilizate | gradul II | 341 |
| 3413 | Fondul de autofinanţare | gradul II | 341 |
| 3414 | Alte fonduri | gradul II | 341 |
| 342 | Subvenţii aferente activelor entităţilor cu proprietate publică | gradul I | 34 |
| 343 | Rezerve din reevaluare | gradul I | 34 |
| 344 | Alte elemente de capital propriu | gradul I | 34 |
| 35 | REZULTAT FINANCIAR TOTAL | grupa | 3 |
| 351 | Rezultat financiar total | gradul I | 35 |
| 4 | DATORII PE TERMEN LUNG | clasa | — |
| 41 | DATORII FINANCIARE PE TERMEN LUNG | grupa | 4 |
| 411 | Credite bancare pe termen lung | gradul I | 41 |
| 4111 | Credite bancare în monedă naţională | gradul II | 411 |
| 4112 | Credite bancare în valută străină | gradul II | 411 |
| 4113 | Datorii convertibile privind creditele bancare | gradul II | 411 |
| 4114 | Alte credite bancare pe termen lung | gradul II | 411 |
| 412 | Împrumuturi pe termen lung | gradul I | 41 |
| 4121 | Împrumuturi din părţi neafiliate | gradul II | 412 |
| 4122 | Împrumuturi din părţi afiliate | gradul II | 412 |
| 4123 | Împrumuturi din emisiunea de obligaţiuni | gradul II | 412 |
| 4124 | Împrumuturi de la personalul entităţii | gradul II | 412 |
| 4125 | Datorii convertibile privind împrumuturile | gradul II | 412 |
| 4126 | Alte împrumuturi pe termen lung | gradul II | 412 |
| 414 | Datorii privind depunerile de economii pe termen lung ale membrilor asociaţiilor de economii şi împrumut | gradul I | 41 |
| 4141 | Depuneri de economii pe termen lung ale membrilor asociaţiilor de economii şi împrumut | gradul II | 414 |
| 4142 | Dobînzi aferente depunerilor de economii pe termen lung ale membrilor asociaţiilor de economii şi împrumut | gradul II | 414 |
| 42 | ALTE DATORII PE TERMEN LUNG | grupa | 4 |
| 421 | Datorii comerciale pe termen lung | gradul I | 42 |
| 4211 | Datorii comerciale în ţară | gradul II | 421 |
| 4212 | Datorii comerciale în străinătate | gradul II | 421 |
| 4213 | Datorii privind leasingul financiar | gradul II | 421 |
| 4214 | Alte datorii comerciale pe termen lung | gradul II | 421 |
| 422 | Datorii faţă de părţile afiliate pe termen lung | gradul I | 42 |
| 4221 | Datorii aferente intereselor de participare | gradul II | 422 |
| 4222 | Alte datorii faţă de părţile afiliate | gradul II | 422 |
| 423 | Avansuri primite pe termen lung | gradul I | 42 |
| 4231 | Avansuri primite din ţară | gradul II | 423 |
| 4232 | Avansuri primite din străinătate | gradul II | 423 |
| 424 | Venituri anticipate pe termen lung | gradul I | 42 |
| 4241 | Subvenţii | gradul II | 424 |
| 4242 | Alte venituri anticipate pe termen lung | gradul II | 424 |
| 425 | Finanţări şi încasări cu destinaţie specială pe termen lung | gradul I | 42 |
| 426 | Provizioane pe termen lung | gradul I | 42 |
| 4261 | Provizioane pentru beneficiile angajaţilor | gradul II | 426 |
| 4262 | Provizioane pentru garanţii acordate cumpărătorilor/clienţilor | gradul II | 426 |
| 4263 | Provizioane pentru impozite | gradul II | 426 |
| 4264 | Alte provizioane | gradul II | 426 |
| 427 | Datorii pe termen lung privind bunurile primite în gestiune economică | gradul I | 42 |
| 428 | Alte datorii pe termen lung | gradul I | 42 |
| 5 | DATORII CURENTE | clasa | — |
| 51 | DATORII FINANCIARE CURENTE | grupa | 5 |
| 511 | Credite bancare pe termen scurt | gradul I | 51 |
| 5111 | Credite bancare în monedă naţională | gradul II | 511 |
| 5112 | Credite bancare în valută străină | gradul II | 511 |
| 5113 | Credite bancare în monedă naţională restante | gradul II | 511 |
| 5114 | Credite bancare în valută străină restante | gradul II | 511 |
| 5115 | Alte credite bancare pe termen scurt | gradul II | 511 |
| 5116 | Dobînzi aferente creditelor bancare | gradul II | 511 |
| 512 | Împrumuturi pe termen scurt | gradul I | 51 |
| 5121 | Împrumuturi de la părţi neafiliate | gradul II | 512 |
| 5122 | Împrumuturi de la părţi afiliate | gradul II | 512 |
| 5123 | Împrumuturi din emisiunea de obligaţiuni | gradul II | 512 |
| 5124 | Împrumuturi de la personalul entităţii | gradul II | 512 |
| 5125 | Alte împrumuturi pe termen scurt | gradul II | 512 |
| 5126 | Dobînzi aferente împrumuturilor | gradul II | 512 |
| 513 | Datorii privind depunerile de economii pe termen scurt ale membrilor asociaţiilor de economii şi împrumut | gradul I | 51 |
| 5131 | Depuneri de economii pe termen scurt ale membrilor asociaţiilor de economii şi împrumut | gradul II | 513 |
| 5132 | Dobînzi aferente depunerilor de economii pe termen scurt ale membrilor asociaţiilor de economii şi împrumut | gradul II | 513 |
| 52 | DATORII COMERCIALE CURENTE | grupa | 5 |
| 521 | Datorii comerciale curente | gradul I | 52 |
| 5211 | Datorii comerciale în ţară | gradul II | 521 |
| 5212 | Datorii comerciale în străinătate | gradul II | 521 |
| 5213 | Datorii privind leasingul | gradul II | 521 |
| 5214 | Alte datorii comerciale curente | gradul II | 521 |
| 522 | Datorii curente faţă de părţile afiliate | gradul I | 52 |
| 5221 | Datorii aferente intereselor de participare | gradul II | 522 |
| 5222 | Alte datorii faţă de părţile afiliate | gradul II | 522 |
| 523 | Avansuri primite curente | gradul I | 52 |
| 5231 | Avansuri primite din ţară | gradul II | 523 |
| 5232 | Avansuri primite din străinătate | gradul II | 523 |
| 53 | DATORII CALCULATE CURENTE | grupa | 5 |
| 531 | Datorii faţă de personal privind retribuirea muncii | gradul I | 53 |
| 5311 | Datorii salariale | gradul II | 531 |
| 5312 | Datorii faţă de deponenţi | gradul II | 531 |
| 532 | Datorii faţă de personal privind alte operaţii | gradul I | 53 |
| 5321 | Datorii faţă de titularii de avans | gradul II | 532 |
| 5322 | Datorii faţă de personal privind alte operaţii | gradul II | 532 |
| 533 | Datorii privind asigurările sociale şi medicale | gradul I | 53 |
| 5331 | Datorii faţă de bugetul asigurărilor sociale de stat | gradul II | 533 |
| 5332 | Datorii faţă de fondurile asigurării obligatorii de asistenţă medicală | gradul II | 533 |
| 5333 | Alte datorii privind asigurările sociale şi medicale | gradul II | 533 |
| 534 | Datorii faţă de buget | gradul I | 53 |
| 5341 | Datorii privind impozitul pe venit din activitatea de întreprinzător şi profesională | gradul II | 534 |
| 5342 | Datorii privind impozitul pe venit din salariu | gradul II | 534 |
| 5343 | Datorii privind impozitul pe venit reţinut la sursa de plată | gradul II | 534 |
| 5344 | Datorii privind taxa pe valoarea adăugată | gradul II | 534 |
| 5345 | Datorii privind accizele | gradul II | 534 |
| 5346 | Datorii privind alte impozite şi taxe | gradul II | 534 |
| 5347 | Datorii privind sancţiunile | gradul II | 534 |
| 5348 | Alte datorii faţă de buget | gradul II | 534 |
| 535 | Venituri anticipate curente | gradul I | 53 |
| 5351 | Subvenţii | gradul II | 535 |
| 5352 | Valoarea activelor circulante intrate cu titlu gratuit | gradul II | 535 |
| 5353 | Alte venituri anticipate curente | gradul II | 535 |
| 536 | Datorii faţă de proprietari | gradul I | 53 |
| 5361 | Datorii privind dividendele calculate | gradul II | 536 |
| 5362 | Datorii privind alte operaţiuni | gradul II | 536 |
| 537 | Finanţări şi încasări cu destinaţie specială curente | gradul I | 53 |
| 538 | Provizioane curente | gradul I | 53 |
| 5381 | Provizioane pentru beneficiile angajaţilor | gradul II | 538 |
| 5382 | Provizioane pentru garanţii acordate cumpărătorilor/clienţilor | gradul II | 538 |
| 5383 | Provizioane pentru impozite | gradul II | 538 |
| 5384 | Alte provizioane | gradul II | 538 |
| 54 | ALTE DATORII CURENTE | grupa | 5 |
| 541 | Datorii preliminate | gradul I | 54 |
| 5411 | Datorii preliminate privind decontările cu bugetul | gradul II | 541 |
| 5412 | Datorii preliminate privind primele de asigurare obligatorie de asistenţă medicală | gradul II | 541 |
| 5413 | Alte datorii preliminate | gradul II | 541 |
| 542 | Datorii privind asigurarea bunurilor şi a persoanelor | gradul I | 54 |
| 543 | Datorii curente privind bunurile primite în gestiune economică | gradul I | 54 |
| 544 | Alte datorii curente | gradul I | 54 |
| 5441 | Datorii privind sancţiunile comerciale | gradul II | 544 |
| 5442 | Datorii aferente mijloacelor nepredestinate în organizaţiile necomerciale | gradul II | 544 |
| 5443 | Alte datorii calculate curente | gradul II | 544 |
| 6 | VENITURI | clasa | — |
| 61 | VENITURI DIN ACTIVITATEA OPERAŢIONALĂ | grupa | 6 |
| 611 | Venituri din vînzări | gradul I | 61 |
| 6111 | Venituri din vînzarea produselor | gradul II | 611 |
| 6112 | Venituri din vînzarea mărfurilor | gradul II | 611 |
| 6113 | Venituri din prestarea serviciilor | gradul II | 611 |
| 6114 | Venituri din executarea lucrărilor | gradul II | 611 |
| 6115 | Venituri din contracte de construcţie | gradul II | 611 |
| 6116 | Venituri din contracte de leasing operaţional şi financiar (arendă, locaţiune) | gradul II | 611 |
| 6117 | Venituri din contracte de microfinanţare | gradul II | 611 |
| 6118 | Alte venituri din vînzări | gradul II | 611 |
| 612 | Alte venituri din activitatea operaţională | gradul I | 61 |
| 6121 | Venituri din ieşirea altor active circulante | gradul II | 612 |
| 6122 | Venituri din sancţiuni | gradul II | 612 |
| 6123 | Venituri din recuperarea prejudiciului material | gradul II | 612 |
| 6124 | Venituri din plusurile de active imobilizate şi circulante constatate la inventariere | gradul II | 612 |
| 6125 | Venituri din decontarea datoriilor cu termen de prescripţie expirat | gradul II | 612 |
| 6126 | Venituri din ajustările privind deprecierea activelor circulante | gradul II | 612 |
| 6127 | Venituri aferente diferenţelor favorabile dintre cursul oficial al BNM şi cursul de cumpărare-vînzare a valutei străine | gradul II | 612 |
| 6128 | Alte venituri operaţionale | gradul II | 612 |
| 613 | Venituri din dobînzile aferente împrumuturilor acordate | gradul I | 61 |
| 6131 | Venituri din dobînzile aferente împrumuturilor pe termen lung acordate | gradul II | 613 |
| 6132 | Venituri din dobînzile aferente împrumuturilor pe termen scurt acordate | gradul II | 613 |
| 616 | Venituri aferente mijloacelor cu destinaţie specială | gradul I | 61 |
| 617 | Alte venituri (cu excepţia veniturilor din activitatea economică) | gradul I | 61 |
| 618 | Venituri din activitatea economică | gradul I | 61 |
| 62 | VENITURI DIN ALTE ACTIVITĂŢI | grupa | 6 |
| 621 | Venituri din operaţiuni cu active imobilizate | gradul I | 62 |
| 6211 | Venituri din ieşirea imobilizărilor necorporale | gradul II | 621 |
| 6212 | Venituri din ieşirea imobilizărilor corporale | gradul II | 621 |
| 6213 | Venituri din ieşirea investiţiilor imobiliare | gradul II | 621 |
| 6214 | Venituri din ieşirea altor active imobilizate | gradul II | 621 |
| 6215 | Venituri din reluarea pierderilor din deprecierea activelor imobilizate | gradul II | 621 |
| 6216 | Venituri din decontarea fondului comercial negativ | gradul II | 621 |
| 6217 | Alte venituri din operaţiuni cu active imobilizate | gradul II | 621 |
| 622 | Venituri financiare | gradul I | 62 |
| 6221 | Venituri din interese de participare | gradul II | 622 |
| 6222 | Venituri din dobînzi | gradul II | 622 |
| 6223 | Venituri din alte investiţii financiare pe termen lung | gradul II | 622 |
| 6224 | Venituri aferente ajustărilor de valoare privind investiţiile financiare pe termen lung şi curente | gradul II | 622 |
| 6225 | Venituri din ieşirea investiţiilor financiare | gradul II | 622 |
| 6226 | Venituri din diferenţe de curs valutar | gradul II | 622 |
| 6227 | Venituri din diferenţe de sumă | gradul II | 622 |
| 6228 | Alte venituri financiare | gradul II | 622 |
| 623 | Venituri excepţionale | gradul I | 62 |
| 6231 | Venituri din compensarea pierderilor din calamităţi | gradul II | 623 |
| 6232 | Venituri din compensarea pierderilor din alte evenimente excepţionale | gradul II | 623 |
| 6233 | Alte venituri excepţionale | gradul II | 623 |
| 7 | CHELTUIELI | clasa | — |
| 71 | CHELTUIELI ALE ACTIVITĂŢII OPERAŢIONALE | grupa | 7 |
| 711 | Costul vînzărilor | gradul I | 71 |
| 7111 | Valoarea contabilă a produselor vîndute | gradul II | 711 |
| 7112 | Valoarea contabilă a mărfurilor vîndute | gradul II | 711 |
| 7113 | Costul serviciilor prestate | gradul II | 711 |
| 7114 | Costul lucrărilor executate terţilor | gradul II | 711 |
| 7115 | Costuri aferente contractelor de construcţie | gradul II | 711 |
| 7116 | Costuri aferente contractelor de leasing operaţional şi financiar (arendă, locaţiune) | gradul II | 711 |
| 7117 | Costuri aferente contractelor de microfinanţare | gradul II | 711 |
| 7118 | Alte costuri aferente veniturilor din vînzări | gradul II | 711 |
| 712 | Cheltuieli de distribuire | gradul I | 71 |
| 7121 | Cheltuieli cu personalul comercial | gradul II | 712 |
| 7122 | Cheltuieli privind amortizarea, întreţinerea şi reparaţia activelor imobilizate cu destinaţie comercială | gradul II | 712 |
| 7123 | Cheltuieli cu ambalajele şi alte materiale utilizate la comercializarea produselor şi mărfurilor | gradul II | 712 |
| 7124 | Cheltuieli de transportare a produselor şi mărfurilor | gradul II | 712 |
| 7125 | Cheltuieli de publicitate şi marketing | gradul II | 712 |
| 7126 | Cheltuieli privind reparaţiile şi deservirea produselor şi mărfurilor în perioada de garanţie | gradul II | 712 |
| 7127 | Cheltuieli privind creanţele comerciale compromise | gradul II | 712 |
| 7128 | Cheltuieli privind returnările şi reducerile | gradul II | 712 |
| 7129 | Alte cheltuieli de distribuire | gradul II | 712 |
| 713 | Cheltuieli administrative | gradul I | 71 |
| 7131 | Cheltuieli cu personalul administrativ | gradul II | 713 |
| 7132 | Cheltuieli privind amortizarea, întreţinerea şi reparaţia activelor imobilizate cu destinaţie administrativă | gradul II | 713 |
| 7133 | Cheltuieli cu impozitele şi taxele, cu excepţia impozitului pe venit | gradul II | 713 |
| 7134 | Cheltuieli în scopuri de filantropie şi sponsorizare | gradul II | 713 |
| 7135 | Cheltuieli privind serviciile cu destinaţie administrativă | gradul II | 713 |
| 7136 | Cheltuieli de protocol (reprezentanţă) | gradul II | 713 |
| 7137 | Cheltuieli privind delegarea personalului administrativ | gradul II | 713 |
| 7138 | Alte cheltuieli administrative | gradul II | 713 |
| 714 | Alte cheltuieli din activitatea operaţională | gradul I | 71 |
| 7141 | Valoarea contabilă şi cheltuielile aferente altor active circulante ieşite | gradul II | 714 |
| 7142 | Cheltuieli privind sancţiunile | gradul II | 714 |
| 7144 | Cheltuieli privind lipsurile şi pierderile din deteriorarea activelor imobilizate şi circulante | gradul II | 714 |
| 7145 | Cheltuieli privind creanţele compromise decontate, cu excepţia celor comerciale | gradul II | 714 |
| 7146 | Cheltuieli aferente ajustărilor privind deprecierea activelor circulante | gradul II | 714 |
| 7147 | Cheltuieli aferente diferenţelor nefavorabile dintre cursul oficial al BNM şi cursul de cumpărare-vînzare a valutei străine | gradul II | 714 |
| 7148 | Alte cheltuieli operaţionale | gradul II | 714 |
| 715 | Cheltuieli aferente dobînzilor calculate | gradul I | 71 |
| 7151 | Cheltuieli aferente dobînzilor calculate la depunerile de economii ale membrilor asociaţiilor de economii şi împrumut | gradul II | 715 |
| 7152 | Cheltuieli aferente dobînzilor calculate la împrumuturile/creditele primite | gradul II | 715 |
| 716 | Cheltuieli aferente mijloacelor cu destinaţie specială | gradul I | 71 |
| 717 | Alte cheltuieli (cu excepţia cheltuielilor din activitatea economică) | gradul I | 71 |
| 718 | Cheltuieli din activitatea economică | gradul I | 71 |
| 72 | CHELTUIELI ALE ALTOR ACTIVITĂŢI | grupa | 7 |
| 721 | Cheltuieli cu active imobilizate | gradul I | 72 |
| 7211 | Valoarea contabilă şi cheltuielile aferente imobilizărilor necorporale ieşite | gradul II | 721 |
| 7212 | Valoarea contabilă şi cheltuielile aferente imobilizărilor corporale ieşite | gradul II | 721 |
| 7213 | Valoarea contabilă şi cheltuielile aferente investiţiilor imobiliare ieşite | gradul II | 721 |
| 7214 | Valoarea contabilă şi cheltuielile aferente altor active imobilizate ieşite | gradul II | 721 |
| 7215 | Pierderi din deprecierea activelor imobilizate | gradul II | 721 |
| 7216 | Pierderi din decontarea fondului comercial pozitiv | gradul II | 721 |
| 7217 | Cheltuieli privind provizioanele aferente activelor imobilizate | gradul II | 721 |
| 7218 | Alte cheltuieli cu active imobilizate | gradul II | 721 |
| 722 | Cheltuieli financiare | gradul I | 72 |
| 7221 | Cheltuieli privind dobînzile | gradul II | 722 |
| 7222 | Cheltuieli aferente ajustărilor de valoare privind investiţiile financiare pe termen lung şi curente | gradul II | 722 |
| 7223 | Cheltuieli aferente ieşirii investiţiilor financiare | gradul II | 722 |
| 7224 | Cheltuieli din diferenţe de curs valutar | gradul II | 722 |
| 7225 | Cheltuieli din diferenţe de sumă | gradul II | 722 |
| 7226 | Alte cheltuieli financiare | gradul II | 722 |
| 723 | Cheltuieli excepţionale | gradul I | 72 |
| 7231 | Cheltuieli privind calamităţile | gradul II | 723 |
| 7232 | Cheltuieli privind alte evenimente excepţionale | gradul II | 723 |
| 7233 | Alte cheltuieli excepţionale | gradul II | 723 |
| 73 | CHELTUIELI PRIVIND IMPOZITUL PE VENIT | grupa | 7 |
| 731 | Cheltuieli privind impozitul pe venit | gradul I | 73 |
| 8 | CONTURI DE GESTIUNE | clasa | — |
| 81 | CONTURI DE CALCULAŢIE | grupa | 8 |
| 811 | Activităţi de bază | gradul I | 81 |
| 812 | Activităţi auxiliare | gradul I | 81 |
| 82 | CONTURI DE REPARTIZARE | grupa | 8 |
| 821 | Costuri indirecte de producţie | gradul I | 82 |
| 822 | Costuri indirecte aferente contractelor de construcţie | gradul I | 82 |
| 823 | Costuri de regie aferente contractelor de construcţie | gradul I | 82 |
| 824 | Alte costuri repartizabile | gradul I | 82 |
| 83 | ALTE CONTURI DE GESTIUNE | grupa | 8 |
| 831 | Adaos comercial | gradul I | 83 |
| 832 | Încasări din vînzarea bunurilor în numerar | gradul I | 83 |
| 833 | Returnarea şi reducerea preţurilor la bunurile vîndute | gradul I | 83 |
| 834 | Costuri aferente bunurilor transmise spre prelucrare terţilor | gradul I | 83 |
| 835 | Producţii şi unităţi de deservire | gradul I | 83 |
| 836 | Costuri refacturate | gradul I | 83 |
| 9 | CONTURI EXTRABILANŢIERE | clasa | — |
| 911 | Imobilizări corporale primite în leasing (arendă, locaţiune) operaţional | gradul I | 9 |
| 912 | Bunuri primite pentru montare | gradul I | 9 |
| 913 | Imobilizări corporale transmise în leasing financiar | gradul I | 9 |
| 914 | Bunuri primite în custodie | gradul I | 9 |
| 915 | Bunuri primite spre prelucrare sau reparare | gradul I | 9 |
| 916 | Bunuri primite în baza contractelor de comision | gradul I | 9 |
| 917 | Bunuri obţinute din materialele prelucrate ale terţilor | gradul I | 9 |
| 918 | Formulare cu regim special | gradul I | 9 |
| 919 | Creanţe compromise decontate | gradul I | 9 |
| 920 | Creanţe contingente | gradul I | 9 |
| 921 | Datorii contingente | gradul I | 9 |
| 922 | Garanţii acordate | gradul I | 9 |
| 923 | Garanţii primite | gradul I | 9 |
| 924 | Pierderi fiscale | gradul I | 9 |
| 925 | Facilităţi fiscale | gradul I | 9 |
---

## 7. Ce nu s-a putut verifica

**Pagini necitite: niciuna.** Toate cele 63 de pagini au fost extrase. Nu s-a folosit alt izvor decât
PDF-ul de la `mf.gov.md`. Nu apare niciun cod de patru cifre în clasa 4 şi niciun cont de tip
4426/4427, deci nu s-a produs contaminarea cu planul de conturi din România (OMFP 1802/2014).

### 7.1 Coduri nealocate — goluri reale în act

| gol | situaţie |
|---|---|
| **312** | Abrogat. `[Contul 312 abrogat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020]`, plus nota generală de excludere din capitolul III. |
| **413** | Abrogat. `[Contul 413 abrogat prin Ordinul Min.Fin. nr.100 din 28.06.2019, în vigoare 01.01.2020]` |
| **614, 615** | **Nealocate, fără nicio explicaţie în act.** Grupa 61 sare de la 613 direct la 616. Şirurile „614" şi „615" nu apar nicăieri în cele 63 de pagini. |
| **7143** | **Nealocat, fără nicio explicaţie în act.** Contul 714 are 7141, 7142, apoi 7144. Şirul „7143" nu apare nicăieri în document. |

Pentru 614, 615 şi 7143 nu există notă de abrogare, spre deosebire de 312 şi 413. Nu se poate spune
dacă au fost vreodată alocate; actul consolidat pur şi simplu nu le conţine. Golurile se raportează
ca atare — niciun cod nu a fost dedus sau completat.

### 7.2 Denumiri care diferă între capitole

S-a comparat automat fiecare clasă, grupă şi cont de gradul I din capitolul II cu toate formele din
capitolul III. Cinci divergenţe:

| cod | Cap. II | Cap. III | observaţie |
|---|---|---|---|
| **920** | Creanţe contingente | **ambele forme** | Caz special — vezi mai jos. |
| **12** | IMOBILIZĂRI CORPORALE, TERENURI, MIJLOACE FIXE ŞI RESURSE MINERALE | IMOBILIZĂRI CORPORALE | Cap. III păstrează denumirea anterioară redacţiei 2019. |
| **31** | CAPITAL SOCIAL, NEÎNREGISTRAT ŞI PRIME DE CAPITAL | CAPITAL SOCIAL ŞI SUPLIMENTAR | Idem — denumire anterioară redacţiei 2019. |
| **112** | Imobilizări necorporale în exploatare | Imobilizări necorporale | |
| **132** | Active biologice imobilizate în exploatare | Active biologice imobilizate | |

**Contul 920 este un caz diferit de cel presupus.** Divergenţa nu este între capitole, ci **în
interiorul capitolului III**:

- Capitolul II (p. 11): `920 Creanţe contingente`
- Capitolul III, **titlul secţiunii**: `Contul 920 “Creanţe contingente”` — identic cu capitolul II
- Capitolul III, **textul narativ**, toate cele trei ocurenţe: `Contul 920 “Active contingente”`

Aşadar „Active contingente" apare exclusiv în corpul descrierii, iar titlul secţiunii concordă cu
nomenclatorul. Contul 920 este singurul cod din tot actul care are două forme de denumire în
capitolul III.

### 7.3 Anomalie de transcriere — contul 1239

**Contul 1239 apare tipărit „Alte mijloace fix"**, fără „e" final, la pagina 4. S-a verificat cu trei
moduri de extracţie independente (`-layout`, implicit, `-raw`) — toate returnează identic „fix".
Nu este artefact de extracţie, ci **eroare materială în actul publicat**. A fost transcrisă ca atare.

Nu există formă de control în capitolul III: acolo nu se descriu conturi de gradul II. Contrastul
intern este însă vizibil — contul rectificativ pereche, 1249, este scris corect
„Amortizarea altor mijloace fixe".

### 7.4 Artefacte de aspect rezolvate

- Linia grupei 52 apare în PDF ca `52 521  DATORII COMERCIALE CURENTE` — două coloane fuzionate la
  extracţie. A fost despărţită în grupa **52 „DATORII COMERCIALE CURENTE"** şi contul
  **521 „Datorii comerciale curente"**, confirmat de titlul din capitolul III:
  `GRUPA 52 “DATORII COMERCIALE CURENTE”`.
- Denumirile care se întind pe mai multe rânduri în PDF au fost reunite cu un singur spaţiu.
  Verificate manual pe cazurile lungi: 414, 4142, 513, 5132, 231, 6127, 7147, 7151.

### 7.5 Verificări de integritate trecute

- Toţi cei 517 părinţi se rezolvă la un cod existent în tabel; niciun orfan.
- Cele 32 de grupe din capitolul II corespund exact celor 32 de titluri `GRUPA` din capitolul III.
- Fiecare clasă, grupă şi cont de gradul I din capitolul II are titlu corespondent în capitolul III;
  invers, niciun cod din capitolul III nu lipseşte din capitolul II.
- Cele 320 de conturi de gradul II nu au corespondent în capitolul III, conform capitolului I:
  „În capitolul III sînt caracterizate clasele, grupele de conturi şi conturile de gradul I".

---

Această consemnare deblochează OD-23: ADR-039 §10.2 cere ca niciun număr de cont să nu intre în
repository fără trimitere la Planul general de conturi şi la ordinul care îl aprobă.
