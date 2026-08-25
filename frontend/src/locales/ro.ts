/**
 * Interface strings, Romanian -- C32 and C15.
 *
 * In a resource file from the first screen, and the rule says why: it is what
 * makes "we are adding Russian" cost a translation instead of a walk through two
 * hundred components. ADR-014 defers Russian as a product decision; it does not
 * exclude it, and this file is what keeps the deferral cheap.
 *
 * No i18n library. Plurals, interpolation and per-route loading solve problems
 * this application does not have yet; they get added when a second real language
 * exists, not before.
 *
 * **No model vocabulary here** (C37): not `tenant`, not `firm`, not
 * `engagement`, not `assignment`. ADR-017 fixes the interface words. The check is
 * a grep over this file, which is exactly what C37 describes.
 *
 * **Nothing here reaches an accounting register.** C33 and ADR-016: the books
 * are kept in Romanian by law, and no interface translation ever appears in a
 * register, a financial statement or a generated document. Those come from the
 * server (C22).
 */
export const ro = {
  app: {
    name: 'Evidenta',
    loading: 'Se încarcă…',
  },
  auth: {
    title: 'Autentificare',
    email: 'E-mail',
    password: 'Parolă',
    code: 'Cod de verificare',
    submit: 'Intră în cont',
    signOut: 'Ieși din cont',
  },
  errors: {
    // Keyed by the stable code from C10, never by the server's message. A client
    // that branched on message text would break the first time a sentence is
    // reworded, and rewording is the cheapest thing in the product.
    'auth.invalid_credentials': 'E-mail sau parolă incorecte.',
    'auth.mfa_required': 'Introduceți codul de verificare.',
    'auth.mfa_enrolment_required':
      'Contul nu are încă un al doilea factor configurat.',
    'auth.no_access_to_tenant': 'Nu aveți acces la acest spațiu de lucru.',
    'api.not_found': 'Nu s-a găsit.',
    // The tenant comes from the subdomain (C8), so this is what a host with no
    // workspace behind it answers -- not an error in the usual sense.
    'tenant.not_found': 'Această adresă nu are un spațiu de lucru.',
    'tenant.mismatch': 'Adresa și sesiunea nu se potrivesc.',
    'auth.required': 'Autentificați-vă pentru a continua.',
    'auth.session_tenant_mismatch':
      'Sesiunea aparține altui spațiu de lucru.',
    'api.forbidden': 'Nu aveți dreptul necesar.',
    'api.not_authenticated': 'Sesiunea a expirat. Autentificați-vă din nou.',
    'api.invalid': 'Datele trimise nu sunt valide.',
    'api.idempotency_key_required':
      'Cerere respinsă: lipsește cheia de idempotență.',
    'api.throttled': 'Prea multe cereri. Încercați peste puțin timp.',
    unknown: 'A apărut o eroare neașteptată.',
    network: 'Serverul nu răspunde.',
    hintSubdomain:
      'Spațiul de lucru se alege din subdomeniu — de exemplu alpha.evidenta.localhost:5173, nu evidenta.localhost:5173.',
  },
} as const

export type Strings = typeof ro
