/**
 * The three authentication calls -- against `platform/identity/urls.py`.
 *
 * The tenant is never a parameter. It comes from the subdomain the browser is
 * already on (C8), so there is nothing here to pass and nothing a caller could
 * pass wrongly.
 */

import { request } from './client'

export interface Session {
  expires_at: string
}

export interface Identity {
  user_id: string
  tenant_id: string
  actor_firm_id: string | null
  request_id: string
}

export interface Credentials {
  email: string
  password: string
  /** The second factor. Mandatory for everyone -- ADR-021, no opt-out. */
  totp_code?: string
  backup_code?: string
}

export function login(credentials: Credentials): Promise<Session> {
  return request<Session>('/api/v1/auth/login', { method: 'POST', body: credentials })
}

export function logout(): Promise<void> {
  return request<void>('/api/v1/auth/logout', { method: 'POST' })
}

/**
 * Who the server says this request is.
 *
 * Answers from the context the middlewares established, with no query -- so
 * reaching it successfully means the cookie resolved, the host resolved, the two
 * agreed, and the context was set. That makes it the honest check of whether a
 * session is live, and the reason the application asks it on load rather than
 * trusting anything stored in the browser.
 */
export function whoami(): Promise<Identity> {
  return request<Identity>('/api/v1/auth/whoami')
}
