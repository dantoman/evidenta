/**
 * Opening balances: what a company brings with it from the system before this one.
 *
 * Until this screen the product was usable only by a company founded today. A
 * firm arriving from 1C had no way in, so its trial balance started at zero and
 * meant nothing -- a balance that balances and describes nothing.
 *
 * **Four steps, and they are the server's steps, not a wizard invented here:**
 * a batch is created against a counterpart account, rows are added while it is a
 * draft, validation freezes them, and posting writes one entry. Validation and
 * posting are separate calls because they are separate decisions -- the checks
 * can pass on numbers somebody still wants to look at again.
 *
 * **Only general-ledger rows.** Receivables and payables need a `partner_id`,
 * and `masterdata/partners` has no HTTP surface at all -- so a field asking for
 * one would be a field nobody can fill. The screen says that out loud rather
 * than leaving a reader to conclude the feature is broken.
 *
 * The totals below are read by a person deciding whether the set is complete, so
 * they are added as integers rather than through floating point, **at the
 * server's scale of four decimals rather than at two**. The first version reused
 * the manual note's two-decimal parser, which reads user keystrokes; handed
 * `"5000.0000"` it matched nothing and returned zero, so every saved row totalled
 * to nothing and the out-of-balance warning never appeared. A test caught it,
 * which is the only reason this paragraph is not a bug report.
 *
 * The refusal that matters is still the server's -- `opening.gl_out_of_balance` --
 * because reconciling to zero is the condition of the import, not its goal: the
 * counterpart does not absorb a difference.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { t } from '@/locales'
import { amount } from '@/shared/format'
import { listAccounts, type Account } from '@/shared/api/coa'
import {
  addGlRows,
  createBatch,
  getBatch,
  postBatch,
  validateBatch,
  type BatchSource,
} from '@/shared/api/opening'
import { Failure } from '@/shared/Failure'

const FIELD = 'w-full rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

interface Draft {
  account_id: string
  debit: string
  credit: string
}

const EMPTY: Draft = { account_id: '', debit: '', credit: '' }

const SOURCE_LABEL: Record<BatchSource, string> = {
  manual: t.accounting.opening.sourceManual,
  onec_import: t.accounting.opening.sourceOnec,
  other_system: t.accounting.opening.sourceOther,
}

/**
 * The scale the server stores in: `numeric(20, 4)`. Sums are integers in these
 * units, so nothing here rounds before the display step -- a total that lost the
 * third decimal would disagree with the ledger by an amount nobody can find.
 */
const SCALE = 4

/** A decimal string as an integer at `SCALE`. Anything unparsed counts as zero. */
function units(value: string): number {
  const match = /^\s*(-?)(\d*)(?:[.,](\d*))?\s*$/.exec(value)
  if (!match) return 0
  const [, sign, whole, fraction = ''] = match
  const scaled = fraction.padEnd(SCALE, '0').slice(0, SCALE)
  const total = Number(whole || '0') * 10 ** SCALE + Number(scaled || '0')
  return sign === '-' ? -total : total
}

/** Back to a decimal string, so `amount()` formats it the one way (C18). */
function decimals(total: number): string {
  const sign = total < 0 ? '-' : ''
  const absolute = Math.abs(total)
  const whole = Math.floor(absolute / 10 ** SCALE)
  const fraction = String(absolute % 10 ** SCALE).padStart(SCALE, '0')
  return `${sign}${whole}.${fraction}`
}

function formatted(total: number): string {
  return amount(decimals(total))
}

