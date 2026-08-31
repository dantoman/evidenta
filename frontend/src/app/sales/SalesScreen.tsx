/**
 * Issued invoices -- create one, price it, issue it.
 *
 * **The two discriminators are on the form, with their reason next to them.**
 * What is sold and whether the customer is a resident each select an account when
 * the invoice posts, and neither can be derived: the partner card carries no
 * residence, and what is on the invoice is not a property of the customer. So the
 * form asks, and says why where somebody is filling it in rather than only in a
 * comment.
 *
 * **Issuing is one button** because it is one step: validating without posting
 * leaves a numbered document with no accounting effect.
 *
 * **Nothing here adds anything up** (`C19`). The line amounts and the totals come
 * back from the server, which derives them with the versioned rounding rule --
 * one implementation of it, not two that agree until one is edited.
 *
 * **No VAT.** Every line is issued under the `fara_tva` regime; the treatment with
 * VAT is a later step, and a column here that showed a rate would imply one exists.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { listPartners } from '@/shared/api/partners'
import {
  createInvoice,
  issueInvoice,
  listInvoices,
  type RevenueKind,
  type SalesInvoice,
  type SalesLineInput,
} from '@/shared/api/sales'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount } from '@/shared/format'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

const STATE_LABELS: Record<string, string> = {
  draft: t.sales.draft,
  confirmed: t.sales.confirmed,
  posted: t.sales.posted,
  cancelled: t.sales.cancelled,
}

export function SalesScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)

  const invoices = useQuery({
    queryKey: ['sales-invoices', companyId],
    queryFn: () => listInvoices(companyId),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['sales-invoices'] })

  const issue = useMutation({
    mutationFn: (documentId: string) => issueInvoice(documentId),
    onSuccess: refresh,
  })

  const columns: Column<SalesInvoice>[] = [
    {
      key: 'number',
      header: t.sales.number,
      cell: (row) => <span className="font-mono">{row.formatted_number ?? t.common.none}</span>,
      width: '12rem',
    },
    { key: 'date', header: t.sales.documentDate, cell: (row) => row.document_date, width: '9rem' },
    {
      key: 'kind',
      header: t.sales.revenueKind,
      cell: (row) =>
        row.revenue_kind === 'services'
          ? t.sales.services
          : row.revenue_kind === 'goods'
            ? t.sales.goods
            : t.sales.products,
      width: '9rem',
    },
    {
      key: 'resident',
      header: t.sales.resident,
      cell: (row) => (row.partner_resident ? t.common.yes : t.common.no),
      width: '9rem',
    },
    {
      key: 'total',
      header: t.sales.total,
      // Formatted from the string the server sent, never parsed to a float.
      cell: (row) => (row.totals ? amount(row.totals.total) : t.common.none),
      numeric: true,
      width: '10rem',
    },
    {
      key: 'state',
      header: t.sales.state,
      cell: (row) => STATE_LABELS[row.state] ?? row.state,
      width: '10rem',
    },
    {
      key: 'action',
      header: '',
      cell: (row) =>
        row.state === 'posted' ? (
          <span className="text-ink-muted">{t.sales.issued}</span>
        ) : (
          <button type="button" className="text-accent" onClick={() => issue.mutate(row.id)}>
            {t.sales.issue}
          </button>
        ),
      width: '16rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-semibold">{t.sales.title}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/registru`} className="text-sm text-accent">
            {t.accounting.register.title}
          </Link>
          <button type="button" onClick={() => setAdding((open) => !open)} className={BUTTON}>
            {adding ? t.companies.cancel : t.sales.add}
          </button>
        </div>
      </header>

      {adding && (
        <NewInvoiceForm
          companyId={companyId}
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}

      {invoices.isError && <Failure error={invoices.error} />}
      {issue.isError && <Failure error={issue.error} />}
      {invoices.data && (
        <>
          <DataGrid
            columns={columns}
            rows={invoices.data}
            rowKey={(row) => row.id}
            emptyMessage={t.sales.empty}
          />
          <p className="text-sm text-ink-muted">{t.sales.totalsFromServer}</p>
        </>
      )}
    </section>
  )
}

function NewInvoiceForm({
  companyId,
  onCreated,
}: {
  companyId: string
  onCreated: () => Promise<void> | void
}) {
  const partners = useQuery({
    queryKey: ['partners-directory', '', false],
    queryFn: () => listPartners({ role: 'customer' }),
  })

  const [partnerId, setPartnerId] = useState('')
  const [documentDate, setDocumentDate] = useState('')
  const [revenueKind, setRevenueKind] = useState<RevenueKind>('services')
  const [resident, setResident] = useState(true)
  const [lines, setLines] = useState<SalesLineInput[]>([
    { description: '', quantity: '1', unit_price: '' },
  ])

  const create = useMutation({
    mutationFn: () =>
      createInvoice(companyId, {
        partner_id: partnerId,
        document_date: documentDate,
        revenue_kind: revenueKind,
        partner_resident: resident,
        lines,
      }),
    onSuccess: onCreated,
  })

  const change = (index: number, field: keyof SalesLineInput, value: string) => {
    setLines(lines.map((line, at) => (at === index ? { ...line, [field]: value } : line)))
  }

  const complete =
    partnerId !== '' &&
    documentDate !== '' &&
    lines.length > 0 &&
    lines.every((line) => line.description.trim() !== '' && line.unit_price !== '')

  return (
    <form
      className="flex flex-col gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-muted">{t.sales.partner}</span>
          <select
            value={partnerId}
            onChange={(event) => setPartnerId(event.target.value)}
            className={`${FIELD} w-72`}
          >
            <option value="">{t.common.none}</option>
            {(partners.data ?? []).map((partner) => (
              <option key={partner.id} value={partner.id}>
                {partner.display_name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-muted">{t.sales.documentDate}</span>
          <input
            type="date"
            value={documentDate}
            onChange={(event) => setDocumentDate(event.target.value)}
            className={`${FIELD} w-40`}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-muted">{t.sales.revenueKind}</span>
          <select
            value={revenueKind}
            onChange={(event) => setRevenueKind(event.target.value as RevenueKind)}
            title={t.sales.goodsHint}
            className={`${FIELD} w-40`}
          >
            <option value="services">{t.sales.services}</option>
            <option value="goods">{t.sales.goods}</option>
            <option value="products">{t.sales.products}</option>
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm" title={t.sales.residentHint}>
          <input
            type="checkbox"
            checked={resident}
            onChange={(event) => setResident(event.target.checked)}
          />
          <span className="text-ink-muted">{t.sales.resident}</span>
        </label>
      </div>

      <table className="text-sm">
        <thead>
          <tr className="text-left text-ink-muted">
            <th className="pr-4 font-normal">{t.sales.lineDescription}</th>
            <th className="pr-4 font-normal">{t.sales.quantity}</th>
            <th className="pr-4 font-normal">{t.sales.unitPrice}</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => (
            <tr key={index}>
              <td className="pr-4 py-1">
                <input
                  value={line.description}
                  onChange={(event) => change(index, 'description', event.target.value)}
                  className={`${FIELD} w-96`}
                />
              </td>
              <td className="pr-4 py-1">
                <input
                  inputMode="decimal"
                  value={line.quantity}
                  onChange={(event) => change(index, 'quantity', event.target.value)}
                  className={`${FIELD} w-24 text-right tabular-nums`}
                />
              </td>
              <td className="pr-4 py-1">
                <input
                  inputMode="decimal"
                  value={line.unit_price}
                  onChange={(event) => change(index, 'unit_price', event.target.value)}
                  className={`${FIELD} w-32 text-right tabular-nums`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() =>
            setLines([...lines, { description: '', quantity: '1', unit_price: '' }])
          }
          className={BUTTON}
        >
          {t.sales.addLine}
        </button>
        <button type="submit" disabled={!complete || create.isPending} className={BUTTON}>
          {t.sales.create}
        </button>
      </div>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}
