/**
 * The role bindings -- against `accounting/slots/urls.py`.
 *
 * A role is what a posting asks for -- the till, VAT collected, trade
 * receivables -- and the binding says which account of the company's chart that
 * means, from a date. The engine refuses an unbound role rather than guessing,
 * and until this existed the panel could say "no cash account is bound" with no
 * way to bind one.
 *
 * **A rebinding is history, never an edit.** `PUT` closes the binding in force on
 * the day the new one starts; postings before that day keep the account they were
 * made with. The date is always stated by the person, never defaulted here.
 *
 * Role keys are the server's vocabulary and are shown as they are: they are the
 * names the engine uses, not interface strings, and translating them would put a
 * second vocabulary between the accountant and the refusal that names one.
 */

import { request } from './client'

export interface RoleBindingRow {
  /** A key of the closed catalogue, e.g. `CASA_MDL`. */
  role: string
  /** The subaccount the general plan imposes for the role. */
  default_code: string
  /** Dimensions the bound account has to carry (ADR-048). */
  dimension_slots: string[]
  /** The binding in force on the date asked for -- all null when the role is unbound. */
  account_id: string | null
  account_code: string | null
  name_ro: string | null
  valid_from: string | null
  source: string | null
}

export interface RoleBinding {
  id: string
  role: string
  account_id: string
  account_code: string
  name_ro: string
  valid_from: string
  valid_to: string | null
  source: string
}

const base = (companyId: string) => `/api/v1/accounting/slots/companies/${companyId}/role-bindings`

/** Every role of the catalogue, with what it resolves to on `on`. */
export function listRoleBindings(companyId: string, on: string): Promise<RoleBindingRow[]> {
  return request<RoleBindingRow[]>(`${base(companyId)}?on=${encodeURIComponent(on)}`)
}

export function rebindRole(
  companyId: string,
  role: string,
  body: { account_id: string; valid_from: string },
): Promise<RoleBinding> {
  return request<RoleBinding>(`${base(companyId)}/${encodeURIComponent(role)}`, {
    method: 'PUT',
    body,
  })
}