export function OpeningBalancesScreen() {
  const { companyId = '', batchId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const accounts = useQuery({
    queryKey: ['accounts', companyId, ''],
    queryFn: () => listAccounts(companyId),
  })

  const batch = useQuery({
    queryKey: ['opening-batch', batchId],
    queryFn: () => getBatch(batchId as string),
    enabled: batchId !== undefined,
  })

  return (
    <section className="flex flex-col gap-4">
      <nav className="flex gap-4 text-sm">
        <Link to={`/companii/${companyId}/plan-de-conturi`} className="text-accent">
          {t.accounting.chart.title}
        </Link>
        <Link to={`/companii/${companyId}/balanta`} className="text-accent">
          {t.accounting.balance.title}
        </Link>
      </nav>

      <header className="flex flex-col gap-1">
        <h1 className="text-base font-semibold">{t.accounting.opening.title}</h1>
        <p className="text-sm text-ink-muted">{t.accounting.opening.lead}</p>
      </header>

      {accounts.isError && <Failure error={accounts.error} />}

      {batchId === undefined ? (
        <NewBatch
          accounts={accounts.data ?? []}
          onCreated={(created) =>
            void navigate(`/companii/${companyId}/solduri-initiale/${created}`)
          }
        />
      ) : (
        <>
          {batch.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
          {batch.isError && <Failure error={batch.error} />}
          {batch.data && (
            <Batch
              accounts={accounts.data ?? []}
              contents={batch.data}
              onChanged={() =>
                queryClient.invalidateQueries({ queryKey: ['opening-batch', batchId] })
              }
            />
          )}
        </>
      )}
    </section>
  )
}

function NewBatch({
  accounts,
  onCreated,
}: {
  accounts: Account[]
  onCreated: (batchId: string) => void
}) {
  const { companyId = '' } = useParams()
  const [asOfDate, setAsOfDate] = useState('')
  const [source, setSource] = useState<BatchSource>('manual')
  const [counterpart, setCounterpart] = useState('')

  const create = useMutation({
    mutationFn: () =>
      createBatch(companyId, {
        as_of_date: asOfDate,
        source,
        counterpart_account_id: counterpart,
      }),
    onSuccess: (created) => onCreated(created.id),
  })

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.opening.asOfDate}</span>
        <input
          type="date"
          value={asOfDate}
          onChange={(event) => setAsOfDate(event.target.value)}
          className={`${FIELD} w-44`}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.opening.source}</span>
        <select
          value={source}
          onChange={(event) => setSource(event.target.value as BatchSource)}
          className={`${FIELD} w-48`}
        >
          {(Object.keys(SOURCE_LABEL) as BatchSource[]).map((key) => (
            <option key={key} value={key}>
              {SOURCE_LABEL[key]}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.opening.counterpart}</span>
        <select
          value={counterpart}
          onChange={(event) => setCounterpart(event.target.value)}
          className={FIELD}
        >
          <option value="" />
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.account_code} — {account.name_ro}
            </option>
          ))}
        </select>
      </label>

      <button
        type="submit"
        disabled={asOfDate === '' || counterpart === '' || create.isPending}
        className={BUTTON}
      >
        {t.accounting.opening.create}
      </button>

      <p className="w-full text-sm text-ink-muted">{t.accounting.opening.asOfDateHint}</p>
      <p className="w-full text-sm text-ink-muted">{t.accounting.opening.counterpartHint}</p>
      {create.isError && (
        <div className="w-full">
          <Failure error={create.error} />
        </div>
      )}
    </form>
  )
}

