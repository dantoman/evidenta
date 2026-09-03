/**
 * Închiderea -- the months of an exercise, what stands before closing one, and
 * the three acts: close the month, reopen it with a reason, close the exercise.
 *
 * **Every check is the server's, and so is every refusal.** The list beside the
 * month is computed there (`periods/services/checks.py`); the screen names each
 * check and shows its count. Whether the month may close is the engine's word
 * (`R12`): the one blocking check disables the button, and everything the
 * server refuses arrives as a stable code and is shown from the catalogue
 * (`C10`). Nothing here decides that a month is ready.
 *
 * **The exercise closes from its last month.** The chain of ADR-050 (6/7 -> 351
 * -> 333) is a posting dated the last day of the exercise, in its last period,
 * which is why the act sits on that month's panel and nowhere else -- and why
 * it asks twice: the closing locks every month, and nothing inside it moves
 * again.
 *
 * **What is not counted is said.** Payroll approved and not posted, unbound
 * roles, an unmatched bank statement: the modules that produce them do not
 * report to the closing yet, and a list that fell silent about them would read
 * as "nothing else to check".
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useParams } from 'react-router'

import { t } from '@/locales'
import { listFiscalYears, type FiscalYear } from '@/shared/api/companies'
import {
  closeFiscalYear,
  closePeriod,
  closingChecks,
  listPeriods,
  reopenPeriod,
  type Period,
  type PeriodStatus,
} from '@/shared/api/periods'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { date, dateTime, month } from '@/shared/format'
import { Badge, Button, Card, Field, Input, PageHeader, Select, type BadgeTone } from '@/shared/ui'

const STATE_TONE: Record<PeriodStatus, BadgeTone> = {
  open: 'credit',
  closed: 'navy',
  locked: 'neutral',
}

/**
 * The exercise the screen opens on: the last open one, else the last there is.
 * The closing works on what is open; a company whose every exercise is closed
 * still sees the last, locked, with its months.
 */
function defaultYear(years: FiscalYear[]): FiscalYear | undefined {
  return [...years].reverse().find((year) => year.status === 'open') ?? years[years.length - 1]
}

const columns: Column<Period>[] = [
  {
    key: 'period_no',
    header: t.accounting.closing.number,
    cell: (row) => row.period_no,
    numeric: true,
    width: '4rem',
  },
  { key: 'month', header: t.accounting.closing.month, cell: (row) => month(row.start_date) },
  {
    key: 'start_date',
    header: t.accounting.closing.from,
    cell: (row) => date(row.start_date),
    width: '8rem',
  },
  {
    key: 'end_date',
    header: t.accounting.closing.to,
    cell: (row) => date(row.end_date),
    width: '8rem',
  },
  {
    key: 'status',
    header: t.accounting.closing.status,
    cell: (row) => (
      <Badge tone={STATE_TONE[row.status]}>{t.accounting.closing.states[row.status]}</Badge>
    ),
    width: '8rem',
  },
  {
    key: 'closed_at',
    header: t.accounting.closing.closedAt,
    cell: (row) => (row.closed_at ? dateTime(row.closed_at) : '—'),
    width: '11rem',
  },
  {
    key: 'reopened_count',
    header: t.accounting.closing.reopened,
    cell: (row) => row.reopened_count,
    numeric: true,
    width: '7rem',
  },
]

export function ClosingScreen() {
  const { companyId = '' } = useParams()
  const [yearChoice, setYearChoice] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  const years = useQuery({
    queryKey: ['fiscal-years', companyId],
    queryFn: () => listFiscalYears(companyId),
  })
  const year = years.data
    ? (years.data.find((row) => row.id === yearChoice) ?? defaultYear(years.data))
    : undefined
  const yearId = year?.id ?? ''

  const periods = useQuery({
    queryKey: ['periods', companyId, yearId],
    queryFn: () => listPeriods(companyId, yearId),
    enabled: yearId !== '',
  })
  const period = periods.data?.find((row) => row.id === selected) ?? null
  const last = periods.data?.[periods.data.length - 1]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title={t.accounting.closing.title}
        lead={t.accounting.closing.lead}
        actions={
          years.data && years.data.length > 0 ? (
            <Field label={t.accounting.closing.exercise}>
              <Select
                value={yearId}
                onChange={(event) => {
                  setYearChoice(event.target.value)
                  setSelected(null)
                }}
                className="w-56"
              >
                {years.data.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.code} · {t.accounting.closing.exerciseStates[row.status] ?? row.status}
                  </option>
                ))}
              </Select>
            </Field>
          ) : undefined
        }
      />

      {years.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {years.isError && <Failure error={years.error} />}
      {years.data?.length === 0 && (
        <p className="text-sm text-ink-muted">{t.accounting.closing.noExercise}</p>
      )}
      {periods.isError && <Failure error={periods.error} />}

      {periods.data && (
        <Card padding="none">
          <DataGrid
            columns={columns}
            rows={periods.data}
            rowKey={(row) => row.id}
            emptyMessage={t.accounting.closing.empty}
            onRowClick={(row) => setSelected(row.id)}
          />
        </Card>
      )}

      {year && period ? (
        <MonthPanel
          key={period.id}
          companyId={companyId}
          year={year}
          period={period}
          isLast={last?.id === period.id}
        />
      ) : (
        periods.data && <p className="text-sm text-ink-muted">{t.accounting.closing.pick}</p>
      )}
    </section>
  )
}

