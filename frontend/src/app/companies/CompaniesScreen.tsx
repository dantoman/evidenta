/**
 * The companies this session may reach -- and the way into each one's books.
 *
 * It is the application's index because the accounting routes are company-scoped:
 * the tenant is the host the browser is already on (C8), but a holding has
 * several companies and every accounting question starts by saying which. The
 * screen it replaced was a formatting demonstration, which had answered that
 * question by not asking it.
 *
 * **The server does no filtering here, and must not** (C3): the policy on the
 * table decides what comes back. A `.filter()` in the view -- or a guard here --
 * would create the impression of safety that RLS provides in fact.
 *
 * `legal_name` is what appears, never an internal name (C39).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import { t } from '@/locales'
import {
  createCompany,
  listCompanies,
  openFiscalYear,
  type Company,
} from '@/shared/api/companies'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'

function chartPath(company: Company): string {
  return `/companii/${company.id}/plan-de-conturi`
}

const columns: Column<Company>[] = [
  {
    key: 'legal_name',
    header: t.companies.legalName,
    // A link, not only a clickable row: a row click is reachable with a mouse
    // and with nothing else. The row keeps its click for the mouse, the link
    // carries the keyboard.
    cell: (company) => (
      <Link to={chartPath(company)} className="text-accent">
        {company.legal_name}
      </Link>
    ),
  },
  {
    key: 'idno',
    // A code, so a monospaced face: IDNO is compared digit by digit, and codes
    // collate as `C` in the database for the same reason (C34).
    header: t.companies.idno,
    cell: (company) => <span className="font-mono">{company.idno}</span>,
    width: '12rem',
  },
  {
    key: 'functional_currency',
    header: t.companies.currency,
    cell: (company) => company.functional_currency,
    width: '12rem',
  },
]

export function CompaniesScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })

  const create = useMutation({
    mutationFn: async (form: { idno: string; legal_name: string; currency: string }) => {
      const company = await createCompany({
        idno: form.idno,
        legal_name: form.legal_name,
        functional_currency: form.currency,
      })
      // The exercise, as a second call. Opening one belongs to `accounting` and
      // creating a company to `platform`, which does not import it -- so the
      // server has two endpoints and the client makes two calls. A company
      // without an exercise cannot be posted into, so this is not optional
      // politeness: it is the other half of "created".
      await openFiscalYear(company.id)
      return company
    },
    onSuccess: async (company) => {
      await queryClient.invalidateQueries({ queryKey: ['companies'] })
      setAdding(false)
      void navigate(chartPath(company))
    },
  })

  if (companies.isPending) {
    return <p className="text-sm text-ink-muted">{t.app.loading}</p>
  }

  if (companies.isError) {
    return <Failure error={companies.error} />
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <h1 className="text-base font-semibold">{t.companies.title}</h1>
        <button type="button" onClick={() => setAdding((open) => !open)} className={BUTTON}>
          {adding ? t.companies.cancel : t.companies.add}
        </button>
      </header>

      {adding && <NewCompanyForm pending={create.isPending} onSubmit={create.mutate} />}
      {create.isError && <Failure error={create.error} />}

      <DataGrid
        columns={columns}
        rows={companies.data}
        rowKey={(company) => company.id}
        emptyMessage={t.companies.empty}
        onRowClick={(company) => void navigate(chartPath(company))}
      />
    </section>
  )
}

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

/**
 * Three fields, which is what the server needs to create a company.
 *
 * The IDNO is checked here for shape only -- thirteen digits -- and the server
 * checks the same thing again. It is not a checksum: the checksum rule is not in
 * any text this repository holds, and an invented one would refuse real
 * companies.
 */
function NewCompanyForm({
  pending,
  onSubmit,
}: {
  pending: boolean
  onSubmit: (form: { idno: string; legal_name: string; currency: string }) => void
}) {
  const [legalName, setLegalName] = useState('')
  const [idno, setIdno] = useState('')
  const [currency, setCurrency] = useState('MDL')

  const complete = /^\d{13}$/.test(idno) && legalName.trim() !== ''

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        onSubmit({ idno, legal_name: legalName.trim(), currency })
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.companies.legalName}</span>
        <input
          value={legalName}
          onChange={(event) => setLegalName(event.target.value)}
          maxLength={255}
          className={`${FIELD} w-96`}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.companies.idno}</span>
        <input
          value={idno}
          onChange={(event) => setIdno(event.target.value.replace(/\D/g, ''))}
          maxLength={13}
          inputMode="numeric"
          placeholder={t.companies.idnoHint}
          className={`${FIELD} w-48 font-mono`}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.companies.currency}</span>
        <input
          value={currency}
          onChange={(event) => setCurrency(event.target.value.toUpperCase().slice(0, 3))}
          className={`${FIELD} w-24 font-mono`}
          title={t.companies.currencyHint}
        />
      </label>
      <button type="submit" disabled={!complete || pending} className={BUTTON}>
        {pending ? t.companies.creating : t.companies.create}
      </button>
    </form>
  )
}
