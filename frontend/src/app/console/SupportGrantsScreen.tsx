/**
 * Support grants, from the platform's side -- ADR-077 §5, on the console.
 *
 * Two things and a sentence. The list: every request ever made, with its space,
 * ticket, justification and state -- pending, active, expired, revoked -- for
 * every employee to see. The request form: for `support` only, whole space, with
 * the ticket number and the reason, both required because the client's consent
 * screen cannot be written without them. And the sentence under the form that
 * says what happens next: the client approves in their own space, the employee
 * signs in there with their ordinary account, read-only, until revocation or
 * expiry. Nothing here opens anything.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { t } from '@/locales'
import {
  listConsoleGrants,
  requestSupportGrant,
  staffMe,
  type ConsoleGrant,
} from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { dateTime } from '@/shared/format'
import { Badge, Button, Card, Field, Input, PageHeader, type BadgeTone } from '@/shared/ui'
import { STAFF_ME_KEY } from './ConsoleLayout'

const LIST_KEY = ['console', 'support-grants'] as const

export function SupportGrantsScreen() {
  const queryClient = useQueryClient()
  const [asking, setAsking] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const me = useQuery({ queryKey: STAFF_ME_KEY, queryFn: staffMe, retry: false })
  const canRequest = me.data?.staff_role === 'support'
  const grants = useQuery({ queryKey: LIST_KEY, queryFn: listConsoleGrants })

  const columns: Column<ConsoleGrant>[] = [
    {
      key: 'space',
      header: t.console.support.space,
      cell: (row) => (
        <span>
          <span className="font-mono">{row.subdomain}</span>
          <span className="text-ink-muted"> · {row.legal_name}</span>
        </span>
      ),
    },
    {
      key: 'ref',
      header: t.console.support.requestRef,
      cell: (row) => <span className="font-mono">#{row.request_ref}</span>,
      width: '8rem',
    },
    { key: 'by', header: t.console.support.requestedBy, cell: (row) => row.requested_by_email },
    {
      key: 'justification',
      header: t.console.support.justification,
      cell: (row) => row.justification,
    },
    {
      key: 'at',
      header: t.console.support.requestedAt,
      cell: (row) => <span className="font-mono">{dateTime(row.requested_at)}</span>,
      width: '11rem',
    },
    {
      key: 'expires',
      header: t.console.support.expiresAt,
      cell: (row) => (
        <span className="font-mono">{row.expires_at ? dateTime(row.expires_at) : ''}</span>
      ),
      width: '11rem',
    },
    {
      key: 'status',
      header: t.console.support.status,
      cell: (row) => <Badge tone={tone(row.status)}>{label(row.status)}</Badge>,
      width: '8rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.support.eyebrow}
        title={t.console.support.title}
        lead={t.console.support.lead}
        actions={
          canRequest ? (
            <Button icon="plus" onClick={() => setAsking((open) => !open)}>
              {t.console.support.request}
            </Button>
          ) : undefined
        }
      />
      {me.data && !canRequest && (
        <p className="m-0 type-body-md text-ink-muted">{t.console.support.readOnly}</p>
      )}
      {asking && canRequest && (
        <RequestForm
          onDone={() => {
            setAsking(false)
            setNotice(t.console.support.requested)
            void queryClient.invalidateQueries({ queryKey: LIST_KEY })
          }}
          onCancel={() => setAsking(false)}
        />
      )}
      {notice && <p className="m-0 type-body-md text-ink-muted">{notice}</p>}
      {grants.isError && <Failure error={grants.error} />}
      <DataGrid
        columns={columns}
        rows={grants.data?.grants ?? []}
        rowKey={(row) => row.id}
        density="compact"
        emptyMessage={t.console.support.empty}
      />
      <p className="m-0 type-caption text-ink-muted">{t.console.support.howToUse}</p>
    </section>
  )
}

function label(status: ConsoleGrant['status']): string {
  switch (status) {
    case 'pending':
      return t.console.support.statusPending
    case 'active':
      return t.console.support.statusActive
    case 'expired':
      return t.console.support.statusExpired
    case 'revoked':
      return t.console.support.statusRevoked
  }
}

function tone(status: ConsoleGrant['status']): BadgeTone {
  if (status === 'active') return 'gold'
  if (status === 'pending') return 'caution'
  return 'neutral'
}

function RequestForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [space, setSpace] = useState('')
  const [ref, setRef] = useState('')
  const [why, setWhy] = useState('')
  const ask = useMutation({
    mutationFn: () =>
      requestSupportGrant({ space: space.trim(), request_ref: ref.trim(), justification: why.trim() }),
    onSuccess: onDone,
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    ask.mutate()
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div>
          <h2 className="m-0 type-title text-heading">{t.console.support.request}</h2>
          <p className="mt-1 mb-0 type-body-md text-ink-muted">{t.console.support.requestLead}</p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Field label={t.console.support.space} hint={t.console.support.spaceHint}>
            <Input
              value={space}
              onChange={(event) => setSpace(event.target.value)}
              required
              className="font-mono"
            />
          </Field>
          <Field label={t.console.support.requestRef}>
            <Input
              value={ref}
              onChange={(event) => setRef(event.target.value)}
              required
              className="font-mono"
            />
          </Field>
          <Field label={t.console.support.justification}>
            <Input value={why} onChange={(event) => setWhy(event.target.value)} required />
          </Field>
        </div>
        {ask.isError && <Failure error={ask.error} />}
        <div className="flex gap-3">
          <Button type="submit" disabled={ask.isPending}>
            {t.console.support.save}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            {t.console.support.cancel}
          </Button>
        </div>
      </form>
    </Card>
  )
}
