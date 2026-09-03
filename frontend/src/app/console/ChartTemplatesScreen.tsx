/**
 * The versions of the general chart of accounts -- `P-10` as a list (ADR-076 §4.3).
 *
 * Read only: a version is loaded from the CSV the operator holds, which no screen
 * can do, and published by the same load. The console adds the overview: which
 * versions exist, from when, under which act, with how many accounts.
 */

import { useQuery } from '@tanstack/react-query'

import { t } from '@/locales'
import { listChartTemplates, type ChartTemplate } from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { date } from '@/shared/format'
import { Badge, PageHeader } from '@/shared/ui'

export function ChartTemplatesScreen() {
  const templates = useQuery({ queryKey: ['console', 'coa-templates'], queryFn: listChartTemplates })

  const columns: Column<ChartTemplate>[] = [
    {
      key: 'code',
      header: t.console.chart.code,
      cell: (row) => <span className="font-mono">{row.code}</span>,
      width: '10rem',
    },
    {
      key: 'version',
      header: t.console.chart.version,
      cell: (row) => <span className="font-mono">{row.version}</span>,
      width: '7rem',
    },
    {
      key: 'status',
      header: t.console.chart.status,
      cell: (row) => (
        <Badge tone={row.status === 'published' ? 'gold' : 'caution'}>
          {row.status === 'published' ? t.console.chart.statusPublished : t.console.chart.statusDraft}
        </Badge>
      ),
      width: '8rem',
    },
    {
      key: 'from',
      header: t.console.chart.from,
      cell: (row) => (row.valid_from ? date(row.valid_from) : ''),
      width: '8rem',
    },
    {
      key: 'to',
      header: t.console.chart.to,
      cell: (row) => (row.valid_to ? date(row.valid_to) : ''),
      width: '8rem',
    },
    {
      key: 'act',
      header: t.console.chart.act,
      cell: (row) => (
        <span title={row.act?.title ?? undefined}>
          {row.act ? `${row.act.act_type} ${row.act.act_number}` : row.source_act}
          {row.source_reference && <span className="text-ink-muted"> · {row.source_reference}</span>}
        </span>
      ),
    },
    {
      key: 'accounts',
      header: t.console.chart.accounts,
      cell: (row) => row.account_count,
      numeric: true,
      width: '7rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.chart.eyebrow}
        title={t.console.chart.title}
        lead={t.console.chart.lead}
      />
      {templates.isError && <Failure error={templates.error} />}
      <DataGrid
        columns={columns}
        rows={templates.data?.templates ?? []}
        rowKey={(row) => row.id}
        density="compact"
        emptyMessage={t.console.chart.empty}
      />
    </section>
  )
}
