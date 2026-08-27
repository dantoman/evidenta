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

/**
 * Creating a company -- `P-9` (ADR-040).
 *
 * The application role cannot insert this row: the policy on `company` requires
 * an access row that requires the company. So the server routes it through a
 * privileged function, and the creator gets access in the same transaction --
 * which is why the list below refreshes to include it.
 */
export interface NewCompany {
  idno: string
  legal_name: string
  functional_currency?: string
  accounting_start_date?: string
}

export function createCompany(company: NewCompany): Promise<Company> {
  return request<Company>('/api/v1/companies', { method: 'POST', body: company })
}

/**
 * The exercise, opened as a second call rather than folded into the first.
 *
 * Not an oversight in the API: opening an exercise belongs to `accounting`, and
 * `platform` -- where companies live -- does not import it. The two calls keep
 * the module boundary the server actually enforces visible here too.
 */
export interface FiscalYear {
  id: string
  code: string
  start_date: string
  end_date: string
  status: string
  periods: number
}

export function openFiscalYear(
  companyId: string,
  year: { code?: string; start_date?: string; end_date?: string } = {},
): Promise<FiscalYear> {
  return request<FiscalYear>(
    `/api/v1/accounting/periods/companies/${companyId}/fiscal-years`,
    { method: 'POST', body: year },
  )
}

export function listFiscalYears(companyId: string): Promise<FiscalYear[]> {
  return request<FiscalYear[]>(
    `/api/v1/accounting/periods/companies/${companyId}/fiscal-years`,
  )
}
