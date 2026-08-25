# Suita 3 — gardian de dependențe

Parcurge `backend/evidenta` și compară fiecare import intern cu graful din `CLAUDE.md` §3.
Autoritate: [ADR-024](../../../docs/decisions/024-gardian-de-dependente.md).

Contractul stă într-un singur loc — `infra/modules/dependencies.toml` — și se citește, nu se
codifică aici. Un gardian ale cărui așteptări stau în propria sursă este un gardian care se editează
ca să treacă suita.

| Regulă | Ce prinde |
|---|---|
| `D0` | pachet sub `evidenta/` care nu apare în contract — raportat, niciodată sărit |
| `DG` | import împotriva direcției din graf |
| `D1` | `fiscal` importă un modul business |
| `D2` | `accounting` importă un modul operațional |
| `D3` | un modul operațional atinge `accounting.ledger`, nu `accounting.events` |
| `D4` | `payroll` importă `tax` |
| `D5` | orice import din `firmspace` |
| `D6` | comunicare prin modelele altui modul |

`D6` are o excepție îngustă, cu ambele condiții impuse: numai un modul `models` poate compune
schemă, și numai către `platform` și `masterdata`. Motivul și măsurătoarea din spatele ei stau în
ADR-024.

Analiza este **statică**. Importul din interiorul unei funcții și cel relativ se văd amândouă —
primul este cum se face de obicei un ciclu să funcționeze la rulare. Ce nu se vede: importul
dinamic prin `importlib`, invizibil oricărei analize statice.

Rulează fără bază de date, în ~0,1 s: `make deps-check`, `make test`, și jobul rapid din CI.

Fiecare regulă are probă că poate eșua — o mică ierarhie de fișiere scrisă într-un director
temporar, cu un singur import în direcția greșită. Fără ele, un gardian care raportează mereu „zero"
nu se deosebește de unul care nu verifică nimic.
