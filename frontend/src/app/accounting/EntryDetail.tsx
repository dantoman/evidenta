/**
 * One entry, opened from a report row -- the drill-down of F1.8, R13 read back.
 *
 * What it shows is what the server says the entry stood on (ADR-048): the rule
 * that produced it, the chart version it was read against, the fiscal date; then
 * the formulas -- the correspondences an accountant reads -- and the lines the
 * balance is built from; then the origin: which event, from which module, about
 * which document. The last hop stops at the document's identifier, because the
 * ledger does not know the source module's tables (D2).
 *
 * **Not `DataGrid`.** An entry is a header with two tables under it, and the
 * grid's contract is one row per record; pushing a nested record through it
 * would be the third grid `C17` forbids, arriving by accident -- the register
 * made the same choice for the same reason.
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { t } from '@/locales'
import { amount, date as formatDate } from '@/shared/format'
import { entryDetail } from '@/shared/api/ledger'
import { Failure } from '@/shared/Failure'

export function EntryDetailPanel({
  entryId,
  companyId,
  onClose,
}: {
  entryId: string
  companyId: string
  onClose: () => void
}) {
  const detail = useQuery({
    queryKey: ['entry-detail', entryId],
    queryFn: () => entryDetail(entryId),
  })

  return (
    <aside className="flex flex-col gap-3 rounded border border-border bg-surface p-3" aria-label={t.accounting.reports.detail}>
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-semibold">{t.accounting.reports.detail}</h2>
        <button type="button" onClick={onClose} className="text-sm text-accent">
          {t.accounting.reports.close}
        </button>
      </div>

      {detail.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {detail.isError && <Failure error={detail.error} />}

      {detail.data && (
        <>
          <dl className="grid grid-cols-[10rem_1fr] gap-x-6 gap-y-1 text-sm">
            <dt className="text-ink-muted">{t.accounting.register.number}</dt>
            <dd className="font-mono">{detail.data.entry_number}</dd>
            <dt className="text-ink-muted">{t.accounting.register.date}</dt>
            <dd>{formatDate(detail.data.accounting_date)}</dd>
            <dt className="text-ink-muted">{t.accounting.register.description}</dt>
            <dd>{detail.data.description}</dd>
            <dt className="text-ink-muted">{t.accounting.reports.stoodOn}</dt>
            <dd className="text-ink-muted">
              {t.accounting.reports.rule}: <span className="font-mono">{detail.data.rule_ref ?? '—'}</span>
              {' · '}
              {t.accounting.reports.chart}: <span className="font-mono">{detail.data.chart ?? '—'}</span>
              {' · '}
              {t.accounting.reports.fiscalDate}:{' '}
              {detail.data.fiscal_effective_date ? formatDate(detail.data.fiscal_effective_date) : '—'}
            </dd>
            {detail.data.origin && (
              <>
                <dt className="text-ink-muted">{t.accounting.reports.origin}</dt>
                <dd className="text-ink-muted">
                  {t.accounting.reports.originEvent}:{' '}
                  <span className="font-mono">{detail.data.origin.event_type}</span>
                  {' · '}
                  {t.accounting.reports.originDocument}:{' '}
                  <span className="font-mono">
                    {detail.data.origin.source_module}/{detail.data.origin.source_document_type}/
                    {detail.data.origin.source_document_id}
                  </span>
                </dd>
              </>
            )}
            {detail.data.reversed_by_entry_id && (
              <>
                <dt className="text-ink-muted">{t.accounting.reports.detail}</dt>
                <dd className="text-danger">{t.accounting.register.reversed}</dd>
              </>
            )}
          </dl>

          <h3 className="text-sm font-medium">{t.accounting.reports.formulas}</h3>
          {detail.data.formulas.length === 0 ? (
            <p className="text-sm text-ink-muted">{t.accounting.reports.noFormulas}</p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-ink-muted">
                  <th className="px-2 font-medium">{t.accounting.reports.debitAccount}</th>
                  <th className="px-2 font-medium">{t.accounting.reports.creditAccount}</th>
                  <th className="px-2 text-right font-medium">{t.accounting.reports.amount}</th>
                  <th className="px-2 text-right font-medium">{t.accounting.reports.vatRate}</th>
                </tr>
              </thead>
              <tbody>
                {detail.data.formulas.map((formula) => (
                  <tr key={formula.formula_number} className="border-t border-border">
                    <td className="px-2">
                      <Link
                        to={`/companii/${companyId}/conturi/${formula.debit_account_id}/fisa`}
                        className="font-mono text-accent"
                      >
                        {formula.debit_code}
                      </Link>
                    </td>
                    <td className="px-2">
                      <Link
                        to={`/companii/${companyId}/conturi/${formula.credit_account_id}/fisa`}
                        className="font-mono text-accent"
                      >
                        {formula.credit_code}
                      </Link>
                    </td>
                    <td className="px-2 text-right tabular">{amount(formula.amount)}</td>
                    <td className="px-2 text-right tabular">
                      {formula.vat_rate === null ? '' : `${amount(formula.vat_rate)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 className="text-sm font-medium">{t.accounting.reports.lines}</h3>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-ink-muted">
                <th className="px-2 font-medium">{t.accounting.register.account}</th>
                <th className="px-2 font-medium">{t.accounting.register.description}</th>
                <th className="px-2 text-right font-medium">{t.accounting.register.debit}</th>
                <th className="px-2 text-right font-medium">{t.accounting.register.credit}</th>
              </tr>
            </thead>
            <tbody>
              {detail.data.lines.map((line) => (
                <tr key={line.line_number} className="border-t border-border">
                  <td className="px-2">
                    <span className="font-mono">{line.account_code}</span>{' '}
                    <span className="text-ink-muted">{line.name_ro}</span>
                  </td>
                  <td className="px-2 text-ink-muted">{line.description}</td>
                  <td className="px-2 text-right tabular">{amount(line.debit)}</td>
                  <td className="px-2 text-right tabular">{amount(line.credit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </aside>
  )
}
