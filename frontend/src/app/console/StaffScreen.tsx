/**
 * Who may enter the console, and as what -- ADR-076 §4.1, ADR-092.
 *
 * Reading is any employee's; granting and revoking are the admin's, and the
 * server says so with a 403 the screen does not wait to hear: the form and the
 * buttons are drawn for an admin only, and the others read the sentence that
 * explains it. A person holds one role at a time, so there is no "change role"
 * -- revoke, then grant, and both dates stay on the row. An admin cannot revoke
 * themselves; the console can never end up with nobody able to reopen it.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { t } from '@/locales'
import {
  grantStaff,
  listStaff,
  revokeStaff,
  staffMe,
  type StaffRole,
  type StaffRow,
} from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { date } from '@/shared/format'
import { Badge, Button, Card, Field, Input, PageHeader, Select } from '@/shared/ui'
import { STAFF_ME_KEY } from './ConsoleLayout'

const LIST_KEY = ['console', 'staff'] as const

const ROLE_HINTS: Record<StaffRole, string> = {
  support: t.console.staff.roleHintSupport,
  operator: t.console.staff.roleHintOperator,
  admin: t.console.staff.roleHintAdmin,
}

export function StaffScreen() {
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const me = useQuery({ queryKey: STAFF_ME_KEY, queryFn: staffMe, retry: false })
  const isAdmin = me.data?.staff_role === 'admin'
  const staff = useQuery({ queryKey: LIST_KEY, queryFn: listStaff })
  const refresh = () => queryClient.invalidateQueries({ queryKey: LIST_KEY })

  const revocation = useMutation({
    mutationFn: revokeStaff,
    onSuccess: () => {
      setNotice(null)
      void refresh()
    },
  })

  const columns: Column<StaffRow>[] = [
    { key: 'email', header: t.console.staff.email, cell: (row) => row.email },
    { key: 'name', header: t.console.staff.name, cell: (row) => row.full_name },
    {
      key: 'role',
      header: t.console.staff.role,
      cell: (row) => t.console.roles[row.staff_role] ?? row.staff_role,
      width: '10rem',
    },
    {
      key: 'granted_by',
      header: t.console.staff.grantedBy,
      cell: (row) => row.granted_by_email,
    },
    {
      key: 'granted_at',
      header: t.console.staff.grantedAt,
      cell: (row) => date(row.granted_at.slice(0, 10)),
      width: '8rem',
    },
    {
      key: 'state',
      header: t.console.staff.revokedAt,
      cell: (row) =>
        row.revoked_at ? (
          <span className="text-ink-muted">{date(row.revoked_at.slice(0, 10))}</span>
        ) : (
          <Badge tone="gold">{t.console.staff.live}</Badge>
        ),
      width: '8rem',
    },
    {
      key: 'action',
      header: '',
      cell: (row) =>
        isAdmin && !row.revoked_at && row.user_id !== me.data?.user_id ? (
          <button
            type="button"
            className="text-danger"
            disabled={revocation.isPending}
            onClick={() => {
              if (window.confirm(t.console.staff.confirmRevoke)) revocation.mutate(row.user_id)
            }}
          >
            {t.console.staff.revoke}
          </button>
        ) : null,
      width: '7rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.staff.eyebrow}
        title={t.console.staff.title}
        lead={t.console.staff.lead}
        actions={
          isAdmin ? (
            <Button icon="plus" onClick={() => setAdding((open) => !open)}>
              {t.console.staff.grant}
            </Button>
          ) : undefined
        }
      />
      {me.data && !isAdmin && (
        <p className="m-0 type-body-md text-ink-muted">{t.console.staff.readOnly}</p>
      )}
      {adding && isAdmin && (
        <GrantForm
          onDone={() => {
            setAdding(false)
            setNotice(t.console.staff.granted)
            void refresh()
          }}
          onCancel={() => setAdding(false)}
        />
      )}
      {notice && <p className="m-0 type-body-md text-ink-muted">{notice}</p>}
      {revocation.isError && <Failure error={revocation.error} />}
      {staff.isError && <Failure error={staff.error} />}
      <DataGrid
        columns={columns}
        rows={staff.data?.staff ?? []}
        rowKey={(row) => `${row.user_id}:${row.granted_at}`}
        density="compact"
        emptyMessage={t.console.staff.empty}
      />
    </section>
  )
}

function GrantForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<StaffRole>('support')
  const grant = useMutation({
    mutationFn: () => grantStaff(email.trim(), role),
    onSuccess: onDone,
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    grant.mutate()
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div>
          <h2 className="m-0 type-title text-heading">{t.console.staff.grant}</h2>
          <p className="mt-1 mb-0 type-body-md text-ink-muted">{t.console.staff.grantLead}</p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label={t.console.staff.email}>
            <Input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>
          <Field label={t.console.staff.role} hint={ROLE_HINTS[role]}>
            <Select value={role} onChange={(event) => setRole(event.target.value as StaffRole)}>
              {(['support', 'operator', 'admin'] as StaffRole[]).map((value) => (
                <option key={value} value={value}>
                  {t.console.roles[value]}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {grant.isError && <Failure error={grant.error} />}
        <div className="flex gap-3">
          <Button type="submit" disabled={grant.isPending}>
            {t.console.staff.save}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            {t.console.staff.cancel}
          </Button>
        </div>
      </form>
    </Card>
  )
}
