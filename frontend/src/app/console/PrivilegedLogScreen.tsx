/**
 * The privileged paths' log -- Spec A §6.3, read for the first time through the
 * product (ADR-076 §4.3).
 *
 * One row per run: which path, who, when, on which space, with what parameters.
 * Never what the run wrote -- the log never held that. The filter is by path
 * code and by space, and both are typed on the server: the function takes
 * parameters, not SQL.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { t } from '@/locales'
import { privilegedLog, type LogRow } from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { dateTime } from '@/shared/format'
import { Field, Input, PageHeader, Select } from '@/shared/ui'

const LIMITS = [50, 100, 500]

export function PrivilegedLogScreen() {
  const [path, setPath] = useState('')
  const [space, setSpace] = useState('')
  const [limit, setLimit] = useState(100)

  const log = useQuery({
    queryKey: ['console', 'privileged-log', path, space, limit],
    queryFn: () => privilegedLog({ path: path || undefined, space: space || undefined, limit }),
  })

  const columns: Column<LogRow>[] = [
    {
      key: 'when',
      header: t.console.log.when,
      cell: (row) => <span className="font-mono">{dateTime(row.occurred_at)}</span>,
      width: '11rem',
    },
    {
      key: 'path',
      header: t.console.log.path,
      cell: (row) => <span className="font-mono">{row.path_code}</span>,
      width: '5rem',
    },
    {
      key: 'actor',
      header: t.console.log.actor,
      cell: (row) => (
        <span>
          {row.actor_email ?? row.actor}
          {row.actor_email && <span className="text-ink-muted"> · {row.actor}</span>}
        </span>
      ),
    },
    {
      key: 'subject',
      header: t.console.log.subject,
      cell: (row) => (
        <span className="font-mono">
          {row.subject_subdomain ??
            (row.tenant_count ? `${row.tenant_count}` : t.console.log.allSpaces)}
        </span>
      ),
      width: '8rem',
    },
    {
      key: 'payload',
      header: t.console.log.payload,
      cell: (row) => (
        <span className="font-mono type-caption" title={row.justification ?? undefined}>
          {row.payload ? JSON.stringify(row.payload) : ''}
        </span>
      ),
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.log.eyebrow}
        title={t.console.log.title}
        lead={t.console.log.lead}
      />
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t.console.log.path}>
          <Select value={path} onChange={(event) => setPath(event.target.value)}>
            <option value="">{t.console.log.allPaths}</option>
            {(log.data?.paths ?? []).map((entry) => (
              <option key={entry.code} value={entry.code}>
                {entry.code}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t.console.log.space} hint={t.console.log.spaceHint}>
          <Input value={space} onChange={(event) => setSpace(event.target.value)} />
        </Field>
        <Field label={t.console.log.limit}>
          <Select value={String(limit)} onChange={(event) => setLimit(Number(event.target.value))}>
            {LIMITS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {log.isError && <Failure error={log.error} />}
      <DataGrid
        columns={columns}
        rows={log.data?.rows ?? []}
        rowKey={(row) => String(row.id)}
        density="dense"
        emptyMessage={t.console.log.empty}
      />
    </section>
  )
}
