/**
 * Panoul de control -- the company's month, on one screen.
 *
 * **Every figure is the server's** (C19). The screen formats decimal strings and
 * never adds one to another: not the KPI, not the register's footer, not the
 * balance check. The one place a number becomes a number is the height of a bar,
 * which is geometry rather than a figure -- and the bar carries the amount as a
 * label, formatted from the string.
 *
 * **Half of this screen states what cannot be known yet, and that is the design.**
 * Three cards of the mock have no source behind them and say so where the figure
 * would be:
 *
 * * *De depus* -- the reporting calendar is a fiscal parameter with a normative
 *   act behind it (R15); `fiscal_parameter` is empty. A date here would be the
 *   defect the rule exists to prevent.
 * * *TVA de plată* -- nothing computes a VAT return. Two account balances
 *   subtracted would look like the answer and carry none of its rules.
 * * *Creanţe scadente* and *Vechimea creanţelor* -- a document carries a date, not
 *   a payment term, so "scadent" cannot be said at all.
 *
 * Drawn rather than dropped, because a panel with a marked gap tells an
 * accountant what the product does not do yet; a panel that quietly omits four
 * cards tells them nothing, and one that fills them with zeros tells them
 * something false. The same choice the shell makes with the notification bell.
 */

import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'

import { t } from '@/locales'
import { getCompany } from '@/shared/api/companies'
import { overview, type DocumentWork, type PanelEntry, type Turnover } from '@/shared/api/overview'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { amount, date, month, monthShort, today } from '@/shared/format'
import {
  Badge,
  Button,
  Card,
  Field,
  Figure,
  Icon,
  Input,
  PageHeader,
  StatTile,
  type IconName,
} from '@/shared/ui'

/**
 * The query parameter that names the day. In the address, so a panel for March
 * can be linked to and comes back after a reload -- and absent when the day is
 * today, so the ordinary address stays the short one.
 */
const DAY_PARAM = 'la'

