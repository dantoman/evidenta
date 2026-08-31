# ADR-084 — Rolul scris la provizionare e de nivel companie, altfel nicio cheie de companie nu se poate ține

- **Stare:** Acceptat — proprietar, **pe recomandarea sesiunii**
- **Data:** 2026-08-31
- **Decis de:** proprietar, prin instrucțiunea *„începe una după alta"* peste cele două variante
  propuse; varianta (a) e cea recomandată de două ori și necontestată. *Dacă intenția era (b) —
  un rol de nivel tenant acoperă implicit toate companiile —, acest ADR se înlocuiește; e o schimbare
  diferită, nu o corecție a acesteia.*
- **Închide:** `OD-124`
- **Atinge:** `infra/migrations/0072_provision_company_role`, `tenancy/0011`,
  `identity.services.roles.realign_company_access`, comanda `repair_company_access`
- **Legate:** [ADR-020](020-roluri-ca-date.md), [ADR-040](040-crearea-tenantului-si-a-companiei.md),
  [ADR-083](083-editarea-companiei.md)

## 1. Ce era, măsurat

`rls.provision_company` (`0045`) scria în `company_access.role_id` rolul pe care creatorul îl are din
`membership` — adică un rol de **nivel tenant**. Dar `role_permission` leagă scopul unei permisiuni de
nivelul rolului, prin cheia străină compusă. Deci pe un rând de acces cu rol de tenant nu se poate ține
**nicio** cheie de nivel companie.

Măsurat pe baza de dezvoltare la 2026-08-31: toate cele patru rânduri vii purtau `owner` — nivel tenant,
șapte permisiuni, niciuna de companie.

Consecința nu era doar a lui ADR-083. **`company.revoke_access` e în catalog de la F0.3.3 și n-a putut
fi ținută de nimeni, niciodată.** Nimic n-a semnalat, fiindcă fixture-urile scriu `company_admin` —
forma pe care `CompanyAccess` o documentează — deci fiecare test era de acord cu modelul și în
dezacord cu producția.

## 2. De ce nu e escaladare, care e obiecția scrisă în `0045`

Fișierul corectat spune, și principiul rămâne valabil: *„o funcție privilegiată care și-ar alege rolul
ar fi o cale de escaladare, nu o cale de provizionare."*

Aici funcția **nu alege**. Caută rolul de sistem de nivel companie pe care platforma îl creează ea
însăși odată cu tenantul (`create_system_roles`), și care e singurul rol de nivel companie pe care
produsul îl garantează. Interogarea are un singur rezultat posibil. Diferența față de „și-ar alege
rolul" e diferența dintre o căutare determinată și o decizie luată de codul privilegiat.

Ce **nu** s-a schimbat: apartenența rămâne condiție. O firmă cu engagement trece de `has_tenant_access`
și n-are `membership` în tenantul clientului, deci nu creează companii acolo — comportamentul lui
`0045`, păstrat.

## 3. Dacă rolul lipsește, refuză

Un tenant fără `company_admin` e un tenant cu provizionarea întreruptă — starea măsurată pe `alpha`
înainte să existe `repair_system_roles`. Funcția refuză, cu mesaj care numește comanda de reparare.

A cădea înapoi pe rolul de membership ar restaura defectul **tăcut și numai la tenanții stricați**,
adică exact acolo unde nimeni nu se uită. Starea nu se poate atinge nici măcar ștergând rolul: un rol
de sistem refuză ștergerea, prin trigger. Se atinge doar nefiind creat niciodată, care e și felul în
care cei reali au ajuns acolo — și așa e construit testul.

## 4. Rândurile existente: comandă de operator, nu migrare

`0072` corectează ce se scrie de acum înainte. Rândurile deja scrise se repară cu
`repair_company_access`, nu dintr-o migrare: a rescrie accesul cuiva dintr-o migrare, sub un rol care
nu poate vedea rândurile pe care le rescrie, e chiar eșecul pe care `OD-94` există să-l facă zgomotos.
Un operator o rulează, vede ce s-a mutat, și poate compara cu ce se aștepta.

**Numai rândurile `granted_via = 'membership'`, și restrângerea e deliberată.** Rândurile de engagement
poartă ce purta prima acordare către firmă; a le muta pe `company_admin` ar da unui utilizator al
firmei `company.close` asupra companiei clientului — o lărgire pe care nimeni n-a decis-o. Cine sunt
oamenii firmei pe registrele clientului e `OD-42`, încă deschisă.

## 5. Consecințe

- **Devine posibil:** `company.edit`, `company.close` și `company.revoke_access` pot fi ținute de cine
  a creat compania — prima oară de când există prima dintre ele.
- **Devine imposibil:** un rând de acces de companie cu rol de nivel tenant, scris de produs.
- **Rămâne cum era:** o firmă nu creează companii în tenantul clientului; rândurile de engagement nu
  se ating.
- **Ce se verifică automat:**
  1. provizionarea scrie un rol de **nivel** companie — nivelul, nu cheia, fiindcă un al doilea rol de
     sistem sub alt nume ar satisface la fel mecanismul permisiunilor;
  2. creatorul ține efectiv `company.edit` după provizionare;
  3. un tenant fără `company_admin` primește refuz, nu o cădere înapoi;
  4. un rol de nivel tenant pe un rând de acces **tot** nu ține nicio cheie de companie — mecanismul pe
     care se sprijină corecția, ținut sub test separat.

## Surse

- `infra/migrations/0045_provision_company.up.sql` (fișierul corectat, păstrat prin `C31`),
  `0032_engagement_provisioning.up.sql` (propagarea care copiază rolul).
- [ADR-020](020-roluri-ca-date.md) *(rolurile ca date, nivelurile)*, [ADR-083](083-editarea-companiei.md) §2.2.
- Măsurat la 2026-08-31: patru rânduri vii cu `owner`; după reparare, patru cu `company_admin`.
- `CLAUDE.md` `C31`, `R5`, `T1`; `OD-94`, `OD-42`.
