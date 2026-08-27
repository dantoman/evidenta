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

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { AccountScreen } from '@/app/accounting/AccountScreen'
import { ChartOfAccountsScreen } from '@/app/accounting/ChartOfAccountsScreen'
import { ChartSetupScreen } from '@/app/accounting/ChartSetupScreen'
import { ManualEntryScreen } from '@/app/accounting/ManualEntryScreen'
import { TrialBalanceScreen } from '@/app/accounting/TrialBalanceScreen'
import { CompaniesScreen } from '@/app/companies/CompaniesScreen'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderScreen } from './render'

const COMPANY = '11111111-1111-1111-1111-111111111111'
const ACCOUNT = '22222222-2222-2222-2222-222222222222'

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
