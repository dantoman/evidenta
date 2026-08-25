# ADR-021 — MFA obligatoriu pentru toți utilizatorii

- **Status:** Acceptat — decizie de produs și securitate, sub regimul `ADR-002`
- **Data:** 2026-08-25
- **Decide:** proprietarul proiectului
- **Închide:** `DN-09` (Spec A §11.9)
- **Afectează:** `user.mfa_enabled`, F0.3.7, onboarding

## Decizie

**MFA este obligatoriu pentru toți utilizatorii, fără excepții.**

Nu doar pentru utilizatorii firmelor de contabilitate, deși aceia sunt ținta cu cel mai mare
efect de pârghie: un cont compromis acolo deschide toți tenanții gestionați.

## Ce se acceptă odată cu ea

**Fricțiune la onboarding, în segmentul cel mai fragil.** Unit economics din V2 §13 spune că
microîntreprinderea pe canal direct este clientul scump; MFA obligatoriu îl face și mai greu de
adus. Aceasta este consecința cunoscută și acceptată, nu o scăpare descoperită ulterior.

Compensarea nu este o excepție, ci calitatea implementării: metode multiple (TOTP și, ulterior,
WebAuthn), coduri de rezervă la înrolare, și un flux de recuperare care nu presupune că
utilizatorul are un al doilea dispozitiv.

## Ce trebuie să existe ca decizia să nu devină o gaură

Un MFA obligatoriu fără cale de recuperare produce conturi pierdute, iar conturile pierdute produc
excepții manuale în producție — care sunt exact vectorul pe care MFA trebuia să-l închidă.

Necesare la F0.3.7, nu ulterior:

1. **Coduri de rezervă** generate la înrolare, afișate o singură dată, stocate ca hash.
2. **Recuperare prin al doilea administrator** al tenantului, nu prin suport. Suportul care poate
   reseta MFA este un MFA opțional cu pași în plus.
3. **Ultimul `owner` nu poate rămâne fără MFA înrolat** — altfel primul tenant cu un singur
   administrator care își pierde telefonul devine intervenție manuală.

## Consecințe

- `user.mfa_enabled` devine invariant, nu preferință: un cont fără MFA înrolat nu poate finaliza
  autentificarea. Coloana rămâne, ca stare de înrolare.
- Modele noi la F0.3.7: metodă MFA, coduri de rezervă.
- Onboarding-ul cere înrolare înainte de primul acces la date.

## Surse

- Spec A §11.9; V2 §12.3, §13 (unit economics)
