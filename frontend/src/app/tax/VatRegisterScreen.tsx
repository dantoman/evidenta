/**
 * The VAT registers -- one side, one VAT fiscal period.
 *
 * **It says what it is not.** The statutory registers of deliveries and of
 * procurements have a prescribed form (Codul fiscal art. 118) that nobody here
 * has read; this is the register of the company's documents with their VAT on
 * the fiscal period, with the figures the prescribed one asks for. The lead
 * says so rather than letting somebody file it as something it is not.
 *
 * **The period is the server's.** The screen names a month; the server finds
 * the VAT fiscal period covering its first day and refuses when there is none
 * -- the refusal points at the company card, where periods are opened.
 *
 * **Nothing here adds anything up** (`C19`): the rows, the totals by regime and
 * the grand totals all come from one result, and the export is a link to the
 * same result (`C20`).
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'

import { t } from '@/locales'
import {
  vatRegister,
  vatRegisterExport,
  type RegisterRow,
  type RegisterSide,
} from '@/shared/api/tax'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount, date, today } from '@/shared/format'
import { Card, Field, Input, PageHeader, Select } from '@/shared/ui'

const KIND_LABELS: Record<RegisterRow['kind'], string> = {
  invoice: t.vatRegisters.invoice,
  credit_note: t.vatRegisters.creditNote,
  supplier_invoice: t.vatRegisters.supplierInvoice,
}

function regimeLabel(code: string, rate: string): string {
  return `${t.vat.regimes[code] ?? code} ${rate}%`
}

function columnsFor(side: RegisterSide): Column<RegisterRow>[] {
  const shared: Column<RegisterRow>[] = [
    {
      key: 'document_date',
      header: t.vatRegisters.documentDate,
      cell: (row) => date(row.document_date),
      width: '8rem',
    },
    {
      key: 'number',
      header: t.vatRegisters.number,
      cell: (row) => <span className="font-mono">{row.formatted_number ?? t.common.none}</span>,
      width: '11rem',
    },
  ]
  const identity: Column<RegisterRow>[] =
    side === 'sales'
      ? [
          {
            key: 'kind',
            header: t.vatRegisters.kind,
            cell: (row) => KIND_LABELS[row.kind],
            width: '9rem',
          },
        ]
      : [
          {
            key: 'supplier_number',
            header: t.vatRegisters.supplierNumber,
            cell: (row) => (
              <span className="font-mono">{row.supplier_document_number ?? t.common.none}</span>
            ),
            width: '10rem',
          },
          {
            key: 'supplier_date',
            header: t.vatRegisters.supplierDate,
            cell: (row) =>
              row.supplier_document_date ? date(row.supplier_document_date) : t.common.none,
            width: '8rem',
          },
          {
            key: 'deductible',
            header: t.vatRegisters.deductible,
            cell: (row) =>
              row.deductible === null ? t.common.none : row.deductible ? t.common.yes : t.common.no,
            width: '7rem',
          },
        ]
  const money: Column<RegisterRow>[] = [
    {
      // The legal name, which is what a register carries (C39).
      key: 'partner',
      header: t.vatRegisters.partner,
      cell: (row) => row.partner_name || t.common.none,
    },
    {
      // A document with two rates shows both here; the export has a line per rate.
      key: 'regimes',
      header: t.vatRegisters.regime,
      cell: (row) =>
        row.slices.map((piece) => regimeLabel(piece.vat_regime_code, piece.vat_rate)).join(', '),
      width: '14rem',
    },
    {
      key: 'net',
      header: t.vatRegisters.net,
      cell: (row) => amount(row.net),
      numeric: true,
      width: '9rem',
    },
    {
      key: 'vat',
      header: t.vatRegisters.vat,
      cell: (row) => amount(row.vat),
      numeric: true,
      width: '8rem',
    },
    {
      key: 'total',
      header: t.vatRegisters.total,
      cell: (row) => amount(row.total),
      numeric: true,
      width: '9rem',
    },
  ]
  return [...shared, ...identity, ...money]
}

export function VatRegisterScreen() {
  const { companyId = '' } = useParams()
  const [side, setSide] = useState<RegisterSide>('sales')
  const [month, setMonth] = useState(today().slice(0, 7))
  // The first day of the month names the period; the server finds it.
  const on = `${month}-01`

  const register = useQuery({
    queryKey: ['vat-register', companyId, side, on],
    queryFn: () => vatRegister(companyId, side, on),
    enabled: month !== '',
  })

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title={t.vatRegisters.title}
        lead={t.vatRegisters.lead}
        actions={
          <a href={vatRegisterExport(companyId, side, on)} className="text-sm text-accent">
            {t.vatRegisters.exportCsv}
          </a>
        }
      />

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <Field label={t.vatRegisters.side}>
            <Select
              value={side}
              onChange={(event) => setSide(event.target.value as RegisterSide)}
              className="w-52"
            >
              <option value="sales">{t.vatRegisters.sales}</option>
              <option value="purchases">{t.vatRegisters.purchases}</option>
            </Select>
          </Field>
          <Field label={t.vatRegisters.month}>
            <Input
              type="month"
              value={month}
              onChange={(event) => setMonth(event.target.value)}
              className="w-44"
            />
          </Field>
        </div>
      </Card>

      {register.isError && <Failure error={register.error} />}
      {register.data && (
        <>
          <p className="text-sm text-ink-muted">
            {t.vatRegisters.period}: {date(register.data.period.start_date)} –{' '}
            {date(register.data.period.end_date)}
            {register.data.period.kind === 'final' ? ` (${t.vatRegisters.finalPeriod})` : ''}
          </p>
          {register.data.unposted > 0 && (
            <p role="status" className="text-sm text-ink-muted">
              {t.vatRegisters.unposted}: {register.data.unposted}
            </p>
          )}
          <Card padding="none">
            <DataGrid
              columns={columnsFor(side)}
              rows={register.data.rows}
              rowKey={(row) => row.document_id}
              emptyMessage={t.vatRegisters.empty}
            />
          </Card>
          <Card>
            <h2 className="type-title-sm mb-3">{t.vatRegisters.byRegime}</h2>
            <dl className="flex flex-wrap gap-8">
              {register.data.by_regime.map((total) => (
                <div key={`${total.vat_regime_code}-${total.vat_rate}`}>
                  <dt className="type-label text-ink-faint">
                    {regimeLabel(total.vat_regime_code, total.vat_rate)}
                  </dt>
                  <dd className="mt-1 font-mono tabular-nums">
                    {amount(total.net)} / {amount(total.vat)}
                  </dd>
                </div>
              ))}
              <Total label={t.vatRegisters.net} value={register.data.totals.net} />
              <Total label={t.vatRegisters.vat} value={register.data.totals.vat} />
              <Total label={t.vatRegisters.total} value={register.data.totals.total} />
              {side === 'purchases' && (
                <Total
                  label={t.vatRegisters.nonDeductible}
                  value={register.data.totals.non_deductible_vat}
                />
              )}
            </dl>
            <p className="mt-3 text-sm text-ink-muted">{t.vatRegisters.totalsFromServer}</p>
          </Card>
        </>
      )}
    </section>
  )
}

function Total({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="type-label text-ink-faint">{label}</dt>
      <dd className="mt-1 font-mono tabular-nums">{amount(value)}</dd>
    </div>
  )
}
