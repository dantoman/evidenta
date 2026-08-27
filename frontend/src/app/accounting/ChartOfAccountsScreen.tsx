/**
 * The chart of accounts of one company.
 *
 * **The company is in the path, the tenant never is** (C8). The tenant is the
 * host the browser is already on; the company is a resource inside it, and the
 * server's own routes are shaped the same way. The first version kept the choice
 * in component state, which meant the chart of a particular company had no
 * address -- nothing could link to it, and a reload picked the first company in
 * the list rather than the one being read.
 *
 * Account names arrive from the server and are rendered as they arrive. The books
 * are kept in Romanian by law (C33, ADR-016): an account name is a stored value,
 * not an interface string, and nothing here translates one. What *is* translated
 * is the vocabulary around it -- the class, the state -- which never reaches a
 * register.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { t } from '@/locales'
import { date } from '@/shared/format'
import {
  getChart,
  listAccounts,
  listTemplates,
  type Account,
  type AccountClass,
} from '@/shared/api/coa'
import { listCompanies } from '@/shared/api/companies'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure, codeOf } from '@/shared/Failure'

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
function columnsFor(companyId: string): Column<Account>[] {
  return [
    {
      key: 'account_code',
      header: t.accounting.chart.code,
      cell: (account) => (
        <Link
          to={`/companii/${companyId}/conturi/${account.id}`}
          className="font-mono text-accent"
        >
          {account.account_code}
        </Link>
      ),
      width: '8rem',
    },
    {
      key: 'name_ro',
      header: t.accounting.chart.name,
      // Indented by depth so the hierarchy reads without a tree control. The
      // chart is two levels in practice; a disclosure widget would cost more
      // than it returns until somebody has a chart deep enough to need one.
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
}

export function ChartOfAccountsScreen() {
  const { companyId = '' } = useParams()
  const navigate = useNavigate()

  /**
   * The date a posting would carry, not "today".
   *
   * Empty means the whole chart, including accounts that are closed or not yet
   * open -- a screen that showed only today's accounts could not explain a
   * posting made last year. The server never substitutes today for a missing
   * date either, and for the same reason (R18).
   */
  const [on, setOn] = useState('')

  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })

  // 404 is a state here, not a failure: a company that was never initialised has
  // no chart. Retrying it would only delay the screen that says so.
  const chart = useQuery({
    queryKey: ['chart', companyId],
    queryFn: () => getChart(companyId),
    retry: false,
  })
  const templates = useQuery({
    queryKey: ['templates'],
    queryFn: listTemplates,
    enabled: chart.isSuccess,
  })

  const accounts = useQuery({
    queryKey: ['accounts', companyId, on],
    queryFn: () => listAccounts(companyId, on || undefined),
  })

  const company = companies.data?.find((row) => row.id === companyId)
  // Named, never shown as an identifier. A UUID in a header is a database key on
  // a screen; if the version cannot be named, nothing is written.
  const template = templates.data?.find((row) => row.id === chart.data?.template_id)
  const missingChart = chart.isError && codeOf(chart.error) === 'api.not_found'

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col">
          <h1 className="text-base font-semibold">{t.accounting.chart.title}</h1>
          {company && <span className="text-sm text-ink-muted">{company.legal_name}</span>}
          <nav className="flex gap-4 pt-1 text-sm">
            <Link to={`/companii/${companyId}/note`} className="text-accent">
              {t.accounting.entry.title}
            </Link>
            <Link to={`/companii/${companyId}/registru`} className="text-accent">
              {t.accounting.register.title}
            </Link>
            <Link to={`/companii/${companyId}/balanta`} className="text-accent">
              {t.accounting.balance.title}
            </Link>
          </nav>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {template && (
            <span className="text-sm text-ink-muted">
              {t.accounting.chart.version}: {template.code} {template.version}
            </span>
          )}
          {companies.data && companies.data.length > 1 && (
            <label className="flex items-center gap-2 text-sm">
              <span className="text-ink-muted">{t.accounting.chart.company}</span>
              <select
                value={companyId}
                onChange={(event) =>
                  void navigate(`/companii/${event.target.value}/plan-de-conturi`)
                }
                className="rounded border border-border bg-surface px-2 text-sm"
              >
                {companies.data.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.legal_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="flex items-center gap-2 text-sm">
            <span className="text-ink-muted">{t.accounting.chart.postableOn}</span>
            <input
              type="date"
              value={on}
              onChange={(event) => setOn(event.target.value)}
              className="rounded border border-border bg-surface px-2 text-sm"
            />
          </label>
          {on && (
            <button
              type="button"
              onClick={() => setOn('')}
              className="text-sm text-accent"
            >
              {t.accounting.chart.postableAll}
            </button>
          )}
        </div>
      </header>

      {on && (
        <p className="text-sm text-ink-muted">
          {t.accounting.chart.postableNote} ({date(on)})
        </p>
      )}

      {missingChart && (
        <p className="text-sm">
          <span className="text-ink-muted">{t.accounting.chart.empty} </span>
          <Link
            to={`/companii/${companyId}/plan-de-conturi/initializare`}
            className="text-accent"
          >
            {t.accounting.chart.initialize}
          </Link>
        </p>
      )}
      {chart.isError && !missingChart && <Failure error={chart.error} />}
      {companies.isError && <Failure error={companies.error} />}

      {accounts.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {accounts.isError && <Failure error={accounts.error} />}
      {accounts.data && !missingChart && (
        <DataGrid
          columns={columnsFor(companyId)}
          rows={accounts.data}
          rowKey={(account) => account.id}
          emptyMessage={t.accounting.chart.empty}
        />
      )}
    </section>
  )
}
