/**
 * Supplier invoices -- `operations/purchases`.
 *
 * **Three things are asked for and never defaulted.** The supplier's own number
 * and date, because without them the same invoice arriving twice -- typed once,
 * imported once -- cannot be recognised as one document. And two discriminators:
 * where the cost lands, which selects the expense account, and whether the
 * supplier is a resident, which selects the payable. Neither is derivable: a
 * service invoice does not say whether the service was administrative, and the
 * partner card carries no residence.
 *
 * **Recording is one call**, the counterpart of issuing: validating without
 * posting leaves a numbered document with no accounting effect.
 *
 * **No amounts are computed here** (`C19`). The client sends quantity and unit
 * price; the server derives the line and the totals with the versioned rounding
 * rule.
 */

import { request } from './client'

export type CostDestination =
  | 'administrative'
  | 'commercial'
  | 'production_direct'
  | 'production_indirect'

export interface PurchaseLineInput {
  description: string
  quantity: string
  unit_price: string
}

export interface PurchaseInvoice {
  id: string
  /** Ours, allocated at validation. Theirs is below, and both appear. */
  formatted_number: string | null
  supplier_document_number: string
  supplier_document_date: string
  document_date: string
  accounting_date: string
  state: string
  partner_id: string | null
  currency: string
  cost_destination: CostDestination
  partner_resident: boolean
  /** On every row, list and detail alike: the register shows the total (`C19`). */
  totals: { net: string; vat: string; total: string }
  posting?: {
    accounting_event_id: string
    journal_entry_id: string | null
    posted_now: boolean
  }
}

export interface NewPurchaseInvoice {
  partner_id: string
  document_date: string
  accounting_date?: string | null
  supplier_document_number: string
  supplier_document_date: string
  cost_destination: CostDestination
  partner_resident: boolean
  notes?: string | null
  lines: PurchaseLineInput[]
}

export function listPurchases(companyId: string): Promise<PurchaseInvoice[]> {
  return request<PurchaseInvoice[]>(`/api/v1/purchases/companies/${companyId}/invoices`)
}

export function createPurchase(
  companyId: string,
  body: NewPurchaseInvoice,
): Promise<PurchaseInvoice> {
  return request<PurchaseInvoice>(`/api/v1/purchases/companies/${companyId}/invoices`, {
    method: 'POST',
    body,
  })
}

export function getPurchase(documentId: string): Promise<PurchaseInvoice> {
  return request<PurchaseInvoice>(`/api/v1/purchases/invoices/${documentId}`)
}

export function replacePurchaseLines(
  documentId: string,
  lines: PurchaseLineInput[],
): Promise<PurchaseInvoice> {
  return request<PurchaseInvoice>(`/api/v1/purchases/invoices/${documentId}/lines`, {
    method: 'PUT',
    body: { lines },
  })
}

export function recordPurchase(documentId: string): Promise<PurchaseInvoice> {
  return request<PurchaseInvoice>(`/api/v1/purchases/invoices/${documentId}/recording`, {
    method: 'POST',
  })
}
