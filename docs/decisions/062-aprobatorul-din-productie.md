# ADR-062 — Aprobatorul din producție e o persoană, nu un nivel de rol

- **Status:** **Acceptat** — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** `OD-71` — **jumătatea „cine semnează"**. Jumătatea „nivel de rol de platformă" rămâne
  la `DN-18`, deliberat (§2)
- **Afectează:** `fiscal/parameters` (`activate_fiscal_parameters`), `fiscal/registry`
  (`activate_version`), `privileged_access_log` calea `P-4`; `F2.C4`, `F2.P2`, bifa `active` din
  `F2.X1`
- **Legate:** [ADR-021](021-mfa-obligatoriu.md), [ADR-049](049-rolul-de-date-de-referinta.md) §7,
  Spec A §3.4, §6.2

## 1. Context

Fiecare activare de parametru fiscal și de versiune de logică poartă un aprobator: pe rând
(`approved_by_user_id`) și pe rândul `P-4` din `privileged_access_log`. Pe baza de dezvoltare
identitatea e `dev@example.md`, contul creat de `make create-tenant`. În producție, `P-4` va purta
identități care contează — cine a aprobat o cotă — iar azi ar semna un cont de probă.

## 2. Întrebarea se desparte de două ori, și a doua despărțire e cea care contează

Rândul din registru lipește **cine semnează** cu **cum apar utilizatorii de sistem pentru rulările
automate**. Prima despărțire e deja făcută în `09-f2-backlog.md`: utilizatorii de sistem (`system:bnm`,
`system:efactura`, `system:billing`) sunt **specificați** în Spec A §3.4 — `is_active = false`, e-mail
nefolosibil, fără `membership`, deci fără acces pe calea normală. Se construiesc după spec, în
`F2.P2`, fără nicio decizie.

**A doua despărțire, făcută aici:** sesiunea recomandase inițial ca `OD-71` să se decidă *împreună*
cu `DN-18` (accesul de suport al platformei), ca „identitățile personalului platformei".
**Recomandarea a fost retrasă de sesiune și retragerea acceptată de proprietar**, din motivul care se
verifică, nu se argumentează: **raze de acțiune diferite.**

- Aprobatorul atinge **exclusiv tabele globale** — `fiscal_parameter`, `fiscal_logic_version`,
  `privileged_access_log`. Nu atinge RLS. Nu atinge `R27`.
- `DN-18` atinge **datele unui tenant**. Atinge RLS și `R27`.

Precedentul citat: `OD-22` a blocat două sarcini luni de zile fiindcă lipea un parametru fiscal de o
structură de plan de conturi, și s-a deblocat abia când [ADR-050](050-lantul-de-inchidere-ca-roluri.md)
le-a despărțit.

## 3. Opțiuni evaluate

1. **A — o persoană reală: un `user` cu MFA ([ADR-021](021-mfa-obligatoriu.md)), fără `membership`,
   fără nivel nou de rol.** Semnătura e **identitate**, nu permisiune; cine poate rula comanda rămâne
   o chestiune de acces la producție. *Avantaje:* zero schemă. **Măsurat la 2026-08-30:**
   `approved_by_user_id` e `UUIDField(null=True)` în `fiscal/parameters/models.py` și în
   `fiscal/registry/models.py` — **fără cheie străină** —, iar `activate_fiscal_parameters` parsează
   `--approver` ca UUID și **nu verifică** existența vreunui rând `user`. Deci schimbarea identității
   costă o valoare de flag. *Dezavantaje:* nimic din model nu impune că doar persoana aceea aprobă;
   garanția e operațională. *Cost de schimbare:* nul.
2. **B — un nivel de rol `platform_operator` în modelul de identitate.** *Avantaje:* permisiunea
   devine impusă și auditabilă în același vocabular ca restul; `DN-18` va avea nevoie de el oricum.
   *Dezavantaje:* deschide schema de identitate pentru o proprietate care azi nu e verificabilă
   oricum. **Măsurat:** `RoleLevel` are exact două valori — `TENANT` și `COMPANY` —, `Permission.scope`
   are CHECK pe ele, iar `Role` aparține unui tenant prin cheie străină. Nu există nivel de platformă;
   adăugarea lui e a treia valoare în enum, relaxarea CHECK-ului și un rol fără tenant.
   *Cost de schimbare:* mare — odată ce nivelul există, rolurile și permisiunile se scriu pe el.

