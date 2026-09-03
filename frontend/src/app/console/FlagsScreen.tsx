/**
 * Release rings and feature flags -- Spec A §13.5, R23 (ADR-076 §4.3).
 *
 * Two catalogues and two assignments, read only: nothing in the product writes
 * an assignment yet, and a button here would invent a path. When one exists it
 * goes through the privileged log like every other platform act. A compliance
 * flag is marked as such because R24 says it is never switched off for a client.
 */

import { useQuery } from '@tanstack/react-query'

import { t } from '@/locales'
import { flagsPage, type FlagsPage } from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { date } from '@/shared/format'
import { Badge, PageHeader } from '@/shared/ui'

type Flag = FlagsPage['flags'][number]
type Ring = FlagsPage['rings'][number]
type Assignment = FlagsPage['ring_assignments'][number]
type Override = FlagsPage['overrides'][number]

export function FlagsScreen() {
  const page = useQuery({ queryKey: ['console', 'flags'], queryFn: flagsPage })

  const flagColumns: Column<Flag>[] = [
    {
      key: 'key',
      header: t.console.flags.key,
      cell: (row) => <span className="font-mono">{row.key}</span>,
      width: '16rem',
    },
    { key: 'description', header: t.console.flags.description, cell: (row) => row.description },
    {
      key: 'default',
      header: t.console.flags.defaultState,
      cell: (row) => (row.default_state ? t.console.flags.on : t.console.flags.off),
      width: '7rem',
    },
    {
      key: 'compliance',
      header: t.console.flags.compliance,
      cell: (row) =>
        row.is_compliance ? (
          <span title={t.console.flags.complianceHint}>
            <Badge tone="gold">{t.console.flags.compliance}</Badge>
          </span>
        ) : null,
      width: '9rem',
    },
  ]

  const ringColumns: Column<Ring>[] = [
    {
      key: 'code',
      header: t.console.flags.ring,
      cell: (row) => <span className="font-mono">{row.code}</span>,
      width: '10rem',
    },
    { key: 'description', header: t.console.flags.description, cell: (row) => row.description },
    {
      key: 'sequence',
      header: t.console.flags.sequence,
      cell: (row) => row.sequence,
      numeric: true,
      width: '6rem',
    },
  ]

  const assignmentColumns: Column<Assignment>[] = [
    {
      key: 'space',
      header: t.console.flags.space,
      cell: (row) => (
        <span>
          <span className="font-mono">{row.subdomain}</span>
          <span className="text-ink-muted"> · {row.legal_name}</span>
        </span>
      ),
    },
    {
      key: 'ring',
      header: t.console.flags.ring,
      cell: (row) => <span className="font-mono">{row.ring_code}</span>,
      width: '10rem',
    },
    {
      key: 'at',
      header: t.console.flags.assignedAt,
      cell: (row) => date(row.assigned_at.slice(0, 10)),
      width: '8rem',
    },
    {
      key: 'by',
      header: t.console.flags.assignedBy,
      cell: (row) => row.assigned_by_email ?? '',
    },
  ]

  const overrideColumns: Column<Override>[] = [
    {
      key: 'space',
      header: t.console.flags.space,
      cell: (row) => (
        <span>
          <span className="font-mono">{row.subdomain}</span>
          <span className="text-ink-muted"> · {row.legal_name}</span>
        </span>
      ),
    },
    {
      key: 'flag',
      header: t.console.flags.key,
      cell: (row) => <span className="font-mono">{row.flag_key}</span>,
      width: '14rem',
    },
    {
      key: 'state',
      header: t.console.flags.state,
      cell: (row) => (row.state ? t.console.flags.on : t.console.flags.off),
      width: '6rem',
    },
    { key: 'reason', header: t.console.flags.reason, cell: (row) => row.reason },
    {
      key: 'expires',
      header: t.console.flags.expiresAt,
      cell: (row) => date(row.expires_at.slice(0, 10)),
      width: '8rem',
    },
  ]

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        eyebrow={t.console.flags.eyebrow}
        title={t.console.flags.title}
        lead={t.console.flags.lead}
      />
      {page.isError && <Failure error={page.error} />}
      <p className="m-0 type-body-md text-ink-muted">{t.console.flags.readOnly}</p>

      <Section title={t.console.flags.flagsTitle}>
        <DataGrid
          columns={flagColumns}
          rows={page.data?.flags ?? []}
          rowKey={(row) => row.key}
          density="compact"
          emptyMessage={t.console.flags.emptyOverrides}
        />
      </Section>
      <Section title={t.console.flags.ringsTitle}>
        <DataGrid
          columns={ringColumns}
          rows={page.data?.rings ?? []}
          rowKey={(row) => row.code}
          density="compact"
          emptyMessage={t.console.flags.emptyAssignments}
        />
      </Section>
      <Section title={t.console.flags.assignmentsTitle}>
        <DataGrid
          columns={assignmentColumns}
          rows={page.data?.ring_assignments ?? []}
          rowKey={(row) => row.subdomain}
          density="compact"
          emptyMessage={t.console.flags.emptyAssignments}
        />
      </Section>
      <Section title={t.console.flags.overridesTitle}>
        <DataGrid
          columns={overrideColumns}
          rows={page.data?.overrides ?? []}
          rowKey={(row) => row.id}
          density="compact"
          emptyMessage={t.console.flags.emptyOverrides}
        />
      </Section>
    </section>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="m-0 type-title text-heading">{title}</h2>
      {children}
    </div>
  )
}
