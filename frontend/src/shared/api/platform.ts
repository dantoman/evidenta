/**
 * The console's calls -- `/api/v1/platform/`, served only on the `admin.` host
 * (ADR-076). Same client, same cookie, same error codes; what differs is that
 * none of these carries a company or a workspace, because there is none.
 */

import { request } from './client'

export type StaffRole = 'support' | 'operator' | 'admin'

export interface StaffMe {
  user_id: string
  email: string
  full_name: string
  staff_role: StaffRole
  granted_at: string
}

export function staffMe(): Promise<StaffMe> {
  return request<StaffMe>('/api/v1/platform/staff/me')
}

export interface ActRef {
  act_type: string
  act_number: string
  act_date: string | null
  title: string | null
  effective_from: string | null
}

export type ParameterStatus = 'draft' | 'approved' | 'active' | 'superseded'
export type ValueType =
  | 'decimal'
  | 'integer'
  | 'money'
  | 'percentage'
  | 'date'
  | 'boolean'
  | 'table'
export type MarginBasis = 'act' | 'platform_convention'
export type Confidence = 'confirmed' | 'provisional'

export interface FiscalParameter {
  id: string
  parameter_key: string
  scope: string
  scope_ref: string | null
  value_type: ValueType
  value: unknown
  unit: string | null
  valid_from: string | null
  valid_to: string | null
  margin_basis: MarginBasis | null
  margin_reference: string | null
  margin_act: ActRef | null
  observed_in: string | null
  act: ActRef
  status: ParameterStatus
  confidence: Confidence
  provisional_reason: string | null
  approved_by_user_id: string | null
  approved_at: string | null
  updated_at: string
}

export function listFiscalParameters(): Promise<{ parameters: FiscalParameter[] }> {
  return request<{ parameters: FiscalParameter[] }>('/api/v1/platform/fiscal-parameters/')
}

export interface ActInput {
  act_type: string
  act_number: string
  act_date: string
  title: string
  effective_from: string | null
  publication?: {
    gazette_year: number
    gazette_number: string
    article: string
    published_at: string | null
  } | null
}

export interface ParameterDraftInput {
  parameter_key: string
  value_type: ValueType
  value: unknown
  unit: string | null
  valid_from: string | null
  valid_to: string | null
  margin_basis: MarginBasis | null
  margin_reference: string | null
  observed_in: string | null
  confidence: Confidence
  provisional_reason: string | null
  act: ActInput
  margin_act?: ActInput | null
}

export interface WriteOutcome {
  outcome: 'created' | 'updated' | 'unchanged' | 'activated' | 'already_active'
  parameter: FiscalParameter
}

/** A new dated version -- `P-4`, written as the signed-in operator. */
export function draftFiscalParameter(input: ParameterDraftInput): Promise<WriteOutcome> {
  return request<WriteOutcome>('/api/v1/platform/fiscal-parameters/', {
    method: 'POST',
    body: input,
  })
}

/** Approval by the signed-in operator; idempotent by state on the server. */
export function activateFiscalParameter(id: string): Promise<WriteOutcome> {
  return request<WriteOutcome>(`/api/v1/platform/fiscal-parameters/${id}/activate`, {
    method: 'POST',
  })
}

// --- the rest of the console (ADR-076 §4.3) ---------------------------------

export interface Space {
  id: string
  subdomain: string
  legal_name: string
  legal_form: string | null
  idno: string | null
  status: 'active' | 'suspended' | 'offboarding' | 'archived' | string
  claimed_at: string | null
  suspended_at: string | null
  offboarding_started_at: string | null
  archived_at: string | null
  created_at: string | null
  company_count: number
  member_count: number
}

export function listSpaces(): Promise<{ spaces: Space[] }> {
  return request<{ spaces: Space[] }>('/api/v1/platform/spaces/')
}

export interface StaffRow {
  user_id: string
  email: string
  full_name: string
  staff_role: StaffRole
  granted_by_email: string
  granted_at: string
  revoked_at: string | null
}

export function listStaff(): Promise<{ staff: StaffRow[] }> {
  return request<{ staff: StaffRow[] }>('/api/v1/platform/staff/')
}

