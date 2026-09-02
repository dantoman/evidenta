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
