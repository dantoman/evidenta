/**
 * Payroll -- people, work relationships, amendments and the timesheet.
 *
 * **Everything here is under a company**, because the legal employer is the
 * company: it withholds, it files, it answers for it. A person working at two
 * companies of the same workspace has two records, deliberately.
 *
 * **Nothing here returns money.** These endpoints record what an employer
 * decided -- who works here, under which clauses, from when, by which order. What
 * that is worth is the payroll run, and it does not exist yet.
 *
 * **The relationship types come from the server**, not from a list kept here. A
 * second copy in the interface is a second copy that drifts, and the drift shows
 * up as a foreign key violation at the worst possible moment.
 */

import { request } from './client'

export interface Employee {
  id: string
  last_name: string
  first_name: string
  idnp: string | null
  identity_document_type: string | null
  identity_document_number: string | null
  tax_residency: 'resident' | 'non_resident'
  social_insurance_code: string | null
}

export interface NewEmployee {
  last_name: string
  first_name: string
  tax_residency: 'resident' | 'non_resident'
  idnp?: string | null
  identity_document_type?: string | null
  identity_document_number?: string | null
  social_insurance_code?: string | null
}

export interface RelationshipType {
  code: string
  statutory_reference: string
}

export interface Amendment {
  id: string
  amendment_number: string
  signed_on: string
  effective_from: string
  order_number: string
  order_date: string
  changed_clause: string
  note: string
  position_title: string | null
  base_salary: string | null
  weekly_hours: string | null
}

export interface Contract {
  id: string
  employee_id: string
  employee_name: string
  relationship_type: string
  contract_number: string
  signed_on: string
  effective_from: string
  effective_to: string | null
  ended_on: string | null
  hire_order_number: string
  hire_order_date: string
  termination_order_number: string | null
  termination_order_date: string | null
  position_title: string
  base_salary: string
  weekly_hours: string
  cas_payer_point: string
  budget_funded_employer: boolean
  amendments?: Amendment[]
}

export interface NewContract {
  employee_id: string
  relationship_type: string
  contract_number: string
  signed_on: string
  effective_from: string
  effective_to?: string | null
  hire_order_number: string
  hire_order_date: string
  position_title: string
  base_salary: string
  weekly_hours: string
  cas_payer_point: string
  budget_funded_employer: boolean
}

export interface NewAmendment {
  amendment_number: string
  signed_on: string
  effective_from: string
  order_number: string
  order_date: string
  changed_clause: string
  note?: string
  position_title?: string | null
  base_salary?: string | null
  weekly_hours?: string | null
}

/** What was in force on a date -- and which document set each field. */
export interface Clauses {
  on: string
  position_title: string
  base_salary: string
  weekly_hours: string
  set_by: Record<string, string>
}

export interface TimesheetLine {
  contract_id: string
  contract_number: string
  employee_name: string
  hours_worked: string
  night_hours: string
  holiday_hours: string
  days_present: number
}

export interface TimesheetMonth {
  id: string
  year: number
  month: number
  norm_hours: string
  status: 'open' | 'closed'
  lines?: TimesheetLine[]
}

export interface TimesheetDay {
  work_date: string
  hours_worked: string
  night_hours: string
  holiday_hours: string
}

const base = (companyId: string) => `/api/v1/payroll/companies/${companyId}`

export function listEmployees(companyId: string, q?: string): Promise<Employee[]> {
  const query = q ? `?q=${encodeURIComponent(q)}` : ''
  return request<Employee[]>(`${base(companyId)}/employees${query}`)
}

export function createEmployee(companyId: string, body: NewEmployee): Promise<Employee> {
  return request<Employee>(`${base(companyId)}/employees`, { method: 'POST', body })
}

export function listRelationshipTypes(): Promise<RelationshipType[]> {
  return request<RelationshipType[]>('/api/v1/payroll/relationship-types')
}

export function listContracts(companyId: string, includeEnded = false): Promise<Contract[]> {
  const query = includeEnded ? '?include_ended=true' : ''
  return request<Contract[]>(`${base(companyId)}/contracts${query}`)
}

export function createContract(companyId: string, body: NewContract): Promise<Contract> {
  return request<Contract>(`${base(companyId)}/contracts`, { method: 'POST', body })
}

export function getContract(contractId: string): Promise<Contract> {
  return request<Contract>(`/api/v1/payroll/contracts/${contractId}`)
}

export function addAmendment(contractId: string, body: NewAmendment): Promise<Contract> {
  return request<Contract>(`/api/v1/payroll/contracts/${contractId}/amendments`, {
    method: 'POST',
    body,
  })
}

export function endContract(
  contractId: string,
  body: { ended_on: string; order_number: string; order_date: string },
): Promise<Contract> {
  return request<Contract>(`/api/v1/payroll/contracts/${contractId}/termination`, {
    method: 'POST',
    body,
  })
}

export function clausesOn(contractId: string, on: string): Promise<Clauses> {
  return request<Clauses>(`/api/v1/payroll/contracts/${contractId}/clauses?on=${on}`)
}

