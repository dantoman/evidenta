/**
 * Posting a manual note, and reading the trial balance.
 *
 * **Amounts are strings on both sides and never become numbers.** The server
 * sends and accepts decimal strings so the value never passes through a float;
 * parsing one here to add it up would undo that at the last step, and the damage
 * would show up as a few bani nobody can attribute to anything.
 *
 * Totals come from the server (C19). Nothing in this file sums a column.
 */

import { request } from './client'

export interface ManualLine {
  account_id: string
  debit: string
  credit: string
  description?: string
}

export interface ManualEntry {
  company_id: string
  accounting_date: string
  description: string
  lines: ManualLine[]
  note_id?: string
}

export interface PostedEntry {
  accounting_event_id: string
  journal_entry_id: string
  /** False when the key found an entry an earlier attempt had already written. */
  posted_now: boolean
}

/**
 * `Idempotency-Key` is required by the server on anything with a financial
 * effect (C9), and it is the caller who has to be able to reproduce it: a key
 * generated inside this function would be a new key on every retry, which is the
 * one thing it must not be.
 */
export function postManualEntry(entry: ManualEntry, idempotencyKey: string): Promise<PostedEntry> {
  return request<PostedEntry>('/api/v1/accounting/entries/manual', {
    method: 'POST',
    body: entry,
    idempotencyKey,
  })
}

export interface TrialBalanceRow {
  account_id: string
  account_code: string
  name_ro: string
  opening: string
  debit: string
  credit: string
  closing: string
}

export interface TrialBalance {
  start_date: string
  end_date: string
  rows: TrialBalanceRow[]
  total_debit: string
  total_credit: string
  /** The server's answer, not a comparison made here. */
  balanced: boolean
}

export function trialBalance(companyId: string, from: string, to: string): Promise<TrialBalance> {
  return request<TrialBalance>(
    `/api/v1/accounting/ledger/companies/${companyId}/trial-balance` +
      `?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  )
}

export interface JournalLineRead {
  line_number: number
  account_id: string
  account_code: string
  name_ro: string
  debit: string
  credit: string
  description: string | null
}

export interface JournalEntryRead {
  id: string
  entry_number: string
  accounting_date: string
  description: string
  status: string
  entry_type: string
  total_debit: string
  total_credit: string
  /** What this entry cancels, and what cancelled it -- both halves of R14. */
  reverses_entry_id: string | null
  reversed_by_entry_id: string | null
  accounting_event_id: string
  lines: JournalLineRead[]
}

export interface Register {
  start_date: string
  end_date: string
  /** True when the page was cut. Said out loud so a short list is not read as all of it. */
  truncated: boolean
  entries: JournalEntryRead[]
}

export function listEntries(companyId: string, from: string, to: string): Promise<Register> {
  return request<Register>(
    `/api/v1/accounting/ledger/companies/${companyId}/entries` +
      `?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  )
}

/**
 * Cancelling a posted entry -- a storno, never an edit (R10).
 *
 * `accounting_date` is required and is deliberately not defaulted here. Which
 * date a correction carries is an open decision (ADR-007) and the server refuses
 * to guess it; a client that filled in today would answer that question from the
 * layer least able to argue about it.
 *
 * `reason` is the only part of a correction a reader cannot reconstruct from the
 * ledger: the amounts, the accounts and the link are all in the mirror entry.
 */
export interface Reversal {
  company_id: string
  accounting_date: string
  reason: string
  corrects_period_id?: string
}

export function reverseEntry(
  entryId: string,
  reversal: Reversal,
  idempotencyKey: string,
): Promise<PostedEntry> {
  return request<PostedEntry>(`/api/v1/accounting/entries/${entryId}/reversal`, {
    method: 'POST',
    body: reversal,
    idempotencyKey,
  })
}

// --- F1.8: the reports ------------------------------------------------------------
//
// Every figure below is the server's (C19): opening, running balance, totals,
// closing. The client formats strings and never adds one to another.

export interface Correspondent {
  account_id: string
  account_code: string
  debit: string
  credit: string
}

export interface AccountLedgerRow {
  journal_entry_id: string
  entry_number: string
  accounting_date: string
  document_date: string
  entry_type: string
  description: string
  debit: string
  credit: string
  /** After this row, over the whole window -- the server's running balance. */
  balance: string
  has_formulas: boolean
  /** Both halves of R14, as on the register. */
  reverses_entry_id: string | null
  reversed_by_entry_id: string | null
  correspondents: Correspondent[]
}

export interface AccountLedger {
  account_id: string
  account_code: string
  name_ro: string
  start_date: string
  end_date: string
  opening: string
  truncated: boolean
  rows: AccountLedgerRow[]
  total_debit: string
  total_credit: string
  closing: string
}

