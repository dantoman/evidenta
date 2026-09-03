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
 * **Receivables and payables arrived with the partner directory.** They were
 * absent while `masterdata/partners` had no HTTP surface, because a field asking
 * for a `partner_id` the interface cannot search is a field nobody can fill; the
 * screen said so rather than leaving a reader to conclude it was broken. The
 * partner is searched by name or IDNO, never typed as an identifier.
 *
 * **The analytical detail must agree with its control account**, and the server
 * is what checks it (`opening.analytical_mismatch`). This screen says the rule
 * next to the fields rather than re-checking it: two opinions about the same
 * arithmetic drift, and the one on the client is the one nobody audits.
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
 *
 * **Stock, fixed assets and payroll cumulatives arrived with G3.** The item, the
 * unit and the asset are identities of the *source* system -- there is no item
 * nomenclator with an HTTP surface and no asset registry yet -- so they are
 * typed or generated as references the company will attach the object to later,
 * and the form says so beside the field. The cumulatives never post: they are
 * the base the income-tax calculation continues from when payroll starts in the
 * middle of a year (ADR-061), and the employee is chosen from the company's own
 * list because that one does exist.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { t } from '@/locales'
import { amount } from '@/shared/format'
import { listAccounts, type Account } from '@/shared/api/coa'
import {
  addAnalyticalRows,
  addGlRows,
  addPartnerRows,
  createBatch,
  CUMULATIVE_CODES,
  getBatch,
  listBatches,
  postBatch,
  validateBatch,
  type AssetRow,
  type BatchContents,
  type BatchSource,
  type CumulativeCode,
  type InventoryRow,
  type PayrollCumulativeRow,
} from '@/shared/api/opening'
import { listPartners, type Partner } from '@/shared/api/partners'
import { listEmployees, type Employee } from '@/shared/api/payroll'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { EntryGrid, type EntryColumn } from '@/shared/EntryGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input, Select } from '@/shared/ui'

