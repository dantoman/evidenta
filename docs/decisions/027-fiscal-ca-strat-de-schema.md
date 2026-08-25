# ADR-027 — `fiscal` intră în lista straturilor de compunere de schemă

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Context:** F0.8 — parametri fiscali și registrul de selecție
- **Modifică:** `infra/modules/dependencies.toml`, secțiunea `[d6]`
- **Depinde de:** [ADR-024](024-gardian-de-dependente.md) (gardianul care impune `D6`)

## Problema

`D6` interzice unui modul să importe modelele altuia. Excepția existentă e îngustă de două ori:
doar un modul `models` poate compune schemă, și doar către straturile enumerate în
`schema_layers`, care astăzi sunt `platform` și `masterdata`.

F0.8 a produs trei tabele: `fiscal_parameter_source`, `fiscal_parameter` (modulul
`fiscal.parameters`) și `fiscal_logic_version` (modulul `fiscal.registry`). Sursa — actul
normativ, numărul de Monitorul Oficial, data publicării — este comună primelor două și **este
referită și de a treia**: o versiune de algoritm implementează, de regulă, o modificare de act.

Cheia străină `fiscal_logic_version.source_id → fiscal_parameter_source.id` traversează două
module din același strat. Gardianul o raportează.

## Ce s-a respins

**Cheia străină doar în SQL, invizibilă lui Django.** Constrângerea ar exista în bază, ORM-ul
n-ar ști de ea. `PROTECT` la ștergere n-ar funcționa, `select_related` n-ar merge, iar
`makemigrations` ar continua să genereze fericit o migrare care o contrazice. O constrângere pe
care jumătate din stivă n-o vede nu e disciplină, e o capcană cu întârziere.

**`source_id` ca UUID liber, fără constrângere.** Ar fi trecut de gardian și ar fi lăsat exact
gaura pe care F0.8 o există ca s-o închidă: un parametru poate arăta către o sursă ștearsă, iar
recalcularea unei perioade din 2026 în 2030 ar întoarce un număr pe care nimeni nu-l poate apara.

**Contopirea celor două module într-un singur app.** Ar fi eliminat întrebarea, nu ar fi
răspuns-o. Parametrii sunt **date** și se schimbă prin INSERT; logica este **cod versionat** și
se schimbă prin deployment — R15 și R16 sunt regula care le ține separate, iar un singur app le-ar
fi topit într-unul la prima refactorizare.

## Decizia

`fiscal` se adaugă la `schema_layers`.

Motivul nu e că F0.8 s-a lovit de gardian. E că `fiscal` are aceeași natură cu `platform` și
`masterdata`: **este strat către care tabelele arată prin natura lor.** Un parametru fiscal nu
este date de business, este act normativ transcris; iar cerința care vine oricum este `R13` —
lanțul complet al unui efect financiar. O înregistrare contabilă care nu poate numi versiunea de
parametru sub care s-a calculat rupe exact lanțul acela, iar `R18` (recalcularea unei perioade
trecute folosește parametrii valabili atunci) cere ca legătura să fie durabilă, nu reconstruită
prin căutare după dată la fiecare interogare.

Cazul pe care `D6` îl vizează rămâne prins: `sales.models → purchases.models` este în continuare
încălcare, fiindcă `operations` nu e strat de compunere de schemă și nu devine.

## Ce rămâne interzis

Condiția pe `models` nu se atinge. `sales/services/vat.py` care importă `fiscal.parameters.models`
rămâne încălcare — chiar dacă `fiscal` e acum strat de schemă. Un serviciu care citește tabela
altui modul o ocolește pe cea publică, și exact asta e cazul pe care regula îl țintește. Calea e
`fiscal.parameters.services.resolution.resolve_parameter()`, care are argumentul de dată
obligatoriu tocmai ca nimeni să nu poată rezolva „la zi” o perioadă închisă.

Măsurat la scrierea acestui ADR: în afara lui `fiscal`, zero importuri către modelele fiscale.
Lărgirea nu legalizează retroactiv nimic.