export function DashboardScreen() {
  const { companyId = '' } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()

  // Today is read once, at mount, and kept: the day is part of the query key, so
  // a clock crossing midnight while the screen is open must not silently refetch
  // a different month under the reader. A day chosen by hand lives in the
  // address instead, and the reader can see it there.
  const [mounted] = useState(today)
  const asked = params.get(DAY_PARAM) ?? mounted

  const panel = useQuery({
    queryKey: ['overview', companyId, asked],
    queryFn: () => overview(companyId, asked),
  })
  // The same key the company screen uses, so the two share one cached answer.
  // Only the currency is wanted here -- the amounts are the ledger's, but which
  // currency they are in is the company's.
  const company = useQuery({
    queryKey: ['company', companyId],
    queryFn: () => getCompany(companyId),
  })

  if (panel.isPending) {
    return <p className="type-body-md text-ink-muted">{t.app.loading}</p>
  }
  if (panel.isError) {
    return <Failure error={panel.error} />
  }

  const data = panel.data
  const currency = company.data?.functional_currency
  const previous = `${t.dashboard.turnoverPrevious} · ${amount(data.previous_month.debit)}`

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={month(data.month.start_date)}
        title={t.dashboard.title}
        lead={t.dashboard.lead}
        actions={
          <>
            {/* Which month. The panel followed the calendar alone at first, and
                on a company whose last posting was in March that read as
                "rulaj 0" beside a list of March entries -- correct, and
                unreadable. The day is a choice, and the choice is visible. */}
            <Field label={t.dashboard.asOf}>
              <Input
                type="date"
                value={asked}
                onChange={(event) => {
                  const chosen = event.target.value
                  if (!chosen) return
                  setParams(chosen === mounted ? {} : { [DAY_PARAM]: chosen }, { replace: true })
                }}
              />
            </Field>
            {/* Drawn and stopped, like the shell's bell: the button belongs to
                the mock, the state is the truth. */}
            <Button variant="secondary" icon="download" disabled title={t.dashboard.exportVatNotYet}>
              {t.dashboard.exportVat}
            </Button>
            <Button
              icon="file-plus"
              onClick={() => void navigate(`/companii/${companyId}/note`)}
            >
              {t.dashboard.newEntry}
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        <StatTile
          tone="inverse"
          icon="scale"
          label={t.dashboard.turnover}
          value={data.month.debit}
          currency={currency}
          note={previous}
        />
        <StatTile icon="receipt" label={t.dashboard.vat} value={null} note={t.dashboard.vatMissing} />
        <StatTile
          icon="clock"
          label={t.dashboard.receivables}
          value={null}
          note={t.dashboard.receivablesMissing}
        />
        <StatTile
          icon="wallet"
          label={t.dashboard.cash}
          value={data.cash ? data.cash.balance : null}
          currency={currency}
          note={
            data.cash
              ? `${t.dashboard.cashAccount} ${data.cash.account_code}`
              : t.dashboard.cashMissing
          }
        />
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] items-start gap-4">
        {/* The extract is the last five postings whenever they were, and the
            footer is this month's turnover: two windows on one card. Each says
            which -- on a company whose last posting was in March, five March
            rows over "Rulajul lunii 0,00" read as a contradiction until they
            did. */}
        <Card
          padding="none"
          eyebrow={extractWindow(data.latest_entries)}
          title={t.dashboard.register.title}
        >
          <div className="mt-4">
            <DataGrid
              columns={ENTRY_COLUMNS}
              rows={data.latest_entries}
              rowKey={(entry) => entry.id}
              density="compact"
              emptyMessage={t.dashboard.register.empty}
              onRowClick={() => void navigate(`/companii/${companyId}/registru`)}
              // The month's turnover, named as such. Not a sum of the five rows
              // above it -- those are the last five, and a footer that added
              // them up would be a total of an arbitrary window.
              serverTotals={{
                entry_number: `${t.dashboard.register.total} · ${month(data.month.start_date)}`,
                amount: amount(data.month.debit),
              }}
            />
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          <Card eyebrow={t.dashboard.deadlines.eyebrow} title={t.dashboard.deadlines.title}>
            <div className="mt-4 flex flex-col gap-2">
              <NoSource>{t.dashboard.deadlines.missing}</NoSource>
              <p className="m-0 type-caption text-ink-faint">{t.dashboard.deadlines.why}</p>
            </div>
          </Card>

          {/* The gold rule sits here and not on the card above it, where the mock
              drew it: it marks the panel that carries the conclusion, and on this
              screen the conclusion is a balance that balances. */}
          <Card
            crestRule
            eyebrow={t.dashboard.balance.eyebrow}
            title={t.dashboard.balance.title}
          >
            <div className="mt-4 flex flex-col gap-2">
              <p className="m-0 type-caption text-ink-muted">
                {t.dashboard.balance.window} · {date(data.year_to_date.end_date)}
              </p>
              <Line label={t.dashboard.balance.debit} value={data.year_to_date.debit} />
              <Line label={t.dashboard.balance.credit} value={data.year_to_date.credit} />
              <div className="my-1.5 h-0.5 bg-[image:var(--gradient-gold-foil)]" />
              <div className="flex items-center justify-between gap-3">
                <span className="type-body-sm text-ink-muted">{t.dashboard.balance.state}</span>
                {data.year_to_date.balanced ? (
                  <Badge tone="credit" dot>
                    {t.dashboard.balance.balanced}
                  </Badge>
                ) : (
                  <Badge tone="debit" dot>
                    {t.dashboard.balance.unbalanced}
                  </Badge>
                )}
              </div>
            </div>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] items-start gap-4">
        <Card eyebrow={t.dashboard.work.eyebrow} title={t.dashboard.work.title}>
          <OpenWork
            documents={data.open_work.documents}
            draftEntries={data.open_work.draft_entries}
            open={(section) => void navigate(`/companii/${companyId}/${section}`)}
          />
        </Card>

        <Card eyebrow={t.dashboard.checks.eyebrow} title={t.dashboard.checks.title}>
          <Checks
            unexplained={data.checks.unexplained}
            unpostable={data.checks.unpostable_with_turnover}
          />
        </Card>
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] items-start gap-4">
        <Card eyebrow={seriesWindow(data.series)} title={t.dashboard.series.title}>
          <Series series={data.series} />
        </Card>

        <Card eyebrow={t.dashboard.aging.eyebrow} title={t.dashboard.aging.title}>
          <div className="mt-4">
            <NoSource>{t.dashboard.aging.missing}</NoSource>
          </div>
        </Card>
      </div>
    </section>
  )
}

