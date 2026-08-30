/**
 * The account ledger (fișa contului) -- one row per document, ADR-053 §3.1.
 *
 * A row is a document's footprint on the account: date, number, description,
 * the accounts it corresponded with, the amount on each side, and the balance
 * after it. Opening a row shows the entry whole (`EntryDetailPanel`) -- the
 * formulas, the lines, what it stood on and where it came from.
 *
 * **Every figure is the server's** (C19): the opening balance above the grid,
 * the running balance in each row, the totals in the footer and the closing
 * balance. When the server cuts the rows it says so, and the totals still cover
 * the whole window. The export link is the same report as a file (C20).
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { amount, date as formatDate } from '@/shared/format'
import { accountLedger, accountLedgerExport, type AccountLedgerRow } from '@/shared/api/ledger'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { EntryDetailPanel } from './EntryDetail'
import { ReportHeader, useWindow } from './ReportHeader'

const columns: Column<AccountLedgerRow>[] = [
  {
    key: 'accounting_date',
    header: t.accounting.reports.date,
    cell: (row) => formatDate(row.accounting_date),
    width: '7rem',
  },
  {
    key: 'entry_number',
    header: t.accounting.reports.number,
    cell: (row) => <span className="font-mono">{row.entry_number}</span>,
    width: '9rem',
  },
  {
    key: 'description',
    header: t.accounting.reports.description,
    // Both directions of R14 on the row, as the register shows them: a
    // correction is not a movement, and a cancelled row is not the last word.
    cell: (row) => (
      <>
        {row.description}
        {row.reverses_entry_id && (
          <span className="ml-2 text-ink-muted">({t.accounting.register.reverses})</span>
        )}
        {row.reversed_by_entry_id && (
          <span className="ml-2 text-danger">({t.accounting.register.reversed})</span>
        )}
      </>
    ),
  },
  {
    key: 'correspondents',
    header: t.accounting.reports.correspondent,
    cell: (row) =>
      row.has_formulas ? (
        <span className="font-mono">{row.correspondents.map((c) => c.account_code).join(', ')}</span>
      ) : (
        <span className="text-ink-muted">{t.accounting.reports.noCorrespondent}</span>
      ),
    width: '12rem',
  },
  {
    key: 'debit',
    header: t.accounting.reports.debit,
    cell: (row) => amount(row.debit),
    numeric: true,
    width: '9rem',
  },
  {
    key: 'credit',
    header: t.accounting.reports.credit,
    cell: (row) => amount(row.credit),
    numeric: true,
    width: '9rem',
  },
  {
    key: 'balance',
    header: t.accounting.reports.runningBalance,
    cell: (row) => amount(row.balance),
    numeric: true,
    width: '9rem',
  },
]

export function AccountLedgerScreen() {
  const { companyId = '', accountId = '' } = useParams()
  const [window, setWindow] = useWindow()
  const [opened, setOpened] = useState<string | null>(null)

  const ledger = useQuery({
    queryKey: ['account-ledger', companyId, accountId, window.from, window.to],
    queryFn: () => accountLedger(companyId, accountId, window.from, window.to),
  })

  return (
    <section className="flex flex-col gap-4">
      <nav className="flex gap-4 text-sm">
        <Link to={`/companii/${companyId}/plan-de-conturi`} className="text-accent">
          {t.accounting.chart.title}
        </Link>
        <Link to={`/companii/${companyId}/conturi/${accountId}`} className="text-accent">
          {t.accounting.account.title}
        </Link>
        <Link to={`/companii/${companyId}/conturi/${accountId}/cartea-mare`} className="text-accent">
          {t.accounting.reports.generalLedger}
        </Link>
        <Link to={`/companii/${companyId}/balanta`} className="text-accent">
          {t.accounting.balance.title}
        </Link>
      </nav>

      <ReportHeader
        title={
          ledger.data
            ? `${t.accounting.reports.ledger} ${ledger.data.account_code} — ${ledger.data.name_ro}`
            : t.accounting.reports.ledger
        }
        lead={t.accounting.reports.ledgerLead}
        window={window}
        onWindow={(next) => {
          setOpened(null)
          setWindow(next)
        }}
        exportHref={accountLedgerExport(companyId, accountId, window.from, window.to)}
      />

      {ledger.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {ledger.isError && <Failure error={ledger.error} />}

      {ledger.data && (
        <>
          <p className="text-sm">
            <span className="text-ink-muted">{t.accounting.reports.opening}:</span>{' '}
            <span className="tabular font-medium">{amount(ledger.data.opening)}</span>
          </p>
          {ledger.data.truncated && (
            <p className="text-sm text-danger">{t.accounting.reports.truncated}</p>
          )}
          <DataGrid
            columns={columns}
            rows={ledger.data.rows}
            rowKey={(row) => row.journal_entry_id}
            emptyMessage={t.accounting.reports.empty}
            onRowClick={(row) => setOpened(row.journal_entry_id)}
            serverTotals={{
              accounting_date: t.accounting.reports.total,
              debit: amount(ledger.data.total_debit),
              credit: amount(ledger.data.total_credit),
              balance: amount(ledger.data.closing),
            }}
          />
          <p className="text-sm">
            <span className="text-ink-muted">{t.accounting.reports.closing}:</span>{' '}
            <span className="tabular font-medium">{amount(ledger.data.closing)}</span>
          </p>
        </>
      )}

      {opened && (
        <EntryDetailPanel entryId={opened} companyId={companyId} onClose={() => setOpened(null)} />
      )}
    </section>
  )
}