/** `P-12`, the admin's: one role per person, a change is revoke then grant. */
export function grantStaff(email: string, role: StaffRole): Promise<{ user_id: string }> {
  return request<{ user_id: string }>('/api/v1/platform/staff/', {
    method: 'POST',
    body: { email, staff_role: role },
  })
}

export function revokeStaff(userId: string): Promise<{ user_id: string; revoked: boolean }> {
  return request<{ user_id: string; revoked: boolean }>(
    `/api/v1/platform/staff/${userId}/revoke`,
    { method: 'POST' },
  )
}

export interface LogRow {
  id: number
  occurred_at: string
  path_code: string
  actor: string
  actor_user_id: string | null
  actor_email: string | null
  subject_tenant_id: string | null
  subject_subdomain: string | null
  tenant_count: number | null
  request_id: string
  justification: string | null
  payload: Record<string, unknown> | null
}

export interface PrivilegedLog {
  paths: { code: string; label: string }[]
  rows: LogRow[]
}

export function privilegedLog(filter: {
  path?: string
  space?: string
  limit?: number
}): Promise<PrivilegedLog> {
  const params = new URLSearchParams()
  if (filter.path) params.set('path', filter.path)
  if (filter.space) params.set('space', filter.space)
  if (filter.limit) params.set('limit', String(filter.limit))
  const query = params.toString()
  return request<PrivilegedLog>(`/api/v1/platform/privileged-log/${query ? `?${query}` : ''}`)
}

export interface Activation {
  id: string
  subdomain: string
  legal_name: string
  company_id: string | null
  company_legal_name: string | null
  company_idno: string | null
  capability_key: string
  effective_from: string
  effective_to: string | null
  initialisation_state: string
  source: string
  activated_at: string
}

export function listActivations(): Promise<{ activations: Activation[] }> {
  return request<{ activations: Activation[] }>('/api/v1/platform/capabilities/')
}

export interface FlagsPage {
  flags: { key: string; description: string; default_state: boolean; is_compliance: boolean }[]
  rings: { code: string; description: string; sequence: number }[]
  ring_assignments: {
    subdomain: string
    legal_name: string
    ring_code: string
    assigned_at: string
    assigned_by_email: string | null
  }[]
  overrides: {
    id: string
    subdomain: string
    legal_name: string
    flag_key: string
    state: boolean
    reason: string
    expires_at: string
    created_at: string
    created_by_email: string | null
  }[]
}

export function flagsPage(): Promise<FlagsPage> {
  return request<FlagsPage>('/api/v1/platform/flags/')
}

export interface ChartTemplate {
  id: string
  code: string
  version: string
  status: string
  valid_from: string | null
  valid_to: string | null
  published_at: string | null
  source_act: string
  source_reference: string | null
  act: ActRef | null
  account_count: number
}

export function listChartTemplates(): Promise<{ templates: ChartTemplate[] }> {
  return request<{ templates: ChartTemplate[] }>('/api/v1/platform/coa-templates/')
}

// --- support grants and incidents (ADR-077, ADR-076 §4.3) ---------------------

export interface ConsoleGrant {
  id: string
  subdomain: string
  legal_name: string
  company_id: string | null
  requested_by_email: string
  request_ref: string
  justification: string
  requested_at: string
  approved_at: string | null
  expires_at: string | null
  revoked_at: string | null
  status: 'pending' | 'active' | 'expired' | 'revoked'
}

export function listConsoleGrants(): Promise<{ grants: ConsoleGrant[] }> {
  return request<{ grants: ConsoleGrant[] }>('/api/v1/platform/support-grants/')
}

/** `P-7`: the request, by a `support` employee. Gives no access by itself. */
export function requestSupportGrant(input: {
  space: string
  request_ref: string
  justification: string
}): Promise<{ grant_id: string }> {
  return request<{ grant_id: string }>('/api/v1/platform/support-grants/', {
    method: 'POST',
    body: input,
  })
}

export interface Probe {
  name: string
  ok: boolean
  detail: string | null
  latency_ms: number | null
}

export interface Incidents {
  database: Probe
  broker: Probe
  workers: Probe
  queues: { name: string; depth: number | null; detail: string | null }[]
  paths: { code: string; label: string; last_run_at: string | null; last_actor: string | null }[]
}

export function incidents(): Promise<Incidents> {
  return request<Incidents>('/api/v1/platform/incidents/')
}
