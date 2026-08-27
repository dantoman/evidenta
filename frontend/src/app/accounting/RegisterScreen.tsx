/**
 * The register: what was actually posted, entry by entry, with its lines.
 *
 * It exists because of what the slice was missing, not for completeness. After
 * posting a note the only evidence was a balance that had moved -- and a balance
 * is a summary, so a person who mistyped an amount had no way to see what they
 * had written, let alone which entry to correct.
 *
 * **Not `DataGrid`.** An entry is a header with lines under it, and the grid's
 * contract is one row per record; a nested table pushed through it would be the
 * third grid component `C17` forbids, arriving by accident. This is a plain
 * table, the same choice the manual note makes and for the same reason.
 *
 * Amounts arrive as strings and are formatted as strings (C18). Nothing here
 * sums a column: the entry totals are the server's, and the balance screen is
 * where totals across entries belong (C19).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { amount, date as formatDate } from '@/shared/format'
import { listEntries, reverseEntry, type JournalEntryRead } from '@/shared/api/ledger'
import { Failure } from '@/shared/Failure'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'

function yearStart(): string {
  return `${new Date().getFullYear()}-01-01`
}

function yearEnd(): string {
  return `${new Date().getFullYear()}-12-31`
}

export function RegisterScreen() {
  const { companyId = '' } = useParams()
  const [from, setFrom] = useState(yearStart)
  const [to, setTo] = useState(yearEnd)
  const [window, setWindow] = useState({ from: yearStart(), to: yearEnd() })

  const register = useQuery({
    queryKey: ['register', companyId, window.from, window.to],
    queryFn: () => listEntries(companyId, window.from, window.to),
  })

  return (
    <section className="flex flex-col gap-4">
      {/* Out of this screen and across to its siblings. The chart is the
          company's home: every other accounting screen is reached from it, so
          it is the one link all three carry. */}
      <nav className="flex gap-4 text-sm">
        <Link to={`/companii/${companyId}/plan-de-conturi`} className="text-accent">
          {t.accounting.chart.title}
        </Link>
        <Link to={`/companii/${companyId}/note`} className="text-accent">
          {t.accounting.entry.title}
        </Link>
        <Link to={`/companii/${companyId}/balanta`} className="text-accent">
          {t.accounting.balance.title}
        </Link>
      </nav>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-semibold">{t.accounting.register.title}</h1>
        <form
          className="flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            setWindow({ from, to })
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.accounting.balance.from}</span>
            <input
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
              className={FIELD}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.accounting.balance.to}</span>
            <input
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
              className={FIELD}
            />
          </label>
          <button
            type="submit"
            className="rounded border border-border bg-surface px-3 text-sm text-accent"
          >
            {t.accounting.balance.show}
          </button>
        </form>
      </header>

      {register.isPending && <p className="text-sm text-ink-muted">{t.app.loading}</p>}
      {register.isError && <Failure error={register.error} />}

      {register.data?.truncated && (
        <p className="text-sm text-danger">{t.accounting.register.truncated}</p>
      )}

      {register.data?.entries.length === 0 && (
        <p className="text-sm text-ink-muted">{t.accounting.register.empty}</p>
      )}

      {register.data?.entries.map((entry) => (
        <Entry key={entry.id} entry={entry} companyId={companyId} />
      ))}
    </section>
  )
}

