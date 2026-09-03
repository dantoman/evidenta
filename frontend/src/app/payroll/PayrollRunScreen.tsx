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
  bankListUrl,
  createPayment,
  createRun,
  getPayment,
  getPayslip,
  payslipPdfUrl,
  getRun,
  listPayments,
  listRuns,
  postPayment,
  recomputeRun,
  updatePayment,
  type RunLine,
  type SalaryPaymentLine,
} from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input, Select } from '@/shared/ui'

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
  const { companyId } = useParams()
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
        <span className="flex flex-wrap gap-x-4 gap-y-1">
          <button
            type="button"
            className="text-accent"
            onClick={() => setPayslipFor(payslipFor === row.employee_id ? null : row.employee_id)}
          >
            {t.payroll.payslip}
          </button>
          {/* The printed one (`C22`, ADR-095): a link the browser opens, not a fetch.
              Only once the month is approved -- the server refuses a draft, and a
              link that always fails is a broken control, not an honest one. */}
          {run.data?.status === 'approved' && (
            <a
              href={payslipPdfUrl(runId, row.employee_id)}
              target="_blank"
              rel="noopener"
              className="text-accent"
            >
              {t.payroll.payslipPdf}
            </a>
          )}
        </span>
      ),
      width: '11rem',
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
            {run.data.posting?.status === 'posted' && (
              <p className="text-sm text-ink-muted" title={t.payroll.postedHint}>
                <span className="font-medium text-ink">{t.payroll.posted}</span> ·{' '}
                <Link to={`/companii/${companyId}/registru`} className="text-accent">
                  {t.payroll.seeRegister}
                </Link>
              </p>
            )}
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

          {/* Only once the run is in the books: a payment settles what the
              accrual put on the salary payable, and before that there is
              nothing on it to settle. The server says whether it is, from the
              event; the screen never infers "posted" from "approved". */}
          {run.data.posting?.status === 'posted' && <PaymentsPanel runId={runId} />}

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

/**
 * Paying what the accrual left, per person, from the till or the bank account.
 *
 * The document is the payroll module's; where the money leaves from is the
 * instrument's (ADR-073 §5), so the form asks for it and defaults to nothing
 * the server would not accept. The bank's list is a file the server builds
 * from the same rows as the lines shown here (`C20`): the link points at the
 * endpoint, and nothing here formats a row.
 */
