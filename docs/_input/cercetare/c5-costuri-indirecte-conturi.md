# `C5` — Conturile repartizării: normele Planului general de conturi pentru 811, 821 și 714

- **Data cercetării:** 2026-08-30
- **Pentru:** ADR-058 (handlerul C5); completează [`c1-c3-c5-stocuri.md`](c1-c3-c5-stocuri.md),
  care avea formula (pct. 29–31) și nu avea conturile
- **Sursa primară:** PDF-ul consolidat al Ministerului Finanțelor,
  <https://mf.gov.md/sites/default/files/legislatie/Planul%20general%20de%20conturi%20contabile.pdf>
  (63 pagini; preluat 2026-08-30, extras ca text). Aceeași copie ca la `od-22-planul-de-conturi.md`.

---

## Clasa 8, capitolul III

> Conturile din clasa 8 „Conturi de gestiune" sînt destinate generalizării informaţiei privind
> costurile de producţie, adaosul comercial, încasările din vînzarea bunurilor în numerar, costurile
> refacturate etc. care cuprind: conturi de calculaţie, conturi de repartizare şi alte conturi de
> gestiune. **La data raportării conturile de gestiune se închid cu conturile de bilanţ şi/sau de
> rezultate.**

Grupa 81, notă de trimitere: *„Componenţa, modul de contabilizare a costurilor de producţie şi de
calculaţie a costului […] sînt reglementate de Indicaţiile metodice privind contabilitatea costurilor
de producţie şi calculaţia costului produselor şi serviciilor, SNC «Contracte de construcţie»,
«Cheltuieli», «Stocuri» şi alte standarde."* — Indicațiile metodice **nu au fost citite**.

## Contul 821 „Costuri indirecte de producţie"

> Contul 821 […] este un cont de activ (colectare – repartizare). În debitul acestui cont se
> înregistrează majorarea costurilor indirecte de producţie în corespondenţă cu creditul conturilor:
> 113, 124, 133, 211, 213, 214, 226, 261, 521, 522, 531, 532, 533, 538, 544 etc.
>
> În creditul contului 821 „Costuri indirecte de producţie" se înregistrează **repartizarea**
> costurilor indirecte de producţie în corespondenţă cu debitul conturilor: **714, 811, 812** etc.

## Contul 811 „Activităţi de bază"

> Contul 811 […] este un cont de activ (calculaţie). În debitul acestui cont se înregistrează soldul
> iniţial al producţiei în curs de execuţie şi costurile directe şi indirecte de producţie în
> corespondenţă cu creditul conturilor: 113, 124, 126, 133, 211, 212, 213, 214, 215, 216, 217, 226,
> 521, 522, 531, 532, 533, 538, 812, **821** etc.
>
> În creditul contului 811 […] se înregistrează costul efectiv al produselor fabricate/serviciilor
> prestate, rebutului definitiv, deşeurilor recuperabile, precum şi soldul final al producţiei în
> curs de execuţie în corespondenţă cu debitul conturilor: 212, 215, 216, 711, 714, 723 etc.

## Contul 714 „Alte cheltuieli din activitatea operaţională"

> […] destinat generalizării informaţiei privind cheltuielile legate de desfăşurarea activităţii
> operaţionale care nu pot fi atribuite la costul vînzărilor, cheltuielile de distribuire sau
> cheltuielile administrative. În debitul contului 714 […] se înregistrează recunoaşterea altor
> cheltuieli ale activităţii operaţionale pe parcursul perioadei de gestiune în corespondenţă cu
> creditul conturilor: […] 538, 542, 543, 544, **811, 812** etc.

## Ce decurge, și ce nu

- Partea **repartizată** a costurilor indirecte: `Dt 811 / Ct 821` — ambele norme o listează.
- Partea **nerepartizată** a costurilor constante (pct. 30(2), „cheltuieli curente"): `Dt 714 / Ct
  821` — 714 e în lista creditului lui 821, iar 714 e contul cheltuielilor operaţionale care nu pot fi
  atribuite costului vînzărilor, distribuirii sau administrării. **Subcontul** nu îl numește niciun
  text citit: 714 are 7141–7148, iar 7148 „Alte cheltuieli operaţionale" e cel plauzibil — plauzibil
  nu e citat. Rolul `COSTURI_INDIRECTE_NEREPARTIZATE` se leagă implicit la **714** (gradul I, cum
  spune norma); compania îl poate lega la subcontul ei (stratul 2).
- Listele sînt explicit **neexhaustive** („etc.", și capitolul I: *principalele* conturi
  corespondente) — `od-22-planul-de-conturi.md` §2, rafinarea 2. Nimic de aici nu se tratează ca
  mulțime închisă.
