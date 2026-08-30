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
import { CompanyNav } from '@/app/layout/CompanyNav'
import { PartnersScreen } from '@/app/partners/PartnersScreen'
import { ContractsScreen } from '@/app/payroll/ContractsScreen'
import { ExemptionsScreen } from '@/app/payroll/ExemptionsScreen'
import { IpcScreen } from '@/app/payroll/IpcScreen'
import { PayrollRunScreen } from '@/app/payroll/PayrollRunScreen'
import { PeopleScreen } from '@/app/payroll/PeopleScreen'
import { TimesheetScreen } from '@/app/payroll/TimesheetScreen'
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

  it('lista de angajați cere persoanele companiei din cale', async () => {
    const fetcher = stubFetch({
      [`/api/v1/payroll/companies/${COMPANY}/employees`]: [
        {
          id: 'e1',
          last_name: 'Rusu',
          first_name: 'Ion',
          idnp: '2001234567890',
          identity_document_type: null,
          identity_document_number: null,
          tax_residency: 'resident',
          social_insurance_code: null,
        },
      ],
    })
    renderScreen(<PeopleScreen />, {
      path: '/companii/:companyId/angajati',
      route: `/companii/${COMPANY}/angajati`,
    })

    expect(await screen.findByText('Rusu Ion')).toBeInTheDocument()
    expect(screen.getByText('2001234567890')).toBeInTheDocument()
    // The company from the path, never from state.
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(([url]) => String(url).includes(`companies/${COMPANY}/employees`)),
      ).toBe(true),
    )
  })

  it('contractele arată forma raportului cu eticheta ei, nu cu codul', async () => {
    stubFetch({
      [`/api/v1/payroll/companies/${COMPANY}/contracts`]: [
        {
          id: 'c1',
          employee_id: 'e1',
          employee_name: 'Rusu Ion',
          relationship_type: 'service_relationship',
          contract_number: 'RS-001',
          signed_on: '2026-01-05',
          effective_from: '2026-01-08',
          effective_to: null,
          ended_on: null,
          hire_order_number: '12-p',
          hire_order_date: '2026-01-06',
          termination_order_number: null,
          termination_order_date: null,
          position_title: 'Contabil',
          base_salary: '9000.0000',
          weekly_hours: '40.00',
          cas_payer_point: '1.1',
        },
      ],
    })
    renderScreen(<ContractsScreen />, {
      path: '/companii/:companyId/contracte',
      route: `/companii/${COMPANY}/contracte`,
    })

    expect(await screen.findByText('RS-001')).toBeInTheDocument()
    // The third value of ADR-071, shown as what it is rather than as its code.
    expect(
      screen.getByText('Raporturi de serviciu (act administrativ)'),
    ).toBeInTheDocument()
  })

  it('pontajul arată totalurile serverului, nu unele calculate aici', async () => {
    stubFetch({
      [`/api/v1/payroll/companies/${COMPANY}/timesheets`]: [
        { id: 'ts1', year: 2026, month: 3, norm_hours: '168.00', status: 'open' },
      ],
      '/api/v1/payroll/timesheets/ts1': {
        id: 'ts1',
        year: 2026,
        month: 3,
        norm_hours: '168.00',
        status: 'open',
        lines: [
          {
            contract_id: 'c1',
            contract_number: 'CIM-001',
            employee_name: 'Rusu Ion',
            hours_worked: '22.50',
            night_hours: '2.00',
            holiday_hours: '0.00',
            days_present: 3,
          },
        ],
      },
      [`/api/v1/payroll/companies/${COMPANY}/contracts`]: [],
    })
    renderScreen(<TimesheetScreen />, {
      path: '/companii/:companyId/pontaj',
      route: `/companii/${COMPANY}/pontaj`,
    })

    fireEvent.click(await screen.findByRole('button', { name: /2026-03/ }))
    expect(await screen.findByText('Rusu Ion')).toBeInTheDocument()
    // Exactly the string the server sent: nothing on the screen adds a column up.
    expect(screen.getByText('22.50')).toBeInTheDocument()
  })

  it('scutirile arată istoricul cu perioadele lui, nu o bifă', async () => {
    stubFetch({
      '/api/v1/payroll/employees/e1/exemptions': [
        {
          id: 'x1',
          code: 'P',
          dependent_id: null,
          dependent_name: null,
          valid_from: '2026-04-01',
          valid_to: '2026-07-01',
          granted_by_filed_on: '2026-03-17',
        },
      ],
      '/api/v1/payroll/employees/e1/dependents': [],
    })
    renderScreen(<ExemptionsScreen />, {
      path: '/companii/:companyId/angajati/:employeeId/scutiri',
      route: `/companii/${COMPANY}/angajati/e1/scutiri`,
    })

    // The period, both ends of it: a withdrawn exemption stays visible, because
    // recalculating the months it covered has to reach the same answer (`R18`).
    expect(await screen.findByText('2026-04-01')).toBeInTheDocument()
    expect(screen.getByText('2026-07-01')).toBeInTheDocument()
    // Twice on the screen: once in the form's dropdown, once in the row. The
    // count is asserted, not worked around -- the dropdown offering exactly the
    // five real codes is half of why there is no `S`.
    expect(screen.getAllByText('P — personală')).toHaveLength(2)
  })

  it('calculul salarial arată motivul, nu un zero, pentru o sumă necalculată', async () => {
    stubFetch({
      [`/api/v1/payroll/companies/${COMPANY}/runs`]: [
        { id: 'r1', year: 2026, month: 3, accrual_date: '2026-03-31', status: 'draft' },
      ],
      '/api/v1/payroll/runs/r1': {
        id: 'r1',
        year: 2026,
        month: 3,
        accrual_date: '2026-03-31',
        status: 'draft',
        unresolved: 1,
        complete: false,
        totals: { gross: '10000.00', withheld: '0', employer_charges: '0', net: '10000.00' },
        lines: [
          {
            employee_id: 'e1',
            employee_name: 'Rusu Ion',
            contract_number: 'CIM-001',
            gross: '10000.00',
            withheld: '0',
            employer_charges: '0',
            net: null,
            complete: false,
            components: [
              {
                component_key: 'salary.gross',
                nature: 'salary_accrual',
                amount: '10000.00',
                basis: null,
                rate: null,
                parameter_key: null,
                unresolved_reason: null,
              },
              {
                component_key: 'cas.employer',
                nature: 'employer_charge',
                amount: null,
                basis: null,
                rate: null,
                parameter_key: null,
                unresolved_reason: 'cnas.employer_rate: fiscal.no_parameter pe 2026-03-31',
              },
            ],
          },
        ],
      },
    })
    renderScreen(<PayrollRunScreen />, {
      path: '/companii/:companyId/salarii',
      route: `/companii/${COMPANY}/salarii`,
    })

    fireEvent.click(await screen.findByRole('button', { name: /2026-03/ }))
    expect(await screen.findByText('Rusu Ion')).toBeInTheDocument()
    // The reason the server gave, shown where a zero would have been.
    expect(
      screen.getByText(/cnas.employer_rate: fiscal.no_parameter pe 2026-03-31/),
    ).toBeInTheDocument()
    // And approval is out of reach while it is open.
    expect(screen.getByRole('button', { name: 'Aprobă' })).toBeDisabled()
  })

  it('banda companiei duce în orice secțiune a ei și lipsește în afara uneia', async () => {
    stubFetch({ '/api/v1/companies': COMPANIES })
    const mounted = renderScreen(<CompanyNav />, {
      path: '*',
      route: `/companii/${COMPANY}/balanta`,
    })

    // Denumirea legală, nu identificatorul: acela e deja în bara de adrese.
    expect(await screen.findByText('Test Vertical SRL')).toBeInTheDocument()
    // Dintr-un ecran de contabilitate se ajunge direct în salarizare: exact
    // drumul care înainte trecea înapoi prin lista de companii.
    expect(screen.getByRole('link', { name: 'Pontaj' })).toHaveAttribute(
      'href',
      `/companii/${COMPANY}/pontaj`,
    )
    expect(screen.getByRole('link', { name: 'Registrul înregistrărilor' })).toHaveAttribute(
      'href',
      `/companii/${COMPANY}/registru`,
    )
    // Și secțiunea deschisă e marcată, nu doar prezentă.
    expect(screen.getByRole('link', { name: 'Balanța de verificare' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    mounted.unmount()
    // Fără companie în adresă nu are ce arăta: antetul rămâne singurul nivel.
    renderScreen(<CompanyNav />, { path: '*', route: '/parteneri' })
    expect(screen.queryByRole('link', { name: 'Pontaj' })).not.toBeInTheDocument()
  })

  it('darea de seamă arată antetul, ambele secțiuni și reconcilierea în ambele sensuri', async () => {
    stubFetch({
      [`/api/v1/tax/ipc/companies/${COMPANY}`]: [
        {
          id: 'd1',
          year: 2026,
          month: 3,
          version_number: 2,
          corrects_id: 'd0',
          status: 'draft',
          due_on: '2026-04-25',
          submitted_on: null,
        },
      ],
      '/api/v1/tax/ipc/d1/reconciliation': {
        agrees: false,
        charged_count: 2,
        declared_count: 1,
        missing: ['11111111-1111-1111-1111-111111111112'],
        extra: [],
      },
      '/api/v1/tax/ipc/d1': {
        id: 'd1',
        year: 2026,
        month: 3,
        version_number: 2,
        corrects_id: 'd0',
        status: 'draft',
        due_on: '2026-04-25',
        submitted_on: null,
        header: { fiscal_code: '1013600012345', cuatm_code: null, caem_code: '62.01' },
        totals: [
          {
            income_source_code: 'SAL',
            cas_tariff_code: '1.1b',
            income_paid: '20000.00',
            income_tax_withheld: '5840.00',
            health_insurance_withheld: '5000.00',
            social_contribution: '10000.00',
          },
        ],
        nominal: [
          {
            line_number: 1,
            person_id: 'p1',
            name: 'Rusu Ion',
            idnp: '2001234567890',
            personal_insurance_code: null,
            work_period_start: '2026-03-01',
            work_period_end: '2026-03-31',
            insured_category_code: null,
            tariff_rate: '50.0000',
            insured_income: '10000.00',
            contribution: '5000.00',
          },
        ],
      },
    })
    renderScreen(<IpcScreen />, {
      path: '/companii/:companyId/darea-de-seama',
      route: `/companii/${COMPANY}/darea-de-seama`,
    })

    fireEvent.click(await screen.findByRole('button', { name: /2026-03/ }))
    // The header, with the code that is missing said rather than blank.
    expect(await screen.findByText('1013600012345')).toBeInTheDocument()
    expect(screen.getByText('lipsește')).toBeInTheDocument()
    // Both sections, from one document.
    expect(screen.getByText('SAL')).toBeInTheDocument()
    expect(screen.getByText('Rusu Ion')).toBeInTheDocument()
    // The category column is empty because Annex 3 is not obtained.
    expect(screen.getByText('Clasificatorul categoriilor nu e disponibil.')).toBeInTheDocument()
    // And `T1` reported, in the direction it failed.
    expect(
      screen.getByText(/Cu sarcină CAS, fără rând nominal/),
    ).toBeInTheDocument()
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
