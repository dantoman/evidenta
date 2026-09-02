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
 * **VAT, since ADR-089, and the screen decides nothing about it.** It asks the
 * server whether the company is a VAT payer on the invoice's date (ADR-088) and
 * which regimes exist on that date; a payer states a regime on every line, a
 * non-payer's lines go out under `fara_tva`, and the server refuses whatever
 * does not match the status on that day. No regime is preselected: the standard
 * rate is the usual answer and still an answer somebody has to give.
 *
 * Built on `shared/ui` since 31.08. It was the last screen carrying its own
 * `FIELD` and `BUTTON` constants -- written while ADR-074 was moving the other
 * sixteen off them, so it missed the sweep and then sat beside its own
 * counterpart, `PurchasesScreen`, looking like a different product.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { taxStatus } from '@/shared/api/companies'
import { vatRegimes } from '@/shared/api/fiscal'
import { listPartners } from '@/shared/api/partners'
import {
  createInvoice,
  issueInvoice,
  listInvoices,
  type RevenueKind,
  type SaleNature,
  type SalesInvoice,
  type SalesLineInput,
} from '@/shared/api/sales'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount } from '@/shared/format'
import { Button, Card, Field, Input, PageHeader, Select } from '@/shared/ui'

const NO_VAT = 'fara_tva'

const STATE_LABELS: Record<string, string> = {
  draft: t.sales.draft,
  confirmed: t.sales.confirmed,
  posted: t.sales.posted,
  cancelled: t.sales.cancelled,
}

