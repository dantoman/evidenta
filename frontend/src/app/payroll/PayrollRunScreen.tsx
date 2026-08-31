/**
 * The monthly calculation: the register, and one payslip at a time.
 *
 * **A line with no amount is shown as a reason, never as a zero.** A rate whose
 * margin was never established applies on no date, and the honest rendering of
 * that is the sentence the server produced -- which names the parameter and the
 * date. Approval is refused while any of them is open, and the screen says so
 * before the button is pressed rather than after.
 *
 * **Two dates, and the form asks for the second.** The month is the work period;
 * the accrual date is when the pay was calculated, and it is what selects the
 * rates. A March salary calculated in June accrues in June.
 *
 * **Nothing is totalled here** (`C19`). Every figure on this screen is a string
 * the server sent, including the net -- which is the gross less the withholdings,
 * derived once, on the server, so the register and the payslip cannot disagree.
 *
 * **The payslip is a document.** Its text, its month name and its decimal
 * separator come from the server in Romanian at fixed `ro-MD` conventions
 * (`C38`); this screen only lays them out. A printable file waits for the
 * document pipeline (`OD-74`).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import {
  approveRun,
  createRun,
  getPayslip,
  getRun,
  listRuns,
  recomputeRun,
  type RunLine,
} from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input } from '@/shared/ui'

export function PayrollRunScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)

  const runs = useQuery({
    queryKey: ['payroll-runs', companyId],
    queryFn: () => listRuns(companyId),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['payroll-runs'] })

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="type-display-2 text-heading">{t.payroll.runs}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/angajati`} className="text-sm text-accent">
            {t.payroll.people}
          </Link>
          <Link to={`/companii/${companyId}/pontaj`} className="text-sm text-accent">
            {t.payroll.timesheets}
          </Link>
          <Link to={`/companii/${companyId}/darea-de-seama`} className="text-sm text-accent">
            {t.payroll.ipc}
          </Link>
        </div>
      </header>

      <NewRunForm companyId={companyId} onCreated={refresh} />

      {runs.isError && <Failure error={runs.error} />}
      {runs.data && (
        <ul className="flex flex-wrap gap-3 text-sm">
          {runs.data.length === 0 && <li className="text-ink-muted">{t.payroll.noRuns}</li>}
          {runs.data.map((run) => (
            <li key={run.id}>
              <Button variant="secondary"
                type="button"
                onClick={() => setSelected(selected === run.id ? null : run.id)}
                className="${selected === run.id ? 'text-ink' : ''}"
              >
                {run.year}-{String(run.month).padStart(2, '0')} ·{' '}
                {run.status === 'approved' ? t.payroll.approved : t.payroll.draft}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {selected && <Register runId={selected} onChanged={refresh} />}
    </section>
  )
}

function NewRunForm({
  companyId,
  onCreated,
}: {
  companyId: string
  onCreated: () => void
}) {
  const now = new Date()
  const [year, setYear] = useState(String(now.getFullYear()))
  const [month, setMonth] = useState(String(now.getMonth() + 1))
  const [accrualDate, setAccrualDate] = useState('')

  const create = useMutation({
    mutationFn: () =>
      createRun(companyId, {
        year: Number(year),
        month: Number(month),
        accrual_date: accrualDate,
      }),
    onSuccess: onCreated,
  })

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <Field label={t.payroll.year}>
        <Input
          inputMode="numeric"
          value={year}
          onChange={(event) => setYear(event.target.value)}
          className="w-24 tabular-nums"
        />
      </Field>
      <Field label={t.payroll.month}>
        <Input
          inputMode="numeric"
          value={month}
          onChange={(event) => setMonth(event.target.value)}
          className="w-16 tabular-nums"
        />
      </Field>
      <Field label={t.payroll.accrualDate}>
        <Input
          type="date"
          value={accrualDate}
          onChange={(event) => setAccrualDate(event.target.value)}
          title={t.payroll.accrualHint}
          className="w-40"
        />
      </Field>
      <Button variant="primary" type="submit" disabled={accrualDate === '' || create.isPending}>
        {t.payroll.compute}
      </Button>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}

function Register({ runId, onChanged }: { runId: string; onChanged: () => void }) {
  const queryClient = useQueryClient()
  const [payslipFor, setPayslipFor] = useState<string | null>(null)

  const run = useQuery({ queryKey: ['payroll-run', runId], queryFn: () => getRun(runId) })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['payroll-run', runId] })
    onChanged()
  }

  const recompute = useMutation({ mutationFn: () => recomputeRun(runId), onSuccess: refresh })
  const approve = useMutation({ mutationFn: () => approveRun(runId), onSuccess: refresh })

  const columns: Column<RunLine>[] = [
    { key: 'employee', header: t.payroll.people, cell: (row) => row.employee_name },
    {
      key: 'contract',
      header: t.payroll.contractNumber,
      cell: (row) => <span className="font-mono">{row.contract_number}</span>,
      width: '10rem',
    },
    { key: 'gross', header: t.payroll.gross, cell: (row) => row.gross, numeric: true, width: '9rem' },
    {
      key: 'withheld',
      header: t.payroll.withheld,
      cell: (row) => row.withheld,
      numeric: true,
      width: '9rem',
    },
    {
      key: 'charges',
      header: t.payroll.employerCharges,
      cell: (row) => row.employer_charges,
      numeric: true,
      width: '12rem',
    },
    {
      key: 'net',
      header: t.payroll.net,
      // Never a zero where the server sent nothing: an amount that could not be
      // calculated is not an amount of zero.
      cell: (row) => row.net ?? t.payroll.notComputed,
      numeric: true,
      width: '9rem',
    },
    {
      key: 'payslip',
      header: '',
      cell: (row) => (
        <button
          type="button"
          className="text-accent"
          onClick={() => setPayslipFor(payslipFor === row.employee_id ? null : row.employee_id)}
        >
          {t.payroll.payslip}
        </button>
      ),
      width: '8rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4 rounded border border-border bg-surface p-4">
      {run.isError && <Failure error={run.error} />}
      {run.data && (
        <>
          <header className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-sm font-semibold">
              {run.data.year}-{String(run.data.month).padStart(2, '0')} ·{' '}
              {t.payroll.accrualDate}: {run.data.accrual_date}
            </h2>
            {run.data.status === 'draft' && (
              <div className="flex items-center gap-3">
                <Button variant="secondary"
                  type="button"
                  onClick={() => recompute.mutate()}
                  disabled={recompute.isPending}
                >
                  {t.payroll.recompute}
                </Button>
                <Button variant="secondary"
                  type="button"
                  onClick={() => approve.mutate()}
                  disabled={approve.isPending || !run.data.complete}
                  title={run.data.complete ? undefined : t.payroll.incompleteHint}
                >
                  {t.payroll.approve}
                </Button>
              </div>
            )}
          </header>

          {!run.data.complete && (
            <p role="status" className="text-sm text-danger">
              {run.data.unresolved} {t.payroll.unresolvedCount}. {t.payroll.incompleteHint}
            </p>
          )}
          {recompute.isError && <Failure error={recompute.error} />}
          {approve.isError && <Failure error={approve.error} />}

          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={run.data.lines ?? []}
              rowKey={(row) => row.employee_id}
              emptyMessage={t.payroll.noRuns}
              serverTotals={
                run.data.totals
                  ? {
                      gross: run.data.totals.gross,
                      withheld: run.data.totals.withheld,
                      charges: run.data.totals.employer_charges,
                      net: run.data.totals.net,
                    }
                  : undefined
              }
            />
          </Card>

          <Reasons lines={run.data.lines ?? []} />

          {payslipFor && <PayslipView runId={runId} employeeId={payslipFor} />}
        </>
      )}
    </section>
  )
}

/** Every amount that could not be calculated, with the sentence the server gave. */
function Reasons({ lines }: { lines: RunLine[] }) {
  const open = lines.flatMap((line) =>
    line.components
      .filter((component) => component.amount === null)
      .map((component) => ({
        who: line.employee_name,
        what: component.component_key,
        why: component.unresolved_reason ?? '',
      })),
  )
  if (open.length === 0) return null

  return (
    <ul className="flex flex-col gap-1 text-sm text-ink-muted">
      {open.map((entry, index) => (
        <li key={`${entry.who}-${entry.what}-${index}`}>
          <span className="font-mono">{entry.what}</span> · {entry.who} — {entry.why}
        </li>
      ))}
    </ul>
  )
}