type Draft = {
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

/** The three keys of ADR-061, labelled. The key stays the server's. */
const CUMULATIVE_LABEL: Record<CumulativeCode, string> = {
  'income_tax.taxable_income': t.accounting.opening.cumulativeTaxableIncome,
  'income_tax.exemptions_granted': t.accounting.opening.cumulativeExemptionsGranted,
  'income_tax.withheld': t.accounting.opening.cumulativeWithheld,
}

/** Point and comma are both the decimal separator (C40), on a plain input too. */
function decimal(value: string): string {
  return value.trim().replace(',', '.')
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

      <header className="flex flex-col gap-1">
        <h1 className="type-display-2 text-heading">{t.accounting.opening.title}</h1>
        <p className="text-sm text-ink-muted">{t.accounting.opening.lead}</p>
      </header>

      {accounts.isError && <Failure error={accounts.error} />}

      {batchId === undefined ? (
        <>
          <Batches companyId={companyId} />
          <NewBatch
            accounts={accounts.data ?? []}
            onCreated={(created) =>
              void navigate(`/companii/${companyId}/solduri-initiale/${created}`)
            }
          />
        </>
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

/**
 * Every batch the company has, newest first.
 *
 * The screen worked without this and was worse for it: a draft abandoned
 * yesterday had an address and no way back to it, so the next import would start
 * from zero beside it -- two partial pictures of the same opening position, both
 * plausible. A batch is never deleted, which is exactly why it has to be findable.
 */
function Batches({ companyId }: { companyId: string }) {
  const batches = useQuery({
    queryKey: ['opening-batches', companyId],
    queryFn: () => listBatches(companyId),
  })

  if (batches.isError) return <Failure error={batches.error} />
  if (!batches.data) return null
  if (batches.data.length === 0) {
    return <p className="text-sm text-ink-muted">{t.accounting.opening.batchesEmpty}</p>
  }

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">{t.accounting.opening.batches}</h2>
      {batches.data.map((batch) => (
        <Link
          key={batch.id}
          to={`/companii/${companyId}/solduri-initiale/${batch.id}`}
          className="flex flex-wrap items-baseline justify-between gap-4 rounded border border-border bg-surface px-3 py-2 text-sm"
        >
          <span className="flex items-baseline gap-3">
            <span className="font-medium">{batch.as_of_date}</span>
            <span className="text-ink-muted">{SOURCE_LABEL[batch.source]}</span>
            <span className="text-ink-muted">
              {batch.gl_rows +
                batch.receivable_rows +
                batch.payable_rows +
                batch.inventory_rows +
                batch.asset_rows +
                batch.payroll_rows}{' '}
              {t.accounting.opening.rows}
            </span>
          </span>
          <span className="flex items-baseline gap-3">
            {batch.rejected_reason && (
              <span className="text-ink-muted">
                {t.accounting.opening.rejectedReason}: {batch.rejected_reason}
              </span>
            )}
            <span className={batch.status === 'posted' ? 'text-ink-muted' : 'text-accent'}>
              {t.accounting.opening[batch.status]}
            </span>
          </span>
        </Link>
      ))}
    </div>
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
      <Field label={t.accounting.opening.asOfDate}>
        <Input
          type="date"
          value={asOfDate}
          onChange={(event) => setAsOfDate(event.target.value)}
          className="w-44"
        />
      </Field>

      <Field label={t.accounting.opening.source}>
        <Select
          value={source}
          onChange={(event) => setSource(event.target.value as BatchSource)}
          className="w-48"
        >
          {(Object.keys(SOURCE_LABEL) as BatchSource[]).map((key) => (
            <option key={key} value={key}>
              {SOURCE_LABEL[key]}
            </option>
          ))}
        </Select>
      </Field>

      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.opening.counterpart}</span>
        <Select
          value={counterpart}
          onChange={(event) => setCounterpart(event.target.value)}
        >
          <option value="" />
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.account_code} — {account.name_ro}
            </option>
          ))}
        </Select>
      </label>

      <Button variant="primary"
        type="submit"
        disabled={asOfDate === '' || counterpart === '' || create.isPending}
      >
        {t.accounting.opening.create}
      </Button>

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

  // The company's own people, for the cumulative set: the one identity of the
  // three new sets that has a list behind it.
  const employees = useQuery({
    queryKey: ['employees', contents.company_id],
    queryFn: () => listEmployees(contents.company_id),
  })

  const glColumns: EntryColumn<Draft>[] = [
    {
      key: 'account_id',
      header: t.accounting.opening.account,
      kind: 'lookup',
      options: accounts.map((account) => ({
        id: account.id,
        code: account.account_code,
        label: `${account.account_code} — ${account.name_ro}`,
      })),
    },
    { key: 'debit', header: t.accounting.opening.debit, kind: 'amount', width: '10rem' },
    { key: 'credit', header: t.accounting.opening.credit, kind: 'amount', width: '10rem' },
  ]

  const save = useMutation({
    mutationFn: () =>
      addGlRows(
        contents.id,
        rows
          .filter((row) => row.account_id !== '')
          .map((row) => ({
            account_id: row.account_id,
            // Canonical already: the grid stores a point, whichever key produced it.
            debit: row.debit || '0',
            credit: row.credit || '0',
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
        <div className="flex flex-col gap-2 rounded border border-border bg-surface p-3">
          {/* The same primitive as the manual note (F1.G2): a surface that is
              not document lines, served by `EntryGrid` without a fork -- which
              is the criterion that makes it a general primitive rather than a
              lines grid. Ctrl+Enter saves the rows; no key handler here (C40). */}
          <Card padding="none">
            <EntryGrid<Draft>
              columns={glColumns}
              rows={rows}
              onChange={setRows}
              newRow={() => ({ ...EMPTY })}
              onValidate={() => {
                if (!rows.every((row) => row.account_id === '') && !save.isPending) save.mutate()
              }}
              balance={{ debit: 'debit', credit: 'credit' }}
              label={t.accounting.opening.title}
              strings={t.accounting.entryGrid}
              footer={<span className="text-xs text-ink-muted">{t.accounting.entryGrid.keys}</span>}
            />
          </Card>
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="secondary"
              type="button"
              onClick={() => setRows((current) => [...current, { ...EMPTY }])}
            >
              {t.accounting.opening.addRow}
            </Button>
            <Button variant="secondary"
              type="button"
              onClick={() => save.mutate()}
              disabled={rows.every((row) => row.account_id === '') || save.isPending}
            >
              {t.accounting.opening.saveRows}
            </Button>
          </div>
          {save.isError && <Failure error={save.error} />}
        </div>
      )}

      {editable && (
        <>
          <PartnerRows
            accounts={accounts}
            batchId={contents.id}
            kind="receivables"
            onSaved={onChanged}
          />
          <PartnerRows
            accounts={accounts}
            batchId={contents.id}
            kind="payables"
            onSaved={onChanged}
          />
          <InventoryRows accounts={accounts} batchId={contents.id} onSaved={onChanged} />
          <AssetRows accounts={accounts} batchId={contents.id} onSaved={onChanged} />
          <CumulativeRows
            batchId={contents.id}
            asOfDate={contents.as_of_date}
            employees={employees.data ?? []}
            onSaved={onChanged}
          />
        </>
      )}

      {(contents.receivables.length > 0 || contents.payables.length > 0) && (
        <p className="text-sm text-ink-muted">{t.accounting.opening.analyticalHint}</p>
      )}

      <SavedSets contents={contents} byId={byId} employees={employees.data ?? []} />

      <div className="flex flex-wrap items-center gap-4">
        {contents.status === 'draft' && (
          <Button variant="secondary"
            type="button"
            onClick={() => validate.mutate()}
            disabled={contents.gl.length === 0 || validate.isPending}
          >
            {t.accounting.opening.validate}
          </Button>
        )}
        {contents.status === 'validated' && (
          <Button variant="secondary"
            type="button"
            onClick={() => post.mutate()}
            disabled={post.isPending}
          >
            {t.accounting.opening.post}
          </Button>
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

/**
 * Receivables or payables: a balance, plus who owes it.
 *
 * The partner is searched, never typed. `masterdata/partners` answers at most
 * 200 rows and does not paginate, so narrowing is the query's job -- a client
 * that paged over that on its own would be inventing an order the server never
 * promised.
 *
 * Whether the detail agrees with its control account is checked by the server
 * (`opening.analytical_mismatch`). Nothing here re-checks it: two opinions about
 * the same arithmetic drift, and the one in the browser is the one nobody audits.
 */
function PartnerRows({
  accounts,
  batchId,
  kind,
  onSaved,
}: {
  accounts: Account[]
  batchId: string
  kind: 'receivables' | 'payables'
  onSaved: () => Promise<void> | void
}) {
  const [search, setSearch] = useState('')
  const [partnerId, setPartnerId] = useState('')
  const [accountId, setAccountId] = useState('')
  const [amount, setAmount] = useState('')

  // A receivable is a debit balance and a payable a credit one. Not a choice the
  // form offers: offering it would be offering the mistake.
  const receivable = kind === 'receivables'

  const partners = useQuery({
    queryKey: ['partners', search, receivable ? 'customer' : 'supplier'],
    queryFn: () =>
      listPartners({ q: search || undefined, role: receivable ? 'customer' : 'supplier' }),
  })

  const add = useMutation({
    mutationFn: () => {
      const row = {
        account_id: accountId,
        partner_id: partnerId,
        debit: receivable ? amount.replace(',', '.') : '0',
        credit: receivable ? '0' : amount.replace(',', '.'),
      }
      return addPartnerRows(batchId, receivable ? { receivables: [row] } : { payables: [row] })
    },
    onSuccess: async () => {
      setPartnerId('')
      setAmount('')
      await onSaved()
    },
  })

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded border border-border bg-surface p-3"
      onSubmit={(event) => {
        event.preventDefault()
        add.mutate()
      }}
    >
      <span className="w-full text-sm font-semibold">
        {receivable ? t.accounting.opening.receivables : t.accounting.opening.payables}
      </span>

      <Field label={t.accounting.opening.partner}>
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t.accounting.opening.partnerSearch}
          className="w-64"
          aria-label={t.accounting.opening.partnerSearch}
        />
      </Field>

      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-ink-muted">&nbsp;</span>
        <Select
          value={partnerId}
          onChange={(event) => setPartnerId(event.target.value)}
          aria-label={`${t.accounting.opening.partner} ${
            receivable ? t.accounting.opening.receivables : t.accounting.opening.payables
          }`}
        >
          <option value="" />
          {(partners.data ?? []).map((partner: Partner) => (
            <option key={partner.id} value={partner.id}>
              {partner.legal_name}
              {partner.idno ? ` — ${partner.idno}` : ''}
            </option>
          ))}
        </Select>
      </label>

      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.opening.account}</span>
        <Select
          value={accountId}
          onChange={(event) => setAccountId(event.target.value)}
          aria-label={`${t.accounting.opening.account} ${
            receivable ? t.accounting.opening.receivables : t.accounting.opening.payables
          }`}
        >
          <option value="" />
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.account_code} — {account.name_ro}
            </option>
          ))}
        </Select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">
          {receivable ? t.accounting.opening.debit : t.accounting.opening.credit}
        </span>
        <Input
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          inputMode="decimal"
          className="tabular w-36 text-right"
          aria-label={`${t.accounting.opening.total} ${
            receivable ? t.accounting.opening.receivables : t.accounting.opening.payables
          }`}
        />
      </label>

      <Button variant="primary"
        type="submit"
        disabled={partnerId === '' || accountId === '' || amount === '' || add.isPending}
      >
        {receivable ? t.accounting.opening.addReceivable : t.accounting.opening.addPayable}
      </Button>

      {partners.data?.length === 0 && (
        <span className="text-sm text-ink-muted">{t.accounting.opening.partnerNone}</span>
      )}
      {add.isError && (
        <div className="w-full">
          <Failure error={add.error} />
        </div>
      )}
    </form>
  )
}

