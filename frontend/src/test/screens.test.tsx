/**
 * A smoke test per screen: it mounts, it asks the server what it should ask, and
 * it renders what came back.
 *
 * `fetch` is stubbed, not the API module. Stubbing `@/shared/api` would let a
 * screen and its client drift apart while every test stayed green -- the payloads
 * below are the shapes the server actually returns, copied from its serializers,
 * so a change on the wire breaks these.
 *
 * What they deliberately do not do is re-check the rules. Whether a note
 * balances, whether a period is open, whether a total is right: all of that is
 * the server's, tested there, and asserting it here would be asserting the stub.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { AccountLedgerScreen } from '@/app/accounting/AccountLedgerScreen'
import { AccountScreen } from '@/app/accounting/AccountScreen'
import { CorrespondenceScreen } from '@/app/accounting/CorrespondenceScreen'
import { GeneralLedgerScreen } from '@/app/accounting/GeneralLedgerScreen'
import { ChartOfAccountsScreen } from '@/app/accounting/ChartOfAccountsScreen'
import { ChartSetupScreen } from '@/app/accounting/ChartSetupScreen'
import { ManualEntryScreen } from '@/app/accounting/ManualEntryScreen'
import { OpeningBalancesScreen } from '@/app/accounting/OpeningBalancesScreen'
import { OperationTemplatesScreen } from '@/app/accounting/OperationTemplatesScreen'
import { RegisterScreen } from '@/app/accounting/RegisterScreen'
import { TrialBalanceScreen } from '@/app/accounting/TrialBalanceScreen'
import { CompaniesScreen } from '@/app/companies/CompaniesScreen'
import { PartnersScreen } from '@/app/partners/PartnersScreen'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderScreen } from './render'

const COMPANY = '11111111-1111-1111-1111-111111111111'
const ACCOUNT = '22222222-2222-2222-2222-222222222222'
const ACCOUNT_B = '33333333-3333-3333-3333-333333333333'

const COMPANIES = [
  {
    id: COMPANY,
    legal_name: 'Test Vertical SRL',
    idno: '1013600012345',
    functional_currency: 'MDL',
  },
]

const ACCOUNTS = [
  {
    id: ACCOUNT,
    account_code: '242',
    name_ro: 'Conturi curente în monedă națională',
    parent_id: null,
    origin: 'system',
    template_account_id: null,
    account_class: 'asset',
    normal_balance: 'debit',
    allows_subaccounts: false,
    currency_tracking: false,
    quantity_tracking: false,
    required_dimensions: [],
    is_blocked: false,
    valid_from: '2020-01-01',
    valid_to: null,
  },
]

/** Answers by path, in the shapes the server's serializers produce. */
function stubFetch(routes: Record<string, unknown>, status = 200) {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const match = Object.keys(routes).find((path) => url.startsWith(path))
    if (match === undefined) {
      return new Response(JSON.stringify({ code: 'api.not_found' }), { status: 404 })
    }
    return new Response(JSON.stringify(routes[match]), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ecranele', () => {
  it('lista de companii afișează denumirea legală și IDNO', async () => {
    stubFetch({ '/api/v1/companies': COMPANIES })
    renderScreen(<CompaniesScreen />)

    expect(await screen.findByText('Test Vertical SRL')).toBeInTheDocument()
    expect(screen.getByText('1013600012345')).toBeInTheDocument()
  })

  it('planul de conturi cere conturile companiei din cale', async () => {
    const fetcher = stubFetch({
      '/api/v1/companies': COMPANIES,
      [`/api/v1/accounting/coa/companies/${COMPANY}/chart`]: {
        id: 'c', company_id: COMPANY, template_id: 't', instantiated_at: '2026-01-01',
        last_propagation_at: null,
      },
      [`/api/v1/accounting/coa/companies/${COMPANY}/accounts`]: ACCOUNTS,
      '/api/v1/accounting/coa/templates': [],
    })
    renderScreen(<ChartOfAccountsScreen />, {
      path: '/companii/:companyId/plan-de-conturi',
      route: `/companii/${COMPANY}/plan-de-conturi`,
    })

    expect(await screen.findByText('Conturi curente în monedă națională')).toBeInTheDocument()
    // The company from the path, never from state: the request has to name it.
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(([url]) => String(url).includes(`companies/${COMPANY}/accounts`)),
      ).toBe(true),
    )
  })

  it('inițializarea planului listează versiunile publicate cu actul lor', async () => {
    stubFetch({
      '/api/v1/companies': COMPANIES,
      '/api/v1/accounting/coa/templates': [
        {
          id: 't1', code: 'SNC', version: '2020', valid_from: '2020-01-01', valid_to: null,
          source_act: 'Ordinul MF nr. 119 din 06.08.2013',
          source_reference: 'MO nr. 177-181', published_at: '2013-08-16', status: 'published',
        },
      ],
      // The chart route is deliberately absent: an unmatched path answers 404
      // `api.not_found`, which is exactly the state this screen exists for -- a
      // company with no chart yet. Returning a 200 whose body said "not found"
      // was the first version, and it made the screen report the opposite.
    })
    renderScreen(<ChartSetupScreen />, {
      path: '/companii/:companyId/plan-de-conturi/initializare',
      route: `/companii/${COMPANY}/plan-de-conturi/initializare`,
    })

    expect(await screen.findByText('Ordinul MF nr. 119 din 06.08.2013')).toBeInTheDocument()
  })

  it('fișa contului arată contul și refuză redenumirea unui cont din plan', async () => {
    stubFetch({ [`/api/v1/accounting/coa/accounts/${ACCOUNT}`]: ACCOUNTS[0] })
    renderScreen(<AccountScreen />, {
      path: '/companii/:companyId/conturi/:accountId',
      route: `/companii/${COMPANY}/conturi/${ACCOUNT}`,
    })

    expect(await screen.findByText('242')).toBeInTheDocument()
    // A system account is not renamed, and the screen says so instead of showing
    // a control the server would refuse.
    expect(
      screen.getByText(/Conturile din plan se mențin centralizat/),
    ).toBeInTheDocument()
  })

  it('nota manuală blochează postarea cât timp nu e echilibrată', async () => {
    stubFetch({ [`/api/v1/accounting/coa/companies/${COMPANY}/accounts`]: ACCOUNTS })
    renderScreen(<ManualEntryScreen />, {
      path: '/companii/:companyId/note',
      route: `/companii/${COMPANY}/note`,
    })

    expect(await screen.findByRole('button', { name: 'Postează nota' })).toBeDisabled()
  })

  it('o notă de cinci rânduri se introduce și se postează fără mouse (F1.G2, criteriul 1)', async () => {
    const second = { ...ACCOUNTS[0]!, id: ACCOUNT_B, account_code: '611', name_ro: 'Venituri din vânzări' }
    const fetcher = stubFetch({
      [`/api/v1/accounting/coa/companies/${COMPANY}/accounts`]: [ACCOUNTS[0], second],
      '/api/v1/accounting/entries/manual': {
        accounting_event_id: 'e', journal_entry_id: 'j', posted_now: true,
      },
    })
    renderScreen(<ManualEntryScreen />, {
      path: '/companii/:companyId/note',
      route: `/companii/${COMPANY}/note`,
    })
    await screen.findByRole('grid', { name: 'Notă contabilă manuală' })

    fireEvent.change(screen.getByLabelText('Descriere'), { target: { value: 'Nota de test' } })

    // Keyboard only from here: Enter advances and, on the last field, opens the
    // next line; F4 finds the account by code; point and comma both post.
    const grid = screen.getByRole('grid', { name: 'Notă contabilă manuală' })
    fireEvent.click(screen.getByRole('gridcell', { name: 'Cont 1' }))
    // The chart arrives asynchronously; the lookup is empty until it does, and
    // a lookup with nothing to match refuses the commit -- correctly.
    fireEvent.keyDown(grid, { key: 'F4' })
    await within(grid).findAllByRole('option')
    fireEvent.keyDown(within(grid).getByRole('textbox'), { key: 'Escape' })
    const lines: [string, string, string][] = [
      ['242', '100,5', ''],
      ['242', '200.25', ''],
      ['611', '', '150'],
      ['611', '', '100,75'],
      ['611', '', '50'],
    ]
    for (const [code, debit, credit] of lines) {
      fireEvent.keyDown(grid, { key: 'F4' })
      fireEvent.change(within(grid).getByRole('textbox'), { target: { value: code } })
      fireEvent.keyDown(within(grid).getByRole('textbox'), { key: 'Enter' })
      fireEvent.keyDown(grid, { key: 'Enter' }) // explanation: left empty
      for (const value of [debit, credit]) {
        if (value === '') {
          fireEvent.keyDown(grid, { key: 'Enter' })
        } else {
          fireEvent.keyDown(grid, { key: value[0]! })
          fireEvent.change(within(grid).getByRole('textbox'), { target: { value } })
          fireEvent.keyDown(within(grid).getByRole('textbox'), { key: 'Enter' })
        }
      }
    }
    expect(screen.getByText('Echilibrat')).toBeInTheDocument()

    fireEvent.keyDown(grid, { key: 'Enter', ctrlKey: true })

    await waitFor(() =>
      expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/entries/manual'))).toBe(true),
    )
    const posted = fetcher.mock.calls.find(([url]) => String(url).endsWith('/entries/manual'))
    const [, init] = posted as unknown as [string, RequestInit]
    const body = JSON.parse(String(init.body))
    expect(body.lines).toEqual([
      { account_id: ACCOUNT, debit: '100.5', credit: '0' },
      { account_id: ACCOUNT, debit: '200.25', credit: '0' },
      { account_id: ACCOUNT_B, debit: '0', credit: '150' },
      { account_id: ACCOUNT_B, debit: '0', credit: '100.75' },
      { account_id: ACCOUNT_B, debit: '0', credit: '50' },
    ])
    expect(await screen.findByText('Nota a fost postată.')).toBeInTheDocument()
  })

  it('fișa contului arată un rând per document cu corespondența și soldul serverului', async () => {
    stubFetch({
      [`/api/v1/accounting/ledger/companies/${COMPANY}/accounts/${ACCOUNT}/ledger`]: {
        account_id: ACCOUNT, account_code: '242', name_ro: 'Conturi curente',
        start_date: '2026-01-01', end_date: '2026-12-31', opening: '10.0000', truncated: false,
        rows: [
          {
            journal_entry_id: 'j1', entry_number: 'NC-2026-0001', accounting_date: '2026-01-10',
            document_date: '2026-01-10', entry_type: 'standard', description: 'Încasare',
            debit: '120.0000', credit: '0.0000', balance: '130.0000', has_formulas: true,
            reverses_entry_id: null, reversed_by_entry_id: null,
            correspondents: [{ account_id: 'x', account_code: '221', debit: '120.0000', credit: '0.0000' }],
          },
        ],
        total_debit: '120.0000', total_credit: '0.0000', closing: '130.0000',
      },
    })
    renderScreen(<AccountLedgerScreen />, {
      path: '/companii/:companyId/conturi/:accountId/fisa',
      route: `/companii/${COMPANY}/conturi/${ACCOUNT}/fisa`,
    })

    expect(await screen.findByText('NC-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('221')).toBeInTheDocument()
    // Server figures, rendered as they came: the running balance and the closing.
    expect(screen.getAllByText('130,00').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/ledger?from=') as string,
    )
  })

  it('Cartea Mare arată lunile cu rulajele în corespondență și partea neexplicată', async () => {
    stubFetch({
      [`/api/v1/accounting/ledger/companies/${COMPANY}/accounts/${ACCOUNT}/general-ledger`]: {
        account_id: ACCOUNT, account_code: '242', name_ro: 'Conturi curente',
        start_date: '2026-01-01', end_date: '2026-12-31', opening: '0.0000',
        months: [
          {
            period_id: 'p1', period_no: 1, start_date: '2026-01-01', end_date: '2026-01-31',
            opening: '0.0000', debit: '57.0000', credit: '0.0000', closing: '57.0000',
            debit_by: [{ account_id: 'x', account_code: '221', amount: '50.0000' }],
            credit_by: [], debit_unassigned: '7.0000', credit_unassigned: '0.0000',
          },
        ],
        total_debit: '57.0000', total_credit: '0.0000', closing: '57.0000',
      },
    })
    renderScreen(<GeneralLedgerScreen />, {
      path: '/companii/:companyId/conturi/:accountId/cartea-mare',
      route: `/companii/${COMPANY}/conturi/${ACCOUNT}/cartea-mare`,
    })

    expect(await screen.findByText(/Luna 1/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '221' })).toBeInTheDocument()
    expect(screen.getByText('fără corespondență (note manuale)')).toBeInTheDocument()
    expect(screen.getByText('7,00')).toBeInTheDocument()
  })

  it('rulajele pe corespondențe listează perechile și spun ce nu explică', async () => {
    stubFetch({
      [`/api/v1/accounting/ledger/companies/${COMPANY}/correspondence`]: {
        start_date: '2026-01-01', end_date: '2026-12-31',
        cells: [
          { debit_account_id: 'a', debit_code: '221', credit_account_id: 'b', credit_code: '611', amount: '300.0000' },
        ],
        debit_totals: [], credit_totals: [],
        total: '300.0000', lines_total: '307.0000', unassigned: '7.0000',
      },
    })
    renderScreen(<CorrespondenceScreen />, {
      path: '/companii/:companyId/rulaje',
      route: `/companii/${COMPANY}/rulaje`,
    })

    const grid = await screen.findByRole('table')
    expect(within(grid).getByText('611')).toBeInTheDocument()
    expect(within(grid).getByText('Total corespondențe')).toBeInTheDocument()
    expect(screen.getByText('7,00')).toBeInTheDocument()
  })

  it('partenerii se listează cu rolurile lor, iar unul retras se poate reactiva', async () => {
    stubFetch({
      '/api/v1/masterdata/partners/': [
        {
          id: 'p1', legal_name: 'Client SRL', short_name: 'Client', kind: 'legal_entity',
          idno: '1003600011111', idnp: null, vat_code: null,
          is_customer: true, is_supplier: false, is_active: true,
        },
        {
          id: 'p2', legal_name: 'Furnizor Retras SRL', short_name: null, kind: 'legal_entity',
          idno: '1003600022222', idnp: null, vat_code: null,
          is_customer: false, is_supplier: true, is_active: false,
        },
      ],
    })
    renderScreen(<PartnersScreen />, { path: '/parteneri', route: '/parteneri' })

    expect(await screen.findByText(/Client SRL/)).toBeInTheDocument()
    expect(screen.getByText('Furnizor')).toBeInTheDocument()
    // Retragerea nu sterge: randul ramane, iar butonul propune inversul starii.
    expect(screen.getByText('Retras')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reactivează' })).toBeInTheDocument()
  })

  it('șabloanele arată ce cer la postare, iar unul retras nu se poate folosi', async () => {
    stubFetch({
      [`/api/v1/accounting/coa/companies/${COMPANY}/accounts`]: ACCOUNTS,
      [`/api/v1/accounting/entries/companies/${COMPANY}/templates`]: [
        {
          id: 'tpl1', name: 'Încasare de la client', entry_description: 'Încasare',
          is_active: true, inputs: ['suma'], line_count: 2,
        },
        {
          id: 'tpl2', name: 'Șablon retras', entry_description: 'Vechi',
          is_active: false, inputs: [], line_count: 2,
        },
      ],
    })
    renderScreen(<OperationTemplatesScreen />, {
      path: '/companii/:companyId/sabloane',
      route: `/companii/${COMPANY}/sabloane`,
    })

    expect(await screen.findByText('Încasare de la client')).toBeInTheDocument()
    // Valorile cerute la postare sunt pe listă, nu descoperite la apăsare.
    expect(screen.getByText(/Valori cerute la postare: suma/)).toBeInTheDocument()
    // Unul singur poate fi folosit: cel retras nu produce înregistrări noi, deci
    // nu oferă butonul.
    expect(screen.getAllByRole('button', { name: 'Folosește' })).toHaveLength(1)
    expect(screen.getByText('Retras')).toBeInTheDocument()
  })

  it('soldurile inițiale arată lotul, totalurile lui și formularele de partener', async () => {
    const BATCH = '33333333-3333-4333-8333-333333333333'
    stubFetch({
      [`/api/v1/accounting/coa/companies/${COMPANY}/accounts`]: ACCOUNTS,
      '/api/v1/masterdata/partners/': [
        {
          id: 'p1', legal_name: 'Client SRL', short_name: null, kind: 'legal_entity',
          idno: '1003600011111', idnp: null, vat_code: null,
          is_customer: true, is_supplier: false, is_active: true,
        },
      ],
      [`/api/v1/accounting/opening-balances/${BATCH}`]: {
        id: BATCH, company_id: COMPANY, as_of_date: '2026-01-01', source: 'onec_import',
        status: 'draft', counterpart_account_id: ACCOUNT,
        gl: [{ account_id: ACCOUNT, debit: '5000.0000', credit: '0', currency: null }],
        receivables: [], payables: [], decomposition: {},
      },
    })
    renderScreen(<OpeningBalancesScreen />, {
      path: '/companii/:companyId/solduri-initiale/:batchId',
      route: `/companii/${COMPANY}/solduri-initiale/${BATCH}`,
    })

    expect(await screen.findByText('Import 1C')).toBeInTheDocument()
    expect(screen.getByText('În lucru')).toBeInTheDocument()
    // Setul nu se închide (5000 debit, 0 credit) — și ecranul spune că
    // contrapartida NU absoarbe diferența, fiindcă serverul o refuză.
    expect(screen.getByText(/Contrapartida nu absoarbe diferența/)).toBeInTheDocument()
    // Creanțele și datoriile există de când există directorul de parteneri, iar
    // partenerul se caută, nu se tastează ca identificator.
    expect(screen.getByText('Creanțe')).toBeInTheDocument()
    expect(screen.getByText('Datorii')).toBeInTheDocument()
    expect(await screen.findByRole('option', { name: /Client SRL/ })).toBeInTheDocument()
  })

  it('registrul arată înregistrarea cu rândurile ei și spune dacă e stornată', async () => {
    stubFetch({
      [`/api/v1/accounting/ledger/companies/${COMPANY}/entries`]: {
        start_date: '2026-01-01',
        end_date: '2026-12-31',
        truncated: false,
        entries: [
          {
            id: 'e1', entry_number: 'NC-2026-000001', accounting_date: '2026-03-07',
            description: 'Aport la capitalul social', status: 'posted', entry_type: 'manual',
            total_debit: '5000.0000', total_credit: '5000.0000',
            reverses_entry_id: null, reversed_by_entry_id: 'e2',
            accounting_event_id: 'ev1',
            lines: [
              {
                line_number: 1, account_id: ACCOUNT, account_code: '242',
                name_ro: 'Conturi curente în monedă națională',
                debit: '5000.0000', credit: '0', description: null,
              },
            ],
          },
        ],
      },
    })
    renderScreen(<RegisterScreen />, {
      path: '/companii/:companyId/registru',
      route: `/companii/${COMPANY}/registru`,
    })

    expect(await screen.findByText('NC-2026-000001')).toBeInTheDocument()
    expect(screen.getByText('Aport la capitalul social')).toBeInTheDocument()
    // R14 în ambele sensuri: ecranul spune că a fost stornată, în loc să lase
    // cititorul să deducă dintr-o a doua înregistrare cu semn opus.
    expect(screen.getByText('Stornată')).toBeInTheDocument()
    // Și, fiind deja stornată, nu mai oferă butonul: serverul ar refuza al
    // doilea storno, iar un control care se refuză la apăsare e o minciună de
    // interfață.
    expect(screen.queryByRole('button', { name: 'Stornează' })).not.toBeInTheDocument()
  })

  it('balanța afișează totalurile serverului, nu ale ei', async () => {
    stubFetch({
      [`/api/v1/accounting/ledger/companies/${COMPANY}/trial-balance`]: {
        start_date: '2026-01-01',
        end_date: '2026-12-31',
        rows: [
          {
            account_id: ACCOUNT, account_code: '242',
            name_ro: 'Conturi curente în monedă națională',
            opening: '0', debit: '5000.0000', credit: '0', closing: '5000.0000',
          },
        ],
        total_debit: '5000.0000',
        total_credit: '5000.0000',
        balanced: true,
      },
    })
    renderScreen(<TrialBalanceScreen />, {
      path: '/companii/:companyId/balanta',
      route: `/companii/${COMPANY}/balanta`,
    })

    expect(await screen.findByText('Balanța este echilibrată.')).toBeInTheDocument()
    // Formatted ro-MD, from the string the server sent -- never parsed to a float.
    expect(screen.getAllByText('5.000,00').length).toBeGreaterThan(0)
  })

  it('fără sesiune, aplicația arată ecranul de autentificare', async () => {
    stubFetch({ '/api/v1/auth/whoami': { code: 'auth.required' } }, 401)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('button', { name: 'Intră în cont' })).toBeInTheDocument()
  })
})