function Entry({ entry, companyId }: { entry: JournalEntryRead; companyId: string }) {
  const queryClient = useQueryClient()
  const [correcting, setCorrecting] = useState(false)

  // Posted, and not already cancelled. The service refuses a second storno
  // anyway; the screen says so first, rather than offering a control whose
  // refusal the person has to discover by pressing it.
  const correctable = entry.status === 'posted' && entry.reversed_by_entry_id === null

  return (
    <article className="rounded border border-border bg-surface">
      <header className="flex flex-wrap items-baseline justify-between gap-4 border-b border-border px-3 py-2">
        <div className="flex flex-wrap items-baseline gap-3 text-sm">
          <span className="font-mono font-semibold">{entry.entry_number}</span>
          <span className="text-ink-muted">{formatDate(entry.accounting_date)}</span>
          <span>{entry.description}</span>
        </div>
        <div className="flex items-baseline gap-3 text-sm">
          {/* Both directions of R14, named rather than implied: an entry that
              cancels another, and one that has itself been cancelled. Two
              entries with opposite amounts and nothing saying which is which is
              exactly what the second link exists to prevent. */}
          {entry.reverses_entry_id && (
            <span className="text-ink-muted">{t.accounting.register.reverses}</span>
          )}
          {entry.reversed_by_entry_id && (
            <span className="text-danger">{t.accounting.register.reversed}</span>
          )}
          <span className="tabular font-medium">{amount(entry.total_debit)}</span>
          {correctable && (
            <button
              type="button"
              onClick={() => setCorrecting((open) => !open)}
              className="text-sm text-accent"
            >
              {correcting ? t.accounting.register.cancel : t.accounting.register.reverse}
            </button>
          )}
        </div>
      </header>

      {correcting && (
        <Reversal
          entry={entry}
          companyId={companyId}
          onDone={async () => {
            setCorrecting(false)
            // The register and the balance both changed. Invalidated rather than
            // patched: what the server wrote is what should be shown, not what
            // the client assumed it wrote.
            await queryClient.invalidateQueries({ queryKey: ['register', companyId] })
            await queryClient.invalidateQueries({ queryKey: ['trial-balance', companyId] })
          }}
        />
      )}

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-ink-muted">
            <th className="px-3 font-medium">{t.accounting.register.account}</th>
            <th className="px-3 font-medium">{t.accounting.register.description}</th>
            <th className="px-3 text-right font-medium">{t.accounting.register.debit}</th>
            <th className="px-3 text-right font-medium">{t.accounting.register.credit}</th>
          </tr>
        </thead>
        <tbody>
          {entry.lines.map((line) => (
            <tr key={line.line_number} className="border-t border-border">
              <td className="px-3">
                <span className="font-mono">{line.account_code}</span>{' '}
                <span className="text-ink-muted">{line.name_ro}</span>
              </td>
              <td className="px-3 text-ink-muted">{line.description}</td>
              <td className="px-3 text-right tabular">{amount(line.debit)}</td>
              <td className="px-3 text-right tabular">{amount(line.credit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  )
}

/**
 * The correction form: a date and a reason, both required, neither guessed.
 *
 * The date is the correction's own (ADR-006's second date) and has no default,
 * because which date a storno carries is open (ADR-007) and the server refuses
 * to answer it. Seeding this field with today would answer it here instead --
 * quietly, and in the layer with the least standing to.
 */
function Reversal({
  entry,
  companyId,
  onDone,
}: {
  entry: JournalEntryRead
  companyId: string
  onDone: () => void
}) {
  const [accountingDate, setAccountingDate] = useState('')
  const [reason, setReason] = useState('')
  // One key per correction, allocated when the form opens: a second press must
  // not become a second storno.
  const [idempotencyKey] = useState(() => crypto.randomUUID())

  const reverse = useMutation({
    mutationFn: () =>
      reverseEntry(
        entry.id,
        { company_id: companyId, accounting_date: accountingDate, reason: reason.trim() },
        idempotencyKey,
      ),
    onSuccess: onDone,
  })

  return (
    <form
      className="flex flex-wrap items-end gap-4 border-b border-border px-3 py-2"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        reverse.mutate()
      }}
    >
      <p className="w-full text-sm text-ink-muted">{t.accounting.register.reverseHint}</p>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.register.reverseDate}</span>
        <input
          type="date"
          value={accountingDate}
          onChange={(event) => setAccountingDate(event.target.value)}
          className={FIELD}
        />
      </label>
      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.register.reverseReason}</span>
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={500}
          className={FIELD}
        />
      </label>
      <button
        type="submit"
        disabled={accountingDate === '' || reason.trim() === '' || reverse.isPending}
        className="rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted"
      >
        {reverse.isPending
          ? t.accounting.register.reversing
          : t.accounting.register.reverseSubmit}
      </button>
      {reverse.isError && (
        <div className="w-full">
          <Failure error={reverse.error} />
        </div>
      )}
    </form>
  )
}
