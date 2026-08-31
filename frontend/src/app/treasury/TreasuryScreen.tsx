/**
 * Money in and out -- one list, in date order.
 *
 * **The three discriminators are on the form with their reason next to them.**
 * Where the money moved decides the treasury account; the direction decides which
 * side it sits on; residence decides whose account it clears. None of the three
 * can be derived from anything the system holds.
 *
 * **The amount is a field, not a sum.** These documents carry no positions, so
 * there is nothing to add up -- and nothing here adds anything up either (`C19`).
 *
 * **What the screen does not offer: choosing which invoice this settles.** The
 * posting does not need it and settlement is its own step; an input here would
 * promise a link the system does not keep.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { listPartners } from '@/shared/api/partners'
import {
  createMovement,
  listMovements,
  recordMovement,
  type Movement,
  type MovementDirection,
  type TreasuryAccount,
} from '@/shared/api/treasury'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount as formatAmount } from '@/shared/format'
import { Button, Card, Field, Input, PageHeader, Select } from '@/shared/ui'

const STATE_LABELS: Record<string, string> = {
  draft: t.treasury.draft,
  confirmed: t.treasury.confirmed,
  posted: t.treasury.posted,
  cancelled: t.treasury.cancelled,
}

export function TreasuryScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)

  const movements = useQuery({
    queryKey: ['treasury-movements', companyId],
    queryFn: () => listMovements(companyId),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['treasury-movements'] })

  const record = useMutation({
    mutationFn: (documentId: string) => recordMovement(documentId),
    onSuccess: refresh,
  })

  const columns: Column<Movement>[] = [
    {
      key: 'date',
      header: t.treasury.documentDate,
      cell: (row) => row.document_date,
      width: '9rem',
    },
    {
      key: 'number',
      header: t.treasury.number,
      cell: (row) => <span className="font-mono">{row.formatted_number ?? t.common.none}</span>,
      width: '12rem',
    },
    {
      key: 'direction',
      header: t.treasury.direction,
      cell: (row) =>
        row.direction === 'receipt' ? t.treasury.receipt : t.treasury.payment,
      width: '9rem',
    },
    {
      key: 'where',
      header: t.treasury.where,
      cell: (row) => (row.treasury_account === 'cash' ? t.treasury.cash : t.treasury.bank),
      width: '9rem',
    },
    {
      key: 'resident',
      header: t.treasury.resident,
      cell: (row) => (row.partner_resident ? t.common.yes : t.common.no),
      width: '8rem',
    },
    {
      key: 'amount',
      header: t.treasury.amount,
      cell: (row) => formatAmount(row.amount),
      numeric: true,
      width: '10rem',
    },
    {
      key: 'state',
      header: t.treasury.state,
      cell: (row) => STATE_LABELS[row.state] ?? row.state,
      width: '10rem',
    },
    {
      key: 'action',
      header: '',
      cell: (row) =>
        row.state === 'posted' ? (
          <span className="text-ink-muted">{t.treasury.recorded}</span>
        ) : (
          <button type="button" className="text-accent" onClick={() => record.mutate(row.id)}>
            {t.treasury.record}
          </button>
        ),
      width: '14rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title={t.treasury.title}
        lead={t.treasury.lead}
        actions={
          <div className="flex items-center gap-3">
            <Link to={`/companii/${companyId}/registru`} className="text-sm text-accent">
              {t.accounting.register.title}
            </Link>
            <Button icon="plus" onClick={() => setAdding((open) => !open)}>
              {adding ? t.companies.cancel : t.treasury.add}
            </Button>
          </div>
        }
      />

      {adding && (
        <NewMovementForm
          companyId={companyId}
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}

      {movements.isError && <Failure error={movements.error} />}
      {record.isError && <Failure error={record.error} />}
      {movements.data && (
        <>
          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={movements.data}
              rowKey={(row) => row.id}
              emptyMessage={t.treasury.empty}
            />
          </Card>
          <p className="text-sm text-ink-muted">{t.treasury.noSettlementYet}</p>
        </>
      )}
    </section>
  )
}

function NewMovementForm({
  companyId,
  onCreated,
}: {
  companyId: string
  onCreated: () => Promise<void> | void
}) {
  const partners = useQuery({
    queryKey: ['partners-directory', 'all', false],
    queryFn: () => listPartners({}),
  })

  const [direction, setDirection] = useState<MovementDirection>('receipt')
  const [partnerId, setPartnerId] = useState('')
  const [documentDate, setDocumentDate] = useState('')
  const [value, setValue] = useState('')
  const [where, setWhere] = useState<TreasuryAccount>('bank')
  const [resident, setResident] = useState(true)

  const create = useMutation({
    mutationFn: () =>
      createMovement(companyId, {
        direction,
        partner_id: partnerId,
        document_date: documentDate,
        // Sent as typed, with the comma accepted as a decimal separator the way
        // the entry grid accepts it. The server holds the scale.
        amount: value.replace(',', '.'),
        treasury_account: where,
        partner_resident: resident,
      }),
    onSuccess: onCreated,
  })

  const complete = partnerId !== '' && documentDate !== '' && value.trim() !== ''

  return (
    <Card>
      <form
        className="flex flex-wrap items-end gap-4"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <Field label={t.treasury.direction}>
          <Select
            value={direction}
            onChange={(event) => setDirection(event.target.value as MovementDirection)}
            className="w-40"
          >
            <option value="receipt">{t.treasury.receipt}</option>
            <option value="payment">{t.treasury.payment}</option>
          </Select>
        </Field>

        <Field label={t.treasury.partner}>
          <Select
            value={partnerId}
            onChange={(event) => setPartnerId(event.target.value)}
            className="w-72"
          >
            <option value="">{t.common.none}</option>
            {(partners.data ?? []).map((partner) => (
              <option key={partner.id} value={partner.id}>
                {partner.display_name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label={t.treasury.documentDate}>
          <Input
            type="date"
            value={documentDate}
            onChange={(event) => setDocumentDate(event.target.value)}
            className="w-40"
          />
        </Field>

        <Field label={t.treasury.amount}>
          <Input
            inputMode="decimal"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            className="w-32 text-right tabular-nums"
          />
        </Field>

        <Field label={t.treasury.where}>
          <Select
            value={where}
            onChange={(event) => setWhere(event.target.value as TreasuryAccount)}
            title={t.treasury.whereHint}
            className="w-40"
          >
            <option value="bank">{t.treasury.bank}</option>
            <option value="cash">{t.treasury.cash}</option>
          </Select>
        </Field>

        <label className="flex items-center gap-2 text-sm" title={t.treasury.residentHint}>
          <input
            type="checkbox"
            checked={resident}
            onChange={(event) => setResident(event.target.checked)}
          />
          <span className="text-ink-muted">{t.treasury.resident}</span>
        </label>

        <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
          {t.treasury.create}
        </Button>
        {create.isError && <Failure error={create.error} />}
      </form>
    </Card>
  )
}
