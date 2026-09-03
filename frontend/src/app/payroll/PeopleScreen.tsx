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
import {
  createEmployee,
  listEmployees,
  setEmployeeBankAccount,
  type Employee,
} from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input, Select } from '@/shared/ui'

export function PeopleScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const [ibanFor, setIbanFor] = useState<Employee | null>(null)

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
    {
      // Where the net goes; the bank's payment list reads it. The cell is the
      // door to setting it, because the account is the one thing on the record
      // that changes during employment.
      key: 'iban',
      header: t.payroll.iban,
      cell: (person) => (
        <button
          type="button"
          className="font-mono text-accent"
          title={t.payroll.ibanHint}
          onClick={() => setIbanFor(ibanFor?.id === person.id ? null : person)}
        >
          {person.bank_iban ?? '—'}
        </button>
      ),
      width: '16rem',
    },
    {
      // A door, not only a route. An endpoint reachable by typing its address is
      // an endpoint nobody reaches -- the class that produced four cases in a day.
      key: 'exemptions',
      header: t.payroll.exemptions,
      cell: (person) => (
        <Link
          to={`/companii/${companyId}/angajati/${person.id}/scutiri`}
          className="text-accent"
        >
          {t.payroll.exemptions}
        </Link>
      ),
      width: '9rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="type-display-2 text-heading">{t.payroll.people}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/contracte`} className="text-sm text-accent">
            {t.payroll.contracts}
          </Link>
          <Link to={`/companii/${companyId}/pontaj`} className="text-sm text-accent">
            {t.payroll.timesheets}
          </Link>
          <Link to={`/companii/${companyId}/salarii`} className="text-sm text-accent">
            {t.payroll.runs}
          </Link>
          <form
            className="flex items-center gap-2"
            onSubmit={(event: FormEvent) => {
              event.preventDefault()
              setQuery(search.trim())
            }}
          >
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t.payroll.searchPeople}
              aria-label={t.payroll.searchPeople}
              className="w-72"
            />
            <Button variant="secondary" type="submit">
              {t.payroll.inForceShow}
            </Button>
          </form>
          <Button variant="primary" type="button" onClick={() => setAdding((open) => !open)}>
            {adding ? t.companies.cancel : t.payroll.addPerson}
          </Button>
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

      {ibanFor && (
        <BankAccountForm
          key={ibanFor.id}
          person={ibanFor}
          onSaved={async () => {
            setIbanFor(null)
            await refresh()
          }}
        />
      )}

      {people.isError && <Failure error={people.error} />}
      {people.data && (
        <Card padding="none">
          <DataGrid
            columns={columns}
            rows={people.data}
            rowKey={(person) => person.id}
            emptyMessage={t.payroll.noPeople}
          />
        </Card>
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
  const [iban, setIban] = useState('')

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
        bank_iban: iban.trim() || null,
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
      <Field label={t.payroll.lastName}>
        <Input
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          className="w-48"
        />
      </Field>
      <Field label={t.payroll.firstName}>
        <Input
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          className="w-48"
        />
      </Field>
      <Field label={t.payroll.residency}>
        <Select
          value={residency}
          onChange={(event) =>
            setResidency(event.target.value === 'resident' ? 'resident' : 'non_resident')
          }
          className="w-48"
        >
          <option value="resident">{t.payroll.resident}</option>
          <option value="non_resident">{t.payroll.nonResident}</option>
        </Select>
      </Field>

      {byIdnp ? (
        <Field label={t.payroll.idnp}>
          <Input
            value={idnp}
            onChange={(event) => setIdnp(event.target.value)}
            maxLength={13}
            title={t.payroll.idnpHint}
            className="w-40 font-mono"
          />
        </Field>
      ) : (
        <>
          <Field label={t.payroll.documentType}>
            <Input
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value)}
              title={t.payroll.documentHint}
              className="w-40"
            />
          </Field>
          <Field label={t.payroll.documentNumber}>
            <Input
              value={documentNumber}
              onChange={(event) => setDocumentNumber(event.target.value)}
              className="w-40 font-mono"
            />
          </Field>
        </>
      )}

      <Field label={t.payroll.insuranceCode}>
        <Input
          value={insuranceCode}
          onChange={(event) => setInsuranceCode(event.target.value)}
          className="w-40 font-mono"
        />
      </Field>
      <Field label={t.payroll.iban}>
        <Input
          value={iban}
          onChange={(event) => setIban(event.target.value)}
          title={t.payroll.ibanHint}
          className="w-64 font-mono"
        />
      </Field>

      <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
        {t.payroll.createPerson}
      </Button>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}

/** The account of one person, set or cleared. The server verifies the check digits. */
function BankAccountForm({
  person,
  onSaved,
}: {
  person: Employee
  onSaved: () => Promise<void> | void
}) {
  const [iban, setIban] = useState(person.bank_iban ?? '')

  const save = useMutation({
    mutationFn: () => setEmployeeBankAccount(person.id, iban.trim() || null),
    onSuccess: onSaved,
  })

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        save.mutate()
      }}
    >
      <p className="text-sm">
        {person.last_name} {person.first_name}
      </p>
      <Field label={t.payroll.iban}>
        <Input
          value={iban}
          onChange={(event) => setIban(event.target.value)}
          title={t.payroll.ibanHint}
          className="w-64 font-mono"
        />
      </Field>
      <Button variant="primary" type="submit" disabled={save.isPending}>
        {t.payroll.saveIban}
      </Button>
      {save.isError && <Failure error={save.error} />}
    </form>
  )
}
