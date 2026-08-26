/**
 * The chart of accounts -- the first screen in the product that shows accounting
 * data.
 *
 * It reads `/api/v1/accounting/coa/`, which has existed and been tested since
 * F1.1 with no consumer at all. That gap is why this screen exists before any
 * other: an API nobody calls is an API nobody has checked the shape of.
 *
 * **The company comes from the path, never the tenant** (C8). The tenant is the
 * host the browser is already on; the company is a resource inside it, and a
 * holding has several -- so the screen has to say which, and the server decides
 * whether the caller may reach it.
 *
 * Account names arrive from the server and are rendered as they arrive. The books
 * are kept in Romanian by law (C33, ADR-016): an account name is a stored value,
 * not an interface string, and nothing here translates one. What *is* translated
 * is the vocabulary around it -- the class, the state -- which never reaches a
 * register.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { t } from '@/locales'
import { listAccounts, type Account, type AccountClass } from '@/shared/api/coa'
import { listCompanies } from '@/shared/api/companies'
import { ApiError } from '@/shared/api/client'
import { DataGrid, type Column } from '@/shared/DataGrid'

const CLASS_LABEL: Record<AccountClass, string> = {
  asset: t.accounting.classes.asset,
  liability: t.accounting.classes.liability,
  equity: t.accounting.classes.equity,
  income: t.accounting.classes.income,
  expense: t.accounting.classes.expense,
}

/**
 * The columns. `account_code` is a code, so it reads in a monospaced face and is
 * left aligned; nothing here is numeric in the accounting sense yet, because a
 * chart carries no amounts -- the balances screen is where `numeric` starts
 * earning its keep.
 */
const columns: Column<Account>[] = [
  {
    key: 'account_code',
    header: t.accounting.chart.code,
    cell: (account) => <span className="font-mono">{account.account_code}</span>,
    width: '8rem',
  },
  {
    key: 'name_ro',
    header: t.accounting.chart.name,
    // Indented by depth so the hierarchy reads without a tree control. The chart
    // is two levels in practice; a disclosure widget would cost more than it
    // returns until somebody has a chart deep enough to need one.
    cell: (account) => (
      <span className={account.parent_id ? 'pl-6' : ''}>{account.name_ro}</span>
    ),
  },
  {
    key: 'account_class',
    header: t.accounting.chart.class,
    cell: (account) => CLASS_LABEL[account.account_class],
    width: '10rem',
  },
  {
    key: 'origin',
    header: t.accounting.chart.origin,
    cell: (account) =>
      account.origin === 'system'
        ? t.accounting.chart.originSystem
        : t.accounting.chart.originCompany,
    width: '10rem',
  },
  {
    key: 'state',
    header: t.accounting.chart.state,
    cell: (account) => {
      if (account.is_blocked) {
        return <span className="text-danger">{t.accounting.chart.blocked}</span>
      }
      if (account.valid_to) {
        return <span className="text-ink-muted">{t.accounting.chart.closed}</span>
      }
      return <span className="text-ink-muted">{t.accounting.chart.open}</span>
    },
    width: '8rem',
  },
]

export function ChartOfAccountsScreen() {
  const [companyId, setCompanyId] = useState<string | null>(null)

  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })

  // The first company only until somebody chooses. Not a default that hides the
  // choice: with more than one, the selector below is rendered and the current
  // one is named, because a screen that silently picks one of a holding's
  // companies is a screen that shows the wrong numbers convincingly.
  const selected = companyId ?? companies.data?.[0]?.id ?? null

  const accounts = useQuery({
    queryKey: ['accounts', selected],
    queryFn: () => listAccounts(selected as string),
    enabled: selected !== null,
  })

  if (companies.isPending) {
    return <p className="text-sm text-ink-muted">{t.app.loading}</p>
  }

  if (companies.isError) {
    return <Failure error={companies.error} />
  }

  if (companies.data.length === 0) {
    return <p className="text-sm text-ink-muted">{t.accounting.chart.noCompany}</p>
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <h1 className="text-base font-semibold">{t.accounting.chart.title}</h1>
        {companies.data.length > 1 && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-ink-muted">{t.accounting.chart.company}</span>
            <select
              value={selected ?? ''}
              onChange={(event) => setCompanyId(event.target.value)}
              className="rounded border border-border bg-surface px-2 text-sm"
            >
              {companies.data.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.legal_name}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      {accounts.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {accounts.isError && <Failure error={accounts.error} />}
      {accounts.data && (
        <DataGrid
          columns={columns}
          rows={accounts.data}
          rowKey={(account) => account.id}
          emptyMessage={t.accounting.chart.empty}
        />
      )}
    </section>
  )
}

/** By stable code, never by the server's message (C10). */
function Failure({ error }: { error: unknown }) {
  const failure = error instanceof ApiError ? error : null
  return (
    <p role="alert" className="text-sm text-danger">
      {failure ? failure.display : t.errors.unknown}
    </p>
  )
}
