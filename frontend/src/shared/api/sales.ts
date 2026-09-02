/**
 * Sales invoices -- `operations/sales`.
 *
 * **Two things are asked for and never defaulted**: what is being sold, and
 * whether the counterparty is a resident. Each selects an account when the
 * invoice posts, and neither is derivable -- the partner card carries no
 * residence, and what is on the invoice is not a property of the customer. A
 * default would answer both in the direction that looks harmless and be wrong
 * silently.
 *
 * **Issuing is one call.** Validating without posting leaves a numbered document
 * with no accounting effect; the server does both in the order the acts impose.
 *
 * **No amounts are computed here.** The client sends quantity and unit price; the
 * server derives the line and the totals with the versioned rounding rule, so
 * there is one implementation of it rather than two that agree until one is
 * edited.
 */

import { request } from './client'

export type RevenueKind = 'services' | 'goods' | 'products'

/**
 * What the document is, not what it contains.
 *
 * `advance` exists in the model and is deliberately not offered: its posting
 * treatment is unregistered, because crediting the advance without the settlement
 * that clears it would grow a balance nothing could reduce (ADR-073 §6). The
 * server refuses it by name, and a screen that offered it would be offering a
 * document nobody can post.
 */
export type SaleNature = 'delivery' | 'return'

export interface SalesLineInput {
  description: string
  quantity: string
  unit_price: string
  /**
   * Stated on every line, never defaulted (ADR-089). `fara_tva` is what a
   * company that is not a VAT payer on the document's date sends; a payer sends
   * a code from the vocabulary `fiscal.vatRegimes` served for that date.
   */
  vat_regime_code: string
}

export interface SalesInvoice {
  id: string
  formatted_number: string | null
  document_date: string
  accounting_date: string
  state: string
  partner_id: string | null
  currency: string
  nature: string
  revenue_kind: RevenueKind
  partner_resident: boolean
  /** On every row, list and detail alike: the register shows the total (`C19`). */
  totals: { net: string; vat: string; total: string }
  posting?: {
    accounting_event_id: string
    journal_entry_id: string | null
    posted_now: boolean
  }
}

export interface NewSalesInvoice {
  partner_id: string
  document_date: string
  accounting_date?: string | null
  /** Required over the wire: forgetting it would make a credit note an invoice. */
  nature: SaleNature
  revenue_kind: RevenueKind
  partner_resident: boolean
  external_number?: string | null
  notes?: string | null
  lines: SalesLineInput[]
}

export function listInvoices(companyId: string): Promise<SalesInvoice[]> {
  return request<SalesInvoice[]>(`/api/v1/sales/companies/${companyId}/invoices`)
}

export function createInvoice(
  companyId: string,
  body: NewSalesInvoice,
): Promise<SalesInvoice> {
  return request<SalesInvoice>(`/api/v1/sales/companies/${companyId}/invoices`, {
    method: 'POST',
    body,
  })
}

export function getInvoice(documentId: string): Promise<SalesInvoice> {
  return request<SalesInvoice>(`/api/v1/sales/invoices/${documentId}`)
}

export function replaceInvoiceLines(
  documentId: string,
  lines: SalesLineInput[],
): Promise<SalesInvoice> {
  return request<SalesInvoice>(`/api/v1/sales/invoices/${documentId}/lines`, {
    method: 'PUT',
    body: { lines },
  })
}

export function issueInvoice(documentId: string): Promise<SalesInvoice> {
  return request<SalesInvoice>(`/api/v1/sales/invoices/${documentId}/issuance`, {
    method: 'POST',
  })
}
