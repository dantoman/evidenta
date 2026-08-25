# Teste de integrare

Fiecare efect financiar are un test care verifică **lanțul complet**, cu sume și conturi:

```
Source Document → Accounting Event → Journal Entry → Journal Lines
```

și navigarea inversă, până la sursă (utilizator / sistem / integrare).

Include obligatoriu:

- test de idempotență: aceeași operațiune de două ori cu aceeași cheie → exact un efect financiar
- test de perioadă: postarea într-o perioadă închisă este refuzată de motor, nu de interfață
- test de storno: înregistrarea de corecție are ambele legături (document sursă și înregistrare anulată)
