/**
 * One person's exemptions -- the history, not a set of checkboxes.
 *
 * Point 18 of the regulation approved by HG 697/2014 grants and cancels
 * exemptions from the month *following* the one the application was filed or
 * withdrawn in. So the form asks for the **filing date**, and the effective date
 * comes back from the server: computing it here would be a second implementation
 * of the rule, drifting the first time only one of them is edited.
 *
 * **Nothing is ever removed.** A withdrawal closes a row with a date, and the
 * closed row stays visible -- recalculating a past month has to reach the same
 * answer it reached then (`R18`).
 *
 * **There is no ordinary spouse exemption in the list**, and its absence is the
 * point: art. 34 para (2) grants only the increased one, so offering `S` would
 * let somebody claim an exemption the Fiscal Code does not give.
 *
 * **No amounts.** What an exemption is worth is a fiscal parameter resolved by
 * the date of the period being calculated, and it belongs to the payroll run.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import {
  addDependent,
  exemptionEffectiveDate,
  fileExemptionApplication,
  listDependents,
  listExemptions,
  withdrawExemptions,
  type Entitlement,
} from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input, Select } from '@/shared/ui'

/** Five codes. The sixth does not exist, and that is deliberate. */
const CODES = [
  { code: 'P', label: t.payroll.codeP, needsDependent: false },
  { code: 'M', label: t.payroll.codeM, needsDependent: false },
  { code: 'Sm', label: t.payroll.codeSm, needsDependent: false },
  { code: 'N', label: t.payroll.codeN, needsDependent: true },
  { code: 'H', label: t.payroll.codeH, needsDependent: true },
]

const LABELS: Record<string, string> = Object.fromEntries(
  CODES.map((entry) => [entry.code, entry.label]),
)

