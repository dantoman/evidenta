# ADR-030 — Atașamentele stau la nivel de companie

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Context:** F0.6.3 — atașamente
- **Închide:** `DN-16` *(nivelul metadatelor)*
- **Nu închide:** coada lui `DN-16` — layout-ul în S3, semnarea URL-urilor, limitele, scanarea
  antivirus, comportamentul la `archived`. Devine `OD-52`.
- **Decis de:** proprietar

## Problema

Spec A §5.2 listează `attachment_metadata` **provizoriu** la nivel tenant. `DN-16` întreabă dacă
rămâne acolo sau coboară la companie.

- **A — nivel tenant.** Același fișier se reutilizează între companiile unui holding, fără
  duplicare.
- **B — nivel companie.** Consecvent cu documentele pe care le însoțesc; izolare mai strictă;
  duplicare la reutilizare.

## Decizia: B

Motivul care decide nu este consecvența, ci **accesul**.

Documentele stau la nivel de companie (§5.3), iar accesul se acordă **per companie**:
`company_access`, cu politica `rls.has_company_access(company_id)`. Un atașament ținut la nivel de
tenant ar avea o graniță de acces **mai largă decât documentul pe care îl însoțește**. Consecința
concretă, nu ipotetică: un contabil căruia i s-a dat acces la o singură companie a unui holding ar
vedea atașamentele celorlalte — exact calea pe care `company_access` există s-o închidă.

Iar atașamentele sunt cazul cel mai prost în care poate apărea scurgerea asta: un PDF de factură
conține tot ce e în document și, de obicei, mai mult — contul bancar al partenerului, condițiile
comerciale, semnături. Nu e o coloană, e o pagină.

## Prețul, acceptat explicit

Același fișier urcat la două companii se stochează de două ori, cu două rânduri de metadate și două
chei de obiect. Este un blob duplicat: ieftin în S3, și fără efect asupra corectitudinii contabile.

Cazul care motiva varianta A — reutilizarea în cadrul unui holding — rămâne posibil prin încărcare
repetată. `checksum_sha256` face duplicarea **vizibilă** (aceeași amprentă, două rânduri), deci
dacă vreodată devine o problemă măsurată, se poate adăuga o deduplicare la nivel de stocare fără să
se atingă granița de acces. Ordinea contează: graniță strictă întâi, optimizare de stocare după,
niciodată invers.

## Cheia de obiect

Se derivă în cod, **niciodată din intrare de utilizator**:

```
{tenant_id}/{company_id}/{yyyy}/{mm}/{attachment_id}
```

Numele original al fișierului se păstrează într-o coloană, ca să poată fi întors la descărcare, dar
nu participă la cheie. Un nume de fișier care ajunge într-o cale este cum se scrie o traversare de
director; iar un `attachment_id` generat de server face cheia neghicibilă, ceea ce contează pentru
orice schemă de semnare a URL-urilor pe care o alegem în `OD-52`.

Prefixul cu `tenant_id` și `company_id` este deliberat **înaintea** deciziei de layout: oricare ar
fi ea — bucket per tenant sau prefix per tenant — izolarea se păstrează, iar o politică de bucket
scrisă mai târziu are pe ce să se sprijine.