/** A reference to the source system: typed, or generated when there is none to type. */
function Reference({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-1 text-sm">
      <span className="text-ink-muted">{label}</span>
      <span className="flex gap-2">
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-80 font-mono"
          aria-label={label}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onChange(crypto.randomUUID())}
        >
          {t.accounting.opening.generate}
        </Button>
      </span>
    </div>
  )
}

function AccountChoice({
  visible,
  name,
  accounts,
  value,
  onChange,
}: {
  visible: string
  /** The accessible name -- the visible label plus which set, so two forms on one screen differ. */
  name: string
  accounts: Account[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-1 flex-col gap-1 text-sm">
      <span className="text-ink-muted">{visible}</span>
      <Select value={value} onChange={(event) => onChange(event.target.value)} aria-label={name}>
        <option value="" />
        {accounts.map((account) => (
          <option key={account.id} value={account.id}>
            {account.account_code} — {account.name_ro}
          </option>
        ))}
      </Select>
    </label>
  )
}

function Amount({
  visible,
  name,
  value,
  onChange,
}: {
  visible: string
  name: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-ink-muted">{visible}</span>
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        inputMode="decimal"
        className="tabular w-32 text-right"
        aria-label={name}
      />
    </label>
  )
}

/**
 * Stock on hand: the account, what and where, the quantity with its unit, the cost.
 *
 * `total_cost` is what posts; the unit cost travels with it and is never
 * multiplied here (ADR-038 section 7.3 -- and the rounding that would take is
 * an open decision). Whether the stock agrees with its control account is the
 * server's check, as for the partner sets.
 */
function InventoryRows({
  accounts,
  batchId,
  onSaved,
}: {
  accounts: Account[]
  batchId: string
  onSaved: () => Promise<void> | void
}) {
  const strings = t.accounting.opening
  const [accountId, setAccountId] = useState('')
  const [itemId, setItemId] = useState('')
  const [uomId, setUomId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unitCost, setUnitCost] = useState('')
  const [totalCost, setTotalCost] = useState('')
  const [lot, setLot] = useState('')

  const add = useMutation({
    mutationFn: () =>
      addAnalyticalRows(batchId, {
        inventory: [
          {
            account_id: accountId,
            item_id: itemId,
            uom_id: uomId,
            quantity: decimal(quantity),
            total_cost: decimal(totalCost),
            unit_cost: unitCost === '' ? null : decimal(unitCost),
            lot: lot === '' ? null : lot,
          },
        ],
      }),
    onSuccess: async () => {
      setItemId('')
      setQuantity('')
      setUnitCost('')
      setTotalCost('')
      setLot('')
      await onSaved()
    },
  })

  const ready =
    accountId !== '' && itemId !== '' && uomId !== '' && quantity !== '' && totalCost !== ''

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded border border-border bg-surface p-3"
      onSubmit={(event) => {
        event.preventDefault()
        add.mutate()
      }}
    >
      <span className="w-full text-sm font-semibold">{strings.inventory}</span>
      <AccountChoice
        visible={strings.account}
        name={`${strings.account} ${strings.inventory}`}
        accounts={accounts}
        value={accountId}
        onChange={setAccountId}
      />
      <Reference label={strings.itemReference} value={itemId} onChange={setItemId} />
      <Reference label={strings.uomReference} value={uomId} onChange={setUomId} />
      <Amount
        visible={strings.quantity}
        name={`${strings.quantity} ${strings.inventory}`}
        value={quantity}
        onChange={setQuantity}
      />
      <Amount
        visible={strings.unitCost}
        name={`${strings.unitCost} ${strings.inventory}`}
        value={unitCost}
        onChange={setUnitCost}
      />
      <Amount
        visible={strings.totalCost}
        name={`${strings.totalCost} ${strings.inventory}`}
        value={totalCost}
        onChange={setTotalCost}
      />
      <Field label={strings.lot}>
        <Input value={lot} onChange={(event) => setLot(event.target.value)} className="w-36" />
      </Field>
      <Button variant="primary" type="submit" disabled={!ready || add.isPending}>
        {strings.addInventory}
      </Button>
      <p className="w-full text-sm text-ink-muted">{strings.itemReferenceHint}</p>
      {add.isError && (
        <div className="w-full">
          <Failure error={add.error} />
        </div>
      )}
    </form>
  )
}

