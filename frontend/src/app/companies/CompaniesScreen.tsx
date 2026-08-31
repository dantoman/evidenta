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
import { Link, useNavigate, useSearchParams } from 'react-router'

import { t } from '@/locales'
import {
  createCompany,
  listCompanies,
  openFiscalYear,
  type Company,
} from '@/shared/api/companies'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input, PageHeader } from '@/shared/ui'

function cardPath(company: Company): string {
  return `/companii/${company.id}`
}

function chartPath(company: Company): string {
  return `/companii/${company.id}/plan-de-conturi`
}

/**
 * The columns, built rather than declared -- kept a function so a column that
 * needs data can take it. Nothing needs any today: the account-holder mark went
 * with ADR-085, where the workspace stopped having a company of its own.
 *
 * The list keeps the server's order -- by legal name -- and only marks the
 * holder. The switcher sorts it to the top instead, and the difference is
 * deliberate: a list that reorders itself is a list whose second row means
 * something else tomorrow, while a switcher is a place you reach for one known
 * thing.
 */
function buildColumns(): Column<Company>[] {
  return [
  {
    key: 'legal_name',
    header: t.companies.legalName,
    // A link, not only a clickable row: a row click is reachable with a mouse
    // and with nothing else. The row keeps its click for the mouse, the link
    // carries the keyboard.
    //
    // Both now open the company's card rather than its chart of accounts
    // (ADR-083). The card carries the way onward, which it has to: without a
    // company selected the sidebar shows no accounting sections, so this list is
    // still the only door in.
    cell: (company) => (
      <Link to={cardPath(company)} className="text-accent">
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
  {
    // Payroll hangs off the company because the legal employer is the company.
    // A link here rather than a header entry for the same reason the chart has
    // one: the header does not know which company, and a screen reachable only
    // by typing its address is a screen nobody reaches.
    key: 'payroll',
    header: t.payroll.people,
    cell: (company) => (
      <Link to={`/companii/${company.id}/angajati`} className="text-accent">
        {t.payroll.people}
      </Link>
    ),
    width: '10rem',
  },
  ]
}

export function CompaniesScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  // Arrived from the workspace screen's offer (ADR-075): the form opens with the
  // account holder's own name and IDNO filled in. A query parameter rather than
  // router state, because state does not survive a reload and this form is one a
  // person may well come back to.
  // `?nou=1` opens the form straight away. It used to be `?titular=1`, filled
  // from the account holder -- an offer ADR-085 removed: the workspace is held by
  // a person, so there is no "holder's company" to pre-fill from.
  const [adding, setAdding] = useState(params.get('nou') === '1')
  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })
  const columns = buildColumns()

  const create = useMutation({
    mutationFn: async (form: {
      idno: string
      legal_name: string
      currency: string
      cuatm_code: string | null
      caem_code: string | null
    }) => {
      const company = await createCompany({
        idno: form.idno,
        legal_name: form.legal_name,
        functional_currency: form.currency,
        cuatm_code: form.cuatm_code,
        caem_code: form.caem_code,
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
      {/* Fără supratitlu: spaţiul de lucru e scris în subsolul barei laterale şi
          în adresă. În machetă îl purta antetul fiindcă acolo nu-l spunea nimic
          altceva; aici ar fi a treia oară. Supratitlul rămâne pe ecranele unei
          companii, unde poartă ce nu se vede altfel -- compania şi versiunea
          planului. */}
      <PageHeader
        title={t.companies.title}
        lead={t.companies.lead}
        actions={
          <Button icon="plus" onClick={() => setAdding((open) => !open)}>
            {adding ? t.companies.cancel : t.companies.add}
          </Button>
        }
      />

      {adding && (
        <NewCompanyForm
          pending={create.isPending}
          onSubmit={create.mutate}
        />
      )}
      {create.isError && <Failure error={create.error} />}

      <Card padding="none">
        <DataGrid
          columns={columns}
          rows={companies.data}
          rowKey={(company) => company.id}
          emptyMessage={t.companies.empty}
          onRowClick={(company) => void navigate(cardPath(company))}
        />
      </Card>
    </section>
  )
}

/**
 * Three fields, which is what the server needs to create a company.
 *
 * The IDNO is checked here for shape only -- thirteen digits -- and the server
 * checks the same thing again. It is not a checksum: the checksum rule is not in
 * any text this repository holds, and an invented one would refuse real
 * companies.
 */
function NewCompanyForm({
  initial,
  pending,
  onSubmit,
}: {
  /** Starting values, when the screen already knows them. */
  initial?: { legal_name: string; idno: string } | null
  pending: boolean
  onSubmit: (form: {
    idno: string
    legal_name: string
    currency: string
    cuatm_code: string | null
    caem_code: string | null
  }) => void
}) {
  const [legalName, setLegalName] = useState(initial?.legal_name ?? '')
  const [idno, setIdno] = useState(initial?.idno ?? '')
  const [currency, setCurrency] = useState('MDL')
  // The two codes a statutory return's header carries. Optional here because
  // neither classifier is in the product yet -- a company recorded without them
  // is ordinary, and the return says which one is missing rather than inventing.
  const [cuatm, setCuatm] = useState('')
  const [caem, setCaem] = useState('')

  const complete = /^\d{13}$/.test(idno) && legalName.trim() !== ''

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        onSubmit({
          idno,
          legal_name: legalName.trim(),
          currency,
          cuatm_code: cuatm.trim() || null,
          caem_code: caem.trim() || null,
        })
      }}
    >
      <Field label={t.companies.legalName}>
        <Input
          value={legalName}
          onChange={(event) => setLegalName(event.target.value)}
          maxLength={255}
          className="w-96"
        />
      </Field>
      <Field label={t.companies.idno}>
        <Input
          value={idno}
          onChange={(event) => setIdno(event.target.value.replace(/\D/g, ''))}
          maxLength={13}
          inputMode="numeric"
          placeholder={t.companies.idnoHint}
          className="w-48 font-mono"
        />
      </Field>
      <Field label={t.companies.currency}>
        <Input
          value={currency}
          onChange={(event) => setCurrency(event.target.value.toUpperCase().slice(0, 3))}
          className="w-24 font-mono"
          title={t.companies.currencyHint}
        />
      </Field>
      <Field label={t.payroll.cuatm}>
        <Input
          value={cuatm}
          onChange={(event) => setCuatm(event.target.value)}
          maxLength={16}
          className="w-28 font-mono"
        />
      </Field>
      <Field label={t.payroll.caem}>
        <Input
          value={caem}
          onChange={(event) => setCaem(event.target.value)}
          maxLength={16}
          className="w-28 font-mono"
        />
      </Field>
      <Button variant="primary" type="submit" disabled={!complete || pending}>
        {pending ? t.companies.creating : t.companies.create}
      </Button>
    </form>
  )
}
