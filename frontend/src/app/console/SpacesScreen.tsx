/**
 * The spaces -- every client's workspace as the platform sees it (ADR-076 §4.3).
 *
 * The row is the `tenant` row and nothing of what is inside: subdomain, name,
 * status, dates, and two counts. A count of companies is metadata about a space;
 * the companies themselves never reach this host, and the server's function
 * returns no column that could carry them.
 *
 * No actions, on purpose. Creating a space from the console is foreseen (ADR-078
 * §3.1) and not built -- it needs the claim path (P-11); suspending and archiving
 * are regimes the product does not serve yet (Spec A §9.4). The note under the
 * list says so instead of a disabled button pretending otherwise.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { t } from '@/locales'
import { listSpaces, type Space } from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { date } from '@/shared/format'
import { Badge, Field, Input, PageHeader, type BadgeTone } from '@/shared/ui'

export function SpacesScreen() {
  const [filter, setFilter] = useState('')
  const spaces = useQuery({ queryKey: ['console', 'spaces'], queryFn: listSpaces })

  const needle = filter.trim().toLocaleLowerCase('ro-MD')
  const rows = (spaces.data?.spaces ?? []).filter(
    (row) =>
      !needle ||
      row.subdomain.includes(needle) ||
      row.legal_name.toLocaleLowerCase('ro-MD').includes(needle),
  )

  const columns: Column<Space>[] = [
    {
      key: 'subdomain',
      header: t.console.spaces.subdomain,
      cell: (row) => <span className="font-mono">{row.subdomain}</span>,
      width: '10rem',
    },
    {
      key: 'name',
      header: t.console.spaces.legalName,
      cell: (row) => (
        <span>
          {row.legal_name}
          {row.legal_form && <span className="text-ink-muted"> · {row.legal_form}</span>}
        </span>
      ),
    },
    {
      key: 'idno',
      header: t.console.spaces.idno,
      cell: (row) => <span className="font-mono">{row.idno ?? ''}</span>,
      width: '10rem',
    },
    {
      key: 'status',
      header: t.console.spaces.status,
      cell: (row) => (
        <span className="flex gap-2">
          <Badge tone={statusTone(row.status)}>{statusLabel(row.status)}</Badge>
          {row.claimed_at ? null : <Badge tone="caution">{t.console.spaces.unclaimed}</Badge>}
        </span>
      ),
      width: '14rem',
    },
    {
      key: 'companies',
      header: t.console.spaces.companies,
      cell: (row) => row.company_count,
      numeric: true,
      width: '7rem',
    },
    {
      key: 'members',
      header: t.console.spaces.members,
      cell: (row) => row.member_count,
      numeric: true,
      width: '7rem',
    },
    {
      key: 'created',
      header: t.console.spaces.createdAt,
      cell: (row) => (row.created_at ? date(row.created_at.slice(0, 10)) : ''),
      width: '8rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.spaces.eyebrow}
        title={t.console.spaces.title}
        lead={t.console.spaces.lead}
      />
      <Field label={t.console.spaces.filter}>
        <Input value={filter} onChange={(event) => setFilter(event.target.value)} />
      </Field>
      {spaces.isError && <Failure error={spaces.error} />}
      <DataGrid
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        density="compact"
        emptyMessage={t.console.spaces.empty}
      />
      <p className="m-0 type-caption text-ink-muted">{t.console.spaces.noActions}</p>
    </section>
  )
}

function statusLabel(status: string): string {
  switch (status) {
    case 'active':
      return t.console.spaces.statusActive
    case 'suspended':
      return t.console.spaces.statusSuspended
    case 'offboarding':
      return t.console.spaces.statusOffboarding
    case 'archived':
      return t.console.spaces.statusArchived
    default:
      return status
  }
}

function statusTone(status: string): BadgeTone {
  if (status === 'active') return 'gold'
  if (status === 'archived') return 'neutral'
  return 'caution'
}
