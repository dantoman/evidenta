/**
 * Work relationships: the list, the series of amendments, and the question a
 * column could not answer.
 *
 * **The contract is the head of a series, not a state** (ADR-067). Any change to
 * any clause of art. 49 para (1) requires a signed amendment, so the screen never
 * offers "edit the salary": it offers an amendment, and shows the series. What
 * was in force on a chosen date is asked of the server, which walks the series --
 * and the answer says *which document* set each field, because "9000 in March" is
 * not defensible without it.
 *
 * **The form of the relationship comes from the server** (ADR-071). Three values,
 * the ones point 1.1 of annex 1 to Law 489/1999 distinguishes; a fourth in a
 * dropdown here would be a vocabulary the acts do not have.
 *
 * **The order is asked for, not derived.** The IRM19 deadline runs from the date
 * on the employer's order, which is neither the signing date nor the day work
 * starts -- so it is a field, and terminating without one is refused.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import {
  addAmendment,
  clausesOn,
  createContract,
  setContractCostDestination,
  endContract,
  getContract,
  listContracts,
  listEmployees,
  listRelationshipTypes,
  type Contract,
} from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount } from '@/shared/format'
import { Button, Card, Field, Input, Select } from '@/shared/ui'

/** The labels for the three codes. The codes themselves come from the server. */
const TYPE_LABELS: Record<string, string> = {
  employment_contract: t.payroll.employmentContract,
  service_relationship: t.payroll.serviceRelationship,
  civil_contract: t.payroll.civilContract,
}

/** The employer's points of annex 1. The server refuses anything else. */
const CAS_POINTS = ['1.1', '1.2', '1.4', '1.5']

export function ContractsScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [includeEnded, setIncludeEnded] = useState(false)
  const [adding, setAdding] = useState(false)
  const [openContract, setOpenContract] = useState<string | null>(null)

  const contracts = useQuery({
    queryKey: ['payroll-contracts', companyId, includeEnded],
    queryFn: () => listContracts(companyId, includeEnded),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['payroll-contracts'] })

  const columns: Column<Contract>[] = [
    { key: 'number', header: t.payroll.contractNumber, cell: (row) => row.contract_number },
    { key: 'employee', header: t.payroll.people, cell: (row) => row.employee_name },
    {
      key: 'type',
      header: t.payroll.relationshipType,
      cell: (row) => TYPE_LABELS[row.relationship_type] ?? row.relationship_type,
      width: '18rem',
    },
    { key: 'position', header: t.payroll.position, cell: (row) => row.position_title },
    {
      key: 'costDestination',
      header: t.payroll.costDestination,
      cell: (row) => <CostDestinationCell contract={row} onChanged={refresh} />,
    },
    {
      key: 'from',
      header: t.payroll.effectiveFrom,
      cell: (row) => row.effective_from,
      width: '9rem',
    },
    {
      key: 'ended',
      header: t.payroll.endedOn,
      cell: (row) => row.ended_on ?? t.common.none,
      width: '9rem',
    },
    {
      key: 'open',
      header: '',
      cell: (row) => (
        <button
          type="button"
          className="text-accent"
          onClick={() => setOpenContract(openContract === row.id ? null : row.id)}
        >
          {t.payroll.amendments}
        </button>
      ),
      width: '10rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="type-display-2 text-heading">{t.payroll.contracts}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/angajati`} className="text-sm text-accent">
            {t.payroll.people}
          </Link>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeEnded}
              onChange={(event) => setIncludeEnded(event.target.checked)}
            />
            <span className="text-ink-muted">{t.payroll.showEnded}</span>
          </label>
          <Button variant="primary" type="button" onClick={() => setAdding((open) => !open)}>
            {adding ? t.companies.cancel : t.payroll.addContract}
          </Button>
        </div>
      </header>

      {adding && (
        <NewContractForm
          companyId={companyId}
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}

      {contracts.isError && <Failure error={contracts.error} />}
      {contracts.data && (
        <Card padding="none">
          <DataGrid
            columns={columns}
            rows={contracts.data}
            rowKey={(row) => row.id}
            emptyMessage={t.payroll.noContracts}
          />
        </Card>
      )}

      {openContract && <ContractSeries contractId={openContract} onChanged={refresh} />}
    </section>
  )
}

