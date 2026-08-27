/**
 * The manual journal note -- the one screen that writes to the ledger.
 *
 * A plain table of inputs, not `EntryGrid`. The keyboard-entry contract (`OD-36`)
 * is open and `EntryGrid` is the component that will have to honour it; building
 * it here, to get four columns on screen, would settle that contract by accident.
 * This is the smallest thing that posts a real entry, and it says so.
 *
 * **The balance check here blocks a button; it does not decide anything.** Σ
 * debit = Σ credit is checked by the engine and by the database (R11), and this
 * screen would be wrong to imply otherwise -- what it saves is a round trip and a
 * refusal the person can already see coming.
 *
 * Amounts are typed as text and sent as text. They never pass through a number:
 * the server stores `numeric`, and a float here would round the value before it
 * ever reached the check that was supposed to catch it.
 *
 * The idempotency key belongs to the note, not to the click (C9, R19). It is
 * generated once when the form is opened, so pressing "post" twice -- or retrying
 * after a lost answer -- posts once and the second attempt says so.
 */

import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { listAccounts } from '@/shared/api/coa'
import { postManualEntry, type ManualLine } from '@/shared/api/ledger'
import { Failure } from '@/shared/Failure'

const FIELD = 'w-full rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

interface Draft {
  account_id: string
  debit: string
  credit: string
  description: string
}

const EMPTY: Draft = { account_id: '', debit: '', credit: '', description: '' }

/**
 * Decimal addition over the strings the user typed, in the smallest unit.
 *
 * Bani, as integers, rather than `Number(value)`: two decimals of a sum are
 * exactly what floating point gets wrong, and this total is the thing the person
 * reads to decide whether the note is finished. Anything the pattern does not
 * match counts as zero and the server refuses it -- this is a display total, and
 * it is allowed to be silent about a value that is not a number yet.
 */
function bani(value: string): number {
  const match = /^\s*(-?)(\d*)(?:[.,](\d{0,2}))?\s*$/.exec(value)
  if (!match) return 0
  const [, sign, whole, fraction = ''] = match
  const amount = Number(whole || '0') * 100 + Number(fraction.padEnd(2, '0') || '0')
  return sign === '-' ? -amount : amount
}

function formatted(total: number): string {
  const sign = total < 0 ? '-' : ''
  const absolute = Math.abs(total)
  return `${sign}${Math.floor(absolute / 100)},${String(absolute % 100).padStart(2, '0')}`
}

/** Today, as the server writes dates. Not a locale format -- an input value. */
function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

