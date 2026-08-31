/**
 * The Cartea Mare of one account -- month by month, in correspondence with the
 * accounts.
 *
 * Not `DataGrid`: a month is a block with two lists under it, and the grid's
 * contract is one row per record (C17). Every amount, including the remainder
 * no formula explains, is the server's (C19). The export is the same blocks as
 * rows of a file (C20).
 */

import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { amount, date as formatDate } from '@/shared/format'
import { generalLedger, generalLedgerExport, type LedgerMonth, type Turnover } from '@/shared/api/ledger'
import { Failure } from '@/shared/Failure'
import { ReportHeader, useWindow } from './ReportHeader'

function Turnovers({
  title,
  items,
  unassigned,
  companyId,
}: {
  title: string
  items: Turnover[]
  unassigned: string
  companyId: string
}) {
  const nothing = items.length === 0 && unassigned === '0.0000'
  return (
    <div className="flex flex-col gap-1 text-sm">
      <h3 className="text-ink-muted">{title}</h3>
      {nothing && <p className="text-ink-muted">—</p>}
      <table className="border-collapse">
        <tbody>
          {items.map((turnover) => (
            <tr key={turnover.account_id}>
              <td className="pr-4">
                <Link
                  to={`/companii/${companyId}/conturi/${turnover.account_id}/fisa`}
                  className="font-mono text-accent"
                >
                  {turnover.account_code}
                </Link>
              </td>
              <td className="text-right tabular">{amount(turnover.amount)}</td>
            </tr>
          ))}
          {unassigned !== '0.0000' && (
            <tr>
              <td className="pr-4 text-ink-muted">{t.accounting.reports.unassigned}</td>
              <td className="text-right tabular">{amount(unassigned)}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function Month({ month, companyId }: { month: LedgerMonth; companyId: string }) {
  return (
    <article className="flex flex-col gap-3 rounded border border-border bg-surface p-3">
      <header className="flex flex-wrap items-baseline justify-between gap-4 text-sm">
        <span className="font-semibold">
          {t.accounting.reports.month} {month.period_no}: {formatDate(month.start_date)} –{' '}
          {formatDate(month.end_date)}
        </span>
        <span>
          <span className="text-ink-muted">{t.accounting.reports.opening}</span>{' '}
          <span className="tabular">{amount(month.opening)}</span>
        </span>
      </header>
      <div className="grid gap-6 sm:grid-cols-2">
        <Turnovers
          title={t.accounting.reports.debitBy}
          items={month.debit_by}
          unassigned={month.debit_unassigned}
          companyId={companyId}
        />
        <Turnovers
          title={t.accounting.reports.creditBy}
          items={month.credit_by}
          unassigned={month.credit_unassigned}
          companyId={companyId}
        />
      </div>
      <footer className="flex flex-wrap justify-between gap-4 border-t border-border pt-2 text-sm">
        <span>
          <span className="text-ink-muted">{t.accounting.reports.turnover}</span>{' '}
          <span className="tabular">{amount(month.debit)}</span> /{' '}
          <span className="tabular">{amount(month.credit)}</span>
        </span>
        <span>
          <span className="text-ink-muted">{t.accounting.reports.closing}</span>{' '}
          <span className="tabular font-medium">{amount(month.closing)}</span>
        </span>
      </footer>
    </article>
  )
}

export function GeneralLedgerScreen() {
  const { companyId = '', accountId = '' } = useParams()
  const [window, setWindow] = useWindow()

  const ledger = useQuery({
    queryKey: ['general-ledger', companyId, accountId, window.from, window.to],
    queryFn: () => generalLedger(companyId, accountId, window.from, window.to),
  })

  return (
    <section className="flex flex-col gap-4">
      <nav className="flex gap-4 text-sm">
        <Link to={`/companii/${companyId}/conturi/${accountId}`} className="text-accent">
          {t.accounting.account.title}
        </Link>
        <Link to={`/companii/${companyId}/conturi/${accountId}/fisa`} className="text-accent">
          {t.accounting.reports.ledger}
        </Link>
      </nav>

      <ReportHeader
        title={
          ledger.data
            ? `${t.accounting.reports.generalLedger} ${ledger.data.account_code} — ${ledger.data.name_ro}`
            : t.accounting.reports.generalLedger
        }
        lead={t.accounting.reports.generalLedgerLead}
        window={window}
        onWindow={setWindow}
        exportHref={generalLedgerExport(companyId, accountId, window.from, window.to)}
      />

      {ledger.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {ledger.isError && <Failure error={ledger.error} />}

      {ledger.data && (
        <>
          <p className="text-sm">
            <span className="text-ink-muted">{t.accounting.reports.opening}:</span>{' '}
            <span className="tabular font-medium">{amount(ledger.data.opening)}</span>
          </p>
          {ledger.data.months.length === 0 && (
            <p className="text-sm text-ink-muted">{t.accounting.reports.empty}</p>
          )}
          {ledger.data.months.map((month) => (
            <Month key={month.period_id} month={month} companyId={companyId} />
          ))}
          <p className="flex flex-wrap justify-between gap-4 text-sm font-medium">
            <span>
              {t.accounting.reports.total}: <span className="tabular">{amount(ledger.data.total_debit)}</span>{' '}
              / <span className="tabular">{amount(ledger.data.total_credit)}</span>
            </span>
            <span>
              {t.accounting.reports.closing}: <span className="tabular">{amount(ledger.data.closing)}</span>
            </span>
          </p>
        </>
      )}
    </section>
  )
}