function NewContractForm({
  companyId,
  onCreated,
}: {
  companyId: string
  onCreated: () => Promise<void> | void
}) {
  const people = useQuery({
    queryKey: ['payroll-people', companyId, ''],
    queryFn: () => listEmployees(companyId),
  })
  const types = useQuery({
    queryKey: ['payroll-relationship-types'],
    queryFn: listRelationshipTypes,
  })

  const [employeeId, setEmployeeId] = useState('')
  const [relationshipType, setRelationshipType] = useState('employment_contract')
  const [number, setNumber] = useState('')
  const [signedOn, setSignedOn] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [orderNumber, setOrderNumber] = useState('')
  const [orderDate, setOrderDate] = useState('')
  const [position, setPosition] = useState('')
  const [salary, setSalary] = useState('')
  const [hours, setHours] = useState('40')
  const [casPoint, setCasPoint] = useState('1.1')
  // No default that could be wrong silently: 29% budgetary against 24% private
  // is chosen by this box, and the server refuses the payload without it.
  const [budgetFunded, setBudgetFunded] = useState(false)
  // Same rule: the destination names the expense account, so the form asks for
  // it and sends nothing until it is chosen.
  const [costDestination, setCostDestination] = useState('')

  const create = useMutation({
    mutationFn: () =>
      createContract(companyId, {
        employee_id: employeeId,
        relationship_type: relationshipType,
        contract_number: number.trim(),
        signed_on: signedOn,
        effective_from: effectiveFrom,
        hire_order_number: orderNumber.trim(),
        hire_order_date: orderDate,
        position_title: position.trim(),
        base_salary: salary,
        weekly_hours: hours,
        cas_payer_point: casPoint,
        budget_funded_employer: budgetFunded,
        cost_destination: costDestination,
      }),
    onSuccess: onCreated,
  })

  const complete =
    employeeId !== '' &&
    number.trim() !== '' &&
    signedOn !== '' &&
    effectiveFrom !== '' &&
    orderNumber.trim() !== '' &&
    orderDate !== '' &&
    position.trim() !== '' &&
    salary !== '' &&
    costDestination !== ''

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <Field label={t.payroll.people}>
        <Select
          value={employeeId}
          onChange={(event) => setEmployeeId(event.target.value)}
          className="w-56"
        >
          <option value="">{t.common.none}</option>
          {(people.data ?? []).map((person) => (
            <option key={person.id} value={person.id}>
              {person.last_name} {person.first_name}
            </option>
          ))}
        </Select>
      </Field>

      <Field label={t.payroll.relationshipType}>
        <Select
          value={relationshipType}
          onChange={(event) => setRelationshipType(event.target.value)}
          className="w-72"
        >
          {(types.data ?? []).map((type) => (
            <option key={type.code} value={type.code}>
              {TYPE_LABELS[type.code] ?? type.code}
            </option>
          ))}
        </Select>
      </Field>

      <Field label={t.payroll.contractNumber}>
        <Input
          value={number}
          onChange={(event) => setNumber(event.target.value)}
          className="w-32 font-mono"
        />
      </Field>

      <Field label={t.payroll.signedOn}>
        <Input
          type="date"
          value={signedOn}
          onChange={(event) => setSignedOn(event.target.value)}
          className="w-40"
        />
      </Field>

      <Field label={t.payroll.effectiveFrom}>
        <Input
          type="date"
          value={effectiveFrom}
          onChange={(event) => setEffectiveFrom(event.target.value)}
          className="w-40"
        />
      </Field>

      <Field label={t.payroll.orderNumber}>
        <Input
          value={orderNumber}
          onChange={(event) => setOrderNumber(event.target.value)}
          className="w-28 font-mono"
        />
      </Field>

      <Field label={t.payroll.orderDate}>
        <Input
          type="date"
          value={orderDate}
          onChange={(event) => setOrderDate(event.target.value)}
          className="w-40"
        />
      </Field>

      <Field label={t.payroll.position}>
        <Input
          value={position}
          onChange={(event) => setPosition(event.target.value)}
          className="w-48"
        />
      </Field>

      <Field label={t.payroll.salary}>
        <Input
          inputMode="decimal"
          value={salary}
          onChange={(event) => setSalary(event.target.value)}
          className="w-32 text-right tabular-nums"
        />
      </Field>

      <Field label={t.payroll.weeklyHours}>
        <Input
          inputMode="decimal"
          value={hours}
          onChange={(event) => setHours(event.target.value)}
          className="w-24 text-right tabular-nums"
        />
      </Field>

      <Field label={t.payroll.casPoint}>
        <Select
          value={casPoint}
          onChange={(event) => setCasPoint(event.target.value)}
          title={t.payroll.casPointHint}
          className="w-24"
        >
          {CAS_POINTS.map((point) => (
            <option key={point} value={point}>
              {point}
            </option>
          ))}
        </Select>
      </Field>

      <Field label={t.payroll.costDestination}>
        <Select
          value={costDestination}
          onChange={(event) => setCostDestination(event.target.value)}
          className="w-64"
          title={t.payroll.costDestinationHint}
        >
          <option value="">{t.common.none}</option>
          {Object.entries(t.payroll.costDestinations).map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </Select>
      </Field>

      <label className="flex items-center gap-2 text-sm" title={t.payroll.budgetFundedHint}>
        <input
          type="checkbox"
          checked={budgetFunded}
          onChange={(event) => setBudgetFunded(event.target.checked)}
        />
        <span className="text-ink-muted">{t.payroll.budgetFunded}</span>
      </label>

      <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
        {t.payroll.createContract}
      </Button>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}

function ContractSeries({
  contractId,
  onChanged,
}: {
  contractId: string
  onChanged: () => void
}) {
  const contract = useQuery({
    queryKey: ['payroll-contract', contractId],
    queryFn: () => getContract(contractId),
  })
  const [on, setOn] = useState('')
  const [asked, setAsked] = useState('')

  const clauses = useQuery({
    queryKey: ['payroll-clauses', contractId, asked],
    queryFn: () => clausesOn(contractId, asked),
    enabled: asked !== '',
  })

  return (
    <section className="flex flex-col gap-4 rounded border border-border bg-surface p-4">
      {contract.isError && <Failure error={contract.error} />}
      {contract.data && (
        <>
          <header className="flex flex-wrap items-end justify-between gap-4">
            <h2 className="text-sm font-semibold">
              {contract.data.contract_number} · {contract.data.employee_name}
            </h2>
            <form
              className="flex items-end gap-2"
              onSubmit={(event: FormEvent) => {
                event.preventDefault()
                setAsked(on)
              }}
            >
              <Field label={t.payroll.inForceOn}>
                <Input
                  type="date"
                  value={on}
                  onChange={(event) => setOn(event.target.value)}
                  className="w-40"
                />
              </Field>
              <Button variant="primary" type="submit" disabled={on === ''}>
                {t.payroll.inForceShow}
              </Button>
            </form>
          </header>

          {clauses.data && (
            <dl className="flex flex-wrap gap-6 text-sm">
              <div>
                <dt className="text-ink-muted">{t.payroll.position}</dt>
                <dd>
                  {clauses.data.position_title}{' '}
                  <span className="text-ink-muted">
                    ({t.payroll.setBy} {clauses.data.set_by.position_title})
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">{t.payroll.salary}</dt>
                <dd className="tabular-nums">
                  {amount(clauses.data.base_salary)}{' '}
                  <span className="text-ink-muted">
                    ({t.payroll.setBy} {clauses.data.set_by.base_salary})
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">{t.payroll.weeklyHours}</dt>
                <dd className="tabular-nums">
                  {clauses.data.weekly_hours}{' '}
                  <span className="text-ink-muted">
                    ({t.payroll.setBy} {clauses.data.set_by.weekly_hours})
                  </span>
                </dd>
              </div>
            </dl>
          )}
          {clauses.isError && <Failure error={clauses.error} />}

          <AmendmentList contract={contract.data} onChanged={onChanged} />
        </>
      )}
    </section>
  )
}

function AmendmentList({
  contract,
  onChanged,
}: {
  contract: Contract
  onChanged: () => void
}) {
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [ending, setEnding] = useState(false)

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['payroll-contract', contract.id] })
    await queryClient.invalidateQueries({ queryKey: ['payroll-clauses', contract.id] })
    onChanged()
  }

  const amendments = contract.amendments ?? []

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <h3 className="text-sm font-semibold">{t.payroll.amendments}</h3>
        <Button variant="primary" type="button" onClick={() => setAdding((open) => !open)}>
          {adding ? t.companies.cancel : t.payroll.addAmendment}
        </Button>
        {!contract.ended_on && (
          <Button variant="secondary" type="button" onClick={() => setEnding((open) => !open)}>
            {ending ? t.companies.cancel : t.payroll.endContract}
          </Button>
        )}
      </div>

      {adding && (
        <AmendmentForm
          contractId={contract.id}
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}
      {ending && (
        <TerminationForm
          contractId={contract.id}
          onEnded={async () => {
            setEnding(false)
            await refresh()
          }}
        />
      )}

      {amendments.length === 0 ? (
        <p className="text-sm text-ink-muted">{t.payroll.noAmendments}</p>
      ) : (
        <ul className="flex flex-col gap-2 text-sm">
          {amendments.map((amendment) => (
            <li key={amendment.id} className="flex flex-wrap gap-4">
              <span className="font-mono">{amendment.amendment_number}</span>
              <span className="text-ink-muted">{amendment.effective_from}</span>
              <span>
                {t.payroll.changedClause} {amendment.changed_clause}
              </span>
              {amendment.base_salary && (
                <span className="tabular-nums">{amount(amendment.base_salary)}</span>
              )}
              {amendment.position_title && <span>{amendment.position_title}</span>}
              <span className="text-ink-muted">
                {t.payroll.orderNumber} {amendment.order_number} · {amendment.order_date}
              </span>
              {amendment.note && <span className="text-ink-muted">{amendment.note}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AmendmentForm({
  contractId,
  onCreated,
}: {
  contractId: string
  onCreated: () => Promise<void> | void
}) {
  const [number, setNumber] = useState('')
  const [signedOn, setSignedOn] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [orderNumber, setOrderNumber] = useState('')
  const [orderDate, setOrderDate] = useState('')
  const [clause, setClause] = useState('')
  const [note, setNote] = useState('')
  const [salary, setSalary] = useState('')
  const [position, setPosition] = useState('')

  const create = useMutation({
    mutationFn: () =>
      addAmendment(contractId, {
        amendment_number: number.trim(),
        signed_on: signedOn,
        effective_from: effectiveFrom,
        order_number: orderNumber.trim(),
        order_date: orderDate,
        changed_clause: clause.trim(),
        note: note.trim(),
        base_salary: salary.trim() || null,
        position_title: position.trim() || null,
      }),
    onSuccess: onCreated,
  })

  const complete =
    number.trim() !== '' &&
    signedOn !== '' &&
    effectiveFrom !== '' &&
    orderNumber.trim() !== '' &&
    orderDate !== '' &&
    clause.trim() !== ''

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border p-3"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <Field label={t.payroll.amendmentNumber}>
        <Input
          value={number}
          onChange={(event) => setNumber(event.target.value)}
          className="w-24 font-mono"
        />
      </Field>
      <Field label={t.payroll.signedOn}>
        <Input
          type="date"
          value={signedOn}
          onChange={(event) => setSignedOn(event.target.value)}
          className="w-40"
        />
      </Field>
      <Field label={t.payroll.effectiveFrom}>
        <Input
          type="date"
          value={effectiveFrom}
          onChange={(event) => setEffectiveFrom(event.target.value)}
          className="w-40"
        />
      </Field>
      <Field label={t.payroll.orderNumber}>
        <Input
          value={orderNumber}
          onChange={(event) => setOrderNumber(event.target.value)}
          className="w-24 font-mono"
        />
      </Field>
      <Field label={t.payroll.orderDate}>
        <Input
          type="date"
          value={orderDate}
          onChange={(event) => setOrderDate(event.target.value)}
          className="w-40"
        />
      </Field>
      <Field label={t.payroll.changedClause}>
        <Input
          value={clause}
          onChange={(event) => setClause(event.target.value)}
          title={t.payroll.changedClauseHint}
          className="w-16 font-mono"
        />
      </Field>
      <Field label={t.payroll.salary}>
        <Input
          inputMode="decimal"
          value={salary}
          onChange={(event) => setSalary(event.target.value)}
          className="w-28 text-right tabular-nums"
        />
      </Field>
      <Field label={t.payroll.position}>
        <Input
          value={position}
          onChange={(event) => setPosition(event.target.value)}
          className="w-40"
        />
      </Field>
      <Field label={t.payroll.note}>
        <Input
          value={note}
          onChange={(event) => setNote(event.target.value)}
          className="w-56"
        />
      </Field>
      <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
        {t.payroll.createAmendment}
      </Button>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}

function TerminationForm({
  contractId,
  onEnded,
}: {
  contractId: string
  onEnded: () => Promise<void> | void
}) {
  const [endedOn, setEndedOn] = useState('')
  const [orderNumber, setOrderNumber] = useState('')
  const [orderDate, setOrderDate] = useState('')

  const end = useMutation({
    mutationFn: () =>
      endContract(contractId, {
        ended_on: endedOn,
        order_number: orderNumber.trim(),
        order_date: orderDate,
      }),
    onSuccess: onEnded,
  })

  const complete = endedOn !== '' && orderNumber.trim() !== '' && orderDate !== ''

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border p-3"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        end.mutate()
      }}
    >
      <Field label={t.payroll.endedOn}>
        <Input
          type="date"
          value={endedOn}
          onChange={(event) => setEndedOn(event.target.value)}
          className="w-40"
        />
      </Field>
      <Field label={t.payroll.terminationOrder}>
        <Input
          value={orderNumber}
          onChange={(event) => setOrderNumber(event.target.value)}
          className="w-24 font-mono"
        />
      </Field>
      <Field label={t.payroll.orderDate}>
        <Input
          type="date"
          value={orderDate}
          onChange={(event) => setOrderDate(event.target.value)}
          className="w-40"
        />
      </Field>
      <Button variant="primary" type="submit" disabled={!complete || end.isPending}>
        {t.payroll.endContract}
      </Button>
      {end.isError && <Failure error={end.error} />}
    </form>
  )
}

function CostDestinationCell({
  contract,
  onChanged,
}: {
  contract: Contract
  onChanged: () => Promise<void> | void
}) {
  // Editable in place: a contract written before the destination existed has
  // none, and a person can move from administration to production. The server
  // keeps what every posted run read.
  const set = useMutation({
    mutationFn: (value: string) => setContractCostDestination(contract.id, value),
    onSuccess: onChanged,
  })
  const labels = t.payroll.costDestinations as Record<string, string>
  return (
    <Select
      value={contract.cost_destination ?? ''}
      onChange={(event) => set.mutate(event.target.value)}
      disabled={set.isPending}
      className="w-56"
      aria-label={t.payroll.costDestination}
    >
      <option value="" disabled>
        {t.common.none}
      </option>
      {Object.entries(labels).map(([code, label]) => (
        <option key={code} value={code}>
          {label}
        </option>
      ))}
    </Select>
  )
}