## 4. Decizie

**Opțiunea A, acum.** Aprobările de parametri fiscali și de versiuni de logică în producție se
semnează cu un **`user` real, cu MFA, angajat al platformei, fără `membership`**. Semnătura e
identitate, nu permisiune.

> **Inferență, marcată și acceptată de proprietar (2026-08-30):** că *accesul controlat la producție
> e garanție suficientă în stadiul acesta* e judecata sesiunii, nu un act și nu o măsurătoare. E
> locul unde decizia se poate revizui fără să se fi schimbat nimic în cod.

**B vine cu `DN-18`**, ca decizie separată.

**Termenul se reformulează.** Registrul spunea „înainte de F2". Corect e **înainte de prima activare
în producție**. Motivul e în §5: costul crește cu fiecare rând semnat sub identitate de probă, nu cu
trecerea fazelor. În baza de dezvoltare nimic nu se schimbă — cele 22 de rânduri ale `F2.X1` stau
`draft`.

## 5. Rândurile deja semnate rămân semnate — și nu se „repară"

Trei rânduri sunt deja aprobate cu `dev@example.md`, cele trei convenții de platformă:
`accounting.amount_scale`, `accounting.unit_price_scale` și versiunea de logică
`accounting.money_rounding`.

**Rămân așa, definitiv.** `privileged_access_log` e append-only, cu trigger
([ADR-049](049-rolul-de-date-de-referinta.md), migrarea `0058`) — aceeași disciplină ca ledgerul, din
același motiv. Corecția unei aprobări nu e o editare, e **un eveniment nou de aprobare**.

Consemnat aici explicit **ca nimeni să nu încerce să le repare**: un rând de jurnal rescris ca să
arate mai bine e exact defectul pe care jurnalul există ca să-l facă imposibil. Sunt aprobări făcute
**sub identitate de dezvoltare, într-o bază de dezvoltare, înainte ca identitatea reală să existe** —
și se citesc așa.

## 6. Consecințe

- **Devine posibil:** `F2.C4` (Compliance Admin — fluxul act → impact → implementare → corpus →
  aprobare → activare programată), jumătatea „aprobator" din `F2.P2`, și trecerea în `active` a
  parametrilor în producție.
- **Devine imposibil:** o activare de producție semnată de un cont care nu e o persoană.
- **Rămâne la `DN-18`:** nivelul de rol de platformă și accesul de suport. Nu se strecoară aici.
- **De modificat ca urmare:** `OD-71` trece în „Închise" cu jumătatea închisă numită;
  `09-f2-backlog.md` — `F2.P2`, `F2.C4`, tabelul de blocaje.
- **Nu se verifică automat.** Că aprobatorul e o persoană și nu un cont de serviciu e regulă de
  proces. Ce se verifică e ce se putea verifica deja: `F2.P2` cere `IZ`-uri noi — utilizatorul de
  sistem nu citește nimic pe calea normală, sub rolul aplicației (`T1`).

## 7. Surse

- Spec A §3.4 (utilizatorii de sistem, specificați), §6.2 (căile privilegiate `P-2`, `P-3`, `P-4`).
- [ADR-049](049-rolul-de-date-de-referinta.md) §7 (utilizatorii de sistem, raportați ca inexistenți),
  [ADR-021](021-mfa-obligatoriu.md).
- Măsurat în cod la 2026-08-30: `fiscal/parameters/models.py`, `fiscal/registry/models.py`
  (`approved_by_user_id` fără FK), `fiscal/parameters/management/commands/activate_fiscal_parameters.py`
  (`--approver` neverificat), `platform/identity/models.py` (`RoleLevel` cu două valori, `Role` legat
  de tenant), `infra/schema/append_only.toml` (`privileged_access_log`).
- Instrucțiunea proprietarului, 2026-08-30.
