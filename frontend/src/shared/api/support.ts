/**
 * The client's side of a support grant -- `/api/v1/support/` (ADR-077).
 *
 * Approving and revoking are the client's acts, through their own permission;
 * `session` is what a support session reads to say, in the bar, on which ticket
 * it runs and until when.
 */

import { request } from './client'

export type GrantStatus = 'pending' | 'active' | 'expired' | 'revoked'

export interface SupportGrant {
  id: string
  company_id: string | null
  request_ref: string
  justification: string
  requested_at: string
  approved_at: string | null
  expires_at: string | null
  revoked_at: string | null
  status: GrantStatus
}

export function listSupportGrants(): Promise<{ grants: SupportGrant[] }> {
  return request<{ grants: SupportGrant[] }>('/api/v1/support/grants')
}

/** Consent for a bounded window; the server's default is 24 hours, its ceiling 72. */
export function approveSupportGrant(id: string, hours?: number): Promise<{ grant: SupportGrant }> {
  return request<{ grant: SupportGrant }>(`/api/v1/support/grants/${id}/approve`, {
    method: 'POST',
    body: hours === undefined ? {} : { hours },
  })
}

export function revokeSupportGrant(id: string): Promise<{ grant: SupportGrant }> {
  return request<{ grant: SupportGrant }>(`/api/v1/support/grants/${id}/revoke`, {
    method: 'POST',
  })
}

export function supportSession(): Promise<{ grant: SupportGrant | null }> {
  return request<{ grant: SupportGrant | null }>('/api/v1/support/session')
}
