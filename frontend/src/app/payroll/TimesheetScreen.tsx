/**
 * The monthly timesheet -- the input the calculation will read.
 *
 * **Hours per day, not days per month.** Art. 22 para (1) wants the minimum
 * contribution base proportional to time worked, and at part time a share of the
 * contribution at the minimum wage. Days follow from hours; hours do not follow
 * from days, and the derivation nobody can perform is the one that gets guessed.
 *
 * **The totals come from the server** (C19). Nothing on this screen adds a
 * column up: in a payroll sheet a wrong total is not a cosmetic inconsistency.
 *
 * **The month's norm is typed, not derived.** It comes from the production
 * calendar, which the product does not hold; asking is what an accountant does
 * anyway, and deriving it from a calendar we do not have would be a number
 * nobody can defend.
 *
 * A closed month is read-only here because it is read-only in the database --
 * the screen reflects that rather than enforcing it.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import {
  closeTimesheet,
  getTimesheet,
  listContracts,
  listDays,
  listTimesheets,
  openTimesheet,
  setDays,
  type TimesheetDay,
  type TimesheetLine,
} from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

export function TimesheetScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)

  const months = useQuery({
    queryKey: ['payroll-timesheets', companyId],
    queryFn: () => listTimesheets(companyId),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['payroll-timesheets'] })

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-semibold">{t.payroll.timesheets}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/angajati`} className="text-sm text-accent">
            {t.payroll.people}
          </Link>
          <Link to={`/companii/${companyId}/contracte`} className="text-sm text-accent">
            {t.payroll.contracts}
          </Link>
        </div>
      </header>

      <OpenMonthForm companyId={companyId} onOpened={refresh} />

      {months.isError && <Failure error={months.error} />}
      {months.data && (
        <ul className="flex flex-wrap gap-3 text-sm">
          {months.data.length === 0 && <li className="text-ink-muted">{t.payroll.noMonths}</li>}
          {months.data.map((month) => (
            <li key={month.id}>
              <button
                type="button"
                onClick={() => setSelected(selected === month.id ? null : month.id)}
                className={`${BUTTON} ${selected === month.id ? 'text-ink' : ''}`}
              >
                {month.year}-{String(month.month).padStart(2, '0')} ·{' '}
                {month.status === 'open' ? t.payroll.open : t.payroll.closed}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected && <MonthDetail companyId={companyId} timesheetId={selected} />}
    </section>
  )
}

function OpenMonthForm({
  companyId,
  onOpened,
}: {
  companyId: string
  onOpened: () => void
}) {
  const now = new Date()
  const [year, setYear] = useState(String(now.getFullYear()))
  const [month, setMonth] = useState(String(now.getMonth() + 1))
  const [norm, setNorm] = useState('')

  const open = useMutation({
    mutationFn: () =>
      openTimesheet(companyId, {
        year: Number(year),
        month: Number(month),
        norm_hours: norm,
      }),
    onSuccess: () => {
      setNorm('')
      onOpened()
    },
  })

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        open.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.year}</span>
        <input
          inputMode="numeric"
          value={year}
          onChange={(event) => setYear(event.target.value)}
          className={`${FIELD} w-24 tabular-nums`}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.month}</span>
        <input
          inputMode="numeric"
          value={month}
          onChange={(event) => setMonth(event.target.value)}
          className={`${FIELD} w-16 tabular-nums`}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.normHours}</span>
        <input
          inputMode="decimal"
          value={norm}
          onChange={(event) => setNorm(event.target.value)}
          title={t.payroll.normHint}
          className={`${FIELD} w-28 text-right tabular-nums`}
        />
      </label>
      <button type="submit" disabled={norm === '' || open.isPending} className={BUTTON}>
        {t.payroll.openMonth}
      </button>
      {open.isError && <Failure error={open.error} />}
    </form>
  )
}

function MonthDetail({ companyId, timesheetId }: { companyId: string; timesheetId: string }) {
  const queryClient = useQueryClient()
  const [contractId, setContractId] = useState('')

  const month = useQuery({
    queryKey: ['payroll-timesheet', timesheetId],
    queryFn: () => getTimesheet(timesheetId),
  })
  const contracts = useQuery({
    queryKey: ['payroll-contracts', companyId, false],
    queryFn: () => listContracts(companyId),
  })

  const close = useMutation({
    mutationFn: () => closeTimesheet(timesheetId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['payroll-timesheet', timesheetId] })
      await queryClient.invalidateQueries({ queryKey: ['payroll-timesheets'] })
    },
  })

  const columns: Column<TimesheetLine>[] = [
    { key: 'employee', header: t.payroll.people, cell: (row) => row.employee_name },
    {
      key: 'contract',
      header: t.payroll.contractNumber,
      cell: (row) => <span className="font-mono">{row.contract_number}</span>,
      width: '10rem',
    },
    // `numeric` rather than a class on the cell: the grid applies right
    // alignment and tabular figures through the token (C27), so a column of
    // hours does not shift horizontally from one row to the next.
    { key: 'worked', header: t.payroll.hoursWorked, cell: (row) => row.hours_worked, numeric: true, width: '9rem' },
    { key: 'night', header: t.payroll.nightHours, cell: (row) => row.night_hours, numeric: true, width: '9rem' },
    { key: 'holiday', header: t.payroll.holidayHours, cell: (row) => row.holiday_hours, numeric: true, width: '11rem' },
    { key: 'days', header: t.payroll.daysPresent, cell: (row) => row.days_present, numeric: true, width: '9rem' },
  ]

  return (
    <section className="flex flex-col gap-4 rounded border border-border bg-surface p-4">
      {month.isError && <Failure error={month.error} />}
      {month.data && (
        <>
          <header className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-sm font-semibold">
              {month.data.year}-{String(month.data.month).padStart(2, '0')} ·{' '}
              {t.payroll.normHours}: <span className="tabular-nums">{month.data.norm_hours}</span>
            </h2>
            {month.data.status === 'open' && (
              <button
                type="button"
                onClick={() => close.mutate()}
                disabled={close.isPending}
                className={BUTTON}
              >
                {t.payroll.closeMonth}
              </button>
            )}
          </header>
          {close.isError && <Failure error={close.error} />}

          <DataGrid
            columns={columns}
            rows={month.data.lines ?? []}
            rowKey={(row) => row.contract_id}
            emptyMessage={t.payroll.noContracts}
          />

          {month.data.status === 'open' && (
            <div className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-muted">{t.payroll.pickContract}</span>
                <select
                  value={contractId}
                  onChange={(event) => setContractId(event.target.value)}
                  className={`${FIELD} w-72`}
                >
                  <option value="">{t.common.none}</option>
                  {(contracts.data ?? []).map((contract) => (
                    <option key={contract.id} value={contract.id}>
                      {contract.employee_name} · {contract.contract_number}
                    </option>
                  ))}
                </select>
              </label>
              {contractId && (
                <DayEditor
                  timesheetId={timesheetId}
                  contractId={contractId}
                  year={month.data.year}
                  month={month.data.month}
                />
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function DayEditor({
  timesheetId,
  contractId,
  year,
  month,
}: {
  timesheetId: string
  contractId: string
  year: number
  month: number
}) {
  const queryClient = useQueryClient()
  const stored = useQuery({
    queryKey: ['payroll-days', timesheetId, contractId],
    queryFn: () => listDays(timesheetId, contractId),
  })
  const [rows, setRows] = useState<TimesheetDay[]>([])

  useEffect(() => {
    if (stored.data) setRows(stored.data)
  }, [stored.data])

  const save = useMutation({
    mutationFn: () => setDays(timesheetId, contractId, rows),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['payroll-timesheet', timesheetId] })
      await queryClient.invalidateQueries({ queryKey: ['payroll-days', timesheetId] })
    },
  })

  const addRow = () => {
    const day = String(rows.length + 1).padStart(2, '0')
    setRows([
      ...rows,
      {
        work_date: `${year}-${String(month).padStart(2, '0')}-${day}`,
        hours_worked: '8.00',
        night_hours: '0.00',
        holiday_hours: '0.00',
      },
    ])
  }

  const change = (index: number, field: keyof TimesheetDay, value: string) => {
    setRows(rows.map((row, at) => (at === index ? { ...row, [field]: value } : row)))
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-ink-muted">{t.payroll.hoursHint}</p>
      <table className="text-sm">
        <thead>
          <tr className="text-left text-ink-muted">
            <th className="pr-4 font-normal">{t.payroll.day}</th>
            <th className="pr-4 font-normal">{t.payroll.hoursWorked}</th>
            <th className="pr-4 font-normal">{t.payroll.nightHours}</th>
            <th className="pr-4 font-normal">{t.payroll.holidayHours}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.work_date}-${index}`}>
              <td className="pr-4 py-1">
                <input
                  type="date"
                  value={row.work_date}
                  onChange={(event) => change(index, 'work_date', event.target.value)}
                  className={`${FIELD} w-40`}
                />
              </td>
              <td className="pr-4 py-1">
                <input
                  inputMode="decimal"
                  value={row.hours_worked}
                  onChange={(event) => change(index, 'hours_worked', event.target.value)}
                  className={`${FIELD} w-24 text-right tabular-nums`}
                />
              </td>
              <td className="pr-4 py-1">
                <input
                  inputMode="decimal"
                  value={row.night_hours}
                  onChange={(event) => change(index, 'night_hours', event.target.value)}
                  className={`${FIELD} w-24 text-right tabular-nums`}
                />
              </td>
              <td className="pr-4 py-1">
                <input
                  inputMode="decimal"
                  value={row.holiday_hours}
                  onChange={(event) => change(index, 'holiday_hours', event.target.value)}
                  className={`${FIELD} w-24 text-right tabular-nums`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-3">
        <button type="button" onClick={addRow} className={BUTTON}>
          {t.payroll.addDay}
        </button>
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending}
          className={BUTTON}
        >
          {t.payroll.saveDays}
        </button>
      </div>
      {save.isError && <Failure error={save.error} />}
      {stored.isError && <Failure error={stored.error} />}
    </div>
  )
}