export function listTimesheets(companyId: string): Promise<TimesheetMonth[]> {
  return request<TimesheetMonth[]>(`${base(companyId)}/timesheets`)
}

export function openTimesheet(
  companyId: string,
  body: { year: number; month: number; norm_hours: string },
): Promise<TimesheetMonth> {
  return request<TimesheetMonth>(`${base(companyId)}/timesheets`, { method: 'POST', body })
}

export function getTimesheet(timesheetId: string): Promise<TimesheetMonth> {
  return request<TimesheetMonth>(`/api/v1/payroll/timesheets/${timesheetId}`)
}

export function listDays(timesheetId: string, contractId: string): Promise<TimesheetDay[]> {
  return request<TimesheetDay[]>(
    `/api/v1/payroll/timesheets/${timesheetId}/contracts/${contractId}/days`,
  )
}

export function setDays(
  timesheetId: string,
  contractId: string,
  days: TimesheetDay[],
): Promise<TimesheetMonth> {
  return request<TimesheetMonth>(
    `/api/v1/payroll/timesheets/${timesheetId}/contracts/${contractId}/days`,
    { method: 'PUT', body: { days } },
  )
}

export function closeTimesheet(timesheetId: string): Promise<TimesheetMonth> {
  return request<TimesheetMonth>(`/api/v1/payroll/timesheets/${timesheetId}/closing`, {
    method: 'POST',
  })
}

/**
 * Exemptions -- an application with an effective date, never a checkbox.
 *
 * Point 18 of the regulation approved by HG 697/2014 grants and cancels them
 * from the month *following* the one the application was filed in, so what the
 * client posts is a filing date and the server derives the rest. The effective
 * date is asked for (`exemptionEffectiveDate`) rather than computed here: a
 * second implementation of the rule drifts the first time only one is edited.
 */

export interface Dependent {
  id: string
  last_name: string
  first_name: string
  idnp: string | null
  identity_document_type: string | null
  identity_document_number: string | null
}

export interface Entitlement {
  id: string
  code: string
  dependent_id: string | null
  dependent_name: string | null
  valid_from: string
  valid_to: string | null
  granted_by_filed_on: string | null
}

export interface Application {
  id: string
  employee_id: string
  filed_on: string
  effective_from: string
  declared_sole_workplace: boolean
  note: string
  granted: Entitlement[]
}

export function listDependents(employeeId: string): Promise<Dependent[]> {
  return request<Dependent[]>(`/api/v1/payroll/employees/${employeeId}/dependents`)
}

export function addDependent(
  employeeId: string,
  body: {
    last_name: string
    first_name: string
    idnp?: string | null
    identity_document_type?: string | null
    identity_document_number?: string | null
  },
): Promise<{ id: string }> {
  return request<{ id: string }>(`/api/v1/payroll/employees/${employeeId}/dependents`, {
    method: 'POST',
    body,
  })
}

/** Without `on`, the whole history. With it, what was in force that day. */
export function listExemptions(employeeId: string, on?: string): Promise<Entitlement[]> {
  const query = on ? `?on=${on}` : ''
  return request<Entitlement[]>(`/api/v1/payroll/employees/${employeeId}/exemptions${query}`)
}

export function fileExemptionApplication(
  employeeId: string,
  body: {
    filed_on: string
    declared_sole_workplace: boolean
    note?: string
    grants: { code: string; dependent_id?: string | null }[]
  },
): Promise<Application> {
  return request<Application>(`/api/v1/payroll/employees/${employeeId}/exemptions`, {
    method: 'POST',
    body,
  })
}

export function withdrawExemptions(
  employeeId: string,
  body: { filed_on: string; entitlement_ids: string[]; note?: string },
): Promise<Application> {
  return request<Application>(
    `/api/v1/payroll/employees/${employeeId}/exemptions/withdrawal`,
    { method: 'POST', body },
  )
}

export function exemptionEffectiveDate(
  filedOn: string,
): Promise<{ filed_on: string; effective_from: string }> {
  return request<{ filed_on: string; effective_from: string }>(
    `/api/v1/payroll/exemption-effective-date?filed_on=${filedOn}`,
  )
}

/**
 * The monthly run -- calculate, read the register, approve, take a payslip.
 *
 * **A line can have no amount**, and the screen shows the reason rather than a
 * zero: a rate whose margin was never established applies on no date, and *a
 * rate that is missing is not a rate of zero*. Approval is refused while any line
 * is in that state, so nothing incomplete becomes a declared fact.
 */

export interface RunComponent {
  component_key: string
  nature: 'salary_accrual' | 'employer_charge' | 'employee_withholding'
  amount: string | null
  basis: string | null
  rate: string | null
  parameter_key: string | null
  unresolved_reason: string | null
}

export interface RunLine {
  employee_id: string
  employee_name: string
  contract_number: string
  components: RunComponent[]
  gross: string
  withheld: string
  employer_charges: string
  net: string | null
  complete: boolean
}