/**
 * A fixed asset: two accounts and two amounts, because that is what one is in a
 * ledger. The cost is a debit on one account and the depreciation already taken
 * a credit on another; a single net book value would post and lose both numbers.
 * The in-service date and the remaining months do not post -- they ride with
 * the batch so the asset module has a schedule rather than a guess.
 */
function AssetRows({
  accounts,
  batchId,
  onSaved,
}: {
  accounts: Account[]
  batchId: string
  onSaved: () => Promise<void> | void
}) {
  const strings = t.accounting.opening
  const [assetId, setAssetId] = useState('')
  const [costAccountId, setCostAccountId] = useState('')
  const [depreciationAccountId, setDepreciationAccountId] = useState('')
  const [entryCost, setEntryCost] = useState('')
  const [accumulated, setAccumulated] = useState('')
  const [inServiceDate, setInServiceDate] = useState('')
  const [remainingMonths, setRemainingMonths] = useState('')

  const add = useMutation({
    mutationFn: () =>
      addAnalyticalRows(batchId, {
        assets: [
          {
            asset_id: assetId,
            cost_account_id: costAccountId,
            depreciation_account_id: depreciationAccountId,
            entry_cost: decimal(entryCost),
            accumulated_depreciation: accumulated === '' ? '0' : decimal(accumulated),
            in_service_date: inServiceDate,
            remaining_months: remainingMonths === '' ? null : Number.parseInt(remainingMonths, 10),
          },
        ],
      }),
    onSuccess: async () => {
      setAssetId('')
      setEntryCost('')
      setAccumulated('')
      setInServiceDate('')
      setRemainingMonths('')
      await onSaved()
    },
  })

  const ready =
    assetId !== '' &&
    costAccountId !== '' &&
    depreciationAccountId !== '' &&
    entryCost !== '' &&
    inServiceDate !== ''

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded border border-border bg-surface p-3"
      onSubmit={(event) => {
        event.preventDefault()
        add.mutate()
      }}
    >
      <span className="w-full text-sm font-semibold">{strings.assets}</span>
      <AccountChoice
        visible={strings.costAccount}
        name={`${strings.costAccount} ${strings.assets}`}
        accounts={accounts}
        value={costAccountId}
        onChange={setCostAccountId}
      />
      <AccountChoice
        visible={strings.depreciationAccount}
        name={`${strings.depreciationAccount} ${strings.assets}`}
        accounts={accounts}
        value={depreciationAccountId}
        onChange={setDepreciationAccountId}
      />
      <Amount
        visible={strings.entryCost}
        name={`${strings.entryCost} ${strings.assets}`}
        value={entryCost}
        onChange={setEntryCost}
      />
      <Amount
        visible={strings.accumulatedDepreciation}
        name={`${strings.accumulatedDepreciation} ${strings.assets}`}
        value={accumulated}
        onChange={setAccumulated}
      />
      <Field label={strings.inServiceDate}>
        <Input
          type="date"
          value={inServiceDate}
          onChange={(event) => setInServiceDate(event.target.value)}
          className="w-44"
        />
      </Field>
      <Field label={strings.remainingMonths}>
        <Input
          value={remainingMonths}
          onChange={(event) => setRemainingMonths(event.target.value)}
          inputMode="numeric"
          className="tabular w-24 text-right"
        />
      </Field>
      <Reference label={strings.assetReference} value={assetId} onChange={setAssetId} />
      <Button variant="primary" type="submit" disabled={!ready || add.isPending}>
        {strings.addAsset}
      </Button>
      <p className="w-full text-sm text-ink-muted">{strings.assetReferenceHint}</p>
      {add.isError && (
        <div className="w-full">
          <Failure error={add.error} />
        </div>
      )}
    </form>
  )
}

