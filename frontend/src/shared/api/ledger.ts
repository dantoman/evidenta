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
