# ADR-025 — Subdomeniul tenantului în dezvoltare locală: `*.evidenta.localhost`

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `OD-20`
- **Afectează:** `TENANT_BASE_DOMAIN`, mediul de dezvoltare, F0.10

## Context

Contextul de tenant vine exclusiv din subdomeniu (`C8`, Spec A §3.2). Regula nu are excepție pentru
dezvoltare — dacă ar avea, calea exercitată local ar fi alta decât cea care rulează în producție,
iar diferența s-ar descoperi la prima punere în staging.

Consecința practică e neplăcută exact acolo unde nu ne așteptam: `http://localhost:8000/` nu poate
servi nimic. Nu are subdomeniu, deci nu are tenant, deci nu are context. Nu este un defect de
configurare, este regula aplicată.

`OD-20` cerea felul în care un dezvoltator ajunge totuși la un tenant pe mașina lui.

## Opțiuni evaluate

**A. `*.evidenta.localhost`.** Chrome și Firefox rezolvă orice etichetă `*.localhost` la loopback
fără nicio intrare în `hosts` (RFC 6761 tratează `localhost` ca nume special). *Avantaje:* un tenant
nou nu costă nimic — `http://alpha.evidenta.localhost:8000/` funcționează imediat, la fel și în CI.
*Dezavantaje:* Safari și o parte din clienții HTTP de linie de comandă nu aplică regula și cer
totuși o linie în `hosts`. *Cost de schimbare:* mic — o variabilă de mediu.

**B. `hosts` per tenant, pe un domeniu propriu (`evidenta.local`).** *Avantaje:* funcționează în
orice browser și orice client. *Dezavantaje:* fiecare tenant de dezvoltare este o editare cu drept
de root, iar uitarea ei arată exact ca un tenant inexistent — 404, adică fix răspunsul pe care
`IZ-37` îl cere să fie indistinct. Cel mai prost mod de a pierde o oră. *Cost de schimbare:* mic.

**C. DNS wildcard local (dnsmasq).** *Avantaje:* fără configurare per tenant, funcționează peste
tot. *Dezavantaje:* infrastructură per mașină, pe care fiecare dezvoltator o instalează și pe care
CI o reproduce. *Cost de schimbare:* mediu.

## Decizie

**Opțiunea A.** `TENANT_BASE_DOMAIN` implicit `evidenta.localhost` în `config/settings/dev.py`;
obligatoriu din mediu în staging și producție, fără valoare implicită.

Pentru clienții care nu rezolvă `*.localhost` singuri, soluția de rezervă este o linie în `hosts` —
adică opțiunea B, disponibilă punctual fără să fie regula.

## Consecințe

- `http://localhost:8000/` răspunde **404**, cu cod `tenant.not_found`, și așa rămâne. Nu este o
  eroare de configurare; este singurul răspuns corect pentru o gazdă fără tenant.
- Cookie-ul de sesiune este **host-only** (fără atribut `Domain`), deci nu se scurge de la un
  subdomeniu la altul. `evidenta.localhost` fiind un domeniu de sine stătător pentru browser,
  proprietatea se verifică local exact ca în producție.
- Valoarea nu are implicit în `base.py`. Un implicit ar fi greșit în orice mediu în afară de cel
  pentru care a fost scris, iar „greșit" aici înseamnă cereri atribuite altui tenant sau niciunuia.