function Batch({
  accounts,
  contents,
  onChanged,
}: {
  accounts: Account[]
  contents: Awaited<ReturnType<typeof getBatch>>
  onChanged: () => Promise<void> | void
}) {
  const [rows, setRows] = useState<Draft[]>([{ ...EMPTY }])
  const [idempotencyKey] = useState(() => crypto.randomUUID())

  const editable = contents.status === 'draft'
  const byId = new Map(accounts.map((account) => [account.id, account]))

  const save = useMutation({
    mutationFn: () =>
      addGlRows(
        contents.id,
        rows
          .filter((row) => row.account_id !== '')
          .map((row) => ({
            account_id: row.account_id,
            debit: row.debit.replace(',', '.') || '0',
            credit: row.credit.replace(',', '.') || '0',
          })),
      ),
    onSuccess: async () => {
      setRows([{ ...EMPTY }])
      await onChanged()
    },
  })

  const validate = useMutation({ mutationFn: () => validateBatch(contents.id), onSuccess: onChanged })
  const post = useMutation({
    mutationFn: () => postBatch(contents.id, idempotencyKey),
    onSuccess: onChanged,
  })

  // The saved rows, as the server holds them -- not the draft above.
  const savedDebit = contents.gl.reduce((sum, row) => sum + units(row.debit), 0)
  const savedCredit = contents.gl.reduce((sum, row) => sum + units(row.credit), 0)
  const difference = savedDebit - savedCredit

  const set = (index: number, field: keyof Draft, value: string) =>
    setRows((current) =>
      current.map((row, at) => (at === index ? { ...row, [field]: value } : row)),
    )

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-[10rem_1fr] gap-x-6 gap-y-1 text-sm">
        <dt className="text-ink-muted">{t.accounting.opening.asOfDate}</dt>
        <dd>{contents.as_of_date}</dd>
        <dt className="text-ink-muted">{t.accounting.opening.source}</dt>
        <dd>{SOURCE_LABEL[contents.source]}</dd>
        <dt className="text-ink-muted">{t.accounting.opening.counterpart}</dt>
        <dd className="font-mono">
          {byId.get(contents.counterpart_account_id)?.account_code ??
            contents.counterpart_account_id}
        </dd>
        <dt className="text-ink-muted">{t.accounting.opening.state}</dt>
        <dd>{t.accounting.opening[contents.status]}</dd>
      </dl>

      <div className="overflow-x-auto rounded border border-border bg-surface">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-ink-muted">
              <th className="px-2 font-medium">{t.accounting.opening.account}</th>
              <th className="px-2 text-right font-medium">{t.accounting.opening.debit}</th>
              <th className="px-2 text-right font-medium">{t.accounting.opening.credit}</th>
            </tr>
          </thead>
          <tbody>
            {contents.gl.length === 0 && (
              <tr className="border-b border-border">
                <td colSpan={3} className="px-2 text-center text-ink-muted">
                  {t.accounting.opening.empty}
                </td>
              </tr>
            )}
            {contents.gl.map((row) => {
              const account = byId.get(row.account_id)
              return (
                <tr key={row.account_id} className="border-b border-border last:border-0">
                  <td className="px-2">
                    <span className="font-mono">{account?.account_code ?? row.account_id}</span>{' '}
                    <span className="text-ink-muted">{account?.name_ro}</span>
                  </td>
                  <td className="px-2 text-right tabular">{amount(row.debit)}</td>
                  <td className="px-2 text-right tabular">{amount(row.credit)}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-border font-medium">
              <td className="px-2">{t.accounting.opening.total}</td>
              <td className="px-2 text-right tabular">{formatted(savedDebit)}</td>
              <td className="px-2 text-right tabular">{formatted(savedCredit)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {difference !== 0 && contents.gl.length > 0 && (
        <p className="text-sm text-danger">
          {t.accounting.opening.difference}: {formatted(difference)} —{' '}
          {t.accounting.opening.unbalanced}
        </p>
      )}

      {editable && (
        <form
          className="flex flex-col gap-2 rounded border border-border bg-surface p-3"
          onSubmit={(event) => {
            event.preventDefault()
            save.mutate()
          }}
        >
          {rows.map((row, index) => (
            <div key={index} className="flex flex-wrap items-end gap-2">
              <label className="flex flex-1 flex-col gap-1 text-sm">
                <span className="text-ink-muted">{t.accounting.opening.account}</span>
                <select
                  value={row.account_id}
                  onChange={(event) => set(index, 'account_id', event.target.value)}
                  className={FIELD}
                  aria-label={`${t.accounting.opening.account} ${index + 1}`}
                >
                  <option value="" />
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_code} — {account.name_ro}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-muted">{t.accounting.opening.debit}</span>
                <input
                  value={row.debit}
                  onChange={(event) => set(index, 'debit', event.target.value)}
                  inputMode="decimal"
                  className={`${FIELD} tabular w-32 text-right`}
                  aria-label={`${t.accounting.opening.debit} ${index + 1}`}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-muted">{t.accounting.opening.credit}</span>
                <input
                  value={row.credit}
                  onChange={(event) => set(index, 'credit', event.target.value)}
                  inputMode="decimal"
                  className={`${FIELD} tabular w-32 text-right`}
                  aria-label={`${t.accounting.opening.credit} ${index + 1}`}
                />
              </label>
              <button
                type="button"
                onClick={() => setRows((current) => current.filter((_, at) => at !== index))}
                disabled={rows.length <= 1}
                className="text-sm text-accent disabled:text-ink-muted"
              >
                {t.accounting.opening.removeRow}
              </button>
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={() => setRows((current) => [...current, { ...EMPTY }])}
              className={BUTTON}
            >
              {t.accounting.opening.addRow}
            </button>
            <button
              type="submit"
              disabled={rows.every((row) => row.account_id === '') || save.isPending}
              className={BUTTON}
            >
              {t.accounting.opening.saveRows}
            </button>
          </div>
          {save.isError && <Failure error={save.error} />}
        </form>
      )}

      <p className="text-sm text-ink-muted">{t.accounting.opening.partnersMissing}</p>

      <div className="flex flex-wrap items-center gap-4">
        {contents.status === 'draft' && (
          <button
            type="button"
            onClick={() => validate.mutate()}
            disabled={contents.gl.length === 0 || validate.isPending}
            className={BUTTON}
          >
            {t.accounting.opening.validate}
          </button>
        )}
        {contents.status === 'validated' && (
          <button
            type="button"
            onClick={() => post.mutate()}
            disabled={post.isPending}
            className={BUTTON}
          >
            {t.accounting.opening.post}
          </button>
        )}
        {contents.status === 'validated' && (
          <span className="text-sm text-ink-muted">{t.accounting.opening.validatedNote}</span>
        )}
        {contents.status === 'posted' && (
          <span className="text-sm text-ink-muted">{t.accounting.opening.postedNote}</span>
        )}
      </div>

      {validate.isError && <Failure error={validate.error} />}
      {post.isError && <Failure error={post.error} />}
    </div>
  )
}