function checkLabel(code: string): string {
  const labels: Record<string, string> = t.accounting.closing.checks
  return labels[code] ?? code
}

function MonthPanel({
  companyId,
  year,
  period,
  isLast,
}: {
  companyId: string
  year: FiscalYear
  period: Period
  isLast: boolean
}) {
  const queryClient = useQueryClient()
  const [reason, setReason] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const checks = useQuery({
    queryKey: ['closing-checks', period.id],
    queryFn: () => closingChecks(period.id),
  })
  // Until the server has answered, the month is treated as not closable: a
  // button enabled before the checks arrive is a button that closes blind.
  const blocked = checks.data?.some((check) => check.blocking && check.count > 0) ?? true

  const refresh = async (message: string) => {
    setNotice(message)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['periods', companyId] }),
      queryClient.invalidateQueries({ queryKey: ['closing-checks', period.id] }),
      queryClient.invalidateQueries({ queryKey: ['fiscal-years', companyId] }),
    ])
  }

  const close = useMutation({
    mutationFn: () => closePeriod(period.id),
    onSuccess: () => refresh(t.accounting.closing.monthClosed),
  })
  const reopen = useMutation({
    mutationFn: () => reopenPeriod(period.id, reason),
    onSuccess: () => {
      setReason('')
      return refresh(t.accounting.closing.monthReopened)
    },
  })
  const closeYear = useMutation({
    mutationFn: () => closeFiscalYear(year.id),
    onSuccess: (result) => {
      setConfirming(false)
      return refresh(
        result.journal_entry_id
          ? t.accounting.closing.yearClosed
          : t.accounting.closing.yearClosedNoEntry,
      )
    },
  })

  return (
    <Card eyebrow={t.accounting.closing.states[period.status]} title={month(period.start_date)}>
      <div className="flex flex-col gap-5">
        <section className="flex flex-col gap-2">
          <h3 className="type-label m-0 text-heading">{t.accounting.closing.checksTitle}</h3>
          {checks.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
          {checks.isError && <Failure error={checks.error} />}
          {checks.data && (
            <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
              {checks.data.map((check) => (
                <li key={check.code} className="flex items-center justify-between gap-4">
                  <span>{checkLabel(check.code)}</span>
                  <span className="flex items-center gap-2">
                    {check.count > 0 && (
                      <Badge tone={check.blocking ? 'debit' : 'caution'}>
                        {check.blocking
                          ? t.accounting.closing.blocking
                          : t.accounting.closing.warning}
                      </Badge>
                    )}
                    <span className="tabular-nums">{check.count}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="m-0 type-caption text-ink-muted">{t.accounting.closing.checksHint}</p>
        </section>

        {period.status === 'open' && (
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="gold"
              icon="lock"
              type="button"
              onClick={() => close.mutate()}
              disabled={blocked || close.isPending}
              title={blocked ? t.accounting.closing.closeMonthBlocked : undefined}
            >
              {t.accounting.closing.closeMonth}
            </Button>
            {close.isError && <Failure error={close.error} />}
          </div>
        )}

        {period.status === 'closed' && year.status === 'open' && (
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event: FormEvent) => {
              event.preventDefault()
              reopen.mutate()
            }}
          >
            <Field
              label={t.accounting.closing.reason}
              hint={t.accounting.closing.reasonHint}
              required
              className="min-w-80"
            >
              <Input value={reason} onChange={(event) => setReason(event.target.value)} />
            </Field>
            <Button
              variant="secondary"
              type="submit"
              disabled={reason.trim() === '' || reopen.isPending}
            >
              {t.accounting.closing.reopenMonth}
            </Button>
            {reopen.isError && <Failure error={reopen.error} />}
          </form>
        )}

        {period.status === 'locked' && (
          <p className="m-0 text-sm text-ink-muted">{t.accounting.closing.locked}</p>
        )}

        {isLast && year.status === 'open' && (
          <section className="flex flex-col gap-3 border-t border-border pt-4">
            <h3 className="type-label m-0 text-heading">{t.accounting.closing.closeYearTitle}</h3>
            <p className="m-0 text-sm text-ink-muted">{t.accounting.closing.closeYearLead}</p>
            {confirming ? (
              <div className="flex flex-wrap items-center gap-3">
                <p role="status" className="m-0 text-sm text-heading">
                  {t.accounting.closing.confirmYear} <strong>{year.code}</strong>
                </p>
                <Button
                  variant="danger"
                  type="button"
                  onClick={() => closeYear.mutate()}
                  disabled={closeYear.isPending}
                >
                  {t.accounting.closing.confirmYearAction}
                </Button>
                <Button variant="ghost" type="button" onClick={() => setConfirming(false)}>
                  {t.accounting.closing.cancel}
                </Button>
              </div>
            ) : (
              <div>
                <Button variant="secondary" type="button" onClick={() => setConfirming(true)}>
                  {t.accounting.closing.closeYear}
                </Button>
              </div>
            )}
            {closeYear.isError && <Failure error={closeYear.error} />}
          </section>
        )}

        {notice && (
          <p role="status" className="m-0 text-sm text-ink-muted">
            {notice}
          </p>
        )}
      </div>
    </Card>
  )
}
