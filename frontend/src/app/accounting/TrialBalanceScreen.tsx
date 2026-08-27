/**
 * The trial balance -- read from the server, totalled by the server (C19).
 *
 * Nothing here sums a column. A total computed in the browser is a total over
 * the rows the browser happens to hold, and in an accounting report that is
 * wrong by construction rather than merely inconsistent. `balanced` is the
 * server's answer too: it is Σ debit = Σ credit over the window, which holds per
 * entry already (R11), so a false here means a line got in without the engine.
 *
 * Amounts arrive as decimal strings and are formatted as strings (C18). They are
 * never parsed into numbers on the way to the screen.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'

import { t } from '@/locales'
import { amount } from '@/shared/format'
import { trialBalance, type TrialBalanceRow } from '@/shared/api/ledger'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'

const columns: Column<TrialBalanceRow>[] = [
  {
    key: 'account_code',
    header: t.accounting.balance.code,
    cell: (row) => <span className="font-mono">{row.account_code}</span>,
    width: '8rem',
  },
  { key: 'name_ro', header: t.accounting.balance.name, cell: (row) => row.name_ro },
  {
    key: 'opening',
    header: t.accounting.balance.opening,
    cell: (row) => amount(row.opening),
    numeric: true,
    width: '10rem',
  },
  {
    key: 'debit',
    header: t.accounting.balance.debit,
    cell: (row) => amount(row.debit),
    numeric: true,
    width: '10rem',
  },
  {
    key: 'credit',
    header: t.accounting.balance.credit,
    cell: (row) => amount(row.credit),
    numeric: true,
    width: '10rem',
  },
  {
    key: 'closing',
    header: t.accounting.balance.closing,
    cell: (row) => amount(row.closing),
    numeric: true,
    width: '10rem',
  },
]

function yearStart(): string {
  return `${new Date().getFullYear()}-01-01`
}

function yearEnd(): string {
  return `${new Date().getFullYear()}-12-31`
}

export function TrialBalanceScreen() {
  const { companyId = '' } = useParams()

  // The window is a choice, and the default is the calendar year rather than
  // "today": a balance for a single day is almost never the question, and a
  // window that moves with the clock is one two people cannot compare.
  const [from, setFrom] = useState(yearStart)
  const [to, setTo] = useState(yearEnd)
  const [window, setWindow] = useState({ from: yearStart(), to: yearEnd() })

  const balance = useQuery({
    queryKey: ['trial-balance', companyId, window.from, window.to],
    queryFn: () => trialBalance(companyId, window.from, window.to),
  })

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-semibold">{t.accounting.balance.title}</h1>
        <form
          className="flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            setWindow({ from, to })
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.accounting.balance.from}</span>
            <input
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
              className={FIELD}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.accounting.balance.to}</span>
            <input
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
              className={FIELD}
            />
          </label>
          <button
            type="submit"
            className="rounded border border-border bg-surface px-3 text-sm text-accent"
          >
            {t.accounting.balance.show}
          </button>
        </form>
      </header>

      {balance.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {balance.isError && <Failure error={balance.error} />}

      {balance.data && (
        <>
          <DataGrid
            columns={columns}
            rows={balance.data.rows}
            rowKey={(row) => row.account_id}
            emptyMessage={t.accounting.balance.empty}
            serverTotals={{
              account_code: t.accounting.balance.total,
              debit: amount(balance.data.total_debit),
              credit: amount(balance.data.total_credit),
            }}
          />
          <p
            className={`text-sm ${balance.data.balanced ? 'text-ink-muted' : 'text-danger'}`}
            role={balance.data.balanced ? undefined : 'alert'}
          >
            {balance.data.balanced
              ? t.accounting.balance.balanced
              : t.accounting.balance.unbalanced}
          </p>
        </>
      )}
    </section>
  )
}
