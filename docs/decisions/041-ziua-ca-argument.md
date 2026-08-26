# ADR-041 — Ziua intră ca argument; niciun predicat nu citește ceasul

- **Stare:** Acceptat — **decizie luată, implementare amânată deliberat** (§6)
- **Data:** 2026-08-26
- **Închide:** `OD-63`
- **Decis de:** proprietar
- **Atinge:** `infra/bootstrap/0003_access_predicates.sql`,
  `infra/migrations/0032_engagement_provisioning.up.sql`

## 1. Problema, măsurată

Aplicația calculează datele în `Europe/Chisinau` — Django pune `TZ` din `settings.TIME_ZONE` — iar
conexiunea pe care o deschide o pune pe `UTC`. Măsurat, în același proces:

```
python date.today():   2026-08-26
current_date (Django): 2026-08-25
```

**Trei ore în fiecare noapte, cele două numesc zile diferite** — între 21:00 și 24:00 UTC.

`rls.has_tenant_access` și `rls.has_company_access` decid **accesul** comparând `valid_to` cu
`current_date`. Un engagement expirat după ceasul aplicației mai dă acces trei ore.

**Mărimea, numărată:** `current_date` apare de **șapte ori executabil, în două fișiere** — patru în
predicatele de acces, trei în provizionarea de engagement. Restul aparițiilor sunt comentariu și
docstring. `now()` compară **momente**, nu zile, deci e corect în orice fus. ORM-ul răspunde deja pe
ziua de la Chișinău: `__date` emite fusul ca **parametru**, luat din fusul Django activ, nu din
conexiune.

Deci nu e o problemă sistemică de fus. Sunt șapte linii.

## 2. Decizia

**Nimeni din bază nu decide ziua. Data intră ca argument, ca peste tot în rest.** Cele șapte linii
nu se repară — se convertesc la parametru.

## 3. De ce, și motivul nu e consecvența

Consecvența contează, dar nu e argumentul.

**Un predicat de control al accesului care citește ceasul întoarce rânduri diferite la momente
diferite, pentru aceeași interogare.** Două consecințe, iar a doua e cea gravă:

1. **Accesul devine netestabil.** S-a văzut: `test_expiry_is_cosmetic_not_the_security_mechanism`
   era verde 87% din timp și a picat CI la 23:03 UTC. Un test care se repară singur după trei ore
   e unul pe care oricine îl clasează drept instabil, iar constatarea de dedesubt dispare.
2. **Accesul devine neauditabil.** La o dispută nu se poate reconstitui ce a văzut cineva, fiindcă
   răspunsul depinde de *când* a rulat interogarea. Într-un sistem în care cabinetele ating datele
   mai multor companii, aceasta este exact proprietatea pe care nu ne-o permitem.

## 4. Precedentul e deja în arhitectură

Cursurile BNM și regulile fiscale sunt **date versionate** tocmai ca o perioadă trecută să poată fi
reconstituită cu regulile de atunci — `R17`, `R18`, și motivul pentru care fiecare rezolvare din
`fiscal` primește data ca argument și nimic nu citește ceasul.

Un predicat care întreabă `current_date` contrazice aceeași disciplină, **într-un loc unde
consecința e securitate, nu raportare.** Partea din sistem care are cel mai mult de pierdut era
singura care nu o respecta.

## 5. Ce s-a respins

**Alinierea sesiunii de bază la `Europe/Chisinau`.** Funcționează — prin
`DATABASES['TIME_ZONE']`, nu prin `OPTIONS`, fiindcă Django emite `SET TIME ZONE 'UTC'` după
deschiderea conexiunii — și s-a verificat că nu mută problema în rapoarte, contrar temerii inițiale.

Se respinge fiindcă rezolvă aceleași șapte linii **făcând corectitudinea să depindă de o setare pe
care nimic n-o verifică**. Un predicat de acces corect fiindcă cineva a pus o cheie în configurație
este un predicat care redevine greșit la prima migrare de mediu, tăcut.

## 6. Implementarea se amână deliberat

Decizia se consemnează acum; codul se scrie cu capul limpede, nu la miezul nopții după o sesiune în
care s-a închis F0.

Motivul e specific, nu igienă generală: **este cod de control al accesului, și e genul de reparație
unde „aproape corect" trece testele.** Un predicat care primește data dar o compară greșit la
margine — inclusiv versus exclusiv — dă acces cu o zi în plus și nu cade niciun test, fiindcă
testele care ar prinde-o sunt exact cele scrise de aceeași persoană în aceeași oră.

Ce trebuie făcut, ca listă:

- `rls.has_tenant_access(p_tenant_id, p_on_date)` și `rls.has_company_access(p_company_id, p_on_date)`
  primesc data; politicile care le apelează o transmit;
- de unde vine data în politici este chiar întrebarea de rezolvat cu grijă — o politică nu are
  argumente, deci sursa e contextul de sesiune, pe modelul lui `app.current_tenant_id()`;
- `rls.provision_company_access` la fel, unde apelantul o are deja;
- fereastra rămâne `[valid_from, valid_to]` inclusiv, cum e azi — **nu se schimbă semantica în
  aceeași trecere**, altfel nu se mai știe care modificare a produs ce;
- `test_the_predicate_follows_the_database_day_not_the_application_day` va cădea, și trebuie să
  cadă: e scris ca să cadă când `OD-63` se închide.