/**
 * Year-to-date amounts of one employee -- the set that makes a mid-year start
 * possible (ADR-061). Three keys, each a magnitude; the window starts on 1
 * January or on the hiring date, and it is typed rather than assumed.
 */
function CumulativeRows({
  batchId,
  asOfDate,
  employees,
  onSaved,
}: {
  batchId: string
  asOfDate: string
  employees: Employee[]
  onSaved: () => Promise<void> | void
}) {
  const strings = t.accounting.opening
  const [employeeId, setEmployeeId] = useState('')
  const [code, setCode] = useState<CumulativeCode>('income_tax.taxable_income')
  const [sum, setSum] = useState('')
  const [fromDate, setFromDate] = useState(`${asOfDate.slice(0, 4)}-01-01`)

  const add = useMutation({
    mutationFn: () =>
      addAnalyticalRows(batchId, {
        payroll_cumulatives: [
          { employee_id: employeeId, code, amount: decimal(sum), from_date: fromDate },
        ],
      }),
    onSuccess: async () => {
      setSum('')
      await onSaved()
    },
  })

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded border border-border bg-surface p-3"
      onSubmit={(event) => {
        event.preventDefault()
        add.mutate()
      }}
    >
      <span className="w-full text-sm font-semibold">{strings.payrollCumulatives}</span>
      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-ink-muted">{strings.employee}</span>
        <Select
          value={employeeId}
          onChange={(event) => setEmployeeId(event.target.value)}
          aria-label={`${strings.employee} ${strings.payrollCumulatives}`}
        >
          <option value="" />
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.last_name} {employee.first_name}
            </option>
          ))}
        </Select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{strings.cumulativeCode}</span>
        <Select
          value={code}
          onChange={(event) => setCode(event.target.value as CumulativeCode)}
          className="w-64"
          aria-label={strings.cumulativeCode}
        >
          {CUMULATIVE_CODES.map((key) => (
            <option key={key} value={key}>
              {CUMULATIVE_LABEL[key]}
            </option>
          ))}
        </Select>
      </label>
      <Amount
        visible={strings.amount}
        name={`${strings.amount} ${strings.payrollCumulatives}`}
        value={sum}
        onChange={setSum}
      />
      <Field label={strings.fromDate}>
        <Input
          type="date"
          value={fromDate}
          onChange={(event) => setFromDate(event.target.value)}
          className="w-44"
        />
      </Field>
      <Button
        variant="primary"
        type="submit"
        disabled={employeeId === '' || sum === '' || fromDate === '' || add.isPending}
      >
        {strings.addCumulative}
      </Button>
      {employees.length === 0 && (
        <span className="text-sm text-ink-muted">{strings.employeeNone}</span>
      )}
      <p className="w-full text-sm text-ink-muted">{strings.fromDateHint}</p>
      <p className="w-full text-sm text-ink-muted">{strings.cumulativesNote}</p>
      {add.isError && (
        <div className="w-full">
          <Failure error={add.error} />
        </div>
      )}
    </form>
  )
}

