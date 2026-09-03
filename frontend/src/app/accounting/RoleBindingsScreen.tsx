/**
 * Conturi de sistem: which account each role means for this company, from when.
 *
 * The engine never writes an account code. A handler asks for a role -- the
 * till, VAT collected, trade receivables -- and the company's binding says which
 * account of its chart that is (ADR-036, `R28`). An unbound role is a refusal at
 * posting, and the panel already reported one ("no cash account is bound") with
 * nothing to click. This is the screen that sentence was pointing at.
 *
 * **A change is a rebinding, dated, never an edit of the row.** The server
 * closes the binding in force on the day the new one starts, so the postings
 * made before that day keep the account they were made with and the ones after
 * reach the new one. The date is typed by the person, defaulting to the date the
 * table is read at -- never to "today" silently, because the company that needs
 * this is usually correcting a setup made months ago.
 *
 * **Only accounts of the same class are offered.** The plan fixes which class a
 * meaning lives in; a company keeps its own analytic under it. The server
 * refuses the rest (`slots.account_class_mismatch`), and offering it would be
 * offering the mistake. The list is what may be posted to on the chosen date,
 * so a blocked or closed account is not on it either.
 *
 * Role keys are shown as the engine names them. They are the vocabulary a
 * refusal cites, and a translated label beside a code the message names would
 * be a second vocabulary to learn.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'

import { t } from '@/locales'
import { listAccounts } from '@/shared/api/coa'
import { listRoleBindings, rebindRole, type RoleBindingRow } from '@/shared/api/slots'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Button, Field, Input, Select } from '@/shared/ui'

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/** The row being changed, with what the person has typed so far. */
interface Change {
  role: string
  account_id: string
  valid_from: string
}

export function RoleBindingsScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [on, setOn] = useState(today)
  const [change, setChange] = useState<Change | null>(null)

  const bindings = useQuery({
    queryKey: ['role-bindings', companyId, on],
    queryFn: () => listRoleBindings(companyId, on),
  })

  // The chart as a posting on the new binding's date may use it -- `?on=`
  // narrows to valid and unblocked, which is exactly what the server will
  // accept. Asked only while a row is open.
  const accounts = useQuery({
    queryKey: ['accounts', companyId, change?.valid_from ?? ''],
    queryFn: () => listAccounts(companyId, change?.valid_from),
    enabled: change !== null,
  })

  const save = useMutation({
    mutationFn: (pending: Change) =>
      rebindRole(companyId, pending.role, {
        account_id: pending.account_id,
        valid_from: pending.valid_from,
      }),
    onSuccess: async () => {
      setChange(null)
      await queryClient.invalidateQueries({ queryKey: ['role-bindings', companyId] })
    },
  })

  const strings = t.accounting.roleBindings

  const sameClass = (row: RoleBindingRow) =>
    (accounts.data ?? []).filter(
      (account) => account.account_code.charAt(0) === row.default_code.charAt(0),
    )

  const columns: Column<RoleBindingRow>[] = [
    {
      key: 'role',
      header: strings.role,
      cell: (row) => <span className="font-mono">{row.role}</span>,
      width: '20rem',
    },
    {
      key: 'default_code',
      header: strings.defaultCode,
      cell: (row) => <span className="font-mono">{row.default_code}</span>,
      width: '8rem',
    },
    {
      key: 'account',
      header: strings.account,
      cell: (row) =>
        change?.role === row.role ? (
          <Select
            value={change.account_id}
            onChange={(event) => setChange({ ...change, account_id: event.target.value })}
            aria-label={`${strings.newAccount} ${row.role}`}
          >
            <option value="" />
            {sameClass(row).map((account) => (
              <option key={account.id} value={account.id}>
                {account.account_code} — {account.name_ro}
              </option>
            ))}
          </Select>
        ) : row.account_code ? (
          <>
            <span className="font-mono">{row.account_code}</span>{' '}
            <span className="text-ink-muted">{row.name_ro}</span>
          </>
        ) : (
          <span className="text-danger">{strings.unbound}</span>
        ),
    },
    {
      key: 'valid_from',
      header: strings.validFrom,
      cell: (row) =>
        change?.role === row.role ? (
          <Input
            type="date"
            value={change.valid_from}
            onChange={(event) => setChange({ ...change, valid_from: event.target.value })}
            aria-label={`${strings.newFrom} ${row.role}`}
          />
        ) : (
          (row.valid_from ?? '—')
        ),
      width: '11rem',
    },
    {
      key: 'source',
      header: strings.source,
      cell: (row) => (row.source === 'company' ? strings.sourceCompany : (row.source ?? '')),
      width: '14rem',
    },
    {
      key: 'actions',
      header: '',
      cell: (row) =>
        change?.role === row.role ? (
          <span className="flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => save.mutate(change)}
              disabled={change.account_id === '' || change.valid_from === '' || save.isPending}
            >
              {strings.save}
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={() => setChange(null)}>
              {strings.cancel}
            </Button>
          </span>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => setChange({ role: row.role, account_id: '', valid_from: on })}
          >
            {row.account_id ? strings.change : strings.bind}
          </Button>
        ),
      width: '12rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="type-display-2 text-heading">{strings.title}</h1>
          <p className="text-sm text-ink-muted">{strings.lead}</p>
        </div>
        <Field label={strings.on}>
          <Input
            type="date"
            value={on}
            onChange={(event) => {
              setOn(event.target.value)
              setChange(null)
            }}
          />
        </Field>
      </header>

      {bindings.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {bindings.isError && <Failure error={bindings.error} />}

      {bindings.data && (
        <>
          <DataGrid
            columns={columns}
            rows={bindings.data}
            rowKey={(row) => row.role}
            emptyMessage={strings.empty}
          />
          <p className="text-sm text-ink-muted">{strings.sameClassHint}</p>
        </>
      )}

      {accounts.isError && <Failure error={accounts.error} />}
      {save.isError && <Failure error={save.error} />}
    </section>
  )
}
