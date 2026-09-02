/**
 * The VAT registers -- `operations/tax`, ADR-090.
 *
 * One side at a time, for the VAT fiscal period covering a day: the client
 * names the day, the server finds the period and refuses when there is none.
 * Nothing here adds anything up (`C19`); the totals by regime and the grand
 * totals are the server's, and the export is a link to the same result (`C20`).
 *
 * **Not the statutory form.** Codul fiscal art. 118 prescribes the registers of
 * deliveries and of procurements; their form has not been read. This is the
 * register of the company's documents with their VAT on the fiscal period, and
 * the screen says so.
 */

import { request } from './client'

export type RegisterSide = 'sales' | 'purchases'

export interface RegisterSlice {
  vat_regime_code: string
  vat_rate_key: string | null
  vat_rate: string
  net: string
  vat: string
}

export interface RegisterRow {
  document_id: string
  document_type: string
  formatted_number: string | null
  document_date: string
  accounting_date: string
  partner_id: string | null
  partner_name: string
  kind: 'invoice' | 'credit_note' | 'supplier_invoice'
  supplier_document_number: string | null
  supplier_document_date: string | null
  /** Purchases only: true in 2252, false in cost, null when posted before the engine recorded it. */
  deductible: boolean | null
  slices: RegisterSlice[]
  net: string
  vat: string
  total: string
}

export interface RegimeTotal {
  vat_regime_code: string
  vat_rate_key: string | null
  vat_rate: string
  net: string
  vat: string
}

export interface VatRegister {
  side: RegisterSide
  period: { id: string; start_date: string; end_date: string; kind: 'monthly' | 'final' }
  rows: RegisterRow[]
  by_regime: RegimeTotal[]
  totals: { net: string; vat: string; total: string; non_deductible_vat: string }
  unposted: number
}

function registerPath(companyId: string, side: RegisterSide, on: string): string {
  return `/api/v1/tax/vat/companies/${companyId}/registers/${side}?on=${encodeURIComponent(on)}`
}

export function vatRegister(companyId: string, side: RegisterSide, on: string): Promise<VatRegister> {
  return request<VatRegister>(registerPath(companyId, side, on))
}

/** The same register as a file -- `?export=`, since `?format=` is the server's own. */
export function vatRegisterExport(companyId: string, side: RegisterSide, on: string): string {
  return `${registerPath(companyId, side, on)}&export=csv`
}