/**
 * Which postings the extract holds: from the oldest listed to the newest.
 *
 * Dates, not amounts -- the one kind of arithmetic the screen may do on the
 * server's rows. The list arrives newest first, so the ends are the two ends.
 */
function extractWindow(entries: PanelEntry[]): string {
  const newest = entries[0]
  const oldest = entries[entries.length - 1]
  if (!newest || !oldest) return t.dashboard.register.eyebrow
  return `${t.dashboard.register.eyebrow} · ${date(oldest.accounting_date)} – ${date(newest.accounting_date)}`
}

/** The months the series spans, oldest first, as the design's eyebrow reads. */
function seriesWindow(series: Turnover[]): string {
  const first = series[0]
  const last = series[series.length - 1]
  if (!first || !last) return t.dashboard.series.title
  return `${month(first.start_date)} — ${month(last.start_date)}`
}

/**
 * A figure the panel could not obtain, and the reason in its place.
 *
 * The reason is always a sentence naming what is missing -- a parameter table, a
 * calculation, a column. "Indisponibil" would be the same as an empty box.
 */
function NoSource({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 flex gap-2.5 type-body-sm text-ink-muted">
      <Icon name="triangle-alert" size={16} className="mt-0.5 shrink-0 text-ink-faint" />
      <span>{children}</span>
    </p>
  )
}

/** Label left, figure right -- the shape a balance is read in. */
function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="type-body-sm text-ink-muted">{label}</span>
      <Figure value={value} size="md" className="tabular" />
    </div>
  )
}

const ENTRY_COLUMNS: Column<PanelEntry>[] = [
  {
    key: 'entry_number',
    header: t.dashboard.register.number,
    cell: (entry) => <span className="font-mono">{entry.entry_number}</span>,
    width: '9rem',
  },
  {
    key: 'accounting_date',
    header: t.dashboard.register.date,
    cell: (entry) => date(entry.accounting_date),
    width: '7rem',
  },
  {
    key: 'content',
    header: t.dashboard.register.content,
    // The counterparty first when a line names one, the description under it;
    // the description alone otherwise. A note between two accounts has no
    // counterparty, and that is the shape of a manual note, not missing data.
    cell: (entry) =>
      entry.partner_name ? (
        <span className="flex flex-col">
          <span className="type-label text-heading">{entry.partner_name}</span>
          <span className="type-caption text-ink-muted">{entry.description}</span>
        </span>
      ) : (
        entry.description
      ),
  },
  {
    key: 'amount',
    header: t.dashboard.register.amount,
    cell: (entry) => amount(entry.amount),
    numeric: true,
    width: '10rem',
  },
  {
    key: 'state',
    header: t.dashboard.register.state,
    cell: (entry) => <EntryState entry={entry} />,
    width: '8rem',
  },
]

/**
 * What the entry is, in a word -- and the word is never carried by colour alone.
 *
 * Three states and they are not the same fact: an entry that cancels another, an
 * entry that has been cancelled, and one that stands. A panel that showed the
 * middle one as a plain posting would be showing an amount that is no longer in
 * the books.
 */