/**
 * The three sets as the server holds them, read back after each save. Nothing
 * here totals: the agreement with the control account is the server's check.
 */
function SavedSets({
  contents,
  byId,
  employees,
}: {
  contents: BatchContents
  byId: Map<string, Account>
  employees: Employee[]
}) {
  const strings = t.accounting.opening
  const code = (id: string) => byId.get(id)?.account_code ?? id
  const names = new Map(
    employees.map((employee) => [employee.id, `${employee.last_name} ${employee.first_name}`]),
  )

  const inventoryColumns: Column<InventoryRow>[] = [
    {
      key: 'account',
      header: strings.account,
      cell: (row) => <span className="font-mono">{code(row.account_id)}</span>,
      width: '8rem',
    },
    {
      key: 'item',
      header: strings.itemReference,
      cell: (row) => <span className="font-mono">{row.item_id}</span>,
    },
    { key: 'lot', header: strings.lot, cell: (row) => row.lot ?? '', width: '8rem' },
    // The quantity as the server stores it, six decimals; there is no display
    // rule for quantities yet, and inventing one here would be the local
    // formatting C18 forbids.
    { key: 'quantity', header: strings.quantity, cell: (row) => row.quantity, numeric: true, width: '9rem' },
    {
      key: 'total_cost',
      header: strings.totalCost,
      cell: (row) => amount(row.total_cost),
      numeric: true,
      width: '10rem',
    },
  ]

  const assetColumns: Column<AssetRow>[] = [
    {
      key: 'asset',
      header: strings.assetReference,
      cell: (row) => <span className="font-mono">{row.asset_id}</span>,
    },
    {
      key: 'cost_account',
      header: strings.costAccount,
      cell: (row) => <span className="font-mono">{code(row.cost_account_id)}</span>,
      width: '8rem',
    },
    {
      key: 'depreciation_account',
      header: strings.depreciationAccount,
      cell: (row) => <span className="font-mono">{code(row.depreciation_account_id)}</span>,
      width: '8rem',
    },
    {
      key: 'entry_cost',
      header: strings.entryCost,
      cell: (row) => amount(row.entry_cost),
      numeric: true,
      width: '10rem',
    },
    {
      key: 'accumulated',
      header: strings.accumulatedDepreciation,
      cell: (row) => amount(row.accumulated_depreciation),
      numeric: true,
      width: '10rem',
    },
    {
      key: 'in_service',
      header: strings.inServiceDate,
      cell: (row) => row.in_service_date,
      width: '9rem',
    },
  ]

  const cumulativeColumns: Column<PayrollCumulativeRow>[] = [
    {
      key: 'employee',
      header: strings.employee,
      cell: (row) => names.get(row.employee_id) ?? <span className="font-mono">{row.employee_id}</span>,
    },
    {
      key: 'code',
      header: strings.cumulativeCode,
      cell: (row) => CUMULATIVE_LABEL[row.code],
      width: '14rem',
    },
    { key: 'amount', header: strings.amount, cell: (row) => amount(row.amount), numeric: true, width: '10rem' },
    { key: 'from', header: strings.fromDate, cell: (row) => row.from_date, width: '9rem' },
  ]

  return (
    <>
      {contents.inventory.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">{strings.inventory}</h2>
          <DataGrid
            columns={inventoryColumns}
            rows={contents.inventory}
            rowKey={(row) => `${row.account_id}:${row.item_id}:${row.lot ?? ''}`}
            emptyMessage={strings.empty}
          />
        </div>
      )}
      {contents.assets.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">{strings.assets}</h2>
          <DataGrid
            columns={assetColumns}
            rows={contents.assets}
            rowKey={(row) => row.asset_id}
            emptyMessage={strings.empty}
          />
        </div>
      )}
      {contents.payroll_cumulatives.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">{strings.payrollCumulatives}</h2>
          <DataGrid
            columns={cumulativeColumns}
            rows={contents.payroll_cumulatives}
            rowKey={(row) => `${row.employee_id}:${row.code}`}
            emptyMessage={strings.empty}
          />
          <p className="text-sm text-ink-muted">{strings.cumulativesNote}</p>
        </div>
      )}
    </>
  )
}
