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
  /** Null on the console host: a session bound to no workspace (ADR-076). */
  tenant_id: string | null
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


/**
 * Correct your own display name.
 *
 * No identifier: it edits the signed-in user and nobody else, because the policy
 * on `user` is self-row and the endpoint has nowhere to put another id.
 *
 * The e-mail, the password and the second factor are **not** here. The first is
 * the credential and needs the new address proved; the other two start from the
 * current ones. Each is its own path, and putting them in a profile form would
 * make three different acts look like one.
 */
export function updateProfile(fullName: string): Promise<{ user_id: string; full_name: string }> {
  return request<{ user_id: string; full_name: string }>('/api/v1/auth/profile', {
    method: 'PATCH',
    body: { full_name: fullName },
  })
}
