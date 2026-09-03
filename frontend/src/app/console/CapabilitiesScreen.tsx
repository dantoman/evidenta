/**
 * Capability activations across every space -- R25 as a list (ADR-076 §4.3).
 *
 * Read only. A capability is activated by the client, inside their own space,
 * with an effective date and an initialisation state; the console shows the
 * fact and does not act on their behalf.
 */

import { useQuery } from '@tanstack/react-query'

import { t } from '@/locales'
import { listActivations, type Activation } from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { date } from '@/shared/format'
import { Badge, PageHeader } from '@/shared/ui'

export function CapabilitiesScreen() {
  const activations = useQuery({ queryKey: ['console', 'capabilities'], queryFn: listActivations })

  const columns: Column<Activation>[] = [
    {
      key: 'space',
      header: t.console.capabilities.space,
      cell: (row) => (
        <span>
          <span className="font-mono">{row.subdomain}</span>
          <span className="text-ink-muted"> · {row.legal_name}</span>
        </span>
      ),
    },
    {
      key: 'company',
      header: t.console.capabilities.company,
      cell: (row) =>
        row.company_legal_name ? (
          <span>
            {row.company_legal_name}
            {row.company_idno && <span className="font-mono text-ink-muted"> {row.company_idno}</span>}
          </span>
        ) : (
          <span className="text-ink-muted">{t.console.capabilities.wholeSpace}</span>
        ),
    },
    {
      key: 'capability',
      header: t.console.capabilities.capability,
      cell: (row) => <span className="font-mono">{row.capability_key}</span>,
      width: '14rem',
    },
    {
      key: 'from',
      header: t.console.capabilities.from,
      cell: (row) => date(row.effective_from),
      width: '8rem',
    },
    {
      key: 'to',
      header: t.console.capabilities.to,
      cell: (row) => (row.effective_to ? date(row.effective_to) : ''),
      width: '8rem',
    },
    {
      key: 'state',
      header: t.console.capabilities.state,
      cell: (row) => <Badge tone="neutral">{row.initialisation_state}</Badge>,
      width: '9rem',
    },
    {
      key: 'source',
      header: t.console.capabilities.source,
      cell: (row) => row.source,
      width: '8rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.capabilities.eyebrow}
        title={t.console.capabilities.title}
        lead={t.console.capabilities.lead}
      />
      {activations.isError && <Failure error={activations.error} />}
      <DataGrid
        columns={columns}
        rows={activations.data?.activations ?? []}
        rowKey={(row) => row.id}
        density="compact"
        emptyMessage={t.console.capabilities.empty}
      />
    </section>
  )
}