function EntryState({ entry }: { entry: PanelEntry }) {
  if (entry.entry_type === 'reversal') {
    return <Badge tone="debit">{t.dashboard.register.reversal}</Badge>
  }
  if (entry.reversed_by_entry_id) {
    return <Badge tone="caution">{t.dashboard.register.reversed}</Badge>
  }
  return (
    <Badge tone="credit" dot>
      {t.dashboard.register.posted}
    </Badge>
  )
}

const WORK_LABEL: Record<DocumentWork['owner'], string> = {
  purchases: t.dashboard.work.purchases,
  sales: t.dashboard.work.sales,
  treasury: t.dashboard.work.treasury,
}

const WORK_ICON: Record<DocumentWork['owner'], IconName> = {
  purchases: 'import',
  sales: 'file-text',
  treasury: 'coins',
}

/** Where each family's documents are worked on -- the section under the company. */
const WORK_SECTION: Record<DocumentWork['owner'], string> = {
  purchases: 'facturi-primite',
  sales: 'facturi',
  treasury: 'trezorerie',
}

/** What has not reached the ledger yet, how much of it, and where to finish it. */
function OpenWork({
  documents,
  draftEntries,
  open,
}: {
  documents: DocumentWork[]
  draftEntries: number
  open: (section: string) => void
}) {
  if (documents.length === 0 && draftEntries === 0) {
    return <p className="mt-4 type-body-sm text-ink-muted">{t.dashboard.work.empty}</p>
  }

  return (
    <div className="mt-4 flex flex-col">
      {documents.map((work) => (
        <Row
          key={work.owner}
          icon={WORK_ICON[work.owner]}
          name={WORK_LABEL[work.owner]}
          // The split, not the sum alone: a draft and a validated document need
          // opposite things done to them.
          hint={`${work.draft} ${t.dashboard.work.draft} · ${work.confirmed} ${t.dashboard.work.confirmed}`}
          count={work.draft + work.confirmed}
          onClick={() => open(WORK_SECTION[work.owner])}
        />
      ))}
      {draftEntries > 0 && (
        <Row
          icon="file-pen"
          name={t.dashboard.work.entries}
          hint={t.dashboard.work.entriesHint}
          count={draftEntries}
          onClick={() => open('registru')}
        />
      )}
    </div>
  )
}

/**
 * One line of work: what it is, what it means, how many.
 *
 * The count is a count of rows, not an amount -- it is the one number on this
 * screen the server produced as an integer, and it is rendered as one rather
 * than through the money formatter.
 */
function Row({
  icon,
  name,
  hint,
  count,
  onClick,
}: {
  icon: IconName
  name: string
  hint: string
  count: number
  onClick?: () => void
}) {
  const body = (
    <>
      <Icon name={icon} size={18} className="shrink-0 text-ink-faint" />
      <span className="min-w-0 flex-1">
        <span className="block type-body-md text-ink">{name}</span>
        <span className="mt-0.5 block type-caption text-ink-muted">{hint}</span>
      </span>
      <span className="shrink-0 type-figure-lg tabular text-navy-700">{count}</span>
    </>
  )
  const shape = 'flex items-center gap-3.5 border-b border-border py-3 last:border-b-0'

  return onClick ? (
    <button type="button" onClick={onClick} className={`${shape} w-full text-left`}>
      {body}
    </button>
  ) : (
    <div className={shape}>{body}</div>
  )
}

/**
 * The month's loose ends -- each one a reading of the ledger, none of them an
 * accusation.
 *
 * Turnover no formula explains is what a manual note produces, and a month of
 * manual notes is a legitimate month. An account blocked after a posting is
 * exactly the second line. So the card reports and does not judge; the screens
 * that can answer "why" are one click away.
 */
