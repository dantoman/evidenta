/**
 * The platform's own state, measured now -- ADR-076 §4.3, "Incidente".
 *
 * Four probes and a table. The probes are what the serving process can honestly
 * measure at the moment of the request: the database, the broker and its queue,
 * whether a worker answers. The table is the one durable trace of platform work
 * that exists -- the privileged log -- read as "when did each path last run".
 * There is no job history because no job persists its state yet, and the page
 * says so rather than drawing an empty chart.
 */

import { useQuery } from '@tanstack/react-query'

import { t } from '@/locales'
import { incidents, type Incidents, type Probe } from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { dateTime } from '@/shared/format'
import { Badge, Button, Card, PageHeader } from '@/shared/ui'

type PathRow = Incidents['paths'][number]

export function IncidentsScreen() {
  const state = useQuery({ queryKey: ['console', 'incidents'], queryFn: incidents, retry: false })

  const columns: Column<PathRow>[] = [
    {
      key: 'code',
      header: t.console.incidents.path,
      cell: (row) => (
        <span>
          <span className="font-mono">{row.code}</span>
          <span className="text-ink-muted"> · {row.label}</span>
        </span>
      ),
    },
    {
      key: 'last',
      header: t.console.incidents.lastRun,
      cell: (row) =>
        row.last_run_at ? (
          <span className="font-mono">{dateTime(row.last_run_at)}</span>
        ) : (
          <span className="text-ink-muted">{t.console.incidents.never}</span>
        ),
      width: '11rem',
    },
    {
      key: 'actor',
      header: t.console.incidents.lastActor,
      cell: (row) => row.last_actor ?? '',
      width: '16rem',
    },
  ]

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        eyebrow={t.console.incidents.eyebrow}
        title={t.console.incidents.title}
        lead={t.console.incidents.lead}
        actions={
          <Button
            icon="refresh-cw"
            variant="secondary"
            onClick={() => void state.refetch()}
            disabled={state.isFetching}
          >
            {t.console.incidents.refresh}
          </Button>
        }
      />
      {state.isError && <Failure error={state.error} />}
      {state.data && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <ProbeCard title={t.console.incidents.database} probe={state.data.database} />
          <ProbeCard title={t.console.incidents.broker} probe={state.data.broker} />
          <ProbeCard
            title={t.console.incidents.workers}
            probe={state.data.workers}
            emptyDetail={t.console.incidents.noWorkers}
          />
          <Card>
            <h2 className="m-0 type-label text-ink-muted">{t.console.incidents.queues}</h2>
            <ul className="mt-2 mb-0 flex list-none flex-col gap-1 p-0">
              {state.data.queues.map((queue) => (
                <li key={queue.name} className="flex items-baseline justify-between gap-3">
                  <span className="font-mono">{queue.name}</span>
                  <span className="type-figure-md">
                    {queue.depth ?? t.console.incidents.unknown}{' '}
                    <span className="type-caption text-ink-muted">
                      {queue.depth === null ? queue.detail : t.console.incidents.depth}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
      <div className="flex flex-col gap-3">
        <h2 className="m-0 type-title text-heading">{t.console.incidents.paths}</h2>
        <p className="m-0 type-caption text-ink-muted">{t.console.incidents.noJobs}</p>
        <DataGrid
          columns={columns}
          rows={state.data?.paths ?? []}
          rowKey={(row) => row.code}
          density="compact"
          emptyMessage={t.console.incidents.never}
        />
      </div>
    </section>
  )
}

function ProbeCard({
  title,
  probe,
  emptyDetail,
}: {
  title: string
  probe: Probe
  emptyDetail?: string
}) {
  return (
    <Card>
      <h2 className="m-0 type-label text-ink-muted">{title}</h2>
      <div className="mt-2 flex items-center gap-3">
        <Badge tone={probe.ok ? 'gold' : 'debit'}>
          {probe.ok ? t.console.incidents.ok : t.console.incidents.down}
        </Badge>
        {probe.latency_ms !== null && (
          <span className="type-figure-sm text-ink-muted">
            {probe.latency_ms} {t.console.incidents.latency}
          </span>
        )}
      </div>
      <p className="mt-2 mb-0 type-caption text-ink-muted">
        {probe.detail ?? (probe.ok ? '' : emptyDetail ?? '')}
        {probe.ok && !probe.detail && emptyDetail && probe.name === 'workers' ? '' : ''}
      </p>
    </Card>
  )
}
