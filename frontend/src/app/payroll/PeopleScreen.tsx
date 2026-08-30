/**
 * The people one company employs.
 *
 * **Under a company, unlike partners**, and the difference is not a routing
 * preference: the legal employer is the company. It withholds, it files, it
 * answers for it -- and a person working at two companies of the same workspace
 * has two records, two withholdings and two declarations.
 *
 * **Exactly one identity, and the form says which.** Residents by IDNP, everyone
 * else by an identity document. The row for which the exception is made is
 * precisely the row that would otherwise carry no natural key, so the second
 * field is required rather than optional -- and the server refuses the pair
 * anyway.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { createEmployee, listEmployees, type Employee } from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

export function PeopleScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)

  const people = useQuery({
    queryKey: ['payroll-people', companyId, query],
    queryFn: () => listEmployees(companyId, query || undefined),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['payroll-people'] })

  const columns: Column<Employee>[] = [
    {
      key: 'name',
      header: t.payroll.lastName,
      cell: (person) => `${person.last_name} ${person.first_name}`,
    },
    {
      key: 'idnp',
      header: t.payroll.idnp,
      // A code, so a monospaced face: it is compared digit by digit.
      cell: (person) => (
        <span className="font-mono">
          {person.idnp ??
            `${person.identity_document_type ?? ''} ${person.identity_document_number ?? ''}`}
        </span>
      ),
      width: '14rem',
    },
    {
      key: 'residency',
      header: t.payroll.residency,
      cell: (person) =>
        person.tax_residency === 'resident' ? t.payroll.resident : t.payroll.nonResident,
      width: '10rem',
    },
    {
      key: 'insurance',
      header: t.payroll.insuranceCode,
      cell: (person) => <span className="font-mono">{person.social_insurance_code ?? ''}</span>,
      width: '12rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-semibold">{t.payroll.people}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/contracte`} className="text-sm text-accent">
            {t.payroll.contracts}
          </Link>
          <Link to={`/companii/${companyId}/pontaj`} className="text-sm text-accent">
            {t.payroll.timesheets}
          </Link>
          <form
            className="flex items-center gap-2"
            onSubmit={(event: FormEvent) => {
              event.preventDefault()
              setQuery(search.trim())
            }}
          >
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t.payroll.searchPeople}
              aria-label={t.payroll.searchPeople}
              className={`${FIELD} w-72`}
            />
            <button type="submit" className={BUTTON}>
              {t.payroll.inForceShow}
            </button>
          </form>
          <button type="button" onClick={() => setAdding((open) => !open)} className={BUTTON}>
            {adding ? t.companies.cancel : t.payroll.addPerson}
          </button>
        </div>
      </header>

      {adding && (
        <NewPersonForm
          companyId={companyId}
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}

      {people.isError && <Failure error={people.error} />}
      {people.data && (
        <DataGrid
          columns={columns}
          rows={people.data}
          rowKey={(person) => person.id}
          emptyMessage={t.payroll.noPeople}
        />
      )}
    </section>
  )
}

function NewPersonForm({
  companyId,
  onCreated,
}: {
  companyId: string
  onCreated: () => Promise<void> | void
}) {
  const [lastName, setLastName] = useState('')
  const [firstName, setFirstName] = useState('')
  const [residency, setResidency] = useState<'resident' | 'non_resident'>('resident')
  const [idnp, setIdnp] = useState('')
  const [documentType, setDocumentType] = useState('')
  const [documentNumber, setDocumentNumber] = useState('')
  const [insuranceCode, setInsuranceCode] = useState('')

  // Which identity the form sends follows the residency, because that is the
  // question a person can answer -- not "which column am I filling in".
  const byIdnp = residency === 'resident'

  const create = useMutation({
    mutationFn: () =>
      createEmployee(companyId, {
        last_name: lastName.trim(),
        first_name: firstName.trim(),
        tax_residency: residency,
        idnp: byIdnp ? idnp.trim() || null : null,
        identity_document_type: byIdnp ? null : documentType.trim() || null,
        identity_document_number: byIdnp ? null : documentNumber.trim() || null,
        social_insurance_code: insuranceCode.trim() || null,
      }),
    onSuccess: onCreated,
  })

  const complete =
    lastName.trim() !== '' &&
    firstName.trim() !== '' &&
    (byIdnp ? idnp.trim() !== '' : documentType.trim() !== '' && documentNumber.trim() !== '')

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.lastName}</span>
        <input
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          className={`${FIELD} w-48`}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.firstName}</span>
        <input
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          className={`${FIELD} w-48`}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.residency}</span>
        <select
          value={residency}
          onChange={(event) =>
            setResidency(event.target.value === 'resident' ? 'resident' : 'non_resident')
          }
          className={`${FIELD} w-48`}
        >
          <option value="resident">{t.payroll.resident}</option>
          <option value="non_resident">{t.payroll.nonResident}</option>
        </select>
      </label>

      {byIdnp ? (
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-muted">{t.payroll.idnp}</span>
          <input
            value={idnp}
            onChange={(event) => setIdnp(event.target.value)}
            maxLength={13}
            title={t.payroll.idnpHint}
            className={`${FIELD} w-40 font-mono`}
          />
        </label>
      ) : (
        <>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.payroll.documentType}</span>
            <input
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value)}
              title={t.payroll.documentHint}
              className={`${FIELD} w-40`}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.payroll.documentNumber}</span>
            <input
              value={documentNumber}
              onChange={(event) => setDocumentNumber(event.target.value)}
              className={`${FIELD} w-40 font-mono`}
            />
          </label>
        </>
      )}

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.insuranceCode}</span>
        <input
          value={insuranceCode}
          onChange={(event) => setInsuranceCode(event.target.value)}
          className={`${FIELD} w-40 font-mono`}
        />
      </label>

      <button type="submit" disabled={!complete || create.isPending} className={BUTTON}>
        {t.payroll.createPerson}
      </button>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}