function Checks({ unexplained, unpostable }: { unexplained: string; unpostable: number }) {
  // A decimal string, compared as a string against the server's own zero. The
  // server sends `0.0000`; parsing it to compare against 0 would be the one
  // parse this screen refuses everywhere else.
  const nothingUnexplained = Number(unexplained) === 0
  if (nothingUnexplained && unpostable === 0) {
    return <p className="mt-4 type-body-sm text-ink-muted">{t.dashboard.checks.clear}</p>
  }

  return (
    <div className="mt-4 flex flex-col">
      {!nothingUnexplained && (
        <Check
          tone="caution"
          name={t.dashboard.checks.unexplained}
          value={`${amount(unexplained)} — ${t.dashboard.checks.unexplainedHint}`}
        />
      )}
      {unpostable > 0 && (
        <Check
          tone="debit"
          name={t.dashboard.checks.unpostable}
          value={`${unpostable} — ${t.dashboard.checks.unpostableHint}`}
        />
      )}
      <Check
        tone="neutral"
        name={t.dashboard.checks.opening}
        value={t.dashboard.checks.openingMissing}
      />
    </div>
  )
}

const CHECK_DOT: Record<'caution' | 'debit' | 'neutral', string> = {
  caution: 'bg-[var(--caution-500)]',
  debit: 'bg-[var(--debit-500)]',
  neutral: 'bg-[var(--ink-300)]',
}

function Check({
  tone,
  name,
  value,
}: {
  tone: keyof typeof CHECK_DOT
  name: string
  value: string
}) {
  return (
    <div className="flex items-start gap-2.5 border-b border-border py-3 last:border-b-0">
      <span className={`mt-1.5 size-1.5 shrink-0 rounded-full ${CHECK_DOT[tone]}`} />
      <span className="min-w-0 flex-1">
        <span className="block type-body-sm text-ink">{name}</span>
        <span className="mt-0.5 block type-figure-sm tabular text-ink-muted">{value}</span>
      </span>
    </div>
  )
}

/**
 * Six months of turnover, both sides.
 *
 * `Number()` appears here and nowhere else on the screen, and only to compute a
 * **height**: the tallest bar is the largest month, and every other bar is a
 * fraction of it. The amounts themselves stay strings and reach the reader
 * through the formatter, on the bar's own title.
 */
function Series({ series }: { series: Turnover[] }) {
  const peak = Math.max(...series.map((window) => Number(window.debit)), ...series.map((window) => Number(window.credit)))

  if (peak <= 0) {
    return <p className="mt-4 type-body-sm text-ink-muted">{t.dashboard.series.empty}</p>
  }

  return (
    <>
      <div className="mt-4 flex items-center gap-5">
        <Legend className="bg-[var(--navy-600)]" label={t.dashboard.series.debit} />
        <Legend className="bg-[var(--gold-500)]" label={t.dashboard.series.credit} />
      </div>
      <div className="mt-5 grid grid-cols-6 gap-5 border-t border-border pt-2">
        {series.map((window) => (
          <div key={window.start_date} className="flex flex-col items-center gap-2.5">
            <div className="flex h-32 w-full items-end justify-center gap-1.5">
              <Bar
                className="bg-[var(--navy-600)]"
                height={Number(window.debit) / peak}
                label={`${t.dashboard.series.debit} ${amount(window.debit)}`}
              />
              <Bar
                className="bg-[var(--gold-500)]"
                height={Number(window.credit) / peak}
                label={`${t.dashboard.series.credit} ${amount(window.credit)}`}
              />
            </div>
            <span className="font-eyebrow text-[11px] font-semibold tracking-[var(--tracking-eyebrow)] text-ink-muted uppercase">
              {monthShort(window.start_date)}
            </span>
          </div>
        ))}
      </div>
    </>
  )
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-2">
      <span className={`size-2.5 ${className}`} />
      <span className="type-caption text-ink-muted">{label}</span>
    </span>
  )
}

function Bar({ className, height, label }: { className: string; height: number; label: string }) {
  return (
    <span
      title={label}
      className={`w-[26%] ${className}`}
      // A hairline for a month with no turnover, so the label below it still has
      // something to sit under -- and it is visibly not a bar.
      style={{ height: `${Math.max(height * 100, 1)}%` }}
    />
  )
}
