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

import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'

import { t } from '@/locales'
import { listCompanies, type Company } from '@/shared/api/companies'
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
  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })

  if (companies.isPending) {
    return <p className="text-sm text-ink-muted">{t.app.loading}</p>
  }

  if (companies.isError) {
    return <Failure error={companies.error} />
  }

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-base font-semibold">{t.companies.title}</h1>
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
