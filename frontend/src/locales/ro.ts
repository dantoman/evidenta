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
    lead: 'Utilizați datele emise de administratorul companiei.',
    email: 'E-mail',
    password: 'Parolă',
    code: 'Cod de verificare',
    codeHint: 'Șase cifre, din aplicația de autentificare.',
    submit: 'Intră în cont',
    signOut: 'Ieșire din cont',
    jurisdiction: 'Republica Moldova · ro-MD',
    // Citatele de pe panoul stâng al autentificării, din pachetul de design.
    // Conținut de interfață, nu de registru: nimic de aici nu ajunge într-un
    // document (C33). Traducerea stă lângă original fiindcă originalul e latin
    // sau german, iar un ecran de intrare nu e locul unde se presupune că
    // cititorul le știe.
    quotes: [
      {
        original: '„Ubi non est ordo, ibi est confusio."',
        translated: 'Unde nu este ordine, acolo este confuzie.',
        source: 'Luca Pacioli · Summa de Arithmetica, 1494',
      },
      {
        original: '„Quod non est in actis, non est in mundo."',
        translated: 'Ce nu se află în acte nu se află în lume.',
        source: 'Adagiu juridic latin',
      },
      {
        original: '„Es ist eine der schönsten Erfindungen des menschlichen Geistes."',
        translated:
          'Partida dublă este una dintre cele mai frumoase invenții ale minții omenești.',
        source: 'J. W. von Goethe · Wilhelm Meister, 1795',
      },
      {
        original: '„Non dormire debet qui in mercatura vult prosperari."',
        translated: 'Cine vrea să prospere în comerț nu trebuie să doarmă.',
        source: 'Luca Pacioli · Summa de Arithmetica, 1494',
      },
    ],
  },
  common: {
    back: 'Înapoi',
    save: 'Salvează',
    add: 'Adaugă',
    none: '—',
    yes: 'Da',
    no: 'Nu',
  },
  // Numele celor doua grupe din banda de navigare a companiei. Doua cuvinte, si
  // niciunul din vocabularul de model (C37): grupele sunt cele pe care le
  // recunoaste un contabil, nu module ale codului.
  nav: {
    accounting: 'Contabilitate',
    // Gruparea comerciala din bara laterala. Adaugata odata cu facturile primite,
    // si ea e cea care a scos la iveala ca ecranul facturilor emise n-avea nicio
    // intrare: exista de la pasul 5, accesibil doar tastandu-i adresa.
    commercial: 'Documente comerciale',
    payroll: 'Salarizare',
    // Deviza livrata cu marca, verbatim. Nu se traduce si nu se rescrie.
    tagline: 'Autoritate în contabilitate',
    compliance: 'Conform SNC',
    company: 'Companie',
    workspace: 'Spațiu de lucru',
    // Marcajul titularului în comutator. Text, nu doar îngroșare: `option` nu se
    // stilează la fel pe toate platformele, iar un marcaj care se vede doar pe
    // unele nu e marcaj.
    chooseCompany: 'Alege compania',
    // Antetul. Ce caută textul e exact ce caută codul: documentele nu sunt
    // căutabile pe server, deci nu apar în îndemn.
    search: 'Caută cont sau contragent',
    searchAccounts: 'Conturi',
    searchPartners: 'Contragenți',
    searchEmpty: 'Nimic găsit.',
    notifications: 'Notificări',
    help: 'Ajutor',
    // Controale desenate, dar oprite: forma antetului e a machetei, starea e
    // adevărul. Un clopoțel care nu numără nimic și un indicator SFS verde ar fi
    // afirmații -- prima nevinovată, a doua despre legătura cu Fiscul.
    notYet: 'Nu este disponibil încă.',
    sfs: 'SFS',
    sfsNotConfigured: 'Integrarea cu SFS nu este configurată.',
  },
  workspace: {
    title: 'Spațiul de lucru',
    // Un rând. Partea a doua -- că spațiul se atribuie unei persoane, iar
    // contabilitatea se ține pe companii -- se spune oricum în cartonașul
    // titularului, deci aici era a doua oară.
    lead: 'Titularul contului și drepturile din el.',
    holder: 'Titularul contului',
    holderNote:
      'Spațiul de lucru se atribuie unei persoane, nu unei companii. Companiile dinăuntru sunt egale între ele, iar drepturile se dau pe fiecare în parte.',
    stateActive: 'Activ',
    stateSuspended: 'Suspendat',
    stateOffboarding: 'În ieșire',
    stateArchived: 'Arhivat',
    email: 'E-mail',
    me: 'Drepturile mele',
    name: 'Nume',
    editName: 'Modifică numele',
    // Ce nu se schimbă din acest formular, spus înainte să fie căutat: fiecare
    // are cale proprie, iar puse laolaltă ar face trei acte diferite să pară
    // unul singur.
    profileNote:
      'E-mailul, parola și al doilea factor se schimbă pe căi proprii: primul cere dovada noii adrese, celelalte două pornesc de la cele actuale.',
    myRole: 'Rol în spațiul de lucru',
    noRole: 'Fără rol în acest spațiu de lucru.',
    membership: 'Apartenență',
    membershipActive: 'Activă',
    membershipInvited: 'Invitat',
    membershipSuspended: 'Suspendată',
    myCompanies: 'Companiile la care am acces',
    grantedViaMembership: 'Prin apartenență',
    grantedViaEngagement: 'Prin mandat',
    noCompanyAccess: 'Nicio companie nu v-a fost atribuită.',
    roles: 'Rolurile spațiului de lucru',
    roleSystem: 'De sistem',
    roleLevelTenant: 'La nivel de spațiu',
    roleLevelCompany: 'La nivel de companie',
    noPermissions: 'Niciun drept.',
    delegated: 'Acces delegat',
    delegatedLead: 'Firmele de contabilitate cu mandat asupra acestui spațiu de lucru.',
    noDelegated: 'Nicio firmă nu are acces la acest spațiu de lucru.',
    validFrom: 'Din',
    validTo: 'Până la',
    allCompanies: 'Toate companiile',
    // Limita e a politicii, nu a ecranului: `membership` se vede rând propriu
    // (migrarea 0011), deci o listă de persoane ar întoarce doar cititorul și ar
    // arăta ca un răspuns. Se spune, nu se ascunde.
    peopleUnavailable:
      'Lista persoanelor din spațiul de lucru nu se poate afișa încă: fiecare vede doar propria apartenență. Decizia care ar deschide întrebarea este OD-37.',
  },
  // Numele rolurilor de sistem. Serverul le ține ca ei -- chei, în engleză, fără
  // etichete (ADR-020) --, iar cum se cheamă în interfață stă aici. Un rol
  // compus de client își poartă numele lui și trece neatins.
  roles: {
    owner: 'Proprietar',
    company_admin: 'Administrator de companie',
  } as Record<string, string>,
  // Etichetele drepturilor. Catalogul serverului poartă chei și domeniu, fără
  // etichete — deliberat: ce se cheamă un drept în interfață stă aici, în
  // română, lângă restul șirurilor (C32), nu într-o coloană care s-ar traduce
  // printr-o migrare.
  permissions: {
    'tenant.manage_roles': 'Administrează rolurile',
    'engagement.invite': 'Invită o firmă de contabilitate',
    'engagement.accept': 'Acceptă un mandat',
    'engagement.suspend': 'Suspendă un mandat',
    'engagement.resume': 'Reia un mandat',
    'engagement.transfer': 'Transferă un mandat',
    'engagement.revoke': 'Retrage un mandat',
    'company.revoke_access': 'Retrage accesul la o companie',
  } as Record<string, string>,
  companies: {
    // „Companii", nu „companiile mele": pagina o citesc si proprietarul, si
    // contabilul care tine evidenta altcuiva, iar ADR-017 le da acelorasi randuri
    // doua formulari diferite („compania mea" / „clientii mei"). Un titlu neutru
    // nu se contrazice cu niciuna.
    title: 'Companii',
    lead: 'Fiecare companie își ține propriul registru. Drumul spre contabilitate trece de aici.',
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
    // Ecranul unei companii (ADR-083). „Fisa companiei", nu „editare": pagina se
    // citeste si de cine n-are dreptul s-o schimbe.
    card: 'Fișa companiei',
    cardLead: 'Ce se corectează, ce nu se corectează, și de ce.',
    shortName: 'Denumire scurtă',
    status: 'Stare',
    statusActive: 'Activă',
    statusSuspended: 'Suspendată',
    statusClosed: 'Închisă',
    save: 'Salvează',
    saving: 'Se salvează…',
    saved: 'Salvat.',
    // Campurile cu consecinte: se arata, nu se editeaza.
    fixed: 'Date care nu se schimbă de aici',
    fixedWhy:
      'IDNO-ul a plecat pe documentele emise, iar moneda și data de început au fost deja folosite ca să dateze și să evalueze ce este în registru. Se corectează prin operator, nu dintr-un formular.',
    accountingStart: 'Începutul evidenței',
    // Inchiderea.
    close: 'Închide compania',
    closeLead:
      'Compania nu mai primește înregistrări. Registrele rămân: nimic din ce este postat nu se șterge și nu se modifică.',
    closeReason: 'Motivul închiderii',
    closing: 'Se închide…',
    closed: 'Compania este închisă. Registrele rămân de citit; nu se mai postează în ele.',
    // Cand cheia lipseste. Nu „acces interzis": accesul exista, dreptul nu.
    noEditRight: 'Nu aveți dreptul de a modifica datele acestei companii.',
    noCloseRight: 'Nu aveți dreptul de a închide această companie.',
    openChart: 'Plan de conturi',
    openPeople: 'Angajați',
  },
  partners: {
    // Partenerul e al spatiului de lucru, nu al unei companii: aceeasi entitate
    // juridica e aceeasi pentru toate companiile firmei. O copie per companie e
    // felul in care un holding ajunge cu doi furnizori identici ale caror solduri
    // nu mai reconciliaza.
    title: 'Parteneri',
    lead:
      'Aceeași entitate juridică pentru toate companiile firmei. Denumirea legală ajunge pe documente; cea scurtă rămâne în interfață.',
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
    edit: 'Modifică',
    editing: 'Modificarea partenerului',
    defaultCurrency: 'Monedă implicită',
    paymentTerms: 'Termen de plată',
    paymentTermsHint: 'Zile de la data documentului.',
    // Granița, scrisă pe ecran: identitatea și TVA-ul nu sunt câmpuri de
    // formular. IDNO-ul e cum numesc partenerul documentele deja emise și e ce
    // împiedică două fișe să împartă un sold; înregistrarea TVA e stare cu dată,
    // deci se adaugă, nu se suprascrie.
    identityNotHere:
      'IDNO-ul și înregistrarea TVA nu se schimbă de aici: primul numește partenerul pe documentele deja emise, a doua este stare cu dată.',
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
    // Grila de introducere -- contractul de tastatura (ADR-052). Sirurile stau
    // aici, componenta le primeste (C32).
    entryGrid: {
      balanceDebit: 'Debit',
      balanceCredit: 'Credit',
      balanceDifference: 'Diferență',
      balanced: 'Echilibrat',
      invalidAmount: 'Nu este o sumă. Se acceptă punct sau virgulă ca separator zecimal.',
      noMatch: 'Niciun element nu corespunde.',
      deleteAgain: 'Rândul are conținut. Apăsați din nou Ctrl+Delete pentru a-l șterge.',
      // Ajutorul de tastatura, cum e in contract; nicio tasta nu se schimba per ecran (C40).
      keys:
        'Enter avansează (pe ultimul câmp deschide rând nou) · Tab navighează · F4 nomenclator · F2 editează · Escape anulează celula, apoi rândul · Ctrl+Delete șterge rândul · Ctrl+Enter validează',
    },
    reports: {
      // Fisa contului, Cartea Mare, rulajele pe corespondente -- toate cu
      // totalurile de pe server (C19) si exportul de pe server (C20).
      from: 'De la',
      to: 'Până la',
      show: 'Afișează',
      exportCsv: 'Export CSV',
      exportHint:
        'Fișierul se generează pe server, din aceleași cifre ca ecranul; Excel și PDF nu sunt încă disponibile.',
      truncated: 'Lista a fost tăiată; totalurile acoperă întreaga perioadă. Restrângeți perioada pentru a vedea toate rândurile.',
      empty: 'Nicio mișcare în perioada aleasă.',
      opening: 'Sold inițial',
      closing: 'Sold final',
      total: 'Total',
      // Fisa contului -- un rand per document (ADR-053).
      ledger: 'Fișa contului',
      ledgerLead: 'Un rând per document, cu contul corespondent; deschiderea unui rând arată formulele.',
      date: 'Data',
      number: 'Număr',
      documentDate: 'Data doc.',
      description: 'Descriere',
      correspondent: 'Cont corespondent',
      noCorrespondent: 'fără corespondență',
      debit: 'Debit',
      credit: 'Credit',
      runningBalance: 'Sold',
      // Cartea Mare -- pe luni, in corespondenta cu conturile.
      generalLedger: 'Cartea Mare',
      generalLedgerLead: 'Rulajele lunare ale contului, în corespondență cu conturile.',
      month: 'Luna',
      debitBy: 'Debit în corespondență cu',
      creditBy: 'Credit în corespondență cu',
      unassigned: 'fără corespondență (note manuale)',
      turnover: 'Rulaj',
      // Rulajele pe corespondente -- sahul.
      correspondence: 'Rulaje pe corespondențe',
      correspondenceLead:
        'Suma fiecărei corespondențe debit–credit din perioadă. Ce nu are corespondență (notele manuale) apare separat.',
      debitAccount: 'Cont debitor',
      creditAccount: 'Cont creditor',
      amount: 'Sumă',
      correspondenceTotal: 'Total corespondențe',
      linesTotal: 'Total rulaj debitor',
      // Detaliul unei inregistrari -- drill-down pana la sursa (R13).
      detail: 'Înregistrarea',
      formulas: 'Formule',
      lines: 'Rânduri',
      stoodOn: 'Postată sub',
      rule: 'Regula',
      chart: 'Planul de conturi',
      fiscalDate: 'Data fiscală',
      origin: 'Sursa',
      originEvent: 'Eveniment',
      originDocument: 'Document',
      vatRate: 'Cota TVA',
      noFormulas: 'Înregistrare introdusă pe rânduri, fără formule.',
      close: 'Închide',
      openLedger: 'Fișa contului',
      openGeneralLedger: 'Cartea Mare',
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
  payroll: {
    // Angajatorul legal e COMPANIA, nu spatiul de lucru: ea retine, ea depune,
    // ea raspunde. De aceea ecranele stau sub companie, spre deosebire de
    // parteneri.
    people: 'Angajați',
    addPerson: 'Persoană nouă',
    lastName: 'Nume',
    firstName: 'Prenume',
    idnp: 'IDNP',
    idnpHint: '13 cifre. Obligatoriu în declarația nominală.',
    documentType: 'Act de identitate',
    documentNumber: 'Seria și numărul',
    documentHint: 'Pentru cine nu are IDNP. Fără el, aceeași persoană se introduce de două ori.',
    residency: 'Rezidență fiscală',
    resident: 'Rezident',
    nonResident: 'Nerezident',
    insuranceCode: 'Cod personal de asigurare',
    searchPeople: 'Caută după nume sau IDNP',
    noPeople: 'Nicio persoană.',
    createPerson: 'Creează persoana',

    contracts: 'Contracte de muncă',
    addContract: 'Contract nou',
    contractNumber: 'Număr contract',
    relationshipType: 'Forma raportului',
    // ADR-071: trei forme, exact cele din pct. 1.1 al anexei nr. 1 la Legea
    // nr. 489/1999. Etichetele stau aici; codurile vin de la server.
    employmentContract: 'Contract individual de muncă',
    serviceRelationship: 'Raporturi de serviciu (act administrativ)',
    civilContract: 'Contract civil (lucrări sau servicii)',
    signedOn: 'Data semnării',
    effectiveFrom: 'În vigoare din',
    effectiveTo: 'Până la',
    endedOn: 'Încetat la',
    // Faptul generator al raportarii e ordinul, nu contractul: termenul de 10
    // zile lucratoare curge din ziua urmatoare datei din ordin.
    hireOrder: 'Ordin de angajare',
    orderNumber: 'Număr ordin',
    orderDate: 'Data ordinului',
    terminationOrder: 'Ordin de încetare',
    position: 'Funcția',
    salary: 'Salariu de bază',
    weeklyHours: 'Ore pe săptămână',
    casPoint: 'Categoria de plătitor',
    casPointHint: 'Punctul din anexa nr. 1 la Legea nr. 489/1999. Este al raportului, nu al companiei.',
    noContracts: 'Niciun contract.',
    showEnded: 'Arată și încetate',
    createContract: 'Creează contractul',
    endContract: 'Încetează contractul',

    amendments: 'Acte adiționale',
    addAmendment: 'Act adițional nou',
    amendmentNumber: 'Număr act adițional',
    // Art. 49 alin. (1) are 19 clauze. Trei sunt coloane; restul se numesc.
    changedClause: 'Clauza modificată',
    changedClauseHint: 'Litera din art. 49 alin. (1) al Codului muncii.',
    note: 'Ce s-a schimbat',
    noAmendments: 'Niciun act adițional. Contractul are clauzele de la semnare.',
    createAmendment: 'Adaugă actul adițional',
    // Intrebarea pe care seria o raspunde si o coloana n-ar putea.
    inForceOn: 'Ce era în vigoare la data',
    inForceShow: 'Arată',
    setBy: 'stabilit prin',

    timesheets: 'Pontaj',
    openMonth: 'Deschide luna',
    year: 'An',
    month: 'Luna',
    normHours: 'Norma lunii (ore)',
    normHint: 'Din calendarul de producție. Se introduce, nu se deduce.',
    status: 'Stare',
    open: 'Deschis',
    closed: 'Închis',
    closeMonth: 'Închide luna',
    hoursWorked: 'Ore lucrate',
    nightHours: 'Ore de noapte',
    holidayHours: 'Ore în zile de sărbătoare',
    hoursHint: 'Orele de noapte și de sărbătoare fac parte din orele lucrate, nu se adaugă la ele.',
    daysPresent: 'Zile prezente',
    noMonths: 'Nicio lună deschisă.',
    day: 'Ziua',
    addDay: 'Adaugă zi',
    saveDays: 'Salvează zilele',
    pickContract: 'Alege contractul',

    // Scutirile: cerere cu data efectiva, nu bifa. Pct. 18 din Regulamentul
    // aprobat prin HG nr. 697/2014 le acorda si le anuleaza „incepand cu luna
    // urmatoare" celei in care s-a depus cererea — deci ecranul cere data
    // depunerii si arata data de la care se aplica, calculata de server.
    exemptions: 'Scutiri',
    exemptionHistory: 'Istoricul scutirilor',
    fileApplication: 'Cerere nouă',
    filedOn: 'Data depunerii',
    // Distinct de `effectiveFrom` al contractului: acolo e data de la care
    // contractul isi produce efectele (art. 49 lit. d), aici e luna urmatoare
    // depunerii cererii (pct. 18). Doua reguli, doua date, doua etichete.
    exemptionAppliesFrom: 'Se aplică din',
    effectiveHint: 'Din luna următoare celei în care s-a depus cererea.',
    soleWorkplace: 'Declar că este unicul loc de muncă',
    soleWorkplaceHint: 'Scutirile se acordă la un singur loc de muncă. Este declarația angajatului.',
    exemptionCode: 'Scutirea',
    // Vocabularul are cinci coduri. Scutirea ordinara pentru sot/sotie NU exista
    // — art. 34 alin. (2) acorda doar pe cea majorata.
    codeP: 'P — personală',
    codeM: 'M — personală majoră',
    codeSm: 'Sm — majoră pentru soț/soție',
    codeN: 'N — persoană întreținută',
    codeH: 'H — persoană întreținută cu dizabilitate',
    dependents: 'Persoane întreținute',
    addDependent: 'Persoană întreținută nouă',
    dependentHint: 'Are nevoie de identificator propriu, altfel aceeași persoană se poate revendica de două ori.',
    pickDependent: 'Alege persoana întreținută',
    addGrant: 'Adaugă o scutire',
    submitApplication: 'Înregistrează cererea',
    withdraw: 'Retrage',
    withdrawn: 'Retrasă din',
    grantedBy: 'cerere din',
    noExemptions: 'Nicio scutire.',
    inForceAt: 'În vigoare la data',

    // Rularea lunara. Doua date: perioada de munca (luna) si data de angajament
    // (cand s-a calculat) — a doua alege parametrii, si de aceea se cere.
    runs: 'Calcul salarial',
    newRun: 'Calculează luna',
    accrualDate: 'Data calculului',
    accrualHint: 'Data la care s-a calculat plata. Ea alege cotele aplicabile, nu luna lucrată.',
    compute: 'Calculează',
    recompute: 'Recalculează',
    approve: 'Aprobă',
    approved: 'Aprobat',
    draft: 'În lucru',
    gross: 'Salariu brut',
    withheld: 'Total reținut',
    employerCharges: 'Sarcini ale angajatorului',
    net: 'Salariu net',
    // O suma care n-a putut fi calculata NU e zero. Ecranul arata motivul.
    notComputed: 'Nu s-a calculat',
    unresolvedCount: 'sume necalculate',
    incompleteHint: 'Luna nu se poate aproba cât timp există sume necalculate.',
    noRuns: 'Nicio lună calculată.',
    payslip: 'Fluturaș',
    // Documentul e generat pe server, in romana, cu conventii `ro-MD` fixe.
    // Ecranul afiseaza ce a trimis serverul; nu formateaza nimic el insusi.
    payslipTitle: 'Fluturaș de salariu',
    basis: 'Bază',
    rate: 'Cotă',
    parameter: 'Parametru',
    budgetFunded: 'Angajator bugetar',
    budgetFundedHint: 'Anexa nr. 1 pct. 1.1: 29% bugetar, 24% privat. Alege cota, deci se cere.',

    // Darea de seama unificata. Art. 5 alin. (1) din Legea nr. 489/1999: evidenta
    // nominala si calcularea CAS sunt PARTE COMPONENTA a dării de seamă — un
    // singur document, nu trei rapoarte.
    ipc: 'Darea de seamă lunară',
    ipcGenerate: 'Generează darea de seamă',
    ipcVersion: 'Versiunea',
    ipcPrimary: 'Primară',
    ipcCorrected: 'Corectată',
    ipcCorrects: 'corectează versiunea',
    // Art. 188: corectarea se face prin dare de seama corectata, nu prin editare.
    ipcCorrect: 'Dare de seamă corectată',
    ipcDueOn: 'Termen',
    ipcSubmit: 'Marchează depusă',
    ipcSubmittedOn: 'Depusă la',
    ipcSubmitted: 'Depusă',
    ipcHeader: 'Antet',
    fiscalCode: 'Cod fiscal',
    cuatm: 'CUATM',
    caem: 'CAEM',
    ipcMissingCode: 'lipsește',
    ipcTotals: 'Totaluri',
    ipcNominal: 'Evidența nominală',
    incomeSource: 'Codul sursei de venit',
    tariffRow: 'Rândul de tarif',
    incomePaid: 'Venit îndreptat spre achitare',
    taxWithheld: 'Impozit reținut',
    healthWithheld: 'Prime AOAM reținute',
    contribution: 'Contribuții CAS',
    insuredIncome: 'Baza de calcul',
    insuredCategory: 'Categoria persoanei asigurate',
    // Anexa nr. 3 (clasificatorul categoriilor) nu e obtinuta: coloana ramane
    // goala, nu se ghiceste un cod.
    insuredCategoryMissing: 'Clasificatorul categoriilor nu e disponibil.',
    cpas: 'CPAS',
    workedPeriod: 'Perioada',
    // Reconcilierea, ambele sensuri.
    reconciliation: 'Reconcilierea populației',
    reconciliationOk: 'Fiecare persoană cu sarcină CAS are rând nominal, și invers.',
    reconciliationMissing: 'Cu sarcină CAS, fără rând nominal',
    reconciliationExtra: 'Cu rând nominal, fără sarcină CAS',
    reconciliationCounts: 'persoane comparate',
    noDeclarations: 'Nicio dare de seamă.',
    // Formularul propriu-zis nu se randeaza: Anexa nr. 1 nu e in repo.
    ipcFormMissing:
      'Formularul tipizat nu se generează încă: textul Anexei nr. 1 la Ordinul MF nr. 94/2020 nu este disponibil. Ce se vede aici este registrul din care se completează.',
  },
  journals: {
    // Jurnalul documentelor, NU registrele statutare de TVA: acelea au forma
    // prescrisa de act si coloane care nu se pot completa cat timp niciun
    // document nu poarta TVA. Se spune pe ecran, ca sa nu fie depus ca altceva.
    title: 'Jurnalul documentelor',
    lead: 'Documentele contabilizate ale unei familii, într-o perioadă. Nu este registrul de livrări sau de procurări — acela are formă prescrisă și vine cu TVA-ul.',
    family: 'Familia',
    sales: 'Vânzări',
    purchases: 'Cumpărări',
    treasury: 'Trezorerie',
    from: 'De la',
    to: 'Până la',
    accountingDate: 'Data contabilă',
    documentDate: 'Data documentului',
    number: 'Număr',
    partner: 'Contraparte',
    net: 'Fără TVA',
    vat: 'TVA',
    total: 'Total',
    empty: 'Niciun document contabilizat în perioada aleasă.',
    exportCsv: 'Export CSV',
    totalsFromServer: 'Totalurile vin de la server, din aceeași sursă ca exportul.',
  },
  settlements: {
    // Decontarea. Nu misca niciun sold: raspunde la „care factura".
    title: 'Solduri deschise',
    lead: 'Ce a rămas de stins, și banii care încă nu arată spre nimic.',
    documents: 'Documente cu sold',
    movements: 'Mișcări nealocate',
    date: 'Data',
    kind: 'Fel',
    number: 'Număr',
    outstanding: 'Rest',
    invoiceIssued: 'Factură emisă',
    invoiceReceived: 'Factură primită',
    chosenDocument: 'Documentul ales',
    chosenMovement: 'Mișcarea aleasă',
    amount: 'Suma decontată',
    match: 'Decontează',
    noDocuments: 'Niciun document cu sold deschis.',
    noMovements: 'Nicio mișcare nealocată.',
    // Se spune pe ecran fiindca e contraintuitiv: potrivirea nu produce nicio
    // inregistrare contabila. Soldul se miscase deja, la contabilizarea miscarii.
    noLedgerEffect:
      'Decontarea nu produce nicio înregistrare contabilă: soldul s-a mișcat deja când mișcarea a fost contabilizată. Ce adaugă este răspunsul la „care document".',
  },
  treasury: {
    // Trezoreria. O singura lista pentru ambele sensuri: cine se uita la banii
    // companiei ii vrea in ordinea datelor, nu in doua ecrane pe care le
    // intercaleaza in cap.
    title: 'Încasări și plăți',
    lead: 'Banii intrați și ieșiți, în ordinea datelor.',
    add: 'Mișcare nouă',
    number: 'Număr',
    documentDate: 'Data',
    partner: 'Partener',
    direction: 'Sens',
    receipt: 'Încasare',
    payment: 'Plată',
    // Contul de trezorerie e al instrumentului, nu al documentului.
    where: 'Unde',
    whereHint:
      'Unde au intrat sau ieșit efectiv banii. Contul de trezorerie e al instrumentului, nu al facturii: aceeași încasare intră în casă sau în cont după cum s-a predat.',
    cash: 'Casă',
    bank: 'Cont curent',
    resident: 'Partener rezident',
    residentHint:
      'Alege contul de creanțe sau de datorii. Fișa partenerului nu poartă rezidența, deci se cere aici.',
    amount: 'Suma',
    create: 'Înregistrează mișcarea',
    state: 'Stare',
    draft: 'În lucru',
    confirmed: 'Validată',
    posted: 'Contabilizată',
    cancelled: 'Anulată',
    record: 'Validează și contabilizează',
    recorded: 'Contabilizată',
    empty: 'Nicio mișcare de trezorerie.',
    // Se spune pe ecran, fiindca e o asteptare pe care altfel si-o face omul:
    // banii sting soldul, dar nu se leaga inca de o factura anume.
    noSettlementYet:
      'Mișcarea reduce soldul partenerului. Legarea de o factură anume — decontarea — vine separat.',
  },
  purchases: {
    // Factura primita. Doua numere pe acelasi rand: al furnizorului, care e pe
    // hartie, si al nostru, alocat la validare. Un registru care arata doar unul
    // nu se poate confrunta nici cu copia furnizorului, nici cu numerotarea proprie.
    title: 'Facturi primite',
    lead: 'Documentul furnizorului, înregistrat cu numărul lui și cu al nostru.',
    add: 'Factură primită',
    supplierNumber: 'Numărul furnizorului',
    supplierNumberHint:
      'Numărul de pe documentul primit. Nu se alocă de noi și nu urmează seria noastră.',
    supplierDate: 'Data furnizorului',
    ourNumber: 'Numărul nostru',
    documentDate: 'Data înregistrării',
    partner: 'Furnizor',
    // Destinatia costului: alege contul de cheltuieli. Nu se deduce din nimic.
    destination: 'Destinația costului',
    destinationHint:
      'Alege contul de cheltuieli. Nu se poate deduce: o factură de servicii nu spune singură dacă serviciul a fost administrativ sau comercial.',
    administrative: 'Administrativă',
    commercial: 'Comercială',
    productionDirect: 'Producție — de bază',
    productionIndirect: 'Producție — indirectă',
    resident: 'Furnizor rezident',
    residentHint:
      'Alege contul de datorii. Fișa partenerului nu poartă rezidența, deci se cere aici.',
    lineDescription: 'Descriere',
    quantity: 'Cantitate',
    unitPrice: 'Preț unitar',
    addLine: 'Adaugă linie',
    create: 'Înregistrează documentul',
    total: 'Total',
    state: 'Stare',
    draft: 'În lucru',
    confirmed: 'Validată',
    posted: 'Contabilizată',
    cancelled: 'Anulată',
    record: 'Validează și contabilizează',
    recorded: 'Contabilizată',
    empty: 'Nicio factură primită.',
    totalsFromServer: 'Totalurile vin de la server, din aceeași sursă ca registrul.',
  },
  sales: {
    // Factura emisa. Fara TVA la pasul 5 — regimul e `fara_tva` pe fiecare linie,
    // iar tratamentul cu TVA e al pasului 6.
    title: 'Facturi emise',
    lead: 'Documentul emis de noi, cu numărul din seria proprie.',
    // Nota de credit e tot un document de vanzare, cu natura retur (ADR-073 §7):
    // aceleasi linii, acelasi ciclu, alt cont de contrapartida.
    nature: 'Fel',
    invoice: 'Factură',
    creditNote: 'Notă de credit',
    natureHint:
      'Nota de credit reduce creanța pe contul de returnări și reduceri, nu pe cel de venit: veniturile rămân cât s-a vândut.',
    add: 'Factură nouă',
    number: 'Număr',
    documentDate: 'Data facturii',
    accountingDate: 'Data contabilă',
    partner: 'Client',
    state: 'Stare',
    draft: 'În lucru',
    confirmed: 'Validată',
    posted: 'Contabilizată',
    cancelled: 'Anulată',
    // Cele doua discriminatoare care aleg conturile. Fara implicit, fiindca
    // niciunul nu se poate deduce din fisa partenerului.
    revenueKind: 'Ce se vinde',
    services: 'Servicii',
    goods: 'Mărfuri',
    products: 'Produse',
    goodsHint: 'Mărfurile și produsele cer descărcarea de gestiune, care vine cu stocurile.',
    resident: 'Client rezident',
    residentHint: 'Alege contul de creanțe: în țară sau peste hotare. Nu se deduce din fișa clientului.',
    lineDescription: 'Descrierea',
    quantity: 'Cantitate',
    unitPrice: 'Preț unitar',
    addLine: 'Adaugă linie',
    net: 'Valoare',
    total: 'Total',
    create: 'Creează factura',
    issue: 'Validează și contabilizează',
    issued: 'Contabilizată',
    entry: 'Înregistrarea contabilă',
    empty: 'Nicio factură.',
    // Serverul calculeaza randul si totalurile; ecranul nu aduna nimic (C19).
    totalsFromServer: 'Totalurile vin de la server.',
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
    'tenancy.company_permission_denied':
      'Nu aveți dreptul necesar asupra acestei companii.',
    'tenancy.company_field_not_editable':
      'Acest câmp nu se modifică din interfață: a plecat pe documente sau stă sub registrul deja postat.',
    'tenancy.company_not_active': 'Compania este închisă și nu se mai modifică.',
    'periods.company_not_postable':
      'Compania nu mai primește înregistrări. Registrele rămân de citit.',
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
    // Refuzul spune și ieșirea, fiindcă altfel omul rămâne blocat pe un ecran
    // care zice „nu" fără să zică „ci cum".
    'partners.name_collision':
      'Există deja un partener cu această denumire și fără IDNO. Completați IDNO-ul la unul dintre ei, sau folosiți fișa existentă.',
    'partners.not_found': 'Partenerul nu a fost găsit.',
    // Salarizare. Fiecare cod exista in `operations/payroll/services/`.
    'payroll.employee_malformed': 'Datele persoanei nu au forma cerută.',
    'payroll.employee_duplicate': 'Compania are deja o fișă pentru această persoană.',
    'payroll.employee_not_found': 'Persoana nu a fost găsită.',
    'payroll.contract_malformed': 'Datele contractului nu au forma cerută.',
    'payroll.contract_number_taken': 'Există deja un contract cu acest număr.',
    'payroll.contract_not_found': 'Contractul nu a fost găsit.',
    'payroll.contract_already_ended': 'Contractul a încetat deja.',
    'payroll.clause_date_required': 'Alegeți data la care se citește contractul.',
    'payroll.timesheet_malformed': 'Datele pontajului nu au forma cerută.',
    'payroll.timesheet_exists': 'Luna este deja deschisă.',
    'payroll.timesheet_not_found': 'Pontajul nu a fost găsit.',
    'payroll.timesheet_closed': 'Luna este închisă; zilele ei nu se mai schimbă.',
    'payroll.exemption_malformed': 'Datele cererii de scutire nu au forma cerută.',
    'payroll.exemption_overlap': 'Scutirea este deja în vigoare pentru această perioadă.',
    'payroll.exemption_not_found': 'Scutirea nu a fost găsită.',
    'payroll.run_malformed': 'Datele rulării nu au forma cerută.',
    'payroll.run_exists': 'Luna are deja o rulare.',
    'payroll.run_not_found': 'Rularea nu a fost găsită.',
    'payroll.run_not_draft': 'Rularea este aprobată; liniile ei nu se mai schimbă.',
    'payroll.run_incomplete':
      'Rularea are sume necalculate. Se aprobă doar când e completă.',
    'tax.ipc_malformed': 'Datele dării de seamă nu au forma cerută.',
    'tax.ipc_exists':
      'Luna are deja o dare de seamă primară. O schimbare se face prin dare de seamă corectată.',
    'tax.ipc_not_found': 'Darea de seamă nu a fost găsită.',
    'tax.ipc_nothing_to_declare':
      'Luna nu are o rulare de salarii aprobată. O dare de seamă goală ar declara că nimeni nu a fost asigurat.',
    'tax.ipc_submitted': 'Darea de seamă este deja marcată ca depusă.',
    'sales.malformed': 'Datele facturii nu au forma cerută.',
    'purchases.supplier_reference_required':
      'Documentul furnizorului are nevoie de numărul lui: fără el, aceeași factură nu poate fi recunoscută dacă ajunge a doua oară.',
    'purchases.supplier_document_already_recorded':
      'Această factură a furnizorului este deja înregistrată în această companie.',
    'purchases.cost_destination_invalid':
      'Destinația costului lipsește sau nu este una dintre cele patru.',
    'purchases.discriminator_missing':
      'Documentul nu spune unde cade costul sau a cui este datoria.',
    'purchases.not_recordable': 'Documentul nu este într-o stare din care se poate contabiliza.',
    'purchases.posting_payload_invalid': 'Datele facturii primite nu au forma cerută.',
    'treasury.account_invalid': 'Alegeți unde au intrat sau ieșit banii: casă sau cont curent.',
    'treasury.amount_invalid':
      'Suma unei mișcări este pozitivă. Sensul este tipul documentului, niciodată semnul.',
    'treasury.discriminator_missing':
      'Documentul nu spune unde s-au mișcat banii sau al cui cont se stinge.',
    'treasury.not_recordable': 'Mișcarea nu este într-o stare din care se poate contabiliza.',
    'treasury.posting_payload_invalid': 'Datele mișcării nu au forma cerută.',
    'settlements.refused': 'Decontarea a fost refuzată în forma cerută.',
    'settlements.not_settleable':
      'Documentele alese nu formează o decontare: o încasare stinge o creanță, o plată o datorie.',
    'settlements.over_allocated':
      'Suma depășește ce a rămas de stins pe document sau ce a rămas nealocat din mișcare.',
    'sales.not_issuable': 'Factura nu poate fi contabilizată în starea aceasta.',
    'sales.discriminator_missing':
      'Factura nu spune ce se vinde sau dacă clientul e rezident. Ambele aleg un cont.',
    'sales.cost_side_requires_inventory':
      'Vânzarea de mărfuri cere și descărcarea de gestiune, care vine cu stocurile.',
    'sales.posting_payload_invalid': 'Factura nu se poate contabiliza în forma aceasta.',
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
