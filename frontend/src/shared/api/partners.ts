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
  vat_code: string | null
  is_customer: boolean
  is_supplier: boolean
  is_active: boolean
}

export interface PartnerQuery {
  /** Matches legal name, short name or IDNO. */
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
  vat_code?: string | null
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
