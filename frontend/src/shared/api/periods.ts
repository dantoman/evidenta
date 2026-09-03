/**
 * The closing door -- the months of an exercise, what stands before closing
 * one, and the three acts: close a month, reopen it with a reason, close the
 * exercise.
 *
 * Every refusal is the engine's (`R12`) and arrives as a stable code (`C10`):
 * `periods.period_not_open`, `periods.period_locked`, `periods.class8_not_settled`,
 * `periods.periods_still_open`. The screen renders the code's message and
 * decides nothing about whether a month may close.
 *
 * No `Idempotency-Key` on the three POSTs, deliberately: the closing services
 * key their accounting event on the period and on the exercise, so a retry of
 * the same closing answers with the same event -- the property the header would
 * otherwise buy (`R19`).
 */

import { request } from './client'
import type { FiscalYear } from './companies'

export type PeriodStatus = 'open' | 'closed' | 'locked'

export interface Period {
  id: string
  /** Counts within the exercise, not the calendar: for an April-to-March
   *  exercise, period 1 is April. */
  period_no: number
  start_date: string
  /** The last day, inclusive. */
  end_date: string
  status: PeriodStatus
  closed_at: string | null
  reopened_count: number
}

/**
 * One thing looked at before the month closes, counted on the server.
 *
 * `blocking` is the engine's word: true only where the closing would be refused.
 * The other checks are warnings the accountant reads before deciding.
 */
export interface ClosingCheck {
  code: string
  count: number
  blocking: boolean
}

export interface MonthClosed {
  period: Period
  accounting_event_id: string
}

export interface YearClosed {
  fiscal_year: FiscalYear
  accounting_event_id: string
  /** Null when the exercise had nothing to close: an event, no entry. */
  journal_entry_id: string | null
  formulas: number
  periods_locked: number
}

const BASE = '/api/v1/accounting/periods'

export function listPeriods(companyId: string, yearId: string): Promise<Period[]> {
  return request<Period[]>(`${BASE}/companies/${companyId}/fiscal-years/${yearId}/periods`)
}

export function closingChecks(periodId: string): Promise<ClosingCheck[]> {
  return request<ClosingCheck[]>(`${BASE}/periods/${periodId}/closing-checks`)
}

export function closePeriod(periodId: string): Promise<MonthClosed> {
  return request<MonthClosed>(`${BASE}/periods/${periodId}/closing`, { method: 'POST', body: {} })
}

export function reopenPeriod(periodId: string, reason: string): Promise<Period> {
  return request<Period>(`${BASE}/periods/${periodId}/reopening`, {
    method: 'POST',
    body: { reason },
  })
}

export function closeFiscalYear(yearId: string): Promise<YearClosed> {
  return request<YearClosed>(`${BASE}/fiscal-years/${yearId}/closing`, {
    method: 'POST',
    body: {},
  })
}
