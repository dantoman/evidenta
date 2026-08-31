/**
 * The partner directory -- `masterdata/partners`.
 *
 * **No company segment, and that is the point.** A partner belongs to the
 * tenant: the same legal entity is the same entity for every company of the
 * firm, and a copy per company is how a holding ends up with two identical
 * suppliers whose balances stop reconciling.
 *
 * `legal_name` is what appears on documents and in registers (C39). A short name
 * exists for the interface and for searching, and never reaches a register.
 */

import { request } from './client'

export interface Partner {
  id: string
  legal_name: string
  short_name: string | null
  kind: string
  idno: string | null
  idnp: string | null
  internal_name: string | null
  /** Prefers the internal name, falls back to the legal one (ADR-034). */
  display_name: string
  /** The code of the still-open VAT registration, or null when there is none. */
  vat_code: string | null
  vat_registered: boolean
  default_currency: string | null
  default_payment_terms_days: number | null
  is_customer: boolean
  is_supplier: boolean
  is_active: boolean
}

export interface PartnerQuery {
  /** Matches legal name, short name, internal name or IDNO. */
  q?: string
  role?: 'customer' | 'supplier'
  includeInactive?: boolean
}

/**
 * The server answers at most 200 rows and does not paginate. A client that
 * paged over that on its own would be inventing an order the server never
 * promised -- so a search that needs narrowing gets narrowed by `q`.
 */
export function listPartners({ q, role, includeInactive }: PartnerQuery = {}): Promise<Partner[]> {
  const query = new URLSearchParams()
  if (q) query.set('q', q)
  if (role) query.set('role', role)
  if (includeInactive) query.set('include_inactive', 'true')
  const suffix = query.toString()
  return request<Partner[]>(`/api/v1/masterdata/partners/${suffix ? `?${suffix}` : ''}`)
}

export interface NewPartner {
  legal_name: string
  kind?: string
  short_name?: string | null
  idno?: string | null
  idnp?: string | null
  internal_name?: string | null
  vat_code?: string | null
  /**
   * Required whenever a VAT code is sent. The server refuses the pair otherwise,
   * and the refusal is the point: whether a counterparty was registered on the
   * day of a document decides how that document is treated, and a start date
   * taken from the day the card was typed answers a different question.
   */
  vat_valid_from?: string | null
  default_currency?: string | null
  default_payment_terms_days?: number | null
  is_customer?: boolean
  is_supplier?: boolean
}

export function createPartner(partner: NewPartner): Promise<Partner> {
  return request<Partner>('/api/v1/masterdata/partners/', { method: 'POST', body: partner })
}

/**
 * Retiring, not deleting. A partner named by a posted entry stays readable --
 * the same reason a withdrawn operation template keeps its definition.
 */
export function setPartnerActive(partnerId: string, active: boolean): Promise<Partner> {
  return request<Partner>(`/api/v1/masterdata/partners/${partnerId}/activation`, {
    method: 'POST',
    body: { active },
  })
}


/**
 * What a person may correct on a partner -- ADR-083's line, drawn again here.
 *
 * The identity is absent on purpose: `idno` and `idnp` are what an issued
 * document names the counterparty by, and what keeps two records from splitting
 * one balance (`R20`). The VAT code is absent because registration is a dated
 * state, not a field: it is added through its own path, never overwritten.
 *
 * The server refuses anything else **by name** rather than dropping it, so a
 * caller that sends `idno` learns that it was not applied.
 */
export interface PartnerEdit {
  legal_name?: string
  short_name?: string | null
  internal_name?: string | null
  default_currency?: string | null
  default_payment_terms_days?: number | null
  is_customer?: boolean
  is_supplier?: boolean
}

export function updatePartner(partnerId: string, change: PartnerEdit): Promise<Partner> {
  return request<Partner>(`/api/v1/masterdata/partners/${partnerId}`, {
    method: 'PATCH',
    body: change,
  })
}
