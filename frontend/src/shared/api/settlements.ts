/**
 * Open balances and matching -- `operations/settlements`.
 *
 * **One call for both lists.** They are read together: a screen that fetched them
 * separately would offer a match against half the truth.
 *
 * **An allocation carries three fields.** Which document, which movement, how
 * much. The side, the residence and the counterparty are read from the documents
 * by the server, because they were asked once already when the documents were
 * entered -- asking again would invite two answers about one invoice.
 */

import { request } from './client'

export interface OpenItem {
  document_id: string
  document_type: string
  formatted_number: string | null
  document_date: string
  partner_id: string | null
  side: 'receivable' | 'payable'
  total: string
  allocated: string
  outstanding: string
}

export interface OpenItems {
  documents: OpenItem[]
  movements: OpenItem[]
}

export interface AllocationResult {
  settlement_id: string
  outstanding_after: string
  document_outstanding: string
}

export function listOpenItems(companyId: string): Promise<OpenItems> {
  return request<OpenItems>(`/api/v1/settlements/companies/${companyId}/open`)
}

export function allocate(
  body: {
    settled_document_id: string
    movement_document_id: string
    amount: string
  },
  idempotencyKey: string,
): Promise<AllocationResult> {
  return request<AllocationResult>('/api/v1/settlements/allocations', {
    method: 'POST',
    body,
    idempotencyKey,
  })
}
