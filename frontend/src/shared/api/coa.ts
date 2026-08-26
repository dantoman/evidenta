/**
 * The chart of accounts -- against `accounting/coa/urls.py`.
 *
 * `name_ro` is displayed as it arrives. The books are kept in Romanian by law
 * (C33, ADR-016), so an account name is a single stored value and never an
 * interface string: nothing here translates it, and nothing may.
 */

import { request } from './client'

/** Where the account came from, which decides what may be done to it. */
export type AccountOrigin = 'system' | 'company'

export type AccountClass = 'asset' | 'liability' | 'equity' | 'income' | 'expense'

export interface Account {
  id: string
  account_code: string
  name_ro: string
  parent_id: string | null
  origin: AccountOrigin
  template_account_id: string | null
  account_class: AccountClass
  normal_balance: 'debit' | 'credit'
  allows_subaccounts: boolean
  currency_tracking: boolean
  quantity_tracking: boolean
  required_dimensions: string[]
  is_blocked: boolean
  valid_from: string
  valid_to: string | null
}

/**
 * The company's chart.
 *
 * `on` narrows to what a posting dated then may use -- inside its validity window
 * and not blocked. Omitted, the whole chart comes back, including accounts that
 * are closed or not yet open: a screen that showed only today's accounts could
 * not explain a posting made last year.
 */
export function listAccounts(companyId: string, on?: string): Promise<Account[]> {
  const query = on ? `?on=${encodeURIComponent(on)}` : ''
  return request<Account[]>(`/api/v1/accounting/coa/companies/${companyId}/accounts${query}`)
}
