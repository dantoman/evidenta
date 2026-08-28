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
  partners: {
    // Partenerul e al spatiului de lucru, nu al unei companii: aceeasi entitate
    // juridica e aceeasi pentru toate companiile firmei. O copie per companie e
    // felul in care un holding ajunge cu doi furnizori identici ale caror solduri
    // nu mai reconciliaza.
    title: 'Parteneri',
    add: 'Partener nou',
    // C39: denumirea legala ajunge pe documente si in registre; cea scurta exista
    // doar pentru interfata si cautare.
    legalName: 'Denumire legală',
    shortName: 'Denumire scurtă',
    shortNameHint: 'Doar pentru interfață și căutare. Nu ajunge pe documente.',
    kind: 'Fel',
    legalEntity: 'Persoană juridică',
    naturalPerson: 'Persoană fizică',
    idno: 'IDNO',
    idnp: 'IDNP',
    vatCode: 'Cod TVA',
    // Inregistrarea in scopuri de TVA e stare cu data efectiva, nu bifa: o
    // contraparte se inregistreaza si poate fi radiata in cursul anului, iar un
    // document emis inainte de radiere era corect atunci. De aceea data e ceruta
    // impreuna cu codul, nu dedusa din ziua in care se completeaza fisa.
    vatValidFrom: 'TVA din data',
    vatValidFromHint: 'Data de la care partenerul este înregistrat ca plătitor de TVA.',
    vatValidFromRequired: 'Introduceți data de la care se aplică codul TVA.',
    internalName: 'Denumire internă',
    internalNameHint: 'Alfabet liber. Apare în liste și în căutare, niciodată pe un document.',
    roles: 'Roluri',
    customer: 'Client',
    supplier: 'Furnizor',
    state: 'Stare',
    active: 'Activ',
    inactive: 'Retras',
    retire: 'Retrage',
    restore: 'Reactivează',
    showInactive: 'Arată și retrașii',
    search: 'Caută după denumire sau IDNO',
    empty: 'Niciun partener.',
    create: 'Creează partenerul',
    rolesRequired: 'Alegeți cel puțin un rol.',
    // Masurat: serverul intoarce cel mult 200 de randuri si nu pagineaza.
    truncated: 'Se afișează cel mult 200. Restrângeți căutarea.',
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
    opening: {
      title: 'Solduri inițiale',
      lead:
        'O companie care vine din alt sistem pornește cu solduri, nu cu registrul gol. Setul se echilibrează pe contul de contrapartidă ales mai jos.',
      asOfDate: 'La data de',
      // Masurat pe server: data lotului trebuie sa cada intr-o perioada deschisa,
      // altfel refuzul e `periods.period_not_found`. Deci exercitiul se deschide
      // inainte, iar „ziua dinaintea primului exercitiu" nu functioneaza.
      asOfDateHint:
        'Data trebuie să cadă într-un exercițiu deschis — de exemplu prima zi a primului exercițiu.',
      source: 'Proveniență',
      sourceManual: 'Introduse manual',
      sourceOnec: 'Import 1C',
      sourceOther: 'Alt sistem',
      counterpart: 'Cont de contrapartidă',
      counterpartHint:
        'Contul pe care se oglindește fiecare sold. Soldul lui după înregistrare este proba de completitudine: trebuie să fie zero.',
      create: 'Creează lotul',
      state: 'Stare',
      draft: 'În lucru',
      validated: 'Validat',
      posted: 'Postat',
      rejected: 'Respins',
      account: 'Cont',
      debit: 'Debit',
      credit: 'Credit',
      addRow: 'Adaugă rând',
      removeRow: 'Șterge',
      saveRows: 'Salvează rândurile',
      total: 'Total',
      difference: 'Diferență',
      // Reconcilierea la zero e conditia importului, nu scopul lui: serverul
      // refuza un set GL dezechilibrat, nu il absoarbe pe contrapartida.
      unbalanced:
        'Setul nu se închide: totalul debitului diferă de cel al creditului. Contrapartida nu absoarbe diferența.',
      validate: 'Validează lotul',
      post: 'Postează soldurile',
      postedNote: 'Soldurile au fost postate. Lotul nu se mai modifică.',
      rowsSaved: 'Rândurile au fost salvate.',
      validatedNote: 'Lotul e validat. Rândurile sunt înghețate.',
      // Onestitate despre ce nu e livrat, pe ecran, nu doar in cod.
      empty: 'Lotul nu are încă niciun rând.',
      // Lista de loturi: un lot nu se sterge niciodata, deci unul abandonat ieri
      // e tot acolo si trebuie sa se poata regasi.
      batches: 'Loturi',
      batchesEmpty: 'Compania nu are încă niciun lot de solduri.',
      newBatch: 'Lot nou',
      rows: 'rânduri',
      rejectedReason: 'Motivul respingerii',
      created: 'Creat',
      // Creante si datorii pe partener.
      receivables: 'Creanțe',
      payables: 'Datorii',
      partner: 'Partener',
      partnerSearch: 'Caută după denumire sau IDNO',
      partnerNone: 'Niciun partener găsit.',
      addReceivable: 'Adaugă creanță',
      addPayable: 'Adaugă datorie',
      analyticalHint:
        'Detaliul pe parteneri trebuie să se potrivească cu soldul contului de control din rândurile de mai sus.',
    },
    // `templates` era luat de versiunile publicate ale planului de conturi, iar
    // ciocnirea a fost prinsa de typecheck, nu de citire. Numele lung e cel corect
    // oricum: sunt doua lucruri diferite si nu se prescurteaza la fel.
    operationTemplates: {
      title: 'Șabloane de operațiuni',
      lead:
        'Un șablon e o scurtătură către o notă contabilă, nu un al doilea fel de a înregistra. Ce postează el este o notă obișnuită.',
      name: 'Denumire',
      entryDescription: 'Descrierea înregistrării',
      lines: 'Rânduri',
      inputs: 'Valori cerute la postare',
      state: 'Stare',
      active: 'Activ',
      inactive: 'Retras',
      showInactive: 'Arată și retrasele',
      empty: 'Compania nu are încă șabloane.',
      // Retragerea nu sterge: o inregistrare postata anul trecut numeste sablonul,
      // iar o definitie necitibila ar lasa-o sa se explice cu un identificator.
      retire: 'Retrage',
      restore: 'Reactivează',
      use: 'Folosește',
      post: 'Postează nota',
      date: 'Data înregistrării',
      description: 'Descriere',
      descriptionHint: 'Lăsat gol, se folosește descrierea din șablon.',
      inputValue: 'Valoare',
      posted: 'Nota a fost postată din șablon.',
      postedAgain: 'Nota era deja postată cu aceeași cheie.',
      fromInput: 'se cere la postare',
      debit: 'Debit',
      credit: 'Credit',
      account: 'Cont',
      amount: 'Sumă',
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
      // Corectia unei inregistrari postate e storno, niciodata modificare (R10).
      reverse: 'Stornează',
      reverseDate: 'Data corecției',
      reverseReason: 'Motivul corecției',
      reverseHint:
        'Înregistrarea postată nu se modifică. Se anulează printr-o înregistrare în oglindă, iar cele două rămân legate.',
      reverseSubmit: 'Confirmă stornarea',
      reversing: 'Se stornează…',
      reverseDone: 'Înregistrarea a fost stornată.',
      cancel: 'Renunță',
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
    // Sabloane de operatiuni.
    'posting.template_not_found': 'Șablonul nu a fost găsit.',
    'posting.template_name_taken': 'Există deja un șablon cu această denumire.',
    'posting.template_malformed': 'Șablonul nu are forma cerută.',
    'posting.template_input_missing': 'Lipsește o valoare pe care șablonul o cere.',
    'posting.template_input_unexpected': 'A fost trimisă o valoare pe care șablonul nu o cere.',
    'posting.template_input_invalid': 'Valoarea trimisă nu este validă.',
    'posting.template_amount_not_storable': 'Suma rezultată nu poate fi stocată exact.',
    'posting.template_unknown_dimension': 'Dimensiune analitică necunoscută în șablon.',
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
    // Soldurile initiale. Codurile sunt culese din `opening/errors.py`.
    'opening.refused': 'Operațiunea a fost refuzată.',
    'opening.batch_not_found': 'Lotul nu a fost găsit.',
    'opening.batch_not_draft': 'Lotul nu mai este în lucru, deci rândurile nu se mai schimbă.',
    'opening.illegal_batch_transition': 'Trecerea aceasta de stare nu este permisă.',
    'opening.empty_gl_set': 'Lotul nu are niciun sold de cont.',
    'opening.gl_out_of_balance':
      'Setul nu se închide: totalul debitului diferă de cel al creditului.',
    'opening.analytical_mismatch':
      'Detaliul analitic nu se potrivește cu soldul contului de control.',
    'opening.account_missing_from_gl': 'Un cont din detaliul analitic lipsește din soldurile de cont.',
    'opening.counterpart_in_gl': 'Contul de contrapartidă nu poate apărea și între solduri.',
    'opening.foreign_currency_unsupported':
      'Soldurile în valută nu se pot introduce încă.',
    'opening.start_period_fixed': 'Data soldurilor inițiale este deja fixată.',
    'opening.batch_already_posted': 'Lotul a fost deja postat.',
    'partners.malformed': 'Datele partenerului nu au forma cerută.',
    'partners.idno_taken': 'Există deja un partener cu acest IDNO.',
    'partners.not_found': 'Partenerul nu a fost găsit.',
    'ledger.entry_already_reversed': 'Înregistrarea a fost deja stornată.',
    'ledger.entry_not_posted': 'Înregistrarea nu este postată, deci nu are ce anula.',
    'posting.reversal_payload_invalid': 'Stornarea are nevoie de un motiv.',
    'posting.reversal_origin_missing':
      'Înregistrarea nu are un eveniment contabil vizibil, deci nu poate fi stornată.',
    'ledger.nothing_to_write': 'Nu există nimic de înregistrat.',
    'ledger.unknown_dimension': 'Dimensiune analitică necunoscută.',
    unknown: 'A apărut o eroare neașteptată.',
    network: 'Serverul nu răspunde.',
    hintSubdomain:
      'Spațiul de lucru se alege din subdomeniu — de exemplu alpha.evidenta.localhost:5173, nu evidenta.localhost:5173.',
  },
} as const

export type Strings = typeof ro