const emptyLine = (): SalesLineInput => ({
  description: '',
  quantity: '1',
  unit_price: '',
  vat_regime_code: '',
})

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
      // The nature first, because it changes what every other column means: the
      // same total is money owed on an invoice and money owed back on a credit
      // note.
      key: 'nature',
      header: t.sales.nature,
      cell: (row) => (row.nature === 'return' ? t.sales.creditNote : t.sales.invoice),
      width: '10rem',
    },
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
      key: 'net',
      header: t.sales.net,
      cell: (row) => amount(row.totals.net),
      numeric: true,
      width: '9rem',
    },
    {
      key: 'vat',
      header: t.sales.vat,
      cell: (row) => amount(row.totals.vat),
      numeric: true,
      width: '8rem',
    },
    {
      key: 'total',
      header: t.sales.total,
      // Formatted from the string the server sent, never parsed to a float.
      cell: (row) => amount(row.totals.total),
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
      <PageHeader
        title={t.sales.title}
        lead={t.sales.lead}
        actions={
          <div className="flex items-center gap-3">
            <Link to={`/companii/${companyId}/registru`} className="text-sm text-accent">
              {t.accounting.register.title}
            </Link>
            <Button icon="plus" onClick={() => setAdding((open) => !open)}>
              {adding ? t.companies.cancel : t.sales.add}
            </Button>
          </div>
        }
      />

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
          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={invoices.data}
              rowKey={(row) => row.id}
              emptyMessage={t.sales.empty}
            />
          </Card>
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
  const [nature, setNature] = useState<SaleNature>('delivery')
  const [revenueKind, setRevenueKind] = useState<RevenueKind>('services')
  const [resident, setResident] = useState(true)
  const [lines, setLines] = useState<SalesLineInput[]>([emptyLine()])

  // Both for the invoice's date, never for today: a back-dated invoice is priced
  // under the status and the vocabulary of the day it bears (ADR-044).
  const status = useQuery({
    queryKey: ['tax-status', companyId, documentDate],
    queryFn: () => taxStatus(companyId, documentDate),
    enabled: documentDate !== '',
  })
  const registered = status.data?.vat.registered === true
  const regimes = useQuery({
    queryKey: ['vat-regimes', documentDate],
    queryFn: () => vatRegimes(documentDate),
    enabled: registered,
  })

  const create = useMutation({
    mutationFn: () =>
      createInvoice(companyId, {
        partner_id: partnerId,
        document_date: documentDate,
        nature,
        revenue_kind: revenueKind,
        partner_resident: resident,
        // A non-payer's lines carry the one code it may state; a payer's carry
        // what was chosen on each line.
        lines: lines.map((line) => ({
          ...line,
          vat_regime_code: registered ? line.vat_regime_code : NO_VAT,
        })),
      }),
    onSuccess: onCreated,
  })

  const change = (index: number, field: keyof SalesLineInput, value: string) => {
    setLines(lines.map((line, at) => (at === index ? { ...line, [field]: value } : line)))
  }

  const complete =
    partnerId !== '' &&
    documentDate !== '' &&
    status.data !== undefined &&
    lines.length > 0 &&
    lines.every(
      (line) =>
        line.description.trim() !== '' &&
        line.unit_price !== '' &&
        (!registered || line.vat_regime_code !== ''),
    )

  return (
    <Card>
      <form
        className="flex flex-col gap-4"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          create.mutate()
        }}
      >
      <div className="flex flex-wrap items-end gap-4">
        <Field label={t.sales.nature}>
          <Select
            value={nature}
            onChange={(event) => setNature(event.target.value as SaleNature)}
            title={t.sales.natureHint}
            className="w-44"
          >
            <option value="delivery">{t.sales.invoice}</option>
            <option value="return">{t.sales.creditNote}</option>
          </Select>
        </Field>

        <Field label={t.sales.partner}>
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

        <Field label={t.sales.documentDate}>
          <Input
            type="date"
            value={documentDate}
            onChange={(event) => setDocumentDate(event.target.value)}
            className="w-40"
          />
        </Field>

        <Field label={t.sales.revenueKind}>
          <Select
            value={revenueKind}
            onChange={(event) => setRevenueKind(event.target.value as RevenueKind)}
            title={t.sales.goodsHint}
            className="w-40"
          >
            <option value="services">{t.sales.services}</option>
            <option value="goods">{t.sales.goods}</option>
            <option value="products">{t.sales.products}</option>
          </Select>
        </Field>

        <label className="flex items-center gap-2 text-sm" title={t.sales.residentHint}>
          <input
            type="checkbox"
            checked={resident}
            onChange={(event) => setResident(event.target.checked)}
          />
          <span className="text-ink-muted">{t.sales.resident}</span>
        </label>
      </div>

      <p className="text-sm text-ink-muted">
        {documentDate === ''
          ? t.sales.statusNeedsDate
          : status.data === undefined
            ? t.app.loading
            : registered
              ? t.sales.registeredOnDate
              : t.sales.notRegisteredOnDate}
      </p>
      {status.isError && <Failure error={status.error} />}
      {regimes.isError && <Failure error={regimes.error} />}

      <table className="text-sm">
        <thead>
          <tr className="text-left text-ink-muted">
            <th className="pr-4 font-normal">{t.sales.lineDescription}</th>
            <th className="pr-4 font-normal">{t.sales.quantity}</th>
            <th className="pr-4 font-normal">{t.sales.unitPrice}</th>
            {registered && <th className="pr-4 font-normal">{t.sales.vatRegime}</th>}
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => (
            <tr key={index}>
              <td className="pr-4 py-1">
                <Input
                  value={line.description}
                  onChange={(event) => change(index, 'description', event.target.value)}
                  className="w-96"
                />
              </td>
              <td className="pr-4 py-1">
                <Input
                  inputMode="decimal"
                  value={line.quantity}
                  onChange={(event) => change(index, 'quantity', event.target.value)}
                  className="w-24 text-right tabular-nums"
                />
              </td>
              <td className="pr-4 py-1">
                <Input
                  inputMode="decimal"
                  value={line.unit_price}
                  onChange={(event) => change(index, 'unit_price', event.target.value)}
                  className="w-32 text-right tabular-nums"
                />
              </td>
              {registered && (
                <td className="pr-4 py-1">
                  <Select
                    value={line.vat_regime_code}
                    onChange={(event) => change(index, 'vat_regime_code', event.target.value)}
                    className="w-64"
                  >
                    <option value="">{t.sales.chooseRegime}</option>
                    {(regimes.data?.regimes ?? []).map((regime) => (
                      <option
                        key={regime.code}
                        value={regime.code}
                        disabled={regime.unavailable !== null}
                        title={regime.unavailable !== null ? t.vat.rateUnavailable : undefined}
                      >
                        {t.vat.regimes[regime.code] ?? regime.code}
                        {regime.rate !== null ? ` (${regime.rate}%)` : ''}
                      </option>
                    ))}
                  </Select>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex items-center gap-3">
        <Button onClick={() => setLines([...lines, emptyLine()])}>{t.sales.addLine}</Button>
        <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
          {t.sales.create}
        </Button>
      </div>
      {create.isError && <Failure error={create.error} />}
      </form>
    </Card>
  )
}