export function ManualEntryScreen() {
  const { companyId = '' } = useParams()

  const [accountingDate, setAccountingDate] = useState(today())
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<Draft[]>([{ ...EMPTY }, { ...EMPTY }])
  // One key per note, allocated when the form appears. Regenerating it per click
  // would make every retry a new posting, which is the failure the header is
  // about.
  const [idempotencyKey, setKey] = useState(() => crypto.randomUUID())

  const accounts = useQuery({
    queryKey: ['accounts', companyId, ''],
    queryFn: () => listAccounts(companyId),
  })

  const post = useMutation({
    mutationFn: () =>
      postManualEntry(
        {
          company_id: companyId,
          accounting_date: accountingDate,
          description: description.trim(),
          lines: lines
            .filter((line) => line.account_id !== '')
            .map<ManualLine>((line) => ({
              account_id: line.account_id,
              debit: line.debit.replace(',', '.') || '0',
              credit: line.credit.replace(',', '.') || '0',
              description: line.description.trim() || undefined,
            })),
        },
        idempotencyKey,
      ),
    onSuccess: () => {
      // A posted note is finished. The next one is a new note, so it gets a new
      // key and an empty form -- reusing either would attach the next entry to
      // the last one's identity.
      setKey(crypto.randomUUID())
      setLines([{ ...EMPTY }, { ...EMPTY }])
      setDescription('')
    },
  })

  const totalDebit = lines.reduce((sum, line) => sum + bani(line.debit), 0)
  const totalCredit = lines.reduce((sum, line) => sum + bani(line.credit), 0)
  const difference = totalDebit - totalCredit

  const filled = lines.filter((line) => line.account_id !== '')
  const balanced = difference === 0 && totalDebit > 0
  const postable =
    balanced && filled.length > 0 && description.trim() !== '' && !post.isPending

  const set = (index: number, field: keyof Draft, value: string) =>
    setLines((current) =>
      current.map((line, at) => (at === index ? { ...line, [field]: value } : line)),
    )

  return (
    <section className="flex flex-col gap-4">
      {/* Out of this screen and across to its siblings. The chart is the
          company's home: every other accounting screen is reached from it, so
          it is the one link all three carry. */}
      <nav className="flex gap-4 text-sm">
        <Link to={`/companii/${companyId}/plan-de-conturi`} className="text-accent">
          {t.accounting.chart.title}
        </Link>
        <Link to={`/companii/${companyId}/registru`} className="text-accent">
          {t.accounting.register.title}
        </Link>
        <Link to={`/companii/${companyId}/balanta`} className="text-accent">
          {t.accounting.balance.title}
        </Link>
      </nav>
      <h1 className="text-base font-semibold">{t.accounting.entry.title}</h1>

      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-muted">{t.accounting.entry.date}</span>
          <input
            type="date"
            value={accountingDate}
            onChange={(event) => setAccountingDate(event.target.value)}
            className={`${FIELD} w-44`}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm">
          <span className="text-ink-muted">{t.accounting.entry.description}</span>
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={500}
            className={FIELD}
          />
        </label>
      </div>

      {accounts.isError && <Failure error={accounts.error} />}
      {accounts.data?.length === 0 && (
        <p className="text-sm text-ink-muted">{t.accounting.entry.noChart}</p>
      )}

      <div className="overflow-x-auto rounded border border-border bg-surface">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-ink-muted">
              <th className="px-2 font-medium">{t.accounting.entry.account}</th>
              <th className="px-2 font-medium">{t.accounting.entry.lineDescription}</th>
              <th className="px-2 text-right font-medium">{t.accounting.entry.debit}</th>
              <th className="px-2 text-right font-medium">{t.accounting.entry.credit}</th>
              <th className="px-2" />
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={index} className="border-b border-border last:border-0">
                <td className="px-2">
                  <select
                    value={line.account_id}
                    onChange={(event) => set(index, 'account_id', event.target.value)}
                    className={FIELD}
                    aria-label={`${t.accounting.entry.account} ${index + 1}`}
                  >
                    <option value="" />
                    {(accounts.data ?? []).map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.account_code} — {account.name_ro}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2">
                  <input
                    value={line.description}
                    onChange={(event) => set(index, 'description', event.target.value)}
                    maxLength={500}
                    className={FIELD}
                    aria-label={`${t.accounting.entry.lineDescription} ${index + 1}`}
                  />
                </td>
                <td className="px-2">
                  <input
                    value={line.debit}
                    onChange={(event) => set(index, 'debit', event.target.value)}
                    inputMode="decimal"
                    className={`${FIELD} tabular text-right`}
                    aria-label={`${t.accounting.entry.debit} ${index + 1}`}
                  />
                </td>
                <td className="px-2">
                  <input
                    value={line.credit}
                    onChange={(event) => set(index, 'credit', event.target.value)}
                    inputMode="decimal"
                    className={`${FIELD} tabular text-right`}
                    aria-label={`${t.accounting.entry.credit} ${index + 1}`}
                  />
                </td>
                <td className="px-2 text-right">
                  <button
                    type="button"
                    onClick={() =>
                      setLines((current) => current.filter((_, at) => at !== index))
                    }
                    disabled={lines.length <= 1}
                    className="text-sm text-accent disabled:text-ink-muted"
                  >
                    {t.accounting.entry.removeLine}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border font-medium">
              <td className="px-2" colSpan={2}>
                {t.accounting.entry.total}
              </td>
              <td className="px-2 text-right tabular">{formatted(totalDebit)}</td>
              <td className="px-2 text-right tabular">{formatted(totalCredit)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={() => setLines((current) => [...current, { ...EMPTY }])}
          className={BUTTON}
        >
          {t.accounting.entry.addLine}
        </button>
        <button type="button" onClick={() => post.mutate()} disabled={!postable} className={BUTTON}>
          {post.isPending ? t.accounting.entry.posting : t.accounting.entry.post}
        </button>
        {difference !== 0 && (
          <span className="text-sm text-danger">
            {t.accounting.entry.difference}: {formatted(difference)}
          </span>
        )}
      </div>

      {difference !== 0 && filled.length > 0 && (
        <p className="text-sm text-ink-muted">{t.accounting.entry.unbalanced}</p>
      )}
      {post.isError && <Failure error={post.error} />}
      {post.isSuccess && (
        <p className="text-sm text-ink-muted">
          {post.data.posted_now ? t.accounting.entry.posted : t.accounting.entry.postedAgain}
        </p>
      )}
    </section>
  )
}
