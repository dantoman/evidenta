/**
 * The revaluation of monetary items in foreign currency -- `A10`, ADR-097.
 *
 * **One action, one date.** The accountant names the reporting date and the
 * server does the rest: what is open in currency, at which rate it is carried,
 * the official rate of that day, the entry. Nothing is computed here (`C19`):
 * the differences on the rows are the server's, signed as it signed them.
 *
 * **A second run for the same date changes nothing**, and the screen says so
 * rather than pretending a new entry appeared: the server returns the first
 * revaluation with `posted_now: false`.
 *
 * **What is not in it is said on the screen.** Cash and bank in foreign currency
 * do not exist yet (the treasury moves lei only), so the revaluation covers
 * receivables and payables; a sentence says so, because a revaluation that
 * silently skipped the bank would be read as having covered it.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { listRevaluations, revalue, type Revaluation } from '@/shared/api/currency'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount as formatAmount, date as formatDate } from '@/shared/format'
import { Button, Card, Field, Input, PageHeader } from '@/shared/ui'

export function RevaluationScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [asOf, setAsOf] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  const revaluations = useQuery({
    queryKey: ['revaluations', companyId],
    queryFn: () => listRevaluations(companyId),
  })

  const run = useMutation({
    mutationFn: () => revalue(companyId, asOf),
    onSuccess: async (result) => {
      setNotice(result.posted_now === false ? t.accounting.revaluation.alreadyRun : null)
      await queryClient.invalidateQueries({ queryKey: ['revaluations'] })
    },
  })

  const columns: Column<Revaluation>[] = [
    {
      key: 'as_of',
      header: t.accounting.revaluation.asOf,
      cell: (row) => formatDate(row.as_of),
      width: '10rem',
    },
    {
      key: 'entry',
      header: t.accounting.revaluation.entry,
      cell: (row) =>
        row.journal_entry_id === null ? (
          <span className="text-ink-muted">{t.accounting.revaluation.noEntry}</span>
        ) : (
          <span className="flex items-center gap-2">
            <Link
              to={`/companii/${companyId}/registru?entry=${row.journal_entry_id}`}
              className="font-mono text-accent"
            >
              {row.journal_entry_id.slice(0, 8)}
            </Link>
            {row.reversed_by !== null && (
              <span className="text-ink-muted">{t.accounting.revaluation.reversed}</span>
            )}
          </span>
        ),
      width: '14rem',
    },
    {
      key: 'items',
      header: t.accounting.revaluation.items,
      cell: (row) => <ItemsTable revaluation={row} />,
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader title={t.accounting.revaluation.title} lead={t.accounting.revaluation.lead} />

      <Card>
        <form
          className="flex flex-wrap items-end gap-4"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            run.mutate()
          }}
        >
          <Field label={t.accounting.revaluation.asOf}>
            <Input
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
              className="w-40"
            />
          </Field>
          <Button variant="primary" type="submit" disabled={asOf === '' || run.isPending}>
            {t.accounting.revaluation.run}
          </Button>
          {run.isError && <Failure error={run.error} />}
        </form>
        {notice !== null && <p className="mt-3 text-sm text-ink-muted">{notice}</p>}
        <p className="mt-3 text-sm text-ink-muted">{t.accounting.revaluation.cashNote}</p>
      </Card>

      {revaluations.isError && <Failure error={revaluations.error} />}
      {revaluations.data && (
        <Card padding="none">
          <DataGrid
            columns={columns}
            rows={revaluations.data}
            rowKey={(row) => row.id}
            emptyMessage={t.accounting.revaluation.empty}
          />
        </Card>
      )}
    </section>
  )
}

function ItemsTable({ revaluation }: { revaluation: Revaluation }) {
  if (revaluation.items.length === 0) {
    return <span className="text-ink-muted">{t.accounting.revaluation.noItems}</span>
  }
  return (
    <table className="text-sm">
      <thead>
        <tr className="text-left text-ink-muted">
          <th className="pr-4 font-normal">{t.accounting.revaluation.side}</th>
          <th className="pr-4 font-normal">{t.accounting.revaluation.amount}</th>
          <th className="pr-4 font-normal">{t.accounting.revaluation.rateBefore}</th>
          <th className="pr-4 font-normal">{t.accounting.revaluation.rateAfter}</th>
          <th className="pr-4 font-normal">{t.accounting.revaluation.difference}</th>
        </tr>
      </thead>
      <tbody>
        {revaluation.items.map((item) => (
          <tr key={item.document_id}>
            <td className="pr-4">
              {item.side === 'receivable'
                ? t.accounting.revaluation.receivable
                : t.accounting.revaluation.payable}
            </td>
            <td className="pr-4 text-right tabular-nums">
              {formatAmount(item.amount_currency)} {item.currency}
            </td>
            <td className="pr-4 text-right tabular-nums">{item.rate_before}</td>
            <td className="pr-4 text-right tabular-nums">{item.rate_after}</td>
            <td className="pr-4 text-right tabular-nums">{formatAmount(item.difference)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