function PaymentsPanel({ runId }: { runId: string }) {
  const queryClient = useQueryClient()
  const [where, setWhere] = useState<'cash' | 'bank'>('bank')
  const [paidOn, setPaidOn] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  const payments = useQuery({
    queryKey: ['payroll-payments', runId],
    queryFn: () => listPayments(runId),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['payroll-payments', runId] })

  const create = useMutation({
    mutationFn: () => createPayment(runId, { paid_on: paidOn, treasury_account: where }),
    onSuccess: async (payment) => {
      setSelected(payment.id)
      await refresh()
    },
  })

  return (
    <section className="flex flex-col gap-3 rounded border border-border p-4">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h3 className="text-sm font-semibold">{t.payroll.payments}</h3>
        <a
          href={bankListUrl(runId)}
          className="text-sm text-accent"
          title={t.payroll.bankListHint}
        >
          {t.payroll.bankList}
        </a>
      </header>

      <form
        className="flex flex-wrap items-end gap-4"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <Field label={t.payroll.paidOn}>
          <Input
            type="date"
            value={paidOn}
            onChange={(event) => setPaidOn(event.target.value)}
            className="w-40"
          />
        </Field>
        <Field label={t.payroll.paidFrom}>
          <Select
            value={where}
            onChange={(event) => setWhere(event.target.value === 'cash' ? 'cash' : 'bank')}
            className="w-40"
          >
            <option value="bank">{t.treasury.bank}</option>
            <option value="cash">{t.treasury.cash}</option>
          </Select>
        </Field>
        <Button variant="primary" type="submit" disabled={paidOn === '' || create.isPending}>
          {t.payroll.paySalaries}
        </Button>
        {create.isError && <Failure error={create.error} />}
      </form>

      {payments.isError && <Failure error={payments.error} />}
      {payments.data && (
        <ul className="flex flex-wrap gap-3 text-sm">
          {payments.data.length === 0 && (
            <li className="text-ink-muted">{t.payroll.noPayments}</li>
          )}
          {payments.data.map((payment) => (
            <li key={payment.id}>
              <Button
                variant="secondary"
                type="button"
                onClick={() => setSelected(selected === payment.id ? null : payment.id)}
              >
                {payment.paid_on} ·{' '}
                {payment.treasury_account === 'cash' ? t.treasury.cash : t.treasury.bank} ·{' '}
                <span className="tabular-nums">{payment.total}</span> ·{' '}
                {payment.status === 'posted' ? t.payroll.paymentPosted : t.payroll.paymentDraft}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {selected && <PaymentView paymentId={selected} runId={runId} onChanged={refresh} />}
    </section>
  )
}

/**
 * One payment: its lines beside what the run left each person.
 *
 * **A line goes down or away, never up**: the amount is changed through the
 * small form, a person is removed with the row's action, and the server refuses
 * anything above what is left (`payroll.overpayment`). Edits are held here until
 * saved; while any are pending the server's total is hidden rather than
 * recomputed (`C19`), and posting waits for the save.
 */
function PaymentView({
  paymentId,
  runId,
  onChanged,
}: {
  paymentId: string
  runId: string
  onChanged: () => Promise<unknown> | void
}) {
  const queryClient = useQueryClient()
  const { companyId } = useParams()
  const [pending, setPending] = useState<SalaryPaymentLine[] | null>(null)
  const [who, setWho] = useState('')
  const [amount, setAmount] = useState('')

  const payment = useQuery({
    queryKey: ['payroll-payment', paymentId],
    queryFn: () => getPayment(paymentId),
  })

  const refresh = async () => {
    setPending(null)
    await queryClient.invalidateQueries({ queryKey: ['payroll-payment', paymentId] })
    await onChanged()
  }

  const lines = pending ?? payment.data?.lines ?? []
  const draft = payment.data?.status === 'draft'

  const save = useMutation({
    mutationFn: () =>
      updatePayment(paymentId, {
        lines: lines.map((line) => ({ employee_id: line.employee_id, amount: line.amount })),
      }),
    onSuccess: refresh,
  })
  const post = useMutation({
    // The key is the document's, so a retry of this action is the same action.
    mutationFn: () => postPayment(paymentId, `payroll.payment:${paymentId}`),
    onSuccess: refresh,
  })

  const columns: Column<SalaryPaymentLine>[] = [
    { key: 'employee', header: t.payroll.people, cell: (row) => row.employee_name },
    {
      key: 'idnp',
      header: t.payroll.idnp,
      cell: (row) => <span className="font-mono">{row.idnp ?? ''}</span>,
      width: '10rem',
    },
    {
      key: 'iban',
      header: t.payroll.iban,
      cell: (row) => <span className="font-mono">{row.bank_iban ?? ''}</span>,
      width: '16rem',
    },
    { key: 'net', header: t.payroll.net, cell: (row) => row.net ?? '', numeric: true, width: '9rem' },
    {
      key: 'paid',
      header: t.payroll.alreadyPaid,
      cell: (row) => row.already_paid ?? '',
      numeric: true,
      width: '9rem',
    },
    {
      key: 'amount',
      header: t.payroll.amountToPay,
      cell: (row) => row.amount,
      numeric: true,
      width: '9rem',
    },
  ]
  if (draft) {
    columns.push({
      key: 'remove',
      header: '',
      cell: (row) => (
        <button
          type="button"
          className="text-accent"
          onClick={() => setPending(lines.filter((line) => line.employee_id !== row.employee_id))}
        >
          {t.payroll.removeLine}
        </button>
      ),
      width: '6rem',
    })
  }

  return (
    <article className="flex flex-col gap-3">
      {payment.isError && <Failure error={payment.error} />}
      {payment.data && (
        <>
          <header className="flex flex-wrap items-center justify-between gap-4 text-sm">
            <p>
              <span className="font-medium">{payment.data.paid_on}</span> ·{' '}
              {payment.data.treasury_account === 'cash' ? t.treasury.cash : t.treasury.bank} ·{' '}
              {payment.data.status === 'posted' ? t.payroll.paymentPosted : t.payroll.paymentDraft}
            </p>
            <div className="flex flex-wrap items-center gap-4">
              {payment.data.posting?.status === 'posted' && (
                <Link to={`/companii/${companyId}/registru`} className="text-accent">
                  {t.payroll.seeRegister}
                </Link>
              )}
              <a href={bankListUrl(runId, paymentId)} className="text-accent">
                {t.payroll.bankList}
              </a>
            </div>
          </header>

          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={lines}
              rowKey={(row) => row.employee_id}
              emptyMessage={t.payroll.noPayments}
              serverTotals={
                pending === null && payment.data.totals
                  ? { amount: payment.data.totals.amount }
                  : undefined
              }
            />
          </Card>

          {draft && (
            <div className="flex flex-wrap items-end gap-4">
              <form
                className="flex flex-wrap items-end gap-3"
                onSubmit={(event: FormEvent) => {
                  event.preventDefault()
                  // Both separators are the decimal separator (C40); the wire
                  // carries the point.
                  const value = amount.trim().replace(',', '.')
                  setPending(
                    lines.map((line) =>
                      line.employee_id === who ? { ...line, amount: value } : line,
                    ),
                  )
                  setAmount('')
                }}
              >
                <Field label={t.payroll.people}>
                  <Select
                    value={who}
                    onChange={(event) => setWho(event.target.value)}
                    className="w-56"
                  >
                    <option value="">{t.payroll.pickPerson}</option>
                    {lines.map((line) => (
                      <option key={line.employee_id} value={line.employee_id}>
                        {line.employee_name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={t.payroll.amountToPay}>
                  <Input
                    inputMode="decimal"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    className="w-32 tabular-nums"
                  />
                </Field>
                <Button
                  variant="secondary"
                  type="submit"
                  disabled={who === '' || amount.trim() === ''}
                >
                  {t.payroll.changeAmount}
                </Button>
              </form>
              <Button
                variant="secondary"
                type="button"
                onClick={() => save.mutate()}
                disabled={pending === null || save.isPending}
              >
                {t.payroll.saveLines}
              </Button>
              <Button
                variant="primary"
                type="button"
                onClick={() => post.mutate()}
                disabled={pending !== null || post.isPending}
                title={t.payroll.postPaymentHint}
              >
                {t.payroll.postPayment}
              </Button>
            </div>
          )}
          {save.isError && <Failure error={save.error} />}
          {post.isError && <Failure error={post.error} />}
        </>
      )}
    </article>
  )
}
