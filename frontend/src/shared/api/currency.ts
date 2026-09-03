/**
 * Exchange rates and the revaluation -- `accounting/currency`.
 *
 * **The rate is read for a day, never "the latest".** A document is converted
 * at the official rate of its own date (ADR-039 §3.2), and a day with no
 * published rate is a refusal (`currency.rate_not_found`), not the nearest
 * neighbour. The screen shows what the server will use and lets the server
 * refuse; it never picks a rate.
 *
 * **A revaluation is a posting**: one per company and date, idempotent on the
 * event (`R19`), and the request carries `Idempotency-Key` because every
 * endpoint with a financial effect does (`C9`).
 */

import { request } from './client'

export type ContractDenomination = 'foreign_currency' | 'conventional_units'

/** The currencies a document may be opened in today. MDL is the functional one. */
export const CURRENCIES = ['MDL', 'EUR', 'USD'] as const

export interface Rate {
  currency: string
  rate_date: string
  /** A string on the wire: eight decimals, and never a float. */
  rate: string
  rate_type: string
}

export interface RevaluationItem {
  document_id: string
  side: 'receivable' | 'payable'
  partner_id: string
  currency: string
  amount_currency: string
  rate_before: string
  rate_after: string
  /** Signed, `new - old` in lei: positive on a receivable is a gain, on a payable a loss. */
  difference: string
}

export interface Revaluation {
  id: string
  as_of: string
  accounting_event_id: string
  /** Null when the revaluation ran and found nothing to post. */
  journal_entry_id: string | null
  /** Set when the entry was cancelled (`R14`); the rate no longer carries forward. */
  reversed_by: string | null
  items: RevaluationItem[]
  posted_now?: boolean
}

export function rateOn(currency: string, on: string): Promise<Rate> {
  const query = new URLSearchParams({ currency, on })
  return request<Rate>(`/api/v1/accounting/currency/rates?${query.toString()}`)
}

export function listRevaluations(companyId: string): Promise<Revaluation[]> {
  return request<Revaluation[]>(`/api/v1/accounting/currency/companies/${companyId}/revaluations`)
}

export function revalue(companyId: string, asOf: string): Promise<Revaluation> {
  return request<Revaluation>(`/api/v1/accounting/currency/companies/${companyId}/revaluations`, {
    method: 'POST',
    body: { as_of: asOf },
    idempotencyKey: crypto.randomUUID(),
  })
}
