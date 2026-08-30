/**
 * The unified monthly return -- header, totals, nominal record, reconciliation.
 *
 * **One document, not three reports.** Art. 5 para (1) of Law 489/1999 makes the
 * nominal record of insured persons and the calculation of social contributions
 * *parts of* the return, so they are sections of one screen and one entity.
 *
 * **Versions, never edits.** Art. 188: a change is a corrected return. The screen
 * lists every version, says which one each corrects, and offers a correction
 * rather than an edit -- there is no field on this screen a person can type into.
 *
 * **What is shown is what was stored.** The return froze its codes and amounts at
 * generation, so a screen reading a filed return shows what was filed, not what
 * today's payroll would produce.
 *
 * **The printed form is not here**, and the screen says so instead of implying
 * completeness: Annex 1 of Ordinul MF nr. 94/2020 is not in the repository, and
 * a rendering invented from the drafts would look like the form and not be it.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import {
  correctIpc,
  generateIpc,
  getIpcDeclaration,
  listIpcDeclarations,
  reconcileIpc,
  submitIpc,
  type IpcNominal,
  type IpcTotal,
} from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

export function IpcScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)

  const declarations = useQuery({
    queryKey: ['ipc-declarations', companyId],
    queryFn: () => listIpcDeclarations(companyId),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['ipc-declarations'] })

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-semibold">{t.payroll.ipc}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <Link to={`/companii/${companyId}/salarii`} className="text-sm text-accent">
            {t.payroll.runs}
          </Link>
          <Link to={`/companii/${companyId}/angajati`} className="text-sm text-accent">
            {t.payroll.people}
          </Link>
        </div>
      </header>

      <p className="text-sm text-ink-muted">{t.payroll.ipcFormMissing}</p>

      <GenerateForm companyId={companyId} onGenerated={refresh} />

      {declarations.isError && <Failure error={declarations.error} />}
      {declarations.data && (
        <ul className="flex flex-wrap gap-3 text-sm">
          {declarations.data.length === 0 && (
            <li className="text-ink-muted">{t.payroll.noDeclarations}</li>
          )}
          {declarations.data.map((declaration) => (
            <li key={declaration.id}>
              <button
                type="button"
                onClick={() =>
                  setSelected(selected === declaration.id ? null : declaration.id)
                }
                className={`${BUTTON} ${selected === declaration.id ? 'text-ink' : ''}`}
              >
                {declaration.year}-{String(declaration.month).padStart(2, '0')} ·{' '}
                {t.payroll.ipcVersion} {declaration.version_number}
                {declaration.version_number > 1 ? ` (${t.payroll.ipcCorrected})` : ''}
                {declaration.submitted_on ? ` · ${t.payroll.ipcSubmitted}` : ''}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected && <Declaration declarationId={selected} onChanged={refresh} />}
    </section>
  )
}

function GenerateForm({
  companyId,
  onGenerated,
}: {
  companyId: string
  onGenerated: () => void
}) {
  const now = new Date()
  const [year, setYear] = useState(String(now.getFullYear()))
  const [month, setMonth] = useState(String(now.getMonth() + 1))

  const generate = useMutation({
    mutationFn: () => generateIpc(companyId, { year: Number(year), month: Number(month) }),
    onSuccess: onGenerated,
  })

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        generate.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.year}</span>
        <input
          inputMode="numeric"
          value={year}
          onChange={(event) => setYear(event.target.value)}
          className={`${FIELD} w-24 tabular-nums`}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.payroll.month}</span>
        <input
          inputMode="numeric"
          value={month}
          onChange={(event) => setMonth(event.target.value)}
          className={`${FIELD} w-16 tabular-nums`}
        />
      </label>
      <button type="submit" disabled={generate.isPending} className={BUTTON}>
        {t.payroll.ipcGenerate}
      </button>
      {generate.isError && <Failure error={generate.error} />}
    </form>
  )
}

function Declaration({
  declarationId,
  onChanged,
}: {
  declarationId: string
  onChanged: () => void
}) {
  const queryClient = useQueryClient()
  const [submittedOn, setSubmittedOn] = useState('')

  const declaration = useQuery({
    queryKey: ['ipc-declaration', declarationId],
    queryFn: () => getIpcDeclaration(declarationId),
  })
  const reconciliation = useQuery({
    queryKey: ['ipc-reconciliation', declarationId],
    queryFn: () => reconcileIpc(declarationId),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['ipc-declaration', declarationId] })
    onChanged()
  }

  const correction = useMutation({ mutationFn: () => correctIpc(declarationId), onSuccess: refresh })
  const submission = useMutation({
    mutationFn: () => submitIpc(declarationId, submittedOn),
    onSuccess: refresh,
  })

  const totalColumns: Column<IpcTotal>[] = [
    { key: 'source', header: t.payroll.incomeSource, cell: (row) => row.income_source_code },
    { key: 'tariff', header: t.payroll.tariffRow, cell: (row) => row.cas_tariff_code },
    {
      key: 'paid',
      header: t.payroll.incomePaid,
      cell: (row) => row.income_paid,
      numeric: true,
    },
    {
      key: 'tax',
      header: t.payroll.taxWithheld,
      cell: (row) => row.income_tax_withheld,
      numeric: true,
    },
    {
      key: 'health',
      header: t.payroll.healthWithheld,
      cell: (row) => row.health_insurance_withheld,
      numeric: true,
    },
    {
      key: 'cas',
      header: t.payroll.contribution,
      cell: (row) => row.social_contribution,
      numeric: true,
    },
  ]

  const nominalColumns: Column<IpcNominal>[] = [
    { key: 'nr', header: '#', cell: (row) => row.line_number, numeric: true, width: '4rem' },
    { key: 'name', header: t.payroll.people, cell: (row) => row.name },
    {
      key: 'idnp',
      header: t.payroll.idnp,
      cell: (row) => <span className="font-mono">{row.idnp ?? t.common.none}</span>,
      width: '12rem',
    },
    {
      key: 'cpas',
      header: t.payroll.cpas,
      cell: (row) => <span className="font-mono">{row.personal_insurance_code ?? t.common.none}</span>,
      width: '10rem',
    },
    {
      key: 'period',
      header: t.payroll.workedPeriod,
      cell: (row) => `${row.work_period_start} – ${row.work_period_end}`,
      width: '15rem',
    },
    {
      key: 'category',
      header: t.payroll.insuredCategory,
      // Empty because Annex 3 is not obtained -- said, not implied.
      cell: (row) =>
        row.insured_category_code ?? (
          <span className="text-ink-muted">{t.payroll.insuredCategoryMissing}</span>
        ),
      width: '18rem',
    },
    {
      key: 'base',
      header: t.payroll.insuredIncome,
      cell: (row) => row.insured_income,
      numeric: true,
    },
    {
      key: 'contribution',
      header: t.payroll.contribution,
      cell: (row) => row.contribution,
      numeric: true,
    },
  ]

  return (
    <section className="flex flex-col gap-4 rounded border border-border bg-surface p-4">
      {declaration.isError && <Failure error={declaration.error} />}
      {declaration.data && (
        <>
          <header className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-sm font-semibold">
              {declaration.data.year}-{String(declaration.data.month).padStart(2, '0')} ·{' '}
              {t.payroll.ipcVersion} {declaration.data.version_number}{' '}
              {declaration.data.version_number === 1
                ? `(${t.payroll.ipcPrimary})`
                : `(${t.payroll.ipcCorrected})`}
            </h2>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-ink-muted">
                {t.payroll.ipcDueOn}: {declaration.data.due_on}
              </span>
              {declaration.data.submitted_on ? (
                <span className="text-sm text-ink-muted">
                  {t.payroll.ipcSubmittedOn}: {declaration.data.submitted_on}
                </span>
              ) : (
                <form
                  className="flex items-end gap-2"
                  onSubmit={(event: FormEvent) => {
                    event.preventDefault()
                    submission.mutate()
                  }}
                >
                  <input
                    type="date"
                    value={submittedOn}
                    onChange={(event) => setSubmittedOn(event.target.value)}
                    aria-label={t.payroll.ipcSubmittedOn}
                    className={`${FIELD} w-40`}
                  />
                  <button type="submit" disabled={submittedOn === ''} className={BUTTON}>
                    {t.payroll.ipcSubmit}
                  </button>
                </form>
              )}
              {/* A correction, never an edit -- there is no editable field here. */}
              <button
                type="button"
                onClick={() => correction.mutate()}
                disabled={correction.isPending}
                className={BUTTON}
              >
                {t.payroll.ipcCorrect}
              </button>
            </div>
          </header>
          {correction.isError && <Failure error={correction.error} />}
          {submission.isError && <Failure error={submission.error} />}

          <dl className="flex flex-wrap gap-6 text-sm">
            <div>
              <dt className="text-ink-muted">{t.payroll.fiscalCode}</dt>
              <dd className="font-mono">{declaration.data.header?.fiscal_code}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">{t.payroll.cuatm}</dt>
              <dd className="font-mono">
                {declaration.data.header?.cuatm_code ?? (
                  <span className="text-danger">{t.payroll.ipcMissingCode}</span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">{t.payroll.caem}</dt>
              <dd className="font-mono">
                {declaration.data.header?.caem_code ?? (
                  <span className="text-danger">{t.payroll.ipcMissingCode}</span>
                )}
              </dd>
            </div>
          </dl>

          {reconciliation.data && (
            <div className="flex flex-col gap-1 text-sm">
              <h3 className="font-semibold">{t.payroll.reconciliation}</h3>
              {reconciliation.data.agrees ? (
                <p className="text-ink-muted">
                  {t.payroll.reconciliationOk} · {reconciliation.data.charged_count}{' '}
                  {t.payroll.reconciliationCounts}
                </p>
              ) : (
                <>
                  {reconciliation.data.missing.length > 0 && (
                    <p role="alert" className="text-danger">
                      {t.payroll.reconciliationMissing}:{' '}
                      {reconciliation.data.missing.join(', ')}
                    </p>
                  )}
                  {reconciliation.data.extra.length > 0 && (
                    <p role="alert" className="text-danger">
                      {t.payroll.reconciliationExtra}: {reconciliation.data.extra.join(', ')}
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          <h3 className="text-sm font-semibold">{t.payroll.ipcTotals}</h3>
          <DataGrid
            columns={totalColumns}
            rows={declaration.data.totals ?? []}
            rowKey={(row) => `${row.income_source_code}-${row.cas_tariff_code}`}
            emptyMessage={t.payroll.noDeclarations}
          />

          <h3 className="text-sm font-semibold">{t.payroll.ipcNominal}</h3>
          <DataGrid
            columns={nominalColumns}
            rows={declaration.data.nominal ?? []}
            rowKey={(row) => row.person_id}
            emptyMessage={t.payroll.noDeclarations}
          />
        </>
      )}
    </section>
  )
}
