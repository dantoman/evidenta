/**
 * Money in and out -- `operations/treasury`.
 *
 * **One list for both directions.** The person looking at a company's money wants
 * it in date order, not split into two screens they interleave mentally.
 *
 * **Three things are asked and never defaulted**: the direction, where the money
 * moved (`cash` or `bank` -- the treasury account is the instrument's, not the
 * document's), and whether the counterparty is a resident.
 *
 * **What is deliberately absent: which invoice this settles.** The posting does
 * not need it, and the link is settlement -- its own step. A field here would be
 * half a link, and half a link is one that reports start reading.
 */

import { request } from './client'

export type MovementDirection = 'receipt' | 'payment'
export type TreasuryAccount = 'cash' | 'bank'

export interface Movement {
  id: string
  formatted_number: string | null
  document_date: string
  accounting_date: string
  state: string
  partner_id: string | null
  currency: string
  direction: MovementDirection
  treasury_account: TreasuryAccount
  /** A string on the wire: parsed to a float it stops being the ledger's number. */
  amount: string
  partner_resident: boolean
  posting?: {
    accounting_event_id: string
    journal_entry_id: string | null
    posted_now: boolean
  }
}

export interface NewMovement {
  direction: MovementDirection
  partner_id: string
  document_date: string
  accounting_date?: string | null
  amount: string
  treasury_account: TreasuryAccount
  partner_resident: boolean
  notes?: string | null
}

export function listMovements(companyId: string): Promise<Movement[]> {
  return request<Movement[]>(`/api/v1/treasury/companies/${companyId}/movements`)
}

export function createMovement(companyId: string, body: NewMovement): Promise<Movement> {
  return request<Movement>(`/api/v1/treasury/companies/${companyId}/movements`, {
    method: 'POST',
    body,
  })
}

export function recordMovement(documentId: string): Promise<Movement> {
  return request<Movement>(`/api/v1/treasury/movements/${documentId}/recording`, {
    method: 'POST',
  })
}
