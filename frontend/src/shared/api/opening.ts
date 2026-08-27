/**
 * Opening balances -- against `accounting/opening/urls.py`.
 *
 * A company arriving from another system starts with balances, not with an empty
 * ledger, and until this existed the product was usable only by a company
 * founded today: its trial balance began at zero and meant nothing.
 *
 * **Only general-ledger rows are here.** The server also accepts receivables and
 * payables, and both need a `partner_id` -- but `masterdata/partners` has no HTTP
 * surface at all, so a form asking for one would be a form nobody can fill in
 * correctly. Same reason the server exposes three of six kinds: a field with no
 * way to supply it looks like delivered function.
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

export interface BatchContents extends BatchSummary {
  gl: GlRow[]
  receivables: PartnerRow[]
  payables: PartnerRow[]
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
