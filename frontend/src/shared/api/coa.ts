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
  /** What the account carries, in slot order (ADR-048). Read-only here; declared through PATCH. */
  dimension_slots: string[]
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

/**
 * A published chart version, with the act it transcribes.
 *
 * `source_act` and `source_reference` travel on the wire deliberately, and the
 * picker is why: choosing a version is choosing a normative act, and a list of
 * `code / version` alone would be asking somebody to pick between two opaque
 * strings.
 */
export interface CoaTemplate {
  id: string
  code: string
  version: string
  valid_from: string
  valid_to: string | null
  source_act: string
  source_reference: string
  published_at: string
  status: string
}

export interface Chart {
  id: string
  company_id: string
  template_id: string
  instantiated_at: string
  last_propagation_at: string | null
}

export function listTemplates(): Promise<CoaTemplate[]> {
  return request<CoaTemplate[]>('/api/v1/accounting/coa/templates')
}

/**
 * Which version this company's chart was built on.
 *
 * **404 is an answer here, not a failure**: a company that has not been
 * initialised has no chart, and that is the state the setup screen exists for.
 * The caller reads the code (`api.not_found`) rather than the status text.
 */
export function getChart(companyId: string): Promise<Chart> {
  return request<Chart>(`/api/v1/accounting/coa/companies/${companyId}/chart`)
}

export function instantiateChart(companyId: string, templateId: string): Promise<Chart> {
  return request<Chart>(`/api/v1/accounting/coa/companies/${companyId}/chart`, {
    method: 'POST',
    body: { template_id: templateId },
  })
}

export function getAccount(accountId: string): Promise<Account> {
  return request<Account>(`/api/v1/accounting/coa/accounts/${accountId}`)
}

/**
 * Rename, block or close -- never all three as one "update".
 *
 * The shape mirrors the server's: three optional fields, each applied by its own
 * service and leaving its own audit entry. A `PUT` of the whole row would make
 * "what changed" a diff somebody has to reconstruct, and an audit trail is
 * exactly what must not be reconstructed.
 */
export interface AccountChange {
  name_ro?: string
  is_blocked?: boolean
  valid_to?: string
}

export function updateAccount(accountId: string, change: AccountChange): Promise<Account> {
  return request<Account>(`/api/v1/accounting/coa/accounts/${accountId}`, {
    method: 'PATCH',
    body: change,
  })
}

/**
 * A company's own subaccount.
 *
 * `account_class` and `normal_balance` are absent because the service inherits
 * them from the parent -- there is no field here in which to get them wrong.
 * `required_dimensions` is absent for a different reason: the vocabulary is
 * closed (ADR-029) and the server defaults it to none, so a screen that offered
 * the choice would be inventing one the parent does not pass down either.
 */
export interface NewSubaccount {
  parent_id: string
  account_code: string
  name_ro: string
  valid_from: string
  currency_tracking?: boolean
  quantity_tracking?: boolean
  allows_subaccounts?: boolean
}

export function createSubaccount(
  companyId: string,
  subaccount: NewSubaccount,
): Promise<Account> {
  return request<Account>(`/api/v1/accounting/coa/companies/${companyId}/accounts`, {
    method: 'POST',
    body: subaccount,
  })
}
