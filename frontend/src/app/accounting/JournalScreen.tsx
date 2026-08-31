/**
 * The document journal -- one family's posted documents over a window.
 *
 * **It says what it is not.** The statutory VAT registers have a prescribed form
 * and columns that cannot be filled while no document carries VAT; this is the
 * journal of documents, and the lead says so rather than letting somebody file it
 * as something it is not.
 *
 * **The family is the module's name.** Which document types "sales" means is the
 * server's answer, so this screen holds no copy of that vocabulary.
 *
 * **Nothing here adds anything up** (`C19`), and the export is a link rather than
 * a fetch (`C20`): the browser downloads it with the session cookie, and the
 * server builds it from the same result it rendered.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'

import { t } from '@/locales'
import {
  documentJournal,
  documentJournalExport,
  type JournalFamily,
  type JournalRow,
} from '@/shared/api/ledger'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount } from '@/shared/format'
import { Card, Field, Input, PageHeader, Select } from '@/shared/ui'

const FAMILY_LABELS: Record<JournalFamily, string> = {
  sales: t.journals.sales,
  purchases: t.journals.purchases,
  treasury: t.journals.treasury,
}

const columns: Column<JournalRow>[] = [
  {
    key: 'accounting_date',
    header: t.journals.accountingDate,
    cell: (row) => row.accounting_date,
    width: '9rem',
  },
  {
    key: 'document_date',
    header: t.journals.documentDate,
    cell: (row) => row.document_date,
    width: '9rem',
  },
  {
    key: 'number',
    header: t.journals.number,
    cell: (row) => <span className="font-mono">{row.formatted_number ?? t.common.none}</span>,
    width: '12rem',
  },
  {
    // The legal name, which is what a register carries (C39).
    key: 'partner',
    header: t.journals.partner,
    cell: (row) => row.partner_name || t.common.none,
  },
  {
    key: 'net',
    header: t.journals.net,
    cell: (row) => amount(row.net),
    numeric: true,
    width: '10rem',
  },
  {
    key: 'vat',
    header: t.journals.vat,
    cell: (row) => amount(row.vat),
    numeric: true,
    width: '9rem',
  },
  {
    key: 'total',
    header: t.journals.total,
    cell: (row) => amount(row.total),
    numeric: true,
    width: '10rem',
  },
]

export function JournalScreen() {
  const { companyId = '' } = useParams()
  const [family, setFamily] = useState<JournalFamily>('sales')
  const [from, setFrom] = useState('2026-01-01')
  const [to, setTo] = useState('2026-01-31')

  const journal = useQuery({
    queryKey: ['document-journal', companyId, family, from, to],
    queryFn: () => documentJournal(companyId, family, from, to),
  })

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title={t.journals.title}
        lead={t.journals.lead}
        actions={
          <a
            href={documentJournalExport(companyId, family, from, to)}
            className="text-sm text-accent"
          >
            {t.journals.exportCsv}
          </a>
        }
      />

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <Field label={t.journals.family}>
            <Select
              value={family}
              onChange={(event) => setFamily(event.target.value as JournalFamily)}
              className="w-52"
            >
              <option value="sales">{FAMILY_LABELS.sales}</option>
              <option value="purchases">{FAMILY_LABELS.purchases}</option>
              <option value="treasury">{FAMILY_LABELS.treasury}</option>
            </Select>
          </Field>
          <Field label={t.journals.from}>
            <Input
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
              className="w-40"
            />
          </Field>
          <Field label={t.journals.to}>
            <Input
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
              className="w-40"
            />
          </Field>
        </div>
      </Card>

      {journal.isError && <Failure error={journal.error} />}
      {journal.data && (
        <>
          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={journal.data.rows}
              rowKey={(row) => row.document_id}
              emptyMessage={t.journals.empty}
            />
          </Card>
          <Card>
            <dl className="flex flex-wrap gap-8">
              <Total label={t.journals.net} value={journal.data.totals.net} />
              <Total label={t.journals.vat} value={journal.data.totals.vat} />
              <Total label={t.journals.total} value={journal.data.totals.total} />
            </dl>
            <p className="mt-3 text-sm text-ink-muted">{t.journals.totalsFromServer}</p>
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
