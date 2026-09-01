/**
 * The company's control panel -- one call, because the panel is one question.
 *
 * Every figure below is the server's (C19). Nothing in this file, and nothing in
 * the screen it feeds, adds one amount to another: the month's turnover, the
 * year's totals and the cash balance are each a total the database produced, and
 * they arrive as decimal strings that go to `@/shared/format` unparsed.
 *
 * **Windows travel with their figures.** Every turnover carries the two dates it
 * covers, so a screen states the month rather than assuming the one the browser's
 * clock is in -- and so two people reading the same panel are reading the same
 * month.
 *
 * **What is missing is missing from the answer, not zeroed in it.** `cash` is
 * `null` when the company's chart binds no cash account. Filing deadlines, VAT
 * payable and overdue receivables are not fields here at all: nothing computes
 * them, and the screen says so in their place.
 */

import { request } from './client'

export interface Turnover {
  start_date: string
  end_date: string
  debit: string
  credit: string
  /** Σ debit = Σ credit over the window -- the server's answer, not a comparison made here. */
  balanced: boolean
}

export interface PanelEntry {
  id: string
  entry_number: string
  accounting_date: string
  description: string
  /** The legal name (C39); empty when no line of the entry names a counterparty. */
  partner_name: string
  amount: string
  entry_type: string
  /** Both halves of R14, as on the register. */
  reverses_entry_id: string | null
  reversed_by_entry_id: string | null
}

export interface DocumentWork {
  owner: 'purchases' | 'sales' | 'treasury'
  draft: number
  confirmed: number
}

export interface Cash {
  account_id: string
  account_code: string
  name_ro: string
  balance: string
}

export interface Overview {
  on: string
  month: Turnover
  previous_month: Turnover
  year_to_date: Turnover
  /** Six months, oldest first, empty ones included as zeros. */
  series: Turnover[]
  latest_entries: PanelEntry[]
  open_work: {
    draft_entries: number
    documents: DocumentWork[]
  }
  /** `null` when the chart binds no cash account -- not a zero balance. */
  cash: Cash | null
  checks: {
    /** Turnover in the month that no formula explains. */
    unexplained: string
    /** Accounts with movement in the month that a posting dated in it could not use. */
    unpostable_with_turnover: number
  }
}

/**
 * `on` is the day the panel is asked for, and the server answers for the month it
 * falls in. Sent by the client rather than read from the server's clock, like
 * every other window in this API: a browser left open overnight would otherwise
 * change months under the reader without saying so.
 */
export function overview(companyId: string, on: string): Promise<Overview> {
  return request<Overview>(
    `/api/v1/accounting/ledger/companies/${companyId}/overview?on=${encodeURIComponent(on)}`,
  )
}
