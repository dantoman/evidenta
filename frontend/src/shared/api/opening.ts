/**
 * Opening balances -- against `accounting/opening/urls.py`.
 *
 * A company arriving from another system starts with balances, not with an empty
 * ledger, and until this existed the product was usable only by a company
 * founded today: its trial balance began at zero and meant nothing.
 *
 * **All six sets are here.** Receivables and payables arrived with the partner
 * directory; stock, fixed assets and payroll cumulatives arrived with G3 of the
 * gap plan. Two of them name identities this product does not hold yet -- the
 * item and the asset are the *source* system's, carried as identifiers the
 * company will attach the object to later -- and the screen says so rather than
 * pretending a registry exists.
 *
 * Amounts are strings on the wire and stay strings here (C18).
 */

import { request } from './client'

/** Where the numbers came from. Asked at reconciliation time, not at import. */
export type BatchSource = 'manual' | 'onec_import' | 'other_system'

export type BatchStatus = 'draft' | 'validated' | 'posted' | 'rejected'

export interface BatchSummary {
  id: string
  company_id: string
  as_of_date: string
  source: BatchSource
  status: BatchStatus
  counterpart_account_id: string
}

export interface GlRow {
  account_id: string
  debit: string
  credit: string
  currency: string | null
}

export interface PartnerRow extends GlRow {
  partner_id: string
}

export interface InventoryRow {
  account_id: string
  item_id: string
  warehouse_id: string | null
  lot: string | null
  quantity: string
  uom_id: string
  unit_cost: string | null
  /** The debit -- a stock balance has one side. */
  total_cost: string
  currency: string | null
}

export interface AssetRow {
  asset_id: string
  cost_account_id: string
  depreciation_account_id: string
  entry_cost: string
  accumulated_depreciation: string
  in_service_date: string
  remaining_months: number | null
}

/** The three keys of the cumulative method -- ADR-061, transcribed from the server. */
export type CumulativeCode =
  | 'income_tax.taxable_income'
  | 'income_tax.exemptions_granted'
  | 'income_tax.withheld'

export const CUMULATIVE_CODES: CumulativeCode[] = [
  'income_tax.taxable_income',
  'income_tax.exemptions_granted',
  'income_tax.withheld',
]

export interface PayrollCumulativeRow {
  employee_id: string
  code: CumulativeCode
  /** A magnitude, never negative: the meaning is the code's (ADR-061). */
  amount: string
  from_date: string
}

export interface BatchContents extends BatchSummary {
  gl: GlRow[]
  receivables: PartnerRow[]
  payables: PartnerRow[]
  inventory: InventoryRow[]
  assets: AssetRow[]
  payroll_cumulatives: PayrollCumulativeRow[]
  /** Signed balance each analytical set contributes, per account. Server-computed. */
  decomposition: Record<string, string>
}

export interface NewBatch {
  as_of_date: string
  source: BatchSource
  /**
   * The account the whole set balances against. Required and never defaulted:
   * a wrong counterpart is a wrong opening entry that still balances, and those
   * are the ones nobody notices.
   */
  counterpart_account_id: string
}

export function createBatch(companyId: string, batch: NewBatch): Promise<BatchSummary> {
  return request<BatchSummary>(`/api/v1/accounting/opening-balances/companies/${companyId}`, {
    method: 'POST',
    body: batch,
  })
}

export function getBatch(batchId: string): Promise<BatchContents> {
  return request<BatchContents>(`/api/v1/accounting/opening-balances/${batchId}`)
}

export function addGlRows(
  batchId: string,
  rows: { account_id: string; debit: string; credit: string }[],
): Promise<BatchSummary> {
  return request<BatchSummary>(`/api/v1/accounting/opening-balances/${batchId}/rows`, {
    method: 'POST',
    body: { gl: rows },
  })
}

/** `draft → validated`: the checks run on the server and the rows freeze. */
export function validateBatch(batchId: string): Promise<BatchSummary> {
  return request<BatchSummary>(`/api/v1/accounting/opening-balances/${batchId}/validation`, {
    method: 'POST',
    body: {},
  })
}

export interface PostedBatch {
  accounting_event_id: string
  journal_entry_id: string
  posted_now: boolean
}

/** The only step with a financial effect, so the only one carrying a key (C9). */
export function postBatch(batchId: string, idempotencyKey: string): Promise<PostedBatch> {
  return request<PostedBatch>(`/api/v1/accounting/opening-balances/${batchId}/posting`, {
    method: 'POST',
    body: {},
    idempotencyKey,
  })
}

export interface BatchListRow extends BatchSummary {
  created_at: string
  gl_rows: number
  receivable_rows: number
  payable_rows: number
  inventory_rows: number
  asset_rows: number
  payroll_rows: number
  /** Why it was abandoned, in the words of whoever abandoned it. */
  rejected_reason: string | null
}

/**
 * Every batch of a company, newest first.
 *
 * A list exists because a batch is never deleted: a draft abandoned yesterday is
 * still there, and without a way back to it the next import starts from zero
 * beside it -- two partial pictures of the same opening position, both plausible.
 */
export function listBatches(companyId: string): Promise<BatchListRow[]> {
  return request<BatchListRow[]>(`/api/v1/accounting/opening-balances/companies/${companyId}`)
}

/** A receivable or a payable: a balance, plus who owes it. */
export interface PartnerRowInput {
  account_id: string
  partner_id: string
  debit: string
  credit: string
}

export function addPartnerRows(
  batchId: string,
  rows: { receivables?: PartnerRowInput[]; payables?: PartnerRowInput[] },
): Promise<BatchSummary> {
  return request<BatchSummary>(`/api/v1/accounting/opening-balances/${batchId}/rows`, {
    method: 'POST',
    body: rows,
  })
}

/** A stock balance as it is typed: the amounts stay strings up to the wire. */
export interface InventoryRowInput {
  account_id: string
  item_id: string
  uom_id: string
  quantity: string
  total_cost: string
  warehouse_id?: string | null
  lot?: string | null
  unit_cost?: string | null
}

export interface AssetRowInput {
  asset_id: string
  cost_account_id: string
  depreciation_account_id: string
  entry_cost: string
  accumulated_depreciation?: string
  in_service_date: string
  remaining_months?: number | null
}

export interface PayrollCumulativeRowInput {
  employee_id: string
  code: CumulativeCode
  amount: string
  from_date: string
}

/**
 * The three sets that decompose an account into something the ledger can
 * carry a dimension for -- stock and fixed assets -- and the one that never
 * posts at all. One call, the same route as the other three sets.
 */
export function addAnalyticalRows(
  batchId: string,
  rows: {
    inventory?: InventoryRowInput[]
    assets?: AssetRowInput[]
    payroll_cumulatives?: PayrollCumulativeRowInput[]
  },
): Promise<BatchSummary> {
  return request<BatchSummary>(`/api/v1/accounting/opening-balances/${batchId}/rows`, {
    method: 'POST',
    body: rows,
  })
}
