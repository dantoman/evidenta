# Migrații SQL — per tabelă, aplicate din migrațiile Django

Autoritate: [ADR-012](../../docs/decisions/012-sql-in-django-migrations.md).

Aici stă SQL-ul **per tabelă** pe care Django nu îl poate exprima:

- `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` și `FORCE ROW LEVEL SECURITY`
- politicile RLS, pentru ambele căi de acces (Spec A §2.5, §2.6)
- granturile către rolul de aplicație

Ce **nu** stă aici: roluri, scheme, funcții de context, predicate de acces. Acelea sunt în
[`../bootstrap/`](../bootstrap/), în afara ciclului de migrare, și granița este verificată mecanic.

## Cum se aplică

Nu direct. Fiecare fișier este referit dintr-o migrare Django, prin
`evidenta.platform.rls.sql.run_sql_file()`, ca tabela și politica ei să ajungă în **aceeași
tranzacție**. O singură comandă (`migrate`), o singură istorie de versiuni, iar un eșec parțial se
derulează înapoi complet.

```python
from evidenta.platform.rls.sql import run_sql_file

class Migration(migrations.Migration):
    dependencies = [("tenancy", "0001_initial")]
    operations = [
        migrations.CreateModel(...),
        run_sql_file(
            "0010_tenancy_policies",
            up_sha256="…",
            down_sha256="…",
        ),
    ]
```

## Reguli

1. **Perechi obligatorii.** `<nume>.up.sql` și `<nume>.down.sql`. Helperul refuză migrarea dacă a
   doua lipsește: o migrare de politică ireversibilă nu se poate derula înapoi împreună cu tabela pe
   care o protejează, ceea ce anulează motivul pentru care sunt în aceeași tranzacție.
2. **Append-only.** Odată referit de o migrare aplicată, un fișier nu se editează, nu se redenumește
   și nu se șterge. Corecția este un fișier nou și o migrare nouă. Aceeași regulă ca pentru ledger,
   din același motiv: ce s-a aplicat s-a aplicat.
3. **Hash-ul se verifică la încărcarea grafului de migrări** — `migrate`, `makemigrations`,
   `showmigrations`, `sqlmigrate` și suita de teste. `check` **nu** îl declanșează: nu încarcă
   migrările. Măsurat pe Django 5.2.17.
   Obținerea lui: `python -c "from evidenta.platform.rls.sql import sha256_of; print(sha256_of('nume'))"`.
4. **Ordinea în interiorul migrării**, obligatorie:
   `CREATE TABLE` → `ENABLE` → `FORCE ROW LEVEL SECURITY` → `CREATE POLICY` → `GRANT`.

## Ce garantează structura, și ce rămâne pentru gardian

Structura garantează că tabela și politica ei apar împreună sau deloc. Gardianul de model
(suita 2, F0.2.2) rămâne ca **plasă**, pentru cazul în care cineva ocolește tiparul.

Cele două se întăresc reciproc. Este singurul loc din proiect unde o garanție de securitate nu
depinde de disciplină — motiv în plus să nu se ocolească tiparul „doar de data asta".
