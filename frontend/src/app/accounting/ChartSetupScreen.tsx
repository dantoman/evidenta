/**
 * Building a company's chart from a published version.
 *
 * Until onboarding exists this is the only way a company gets a chart at all --
 * `P-9` (ADR-040) is decided and unwritten, and when it lands it calls the same
 * service in the same transaction rather than this endpoint. So the screen is a
 * real gap being closed, not a convenience: before it, a company with no chart
 * was a dead end that said so and offered nothing.
 *
 * **The version is chosen, then confirmed.** A button on every row would make an
 * irreversible choice a single mis-click away: a company has exactly one chart,
 * and a second is refused (`coa.chart_already_instantiated`). The selection is
 * named back before the confirmation, in the words of the act it transcribes.
 *
 * Only published versions arrive from the server. A draft is a version being
 * prepared and the service refuses to instantiate one, so listing drafts would
 * put a choice on screen that the server will not honour.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { t } from '@/locales'
import { date } from '@/shared/format'
import { getChart, instantiateChart, listTemplates, type CoaTemplate } from '@/shared/api/coa'
import { listCompanies } from '@/shared/api/companies'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure, codeOf } from '@/shared/Failure'
import { Card } from '@/shared/ui'

function validity(template: CoaTemplate): string {
  const until = template.valid_to ? date(template.valid_to) : t.common.none
  return `${date(template.valid_from)} — ${until}`
}

export function ChartSetupScreen() {
  const { companyId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [chosen, setChosen] = useState<string | null>(null)

  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })
  const templates = useQuery({ queryKey: ['templates'], queryFn: listTemplates })
  const chart = useQuery({
    queryKey: ['chart', companyId],
    queryFn: () => getChart(companyId),
    retry: false,
  })

  const instantiate = useMutation({
    mutationFn: (templateId: string) => instantiateChart(companyId, templateId),
    onSuccess: async () => {
      // The chart and the accounts both changed, and the screen being returned
      // to reads them. Invalidated rather than written into the cache: what the
      // server built is what should be displayed, not what the client assumed
      // it built.
      await queryClient.invalidateQueries({ queryKey: ['chart', companyId] })
      await queryClient.invalidateQueries({ queryKey: ['accounts', companyId] })
      void navigate(`/companii/${companyId}/plan-de-conturi`)
    },
  })

  const company = companies.data?.find((row) => row.id === companyId)
  const alreadyInstantiated = chart.isSuccess
  const selected = templates.data?.find((row) => row.id === chosen)

  const columns: Column<CoaTemplate>[] = [
    {
      key: 'choose',
      header: t.accounting.templates.choose,
      cell: (template) => (
        <input
          type="radio"
          name="template"
          value={template.id}
          checked={chosen === template.id}
          onChange={() => setChosen(template.id)}
          aria-label={`${template.code} ${template.version}`}
        />
      ),
      width: '4rem',
    },
    {
      key: 'code',
      header: t.accounting.templates.code,
      cell: (template) => <span className="font-mono">{template.code}</span>,
      width: '10rem',
    },
    {
      key: 'version',
      header: t.accounting.templates.version,
      cell: (template) => <span className="font-mono">{template.version}</span>,
      width: '8rem',
    },
    {
      key: 'valid',
      header: t.accounting.templates.validity,
      cell: validity,
      width: '14rem',
    },
    { key: 'act', header: t.accounting.templates.act, cell: (template) => template.source_act },
    {
      key: 'reference',
      header: t.accounting.templates.reference,
      cell: (template) => template.source_reference,
      width: '14rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="type-display-2 text-heading">{t.accounting.templates.title}</h1>
        {company && <span className="text-sm text-ink-muted">{company.legal_name}</span>}
      </header>

      {alreadyInstantiated ? (
        <p className="text-sm">
          <span className="text-ink-muted">{t.accounting.templates.already} </span>
          <Link to={`/companii/${companyId}/plan-de-conturi`} className="text-accent">
            {t.accounting.chart.title}
          </Link>
        </p>
      ) : (
        <>
          <p className="text-sm text-ink-muted">{t.accounting.templates.lead}</p>

          {templates.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
          {templates.isError && <Failure error={templates.error} />}
          {templates.data && (
            <Card padding="none">
              <DataGrid
                columns={columns}
                rows={templates.data}
                rowKey={(template) => template.id}
                emptyMessage={t.accounting.templates.empty}
                density="comfortable"
                onRowClick={(template) => setChosen(template.id)}
              />
            </Card>
          )}

          {instantiate.isError && <Failure error={instantiate.error} />}

          <div className="flex items-center gap-4">
            <button
              type="button"
              disabled={!chosen || instantiate.isPending}
              onClick={() => chosen && instantiate.mutate(chosen)}
              className="rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted"
            >
              {t.accounting.templates.submit}
            </button>
            {selected && (
              <span className="text-sm text-ink-muted">
                {t.accounting.templates.chosen}: {selected.code} {selected.version} —{' '}
                {selected.source_act}
              </span>
            )}
          </div>
        </>
      )}

      {chart.isError && codeOf(chart.error) !== 'api.not_found' && (
        <Failure error={chart.error} />
      )}
    </section>
  )
}
