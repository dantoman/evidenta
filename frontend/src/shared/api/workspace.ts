/**
 * The workspace as the server sees it -- `/api/v1/workspace`.
 *
 * One call, because the four answers are one question: *whose account is this,
 * and what may I do in it?* Splitting them into four endpoints would let a screen
 * render three of them and leave the fourth loading, which on this screen means
 * showing a workspace without saying what you may do in it.
 *
 * The tenant is never a parameter (C8).
 */

import { request } from './client'

export interface WorkspaceRole {
  key: string
  name: string
  level: 'tenant' | 'company'
  is_system: boolean
  permissions: string[]
}

export interface WorkspaceCompanyAccess {
  company_id: string
  role_key: string
  /** How the right arrived: belonging to the workspace, or a firm's mandate. */
  granted_via: 'membership' | 'engagement'
}

export interface Workspace {
  tenant: {
    id: string
    subdomain: string
    legal_name: string
    /**
     * The **subscriber's** fiscal identity -- who the subscription invoice is
     * made out to (ADR-085). A person or a firm; nobody's ledger. Nothing is
     * derived from it: no company of the workspace is "the holder's".
     */
    idno: string | null
    legal_form: string | null
    status: string
  }
  me: {
    user_id: string
    email: string
    full_name: string
    membership_status: string | null
    role: WorkspaceRole | null
    companies: WorkspaceCompanyAccess[]
  }
  roles: WorkspaceRole[]
  delegated_access: {
    engagement_id: string
    firm_name: string
    status: string
    covers_all_companies: boolean
    valid_from: string
    valid_to: string | null
  }[]
}

export function workspace(): Promise<Workspace> {
  return request<Workspace>('/api/v1/workspace')
}
