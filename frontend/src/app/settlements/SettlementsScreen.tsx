/**
 * Open balances, and the match between them.
 *
 * **Two lists, chosen from, not computed.** What a partner still owes and money
 * that has not been pointed at anything are different questions: a receipt with
 * nothing to match is not an error, and neither is an unpaid invoice.
 *
 * **The amount is offered, not imposed.** It starts at the smaller of the two
 * remainders -- which is the common case, a payment that clears an invoice -- and
 * stays editable, because a partial payment is ordinary and the server refuses
 * anything above either remainder rather than quietly clamping it.
 *
 * **Nothing here adds anything up** (`C19`): every figure is the server's, and the
 * remainder after a match comes back from it rather than being subtracted here.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'

import { t } from '@/locales'
import { allocate, listOpenItems, type OpenItem } from '@/shared/api/settlements'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount as formatAmount } from '@/shared/format'
import { Button, Card, Field, Input, PageHeader } from '@/shared/ui'

const TYPE_LABELS: Record<string, string> = {
  'sales.document': t.settlements.invoiceIssued,
  'purchases.document': t.settlements.invoiceReceived,
  'treasury.receipt': t.treasury.receipt,
  'treasury.payment': t.treasury.payment,
}

export function SettlementsScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()

  const [document, setDocument] = useState<OpenItem | null>(null)
  const [movement, setMovement] = useState<OpenItem | null>(null)
  const [value, setValue] = useState('')

  const open = useQuery({
    queryKey: ['open-items', companyId],
    queryFn: () => listOpenItems(companyId),
  })

  // One key per attempt: a retry of the same allocation finds its first arrival
  // on the server (R19); a new allocation gets a new key once this one landed.
  const [idempotencyKey, setKey] = useState(() => crypto.randomUUID())
  const match = useMutation({
    mutationFn: () =>
      allocate(
        {
          settled_document_id: document?.document_id ?? '',
          movement_document_id: movement?.document_id ?? '',
          amount: value.replace(',', '.'),
        },
        idempotencyKey,
      ),
    onSuccess: async () => {
      setKey(crypto.randomUUID())
      setDocument(null)
      setMovement(null)
      setValue('')
      await queryClient.invalidateQueries({ queryKey: ['open-items'] })
    },
  })

  /** Selecting both sides proposes the amount that clears the smaller one. */
  const propose = (nextDocument: OpenItem | null, nextMovement: OpenItem | null) => {
    if (nextDocument && nextMovement) {
      const smaller =
        Number(nextDocument.outstanding) <= Number(nextMovement.outstanding)
          ? nextDocument.outstanding
          : nextMovement.outstanding
      setValue(smaller)
    }
  }

  const columns = (selected: OpenItem | null): Column<OpenItem>[] => [
    {
      key: 'date',
      header: t.settlements.date,
      cell: (row) => (
        <span className={row === selected ? 'font-bold' : undefined}>{row.document_date}</span>
      ),
      width: '9rem',
    },
    {
      key: 'kind',
      header: t.settlements.kind,
      cell: (row) => TYPE_LABELS[row.document_type] ?? row.document_type,
      width: '11rem',
    },
    {
      key: 'number',
      header: t.settlements.number,
      cell: (row) => <span className="font-mono">{row.formatted_number ?? t.common.none}</span>,
      width: '11rem',
    },
    {
      key: 'outstanding',
      header: t.settlements.outstanding,
      cell: (row) => formatAmount(row.outstanding),
      numeric: true,
      width: '10rem',
    },
  ]

  const ready = document !== null && movement !== null && value.trim() !== ''

  return (
    <section className="flex flex-col gap-4">
      <PageHeader title={t.settlements.title} lead={t.settlements.lead} />

      {open.isError && <Failure error={open.error} />}
      {open.data && (
        <div className="flex flex-col gap-4 xl:flex-row">
          <Card padding="none" className="flex-1">
            <h2 className="type-title-sm px-4 pt-4">{t.settlements.documents}</h2>
            <DataGrid
              columns={columns(document)}
              rows={open.data.documents}
              rowKey={(row) => row.document_id}
              emptyMessage={t.settlements.noDocuments}
              onRowClick={(row) => {
                setDocument(row)
                propose(row, movement)
              }}
            />
          </Card>
          <Card padding="none" className="flex-1">
            <h2 className="type-title-sm px-4 pt-4">{t.settlements.movements}</h2>
            <DataGrid
              columns={columns(movement)}
              rows={open.data.movements}
              rowKey={(row) => row.document_id}
              emptyMessage={t.settlements.noMovements}
              onRowClick={(row) => {
                setMovement(row)
                propose(document, row)
              }}
            />
          </Card>
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <Field label={t.settlements.chosenDocument}>
            <Input readOnly value={document?.formatted_number ?? ''} className="w-44 font-mono" />
          </Field>
          <Field label={t.settlements.chosenMovement}>
            <Input readOnly value={movement?.formatted_number ?? ''} className="w-44 font-mono" />
          </Field>
          <Field label={t.settlements.amount}>
            <Input
              inputMode="decimal"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="w-32 text-right tabular-nums"
            />
          </Field>
          <Button variant="primary" disabled={!ready || match.isPending} onClick={() => match.mutate()}>
            {t.settlements.match}
          </Button>
        </div>
        <p className="mt-3 text-sm text-ink-muted">{t.settlements.noLedgerEffect}</p>
        {match.isError && <Failure error={match.error} />}
      </Card>
    </section>
  )
}
