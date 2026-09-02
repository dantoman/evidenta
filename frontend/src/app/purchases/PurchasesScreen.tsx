/**
 * Received invoices -- record one, price it, post it.
 *
 * **Both numbers appear, and that is the point of the screen.** Ours is allocated
 * at validation; theirs is on the paper in front of the person entering it. A
 * register showing only one of them cannot be cross-checked against either the
 * supplier's copy or our own numbering.
 *
 * **The two discriminators are on the form, with their reason next to them.**
 * Where the cost lands selects the expense account and whether the supplier is a
 * resident selects the payable; neither can be derived, so the form asks, where
 * somebody is filling it in rather than only in a comment (ADR-073 §2).
 *
 * **Nothing here adds anything up** (`C19`). Line amounts and totals come back
 * from the server, which derives them with the versioned rounding rule.
 *
 * **VAT as the paper states it, since ADR-089.** Every line says under which
 * regime the supplier invoiced it, from the vocabulary the server serves for the
 * document's date -- and whether that VAT is ours to deduct or is part of the
 * cost is not asked here: it follows from the company's registration on the
 * accounting date, and the server decides it at posting (ADR-088).
 *
 * **No stock.** None of the four destinations buys an asset: goods and materials
 * go on the balance sheet, and that entry's second half is F4.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { vatRegimes } from '@/shared/api/fiscal'
import { listPartners } from '@/shared/api/partners'
import {
  createPurchase,
  listPurchases,
  recordPurchase,
  type CostDestination,
  type PurchaseInvoice,
  type PurchaseLineInput,
} from '@/shared/api/purchases'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount } from '@/shared/format'
import { Button, Card, Field, Input, PageHeader, Select } from '@/shared/ui'

const STATE_LABELS: Record<string, string> = {
  draft: t.purchases.draft,
  confirmed: t.purchases.confirmed,
  posted: t.purchases.posted,
  cancelled: t.purchases.cancelled,
}

const DESTINATION_LABELS: Record<CostDestination, string> = {
  administrative: t.purchases.administrative,
  commercial: t.purchases.commercial,
  production_direct: t.purchases.productionDirect,
  production_indirect: t.purchases.productionIndirect,
}

const NO_VAT = 'fara_tva'

const emptyLine = (): PurchaseLineInput => ({
  description: '',
  quantity: '1',
  unit_price: '',
  vat_regime_code: '',
})

export function PurchasesScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)

  const invoices = useQuery({
    queryKey: ['purchase-invoices', companyId],
    queryFn: () => listPurchases(companyId),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['purchase-invoices'] })

  const record = useMutation({
    mutationFn: (documentId: string) => recordPurchase(documentId),
    onSuccess: refresh,
  })

  const columns: Column<PurchaseInvoice>[] = [
    {
      key: 'supplier_number',
      header: t.purchases.supplierNumber,
      cell: (row) => <span className="font-mono">{row.supplier_document_number}</span>,
      width: '12rem',
    },
    {
      key: 'supplier_date',
      header: t.purchases.supplierDate,
      cell: (row) => row.supplier_document_date,
      width: '9rem',
    },
    {
      key: 'number',
      header: t.purchases.ourNumber,
      cell: (row) => <span className="font-mono">{row.formatted_number ?? t.common.none}</span>,
      width: '12rem',
    },
    {
      key: 'destination',
      header: t.purchases.destination,
      cell: (row) => DESTINATION_LABELS[row.cost_destination] ?? row.cost_destination,
      width: '12rem',
    },
    {
      key: 'resident',
      header: t.purchases.resident,
      cell: (row) => (row.partner_resident ? t.common.yes : t.common.no),
      width: '8rem',
    },
    {
      key: 'vat',
      header: t.purchases.vat,
      cell: (row) => amount(row.totals.vat),
      numeric: true,
      width: '8rem',
    },
    {
      key: 'total',
      header: t.purchases.total,
      cell: (row) => amount(row.totals.total),
      numeric: true,
      width: '10rem',
    },
    {
      key: 'state',
      header: t.purchases.state,
      cell: (row) => STATE_LABELS[row.state] ?? row.state,
      width: '10rem',
    },
    {
      key: 'action',
      header: '',
      cell: (row) =>
        row.state === 'posted' ? (
          <span className="text-ink-muted">{t.purchases.recorded}</span>
        ) : (
          <button type="button" className="text-accent" onClick={() => record.mutate(row.id)}>
            {t.purchases.record}
          </button>
        ),
      width: '14rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title={t.purchases.title}
        lead={t.purchases.lead}
        actions={
          <div className="flex items-center gap-3">
            <Link to={`/companii/${companyId}/registru`} className="text-sm text-accent">
              {t.accounting.register.title}
            </Link>
            <Button icon="plus" onClick={() => setAdding((open) => !open)}>
              {adding ? t.companies.cancel : t.purchases.add}
            </Button>
          </div>
        }
      />

      {adding && (
        <NewPurchaseForm
          companyId={companyId}
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}

      {invoices.isError && <Failure error={invoices.error} />}
      {record.isError && <Failure error={record.error} />}
      {invoices.data && (
        <>
          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={invoices.data}
              rowKey={(row) => row.id}
              emptyMessage={t.purchases.empty}
            />
          </Card>
          <p className="text-sm text-ink-muted">{t.purchases.totalsFromServer}</p>
        </>
      )}
    </section>
  )
}

function NewPurchaseForm({
  companyId,
  onCreated,
}: {
  companyId: string
  onCreated: () => Promise<void> | void
}) {
  const partners = useQuery({
    queryKey: ['partners-directory', 'supplier', false],
    queryFn: () => listPartners({ role: 'supplier' }),
  })

  const [partnerId, setPartnerId] = useState('')
  const [documentDate, setDocumentDate] = useState('')
  const [supplierNumber, setSupplierNumber] = useState('')
  const [supplierDate, setSupplierDate] = useState('')
  const [destination, setDestination] = useState<CostDestination>('administrative')
  const [resident, setResident] = useState(true)
  const [lines, setLines] = useState<PurchaseLineInput[]>([emptyLine()])

  // The vocabulary of the document's date, plus the one code that is not in
  // it: a supplier who is not a VAT payer invoices without VAT.
  const regimes = useQuery({
    queryKey: ['vat-regimes', documentDate],
    queryFn: () => vatRegimes(documentDate),
    enabled: documentDate !== '',
  })

  const create = useMutation({
    mutationFn: () =>
      createPurchase(companyId, {
        partner_id: partnerId,
        document_date: documentDate,
        supplier_document_number: supplierNumber.trim(),
        supplier_document_date: supplierDate,
        cost_destination: destination,
        partner_resident: resident,
        lines,
      }),
    onSuccess: onCreated,
  })

  const change = (index: number, field: keyof PurchaseLineInput, value: string) => {
    setLines(lines.map((line, at) => (at === index ? { ...line, [field]: value } : line)))
  }

  const complete =
    partnerId !== '' &&
    documentDate !== '' &&
    supplierNumber.trim() !== '' &&
    supplierDate !== '' &&
    lines.length > 0 &&
    lines.every(
      (line) =>
        line.description.trim() !== '' && line.unit_price !== '' && line.vat_regime_code !== '',
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
          <Field label={t.purchases.partner}>
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

          <Field label={t.purchases.supplierNumber}>
            <Input
              value={supplierNumber}
              onChange={(event) => setSupplierNumber(event.target.value)}
              maxLength={100}
              className="w-44 font-mono"
              title={t.purchases.supplierNumberHint}
            />
          </Field>

          <Field label={t.purchases.supplierDate}>
            <Input
              type="date"
              value={supplierDate}
              onChange={(event) => setSupplierDate(event.target.value)}
              className="w-40"
            />
          </Field>

          <Field label={t.purchases.documentDate}>
            <Input
              type="date"
              value={documentDate}
              onChange={(event) => setDocumentDate(event.target.value)}
              className="w-40"
            />
          </Field>

          <Field label={t.purchases.destination}>
            <Select
              value={destination}
              onChange={(event) => setDestination(event.target.value as CostDestination)}
              title={t.purchases.destinationHint}
              className="w-52"
            >
              <option value="administrative">{t.purchases.administrative}</option>
              <option value="commercial">{t.purchases.commercial}</option>
              <option value="production_direct">{t.purchases.productionDirect}</option>
              <option value="production_indirect">{t.purchases.productionIndirect}</option>
            </Select>
          </Field>

          <label className="flex items-center gap-2 text-sm" title={t.purchases.residentHint}>
            <input
              type="checkbox"
              checked={resident}
              onChange={(event) => setResident(event.target.checked)}
            />
            <span className="text-ink-muted">{t.purchases.resident}</span>
          </label>
        </div>

        <p className="text-sm text-ink-muted">
          {documentDate === '' ? t.purchases.regimesNeedDate : t.purchases.vatRegimeHint}
        </p>
        {regimes.isError && <Failure error={regimes.error} />}

        <table className="text-sm">
          <thead>
            <tr className="text-left text-ink-muted">
              <th className="pr-4 font-normal">{t.purchases.lineDescription}</th>
              <th className="pr-4 font-normal">{t.purchases.quantity}</th>
              <th className="pr-4 font-normal">{t.purchases.unitPrice}</th>
              <th className="pr-4 font-normal">{t.purchases.vatRegime}</th>
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
                <td className="pr-4 py-1">
                  <Select
                    value={line.vat_regime_code}
                    onChange={(event) => change(index, 'vat_regime_code', event.target.value)}
                    disabled={documentDate === ''}
                    className="w-64"
                  >
                    <option value="">{t.purchases.chooseRegime}</option>
                    <option value={NO_VAT}>{t.vat.regimes[NO_VAT]}</option>
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
              </tr>
            ))}
          </tbody>
        </table>

        <div className="flex items-center gap-3">
          <Button onClick={() => setLines([...lines, emptyLine()])}>{t.purchases.addLine}</Button>
          <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
            {t.purchases.create}
          </Button>
        </div>
        {create.isError && <Failure error={create.error} />}
      </form>
    </Card>
  )
}
