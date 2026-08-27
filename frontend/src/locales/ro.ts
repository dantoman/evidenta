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
    signOut: 'Ieșire din cont',
  },
  common: {
    back: 'Înapoi',
    save: 'Salvează',
    add: 'Adaugă',
    none: '—',
  },
  companies: {
    // „Companii", nu „companiile mele": pagina o citesc si proprietarul, si
    // contabilul care tine evidenta altcuiva, iar ADR-017 le da acelorasi randuri
    // doua formulari diferite („compania mea" / „clientii mei"). Un titlu neutru
    // nu se contrazice cu niciuna.
    title: 'Companii',
    legalName: 'Denumire legală',
    idno: 'IDNO',
    currency: 'Monedă funcțională',
    empty: 'Nu aveți acces la nicio companie.',
    add: 'Companie nouă',
    // Formularul: trei campuri, atat cat cere serverul. Restul datelor companiei
    // se completeaza mai tarziu, din ecranele care le folosesc.
    create: 'Creează compania',
    creating: 'Se creează…',
    currencyHint: 'Moneda în care se țin registrele.',
    idnoHint: '13 cifre.',
    cancel: 'Renunță',
  },
  accounting: {
    // Vocabularul din jurul contului, nu numele lui. Denumirea contului vine de la
    // server si se afiseaza cum vine: contabilitatea se tine in romana prin lege
    // (C33, ADR-016), deci e valoare stocata, nu sir de interfata.
    classes: {
      asset: 'Activ',
      liability: 'Datorie',
      equity: 'Capital propriu',
      income: 'Venit',
      expense: 'Cheltuială',
    },
    chart: {
      title: 'Plan de conturi',
      company: 'Companie',
      code: 'Cod',
      name: 'Denumire',
      class: 'Clasă',
      origin: 'Origine',
      // C37: fara vocabular de model. „Cont de sistem" descrie de unde vine
      // contul, nu tabela din care a fost copiat.
      originSystem: 'Din plan',
      originCompany: 'Propriu',
      state: 'Stare',
      open: 'Activ',
      closed: 'Închis',
      blocked: 'Blocat',
      empty: 'Compania nu are încă un plan de conturi.',
      version: 'Versiune',
      // Filtrul `?on=`: ce se poate inregistra la o data, nu ce exista azi.
      postableOn: 'Se poate înregistra la data',
      postableAll: 'Tot planul',
      postableNote:
        'Se afișează doar conturile în care se poate înregistra la data aleasă — valabile și neblocate atunci.',
      initialize: 'Inițializează planul de conturi',
    },
    templates: {
      title: 'Inițializarea planului de conturi',
      lead: 'Planul se construiește dintr-o versiune publicată. Alegeți versiunea, apoi confirmați.',
      code: 'Cod',
      version: 'Versiune',
      validity: 'Valabilitate',
      // Actul normativ este pe sarma tocmai ca alegerea sa nu fie intre doua
      // siruri opace -- cine alege o versiune alege un act.
      act: 'Act normativ',
      reference: 'Referință',
      published: 'Publicat',
      choose: 'Alege',
      chosen: 'Versiunea aleasă',
      submit: 'Inițializează planul',
      empty: 'Nu există nicio versiune publicată.',
      already: 'Compania are deja un plan de conturi.',
    },
    entry: {
      title: 'Notă contabilă manuală',
      date: 'Data înregistrării',
      description: 'Descriere',
      account: 'Cont',
      lineDescription: 'Explicație',
      debit: 'Debit',
      credit: 'Credit',
      addLine: 'Adaugă rând',
      removeLine: 'Șterge',
      total: 'Total',
      difference: 'Diferență',
      // Σ Debit = Σ Credit este invariant de baza (R11), verificat pe server. Aici
      // se blocheaza doar butonul: refuzul adevarat nu e al ecranului.
      unbalanced: 'Notă neechilibrată: totalul debitului diferă de cel al creditului.',
      post: 'Postează nota',
      posting: 'Se postează…',
      posted: 'Nota a fost postată.',
      postedAgain: 'Nota era deja postată cu aceeași cheie; nu s-a postat a doua oară.',
      empty: 'Adăugați cel puțin un rând.',
      needAccount: 'Fiecare rând are nevoie de un cont.',
      needDescription: 'Nota are nevoie de o descriere.',
      noChart: 'Compania nu are încă un plan de conturi.',
    },
    register: {
      title: 'Registrul înregistrărilor',
      number: 'Număr',
      date: 'Data',
      description: 'Descriere',
      debit: 'Debit',
      credit: 'Credit',
      account: 'Cont',
      // C37: „stornată" descrie inregistrarea, nu tabela.
      reversed: 'Stornată',
      reverses: 'Stornează',
      empty: 'Nicio înregistrare în perioada aleasă.',
      truncated: 'Lista a fost tăiată. Restrângeți perioada pentru a vedea restul.',
      lines: 'Rânduri',
    },
    balance: {
      title: 'Balanța de verificare',
      from: 'De la',
      to: 'Până la',
      show: 'Afișează',
      code: 'Cont',
      name: 'Denumire',
      opening: 'Sold inițial',
      debit: 'Rulaj debit',
      credit: 'Rulaj credit',
      closing: 'Sold final',
      total: 'Total',
      empty: 'Nicio înregistrare în perioada aleasă.',
      balanced: 'Balanța este echilibrată.',
      unbalanced: 'Balanța NU este echilibrată.',
    },
    account: {
      title: 'Fișa contului',
      code: 'Cod',
      name: 'Denumire',
      class: 'Clasă',
      origin: 'Origine',
      normalBalance: 'Sold normal',
      debit: 'Debit',
      credit: 'Credit',
      parent: 'Cont superior',
      validFrom: 'Valabil din',
      validTo: 'Valabil până la',
      tracking: 'Urmărire',
      currencyTracking: 'Valută',
      quantityTracking: 'Cantitate',
      allowsSubaccounts: 'Permite subconturi',
      requiredDimensions: 'Dimensiuni obligatorii',
      state: 'Stare',
      rename: 'Redenumire',
      renameSystem:
        'Conturile din plan se mențin centralizat și nu se redenumesc. Blocarea și închiderea rămân posibile.',
      block: 'Blochează contul',
      unblock: 'Deblochează contul',
      close: 'Închiderea contului',
      closeFrom: 'Valabil până la',
      closeAction: 'Închide contul',
      subaccount: 'Subcont nou',
      subaccountNotAllowed: 'Acest cont nu permite subconturi.',
      subaccountDimensions:
        'Dimensiunile obligatorii nu se aleg aici: subcontul pornește fără niciuna, ca pe server.',
      saved: 'Modificarea a fost salvată.',
      created: 'Subcontul a fost creat.',
    },
  },
  errors: {
    // Keyed by the stable code from C10, never by the server's message. A client
    // that branched on message text would break the first time a sentence is
    // reworded, and rewording is the cheapest thing in the product.
    // Copiate din codurile pe care le ridică `platform/identity`, nu inventate.
    // Prima versiune avea `auth.mfa_required`, un nume pe care serverul nu-l
    // trimite niciodată, deci orice cod greșit cădea pe „eroare neașteptată" --
    // exact ce `C10` există ca să prevină. `test_error_catalogue.py` verifică
    // acum că fiecare cod al serverului are un mesaj aici.
    'auth.invalid_credentials': 'E-mail sau parolă incorecte.',
    'auth.mfa_code_required': 'Introduceți codul de verificare.',
    'auth.invalid_mfa_code': 'Codul de verificare este greșit sau a expirat.',
    'auth.invalid_backup_code': 'Codul de recuperare nu este valid.',
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
    'api.idempotency_key_invalid': 'Cheia de idempotență nu este validă.',
    'api.tenant_context_missing': 'Cererea a ajuns fără spațiu de lucru.',
    'error.unknown': 'A apărut o eroare neașteptată.',
    // Planul de conturi. Fiecare cod exista in `accounting/coa/errors.py`; niciun
    // mesaj de aici nu descrie altceva decat clasa de acolo.
    'coa.chart_already_instantiated': 'Compania are deja un plan de conturi.',
    'coa.template_not_published': 'Versiunea aleasă nu este publicată.',
    // Un rand inaccesibil este absent, niciodata interzis (IZ-04): serverul da un
    // singur cod pentru „nu exista" si „nu aveti acces", iar mesajul nu are voie
    // sa le desparta inapoi.
    'coa.company_not_visible': 'Compania nu există sau nu aveți acces la ea.',
    'coa.account_not_found': 'Contul nu a fost găsit.',
    'coa.subaccounts_not_allowed': 'Contul superior nu permite subconturi.',
    'coa.parent_account_closed':
      'Contul superior nu mai este valabil la data de la care ar începe subcontul.',
    'coa.account_code_taken': 'Există deja un cont cu acest cod în planul companiei.',
    'coa.system_account_immutable':
      'Conturile din plan nu se redenumesc. Blocarea și închiderea rămân posibile.',
    'coa.unknown_dimension': 'Dimensiune analitică din afara vocabularului.',
    'coa.invalid_validity_window': 'Perioada de valabilitate nu este validă.',
    'coa.invalid_date': 'Data nu este o dată validă.',
    'ledger.invalid_period': 'Perioada cerută nu este validă.',
    'tenancy.company_idno_taken': 'Există deja o companie cu acest IDNO.',
    'tenancy.company_provisioning_refused':
      'Nu aveți dreptul să creați o companie în acest spațiu de lucru.',
    // Postarea. Fiecare cod e cules din sursa serverului, nu scris din memorie:
    // prima versiune a acestui bloc inventase `posting.out_of_balance` cu alt
    // nume si doua coduri care nu exista nicaieri, adica exact cazul pentru care
    // `C10` cere ca cele doua jumatati sa fie scrise din acelasi loc.
    'posting.out_of_balance': 'Suma debitului nu este egală cu suma creditului.',
    'posting.no_lines': 'Nota nu are niciun rând.',
    'posting.zero_amount_line': 'Un rând fără sumă nu se postează.',
    'posting.malformed_line_amount': 'Suma nu poate fi stocată exact.',
    'posting.manual_payload_malformed': 'Nota nu are forma cerută.',
    'posting.manual_foreign_currency_unsupported':
      'Nota manuală se scrie în moneda în care compania își ține registrele.',
    'posting.account_not_postable':
      'Contul nu poate primi înregistrări la această dată: este închis sau blocat.',
    'posting.missing_required_dimension': 'Contul cere o dimensiune analitică obligatorie.',
    'posting.mixed_company': 'Toate rândurile aparțin aceleiași companii.',
    'posting.mixed_tenant': 'Toate rândurile aparțin aceluiași spațiu de lucru.',
    'posting.mixed_period': 'Toate rândurile cad în aceeași perioadă contabilă.',
    'posting.refused': 'Postarea a fost refuzată de motor.',
    'accounting.idempotency_key_required': 'Cerere respinsă: lipsește cheia de idempotență.',
    'accounting.idempotency_conflict':
      'Aceeași cheie de idempotență a fost folosită pentru altă operațiune.',
    'accounting.no_handler': 'Nu există tratament pentru acest tip de eveniment la data cerută.',
    'accounting.payload_malformed': 'Datele evenimentului nu au forma cerută.',
    // Perioadele. `R12`: refuzul e al motorului, nu al interfetei.
    'periods.period_not_open': 'Perioada este închisă. Corecția se face prin storno.',
    'periods.period_not_found': 'Nu există o perioadă contabilă pentru această dată.',
    'periods.period_locked': 'Perioada este blocată.',
    'periods.fiscal_year_closed': 'Exercițiul este închis.',
    'periods.fiscal_year_code_taken': 'Compania are deja un exercițiu cu acest cod.',
    'periods.fiscal_year_overlaps': 'Exercițiul se suprapune cu altul existent.',
    'periods.fiscal_year_not_found': 'Exercițiul nu a fost găsit.',
    'periods.invalid_fiscal_year_window':
      'Exercițiul începe în prima zi a unei luni și se termină în ultima.',
    'periods.company_not_visible': 'Compania nu există sau nu aveți acces la ea.',
    'ledger.entry_not_found': 'Înregistrarea nu a fost găsită.',
    'ledger.nothing_to_write': 'Nu există nimic de înregistrat.',
    'ledger.unknown_dimension': 'Dimensiune analitică necunoscută.',
    unknown: 'A apărut o eroare neașteptată.',
    network: 'Serverul nu răspunde.',
    hintSubdomain:
      'Spațiul de lucru se alege din subdomeniu — de exemplu alpha.evidenta.localhost:5173, nu evidenta.localhost:5173.',
  },
} as const

export type Strings = typeof ro