function PayslipView({ runId, employeeId }: { runId: string; employeeId: string }) {
  const slip = useQuery({
    queryKey: ['payroll-payslip', runId, employeeId],
    queryFn: () => getPayslip(runId, employeeId),
  })

  if (slip.isError) return <Failure error={slip.error} />
  if (!slip.data) return null

  return (
    <article className="flex flex-col gap-2 rounded border border-border p-4 text-sm">
      <h3 className="font-semibold">{slip.data.title}</h3>
      <p className="text-ink-muted">
        {slip.data.period} · {slip.data.accrual_date_ro}
      </p>
      <p>
        {slip.data.employee_name} · {slip.data.position_title} ·{' '}
        <span className="font-mono">{slip.data.contract_number}</span>
      </p>

      <dl className="flex flex-col gap-1">
        {slip.data.components.map((component) => (
          <div key={component.component_key} className="flex flex-wrap gap-2">
            <dt className="text-ink-muted">{component.label}</dt>
            <dd className="tabular-nums">
              {/* The rendered form the server produced -- this screen never
                  formats an amount of its own (C18, C38). */}
              {component.amount_ro ?? (
                <span className="text-danger">
                  {t.payroll.notComputed} — {component.unresolved_reason}
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>

      {slip.data.exemptions.length > 0 && (
        <ul className="text-ink-muted">
          {slip.data.exemptions.map((exemption) => (
            <li key={`${exemption.code}-${exemption.dependent_name ?? ''}`}>
              {exemption.label}
              {exemption.dependent_name ? ` — ${exemption.dependent_name}` : ''}
            </li>
          ))}
        </ul>
      )}

      <p className="tabular-nums">
        {t.payroll.net}: {slip.data.net_ro ?? t.payroll.notComputed}
      </p>
    </article>
  )
}
