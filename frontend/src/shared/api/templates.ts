/**
 * Operation templates -- a shortcut to a manual note, not a second kind of
 * posting. They live under `entries/` on the server for that reason, and what
 * they produce is an ordinary entry: the register shows it as `standard`,
 * indistinguishable from one typed line by line. If a screen ever wants to say
 * "posted from template X", that is the screen's knowledge and does not belong
 * in the register.
 *
 * **An amount is either a decimal string or `{from_input: key}`**, and the two
 * are not collapsed into one field with a magic string. A template whose amount
 * is literally the text "from_input" would be one nobody can post, and the
 * ambiguity would surface at expansion instead of at definition.
 */

import { request } from './client'

export type TemplateAmount = string | { from_input: string }

export interface TemplateLine {
  line_number?: number
  account_id: string
  side: 'debit' | 'credit'
  amount: TemplateAmount
  description?: string | null
  dimensions?: Record<string, TemplateAmount>
}

export interface TemplateSummary {
  id: string
  name: string
  entry_description: string
  is_active: boolean
  /** The keys the template will ask for at posting time. */
  inputs: string[]
  line_count: number
}

export interface TemplateDefinition extends Omit<TemplateSummary, 'line_count'> {
  lines: TemplateLine[]
}

const base = (companyId: string) => `/api/v1/accounting/entries/companies/${companyId}/templates`

/**
 * The default list hides retired templates; a retired one stays readable by id.
 * Expansion must not reach a withdrawn template, but an entry posted last year
 * names one -- and a definition that became unreadable would leave that entry
 * explaining itself with an identifier.
 */
export function listTemplates(
  companyId: string,
  includeInactive = false,
): Promise<TemplateSummary[]> {
  return request<TemplateSummary[]>(
    `${base(companyId)}${includeInactive ? '?include_inactive=true' : ''}`,
  )
}

export function getTemplate(companyId: string, templateId: string): Promise<TemplateDefinition> {
  return request<TemplateDefinition>(`${base(companyId)}/${templateId}`)
}

export interface TemplateInput {
  name: string
  entry_description: string
  lines: TemplateLine[]
}

export function createTemplate(
  companyId: string,
  definition: TemplateInput,
): Promise<TemplateDefinition> {
  return request<TemplateDefinition>(base(companyId), { method: 'POST', body: definition })
}

/** The definition round-trips: what `getTemplate` returns goes back unchanged. */
export function redefineTemplate(
  companyId: string,
  templateId: string,
  definition: TemplateInput,
): Promise<TemplateDefinition> {
  return request<TemplateDefinition>(`${base(companyId)}/${templateId}`, {
    method: 'PUT',
    body: definition,
  })
}

export function setTemplateActive(
  companyId: string,
  templateId: string,
  active: boolean,
): Promise<TemplateDefinition> {
  return request<TemplateDefinition>(`${base(companyId)}/${templateId}/activation`, {
    method: 'POST',
    body: { active },
  })
}

export interface TemplatePosting {
  accounting_date: string
  note_id: string
  inputs: Record<string, string>
  description?: string
}

export interface PostedFromTemplate {
  accounting_event_id: string
  journal_entry_id: string
  posted_now: boolean
}

export function postFromTemplate(
  companyId: string,
  templateId: string,
  posting: TemplatePosting,
  idempotencyKey: string,
): Promise<PostedFromTemplate> {
  return request<PostedFromTemplate>(`${base(companyId)}/${templateId}/posting`, {
    method: 'POST',
    body: posting,
    idempotencyKey,
  })
}