function window(from: string, to: string): string {
  return `?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
}

function ledgerBase(companyId: string): string {
  return `/api/v1/accounting/ledger/companies/${companyId}`
}

export function accountLedger(
  companyId: string,
  accountId: string,
  from: string,
  to: string,
): Promise<AccountLedger> {
  return request<AccountLedger>(
    `${ledgerBase(companyId)}/accounts/${accountId}/ledger${window(from, to)}`,
  )
}

export interface Turnover {
  account_id: string
  account_code: string
  amount: string
}

export interface LedgerMonth {
  period_id: string
  period_no: number
  start_date: string
  end_date: string
  opening: string
  debit: string
  credit: string
  closing: string
  debit_by: Turnover[]
  credit_by: Turnover[]
  /** Turnover no formula explains -- a lines-only entry in the month. */
  debit_unassigned: string
  credit_unassigned: string
}

export interface GeneralLedger {
  account_id: string
  account_code: string
  name_ro: string
  start_date: string
  end_date: string
  opening: string
  months: LedgerMonth[]
  total_debit: string
  total_credit: string
  closing: string
}

export function generalLedger(
  companyId: string,
  accountId: string,
  from: string,
  to: string,
): Promise<GeneralLedger> {
  return request<GeneralLedger>(
    `${ledgerBase(companyId)}/accounts/${accountId}/general-ledger${window(from, to)}`,
  )
}

export interface CorrespondenceCell {
  debit_account_id: string
  debit_code: string
  credit_account_id: string
  credit_code: string
  amount: string
}

export interface CorrespondenceReport {
  start_date: string
  end_date: string
  cells: CorrespondenceCell[]
  debit_totals: Turnover[]
  credit_totals: Turnover[]
  total: string
  lines_total: string
  /** `lines_total - total`: what the chess-board cannot explain. */
  unassigned: string
}

export function correspondence(
  companyId: string,
  from: string,
  to: string,
): Promise<CorrespondenceReport> {
  return request<CorrespondenceReport>(`${ledgerBase(companyId)}/correspondence${window(from, to)}`)
}

export interface LineDetail {
  line_number: number
  account_id: string
  account_code: string
  name_ro: string
  debit: string
  credit: string
  currency: string
  amount_currency: string
  exchange_rate: string
  document_date: string
  rate_date: string
  description: string | null
  dimensions: Record<string, string>
}

export interface FormulaDetail {
  formula_number: number
  debit_account_id: string
  debit_code: string
  credit_account_id: string
  credit_code: string
  amount: string
  currency: string
  amount_currency: string
  exchange_rate: string
  vat_rate: string | null
  vat_rate_key: string | null
  description: string | null
  slots: Record<string, string>
}

export interface EntryOrigin {
  accounting_event_id: string
  event_type: string
  source_module: string
  source_document_type: string
  source_document_id: string
  occurred_at: string
}

export interface EntryDetail {
  id: string
  company_id: string
  entry_number: string
  accounting_date: string
  entry_type: string
  status: string
  description: string
  total_debit: string
  total_credit: string
  posted_at: string | null
  reverses_entry_id: string | null
  reversed_by_entry_id: string | null
  /** What it stood on (ADR-048). */
  rule_ref: string | null
  chart: string | null
  fiscal_effective_date: string | null
  lines: LineDetail[]
  formulas: FormulaDetail[]
  origin: EntryOrigin | null
}

export function entryDetail(entryId: string): Promise<EntryDetail> {
  return request<EntryDetail>(`/api/v1/accounting/ledger/entries/${entryId}`)
}

/**
 * The address of the same report as a file (C20). A link, not a fetch: the
 * browser downloads it with the session cookie, and the server builds it from
 * the same result it rendered -- `?export=`, because `?format=` belongs to the
 * server's own content negotiation.
 */
export function exportUrl(path: string, from: string, to: string): string {
  return `${path}${window(from, to)}&export=csv`
}

export function trialBalanceExport(companyId: string, from: string, to: string): string {
  return exportUrl(`${ledgerBase(companyId)}/trial-balance`, from, to)
}

export function accountLedgerExport(companyId: string, accountId: string, from: string, to: string): string {
  return exportUrl(`${ledgerBase(companyId)}/accounts/${accountId}/ledger`, from, to)
}

export function generalLedgerExport(companyId: string, accountId: string, from: string, to: string): string {
  return exportUrl(`${ledgerBase(companyId)}/accounts/${accountId}/general-ledger`, from, to)
}

export function correspondenceExport(companyId: string, from: string, to: string): string {
  return exportUrl(`${ledgerBase(companyId)}/correspondence`, from, to)
}