export function ExemptionsScreen() {
  const { companyId = '', employeeId = '' } = useParams()
  const queryClient = useQueryClient()
  const [on, setOn] = useState('')
  const [asked, setAsked] = useState('')

  const history = useQuery({
    queryKey: ['payroll-exemptions', employeeId, asked],
    queryFn: () => listExemptions(employeeId, asked || undefined),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['payroll-exemptions'] })

  const withdrawal = useMutation({
    mutationFn: (entitlementId: string) =>
      withdrawExemptions(employeeId, {
        filed_on: new Date().toISOString().slice(0, 10),
        entitlement_ids: [entitlementId],
      }),
    onSuccess: refresh,
  })

  const columns: Column<Entitlement>[] = [
    {
      key: 'code',
      header: t.payroll.exemptionCode,
      cell: (row) => LABELS[row.code] ?? row.code,
    },
    {
      key: 'dependent',
      header: t.payroll.dependents,
      cell: (row) => row.dependent_name ?? t.common.none,
      width: '14rem',
    },
    { key: 'from', header: t.payroll.exemptionAppliesFrom, cell: (row) => row.valid_from, width: '9rem' },
    {
      key: 'to',
      header: t.payroll.withdrawn,
      cell: (row) => row.valid_to ?? t.common.none,
      width: '9rem',
    },
    {
      key: 'granted',
      header: t.payroll.grantedBy,
      cell: (row) => row.granted_by_filed_on ?? t.common.none,
      width: '9rem',
    },
    {
      key: 'action',
      header: '',
      cell: (row) =>
        row.valid_to ? null : (
          <button
            type="button"
            className="text-accent"
            onClick={() => withdrawal.mutate(row.id)}
          >
            {t.payroll.withdraw}
          </button>
        ),
      width: '8rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="type-display-2 text-heading">{t.payroll.exemptionHistory}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/angajati`} className="text-sm text-accent">
            {t.payroll.people}
          </Link>
          <form
            className="flex items-end gap-2"
            onSubmit={(event: FormEvent) => {
              event.preventDefault()
              setAsked(on)
            }}
          >
            <Field label={t.payroll.inForceAt}>
              <Input
                type="date"
                value={on}
                onChange={(event) => setOn(event.target.value)}
                className="w-40"
              />
            </Field>
            <Button variant="primary" type="submit">
              {t.payroll.inForceShow}
            </Button>
          </form>
        </div>
      </header>

      <ApplicationForm employeeId={employeeId} onFiled={refresh} />
      <DependentForm employeeId={employeeId} />

      {history.isError && <Failure error={history.error} />}
      {withdrawal.isError && <Failure error={withdrawal.error} />}
      {history.data && (
        <Card padding="none">
          <DataGrid
            columns={columns}
            rows={history.data}
            rowKey={(row) => row.id}
            emptyMessage={t.payroll.noExemptions}
          />
        </Card>
      )}
    </section>
  )
}

function ApplicationForm({
  employeeId,
  onFiled,
}: {
  employeeId: string
  onFiled: () => void
}) {
  const [filedOn, setFiledOn] = useState('')
  const [sole, setSole] = useState(true)
  const [code, setCode] = useState('P')
  const [dependentId, setDependentId] = useState('')

  const dependents = useQuery({
    queryKey: ['payroll-dependents', employeeId],
    queryFn: () => listDependents(employeeId),
  })

  // The rule is the server's. Asking it keeps one implementation of point 18.
  const effective = useQuery({
    queryKey: ['payroll-exemption-effective', filedOn],
    queryFn: () => exemptionEffectiveDate(filedOn),
    enabled: filedOn !== '',
  })

  const file = useMutation({
    mutationFn: () =>
      fileExemptionApplication(employeeId, {
        filed_on: filedOn,
        declared_sole_workplace: sole,
        grants: [{ code, dependent_id: dependentId || null }],
      }),
    onSuccess: () => {
      setFiledOn('')
      setDependentId('')
      onFiled()
    },
  })

  const needsDependent = CODES.find((entry) => entry.code === code)?.needsDependent ?? false
  const complete = filedOn !== '' && (!needsDependent || dependentId !== '')

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        file.mutate()
      }}
    >
      <Field label={t.payroll.filedOn}>
        <Input
          type="date"
          value={filedOn}
          onChange={(event) => setFiledOn(event.target.value)}
          className="w-40"
        />
      </Field>

      <div className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.exemptionAppliesFrom}</span>
        <span className="px-2 py-1 tabular-nums" title={t.payroll.effectiveHint}>
          {effective.data?.effective_from ?? t.common.none}
        </span>
      </div>

      <Field label={t.payroll.exemptionCode}>
        <Select
          value={code}
          onChange={(event) => {
            setCode(event.target.value)
            setDependentId('')
          }}
          className="w-72"
        >
          {CODES.map((entry) => (
            <option key={entry.code} value={entry.code}>
              {entry.label}
            </option>
          ))}
        </Select>
      </Field>

      {needsDependent && (
        <Field label={t.payroll.pickDependent}>
          <Select
            value={dependentId}
            onChange={(event) => setDependentId(event.target.value)}
            className="w-56"
          >
            <option value="">{t.common.none}</option>
            {(dependents.data ?? []).map((dependent) => (
              <option key={dependent.id} value={dependent.id}>
                {dependent.last_name} {dependent.first_name}
              </option>
            ))}
          </Select>
        </Field>
      )}

      <label className="flex items-center gap-2 text-sm" title={t.payroll.soleWorkplaceHint}>
        <input
          type="checkbox"
          checked={sole}
          onChange={(event) => setSole(event.target.checked)}
        />
        <span className="text-ink-muted">{t.payroll.soleWorkplace}</span>
      </label>

      <Button variant="primary" type="submit" disabled={!complete || file.isPending}>
        {t.payroll.submitApplication}
      </Button>
      {file.isError && <Failure error={file.error} />}
    </form>
  )
}

function DependentForm({ employeeId }: { employeeId: string }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [lastName, setLastName] = useState('')
  const [firstName, setFirstName] = useState('')
  const [idnp, setIdnp] = useState('')

  const create = useMutation({
    mutationFn: () =>
      addDependent(employeeId, {
        last_name: lastName.trim(),
        first_name: firstName.trim(),
        idnp: idnp.trim() || null,
      }),
    onSuccess: async () => {
      setLastName('')
      setFirstName('')
      setIdnp('')
      setOpen(false)
      await queryClient.invalidateQueries({ queryKey: ['payroll-dependents', employeeId] })
    },
  })

  if (!open) {
    return (
      <Button variant="secondary" type="button" onClick={() => setOpen(true)} className="self-start">
        {t.payroll.addDependent}
      </Button>
    )
  }

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border p-3"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <Field label={t.payroll.lastName}>
        <Input
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          className="w-40"
        />
      </Field>
      <Field label={t.payroll.firstName}>
        <Input
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          className="w-40"
        />
      </Field>
      <Field label={t.payroll.idnp}>
        <Input
          value={idnp}
          onChange={(event) => setIdnp(event.target.value)}
          maxLength={13}
          title={t.payroll.dependentHint}
          className="w-40 font-mono"
        />
      </Field>
      <Button variant="primary"
        type="submit"
        disabled={lastName.trim() === '' || firstName.trim() === '' || create.isPending}
      >
        {t.common.add}
      </Button>
      <Button variant="secondary" type="button" onClick={() => setOpen(false)}>
        {t.companies.cancel}
      </Button>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}
