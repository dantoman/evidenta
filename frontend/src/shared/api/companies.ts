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
  /** The day the books start. Sent since the list existed; declared here since
   *  the company card had to show it. */
  accounting_start_date: string
  /** The two codes a statutory return's header carries. Null until entered. */
  cuatm_code: string | null
  caem_code: string | null
  short_name: string | null
  registered_address: unknown | null
  /** `active`, `suspended` or `closed` -- ADR-083. A closed company is refused
   *  by the posting engine, so the screens say so rather than letting somebody
   *  discover it at the first entry. */
  status: string
}

/**
 * One company, and what may be corrected on it -- ADR-083.
 *
 * The fields absent from `EditableCompany` are absent on purpose, not by
 * oversight: `idno` has left on issued documents, and the currency and start date
 * have already dated and valued what is in the ledger. The server refuses them by
 * name; the screen shows them as facts rather than as inputs.
 */
export interface EditableCompany {
  legal_name?: string
  short_name?: string | null
  cuatm_code?: string | null
  caem_code?: string | null
}

export function getCompany(companyId: string): Promise<Company> {
  return request<Company>(`/api/v1/companies/${companyId}`)
}

export function updateCompany(companyId: string, fields: EditableCompany): Promise<Company> {
  return request<Company>(`/api/v1/companies/${companyId}`, { method: 'PATCH', body: fields })
}

/**
 * Closing is a POST to a named sub-resource, not a PATCH of `status`.
 *
 * It carries a reason because a company that stopped trading and one closed by
 * mistake look identical afterwards, and it holds its own permission key because
 * it is irreversible in practice -- nothing in the ledger moves, and nothing new
 * is written either.
 */
export function closeCompany(companyId: string, reason: string): Promise<Company> {
  return request<Company>(`/api/v1/companies/${companyId}/close`, {
    method: 'POST',
    body: { reason },
  })
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
  cuatm_code?: string | null
  caem_code?: string | null
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

/**
 * The company's VAT registrations -- a dated fact with a history, never a
 * toggle (ADR-088, ADR-089).
 *
 * `valid_to` is the last day the registration applies, inclusive, and is null
 * for one still open. The status endpoint answers for **one day**, and asks for
 * it: which regimes an invoice may state is a question about the invoice's date,
 * not about today (ADR-044).
 */
export interface VatRegistration {
  id: string
  vat_code: string
  valid_from: string
  valid_to: string | null
  source: string | null
}

export interface NewVatRegistration {
  vat_code: string
  valid_from: string
  valid_to?: string | null
  source?: string | null
}

export interface TaxStatus {
  version: number
  on: string
  vat:
    | { registered: false }
    | { registered: true; code: string; valid_from: string; valid_to: string | null }
}

export function listVatRegistrations(companyId: string): Promise<VatRegistration[]> {
  return request<VatRegistration[]>(`/api/v1/companies/${companyId}/vat-registrations`)
}

export function registerForVat(
  companyId: string,
  registration: NewVatRegistration,
): Promise<VatRegistration> {
  return request<VatRegistration>(`/api/v1/companies/${companyId}/vat-registrations`, {
    method: 'POST',
    body: registration,
  })
}

export function taxStatus(companyId: string, on: string): Promise<TaxStatus> {
  return request<TaxStatus>(`/api/v1/companies/${companyId}/tax-status?on=${on}`)
}

/**
 * The VAT fiscal periods -- ADR-039 §7, with a door since ADR-090.
 *
 * Opened as a second call after the registration, for the reason the exercise
 * is: `platform` records the registration and does not import `accounting`,
 * where the period lives. The server refuses a month the registration does not
 * cover, so the client names the months and does not derive the answer.
 */
export interface VatPeriod {
  id: string
  start_date: string
  /** The last day, inclusive. Longer than a month only for the final period. */
  end_date: string
  kind: 'monthly' | 'final'
}

export function listVatPeriods(companyId: string): Promise<VatPeriod[]> {
  return request<VatPeriod[]>(`/api/v1/accounting/periods/companies/${companyId}/vat-periods`)
}

export function openVatPeriods(
  companyId: string,
  window: { first_month: string; through: string },
): Promise<VatPeriod[]> {
  return request<VatPeriod[]>(`/api/v1/accounting/periods/companies/${companyId}/vat-periods`, {
    method: 'POST',
    body: window,
  })
}
