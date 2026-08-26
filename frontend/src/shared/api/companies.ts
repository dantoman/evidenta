/**
 * The companies this session may reach.
 *
 * Every company-scoped screen needs this before it can ask anything else: the
 * routes take a company identifier, and until now the client had no way to learn
 * one -- `whoami` answers with the tenant and the user, never with a company.
 *
 * The server does no filtering; the policy on the table does. What comes back is
 * exactly what the caller may see.
 */

import { request } from './client'

export interface Company {
  id: string
  legal_name: string
  idno: string
  functional_currency: string
}

export function listCompanies(): Promise<Company[]> {
  return request<Company[]>('/api/v1/companies')
}