export interface PayrollRun {
  id: string
  year: number
  month: number
  accrual_date: string
  status: 'draft' | 'approved'
  lines?: RunLine[]
  totals?: { gross: string; withheld: string; employer_charges: string; net: string }
  unresolved?: number
  complete?: boolean
}

export interface PayslipComponent {
  component_key: string
  label: string
  nature: string
  amount: string | null
  amount_ro: string | null
  basis_ro: string | null
  rate: string | null
  unresolved_reason: string | null
}

export interface Payslip {
  title: string
  period: string
  accrual_date_ro: string
  employee_name: string
  idnp: string | null
  position_title: string
  contract_number: string
  components: PayslipComponent[]
  exemptions: { code: string; label: string; dependent_name: string | null }[]
  gross_ro: string
  withheld_ro: string
  employer_charges_ro: string
  net_ro: string | null
  complete: boolean
}

export function listRuns(companyId: string): Promise<PayrollRun[]> {
  return request<PayrollRun[]>(`${base(companyId)}/runs`)
}

export function createRun(
  companyId: string,
  body: { year: number; month: number; accrual_date: string },
): Promise<PayrollRun> {
  return request<PayrollRun>(`${base(companyId)}/runs`, { method: 'POST', body })
}

export function getRun(runId: string): Promise<PayrollRun> {
  return request<PayrollRun>(`/api/v1/payroll/runs/${runId}`)
}

export function recomputeRun(runId: string): Promise<PayrollRun> {
  return request<PayrollRun>(`/api/v1/payroll/runs/${runId}/recomputation`, { method: 'POST' })
}

export function approveRun(runId: string): Promise<PayrollRun> {
  return request<PayrollRun>(`/api/v1/payroll/runs/${runId}/approval`, { method: 'POST' })
}

export function getPayslip(runId: string, employeeId: string): Promise<Payslip> {
  return request<Payslip>(`/api/v1/payroll/runs/${runId}/payslips/${employeeId}`)
}

/**
 * The unified monthly return -- IPC.
 *
 * **One entity, three sections** (art. 5 para (1) of Law 489/1999): the nominal
 * record and the contribution calculation are parts of the return, not reports
 * of their own.
 *
 * **Versions, never overwrites** (art. 188): a correction is a new version that
 * names the one it replaces. Both stay readable.
 *
 * **The form itself is not rendered here.** Annex 1 of Ordinul MF nr. 94/2020 is
 * not in the repository, so what the screen shows is the register the form reads
 * from: the header, the totals and the nominal rows, as stored.
 */

export interface IpcTotal {
  income_source_code: string
  cas_tariff_code: string
  income_paid: string
  income_tax_withheld: string
  health_insurance_withheld: string
  social_contribution: string
}

export interface IpcNominal {
  line_number: number
  person_id: string
  name: string
  idnp: string | null
  personal_insurance_code: string | null
  work_period_start: string
  work_period_end: string
  insured_category_code: string | null
  tariff_rate: string | null
  insured_income: string
  contribution: string
}

export interface IpcDeclaration {
  id: string
  year: number
  month: number
  version_number: number
  corrects_id: string | null
  status: 'draft' | 'submitted'
  due_on: string
  submitted_on: string | null
  header?: { fiscal_code: string; cuatm_code: string | null; caem_code: string | null }
  totals?: IpcTotal[]
  nominal?: IpcNominal[]
}

/** `T1`, both directions: charged and not declared, declared without a charge. */
export interface IpcReconciliation {
  agrees: boolean
  charged_count: number
  declared_count: number
  missing: string[]
  extra: string[]
}

export function listIpcDeclarations(companyId: string): Promise<IpcDeclaration[]> {
  return request<IpcDeclaration[]>(`/api/v1/tax/ipc/companies/${companyId}`)
}

export function generateIpc(
  companyId: string,
  body: { year: number; month: number },
): Promise<IpcDeclaration> {
  return request<IpcDeclaration>(`/api/v1/tax/ipc/companies/${companyId}`, {
    method: 'POST',
    body,
  })
}

export function getIpcDeclaration(declarationId: string): Promise<IpcDeclaration> {
  return request<IpcDeclaration>(`/api/v1/tax/ipc/${declarationId}`)
}

export function correctIpc(declarationId: string): Promise<IpcDeclaration> {
  return request<IpcDeclaration>(`/api/v1/tax/ipc/${declarationId}/correction`, {
    method: 'POST',
  })
}

export function submitIpc(
  declarationId: string,
  submittedOn: string,
): Promise<IpcDeclaration> {
  return request<IpcDeclaration>(`/api/v1/tax/ipc/${declarationId}/submission`, {
    method: 'POST',
    body: { submitted_on: submittedOn },
  })
}

export function reconcileIpc(declarationId: string): Promise<IpcReconciliation> {
  return request<IpcReconciliation>(`/api/v1/tax/ipc/${declarationId}/reconciliation`)
}
