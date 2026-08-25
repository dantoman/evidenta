# ADR-018 — Un tenant poate avea engagementuri active cu mai multe firme

- **Status:** Acceptat — decizie de model, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `DN-06` (Spec A §1.4)
- **Afectează:** `engagement`, `engagement_module_scope`, politica RLS din Spec A §2.4, suita de
  penetrare (IZ-25…IZ-29), F0.3.3, F0.3.4, F0.2.4

## Context

Documentele de intrare descriu engagementul ca relație firmă → tenant, fără să spună dacă un tenant
poate avea două astfel de relații vii simultan. Cazul real din piață e concret și frecvent: o firmă
ține contabilitatea, alta ține salarizarea. Un tenant care crește face exact această mișcare — nu
schimbă firma, ci adaugă una specializată.

Întrebarea nu putea fi amânată: răspunsul intră direct în constrângerea de unicitate de pe
`engagement`, în predicatul de acces al firmei și în fiecare scenariu din suita de penetrare care
implică o a doua firmă. Toate trei se scriu la F0.3.3.

## Opțiuni evaluate

1. **A — o singură firmă activă per tenant.** `UNIQUE (client_tenant_id) WHERE status = 'active'`.
   Model simplu, dashboard simplu, teste cu o dimensiune mai puțin. Refuză însă un scenariu frecvent
   și forțează clientul să aleagă între contabilitate și salarizare la firme diferite.
2. **B — mai multe firme, separate prin scope de module.** Unicitatea rămâne per pereche
   firmă–tenant; suprapunerea se controlează prin `engagement_module_scope`. Cere o regulă de
   arbitraj și adaugă o dimensiune fiecărui test de izolare.
3. **C — mai multe firme, separate prin companii.** Firma X ține compania 1, firma Y compania 2.
   Mai ușor de verificat, fiindcă separarea se face pe o entitate care există deja. Nu acoperă cazul
   „aceeași companie, module diferite" — exact cazul contabilitate/salarizare al unui tenant cu o
   singură companie, adică majoritatea.

## Decizie

**Opțiunea B.** Un tenant poate avea simultan engagementuri vii cu mai multe firme, separate prin
scope de module.

- Unicitatea rămâne cea din Spec A §1.4:
  `UNIQUE (firm_id, client_tenant_id) WHERE status IN ('invited','active','suspended')` — o firmă
  are cel mult o relație vie cu un tenant. Nu se adaugă o constrângere pe `client_tenant_id` singur.
- **Regula de arbitraj: fără suprapunere.** Un `module_key` este revendicat de cel mult un
  engagement viu per tenant. Două firme nu pot avea simultan `payroll` la același tenant.
- **Regula se impune în bază, nu doar în serviciu.** Forma exactă — coloană de stare denormalizată
  cu index unic parțial, sau constraint trigger — se fixează la F0.3.3, cu `schema-reviewer`. Ce nu
  este negociabil: o verificare doar în stratul de servicii ar fi ocolită de primul import în masă
  sau de prima scriere concurentă, iar rezultatul ar fi două firme cu acces la aceleași salarii.

Direcția a fost aleasă și pentru că este cea ieftin reversibilă: din B se ajunge la A adăugând o
constrângere, în timp ce din A la B se schimbă constrângerea unică **și** fiecare presupunere din
suita de penetrare.

## Ce rămâne în afara deciziei

**Transferul între firme (`DN-15`) rămâne deschis și interacționează direct cu regula de
suprapunere.** Spec A §4.5 pune opțiunea ca firma veche să păstreze acces numai-citire pe durata
predării — ceea ce este, prin definiție, o suprapunere pe aceleași module. Când `DN-15` se închide
cu acea variantă, regula de aici primește o excepție explicită, scrisă și testată, nu una dedusă.
Până atunci, transferul se modelează ca succesiune, nu ca suprapunere.

Vocabularul de `module_key` este `DN-07`, închisă separat prin [ADR-019](019-vocabular-scope.md).
Fără el, decizia de față nu se poate implementa: separarea prin module cere ca modulele să aibă
nume.

## Consecințe

- Devine posibil: contabilitate la o firmă, salarizare la alta, pe aceeași companie.
- Politica RLS pentru calea firmei trece obligatoriu prin `engagement_module_scope`. Un predicat
  care verifică doar existența engagementului activ devine insuficient — dă acces la tot.
- Suita de penetrare primește o dimensiune reală: IZ-28 („scope de modul restrâns, se cere un modul
  din afara scope-ului") devine scriibil, iar cazurile IZ-25…IZ-29 se scriu cu două firme, nu cu
  una.
- Dashboardul contabilului și comutatorul de tenant nu mai pot presupune o singură firmă per client.
- Costul acceptat: fiecare test de izolare care implică firma capătă o dimensiune în plus.
