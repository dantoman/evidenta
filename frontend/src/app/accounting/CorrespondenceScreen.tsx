/**
 * Turnover by correspondence -- the chess-board, one row per (debit, credit) pair.
 *
 * Read straight off the formulas (ADR-048); what has no formula -- a manual
 * note -- is named under the grid as the amount the board does not explain,
 * never spread across pairs. Totals are the server's (C19); the export is the
 * same rows as a file (C20).
 */

import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'

import { t } from '@/locales'
import { amount } from '@/shared/format'
import { correspondence, correspondenceExport, type CorrespondenceCell } from '@/shared/api/ledger'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { ReportHeader, useWindow } from './ReportHeader'
import { Card } from '@/shared/ui'

const columns: Column<CorrespondenceCell>[] = [
  {
    key: 'debit_code',
    header: t.accounting.reports.debitAccount,
    cell: (row) => <span className="font-mono">{row.debit_code}</span>,
    width: '10rem',
  },
  {
    key: 'credit_code',
    header: t.accounting.reports.creditAccount,
    cell: (row) => <span className="font-mono">{row.credit_code}</span>,
    width: '10rem',
  },
  {
    key: 'amount',
    header: t.accounting.reports.amount,
    cell: (row) => amount(row.amount),
    numeric: true,
    width: '10rem',
  },
]

export function CorrespondenceScreen() {
  const { companyId = '' } = useParams()
  const navigate = useNavigate()
  const [window, setWindow] = useWindow()

  const report = useQuery({
    queryKey: ['correspondence', companyId, window.from, window.to],
    queryFn: () => correspondence(companyId, window.from, window.to),
  })

  return (
    <section className="flex flex-col gap-4">

      <ReportHeader
        title={t.accounting.reports.correspondence}
        lead={t.accounting.reports.correspondenceLead}
        window={window}
        onWindow={setWindow}
        exportHref={correspondenceExport(companyId, window.from, window.to)}
      />

      {report.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {report.isError && <Failure error={report.error} />}

      {report.data && (
        <>
          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={report.data.cells}
              rowKey={(row) => `${row.debit_account_id}:${row.credit_account_id}`}
              emptyMessage={t.accounting.reports.empty}
              onRowClick={(row) => navigate(`/companii/${companyId}/conturi/${row.debit_account_id}/fisa`)}
              serverTotals={{
                debit_code: t.accounting.reports.correspondenceTotal,
                amount: amount(report.data.total),
              }}
            />
          </Card>
          <dl className="grid grid-cols-[14rem_auto] gap-x-6 gap-y-1 text-sm">
            <dt className="text-ink-muted">{t.accounting.reports.linesTotal}</dt>
            <dd className="tabular">{amount(report.data.lines_total)}</dd>
            <dt className="text-ink-muted">{t.accounting.reports.unassigned}</dt>
            <dd className="tabular">{amount(report.data.unassigned)}</dd>
          </dl>
        </>
      )}
    </section>
  )
}
