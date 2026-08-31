/**
 * The manual journal note -- the one screen that writes to the ledger, now on
 * `EntryGrid` (F1.G2, ADR-052).
 *
 * The first version was a plain table of inputs, because the keyboard contract
 * was open and building the grid here would have settled it by accident. The
 * contract is ADR-052 now, `EntryGrid` honours it, and this screen adds **no
 * key handler of its own** (C40): Enter advances and opens the next line, F4
 * opens the chart, Ctrl+Enter posts -- through the grid's `onValidate`, which
 * is the only way a key reaches this file.
 *
 * **The balance check here blocks a button; it does not decide anything.** Σ
 * debit = Σ credit is checked by the engine and by the database (R11); the
 * indicator under the grid and the button's state use the same integer
 * arithmetic at the server's scale, so they cannot disagree with each other --
 * and both save a round trip, nothing more.
 *
 * Amounts are typed with a point or a comma and stored canonical (a point, no
 * grouping); they are sent as strings and never pass through a number. The
 * idempotency key belongs to the note, not to the click (C9, R19): generated
 * once when the form opens, so a retry posts once and the second attempt says so.
 */

import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { listAccounts } from '@/shared/api/coa'
import { postManualEntry, type ManualLine } from '@/shared/api/ledger'
import { EntryGrid, amountUnits, type EntryColumn, type LookupOption } from '@/shared/EntryGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input } from '@/shared/ui'

type Draft = { account_id: string; description: string; debit: string; credit: string }

const EMPTY: Draft = { account_id: '', description: '', debit: '', credit: '' }

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
  const [idempotencyKey, setKey] = useState(() => crypto.randomUUID())

  const accounts = useQuery({
    queryKey: ['accounts', companyId, ''],
    queryFn: () => listAccounts(companyId),
  })

  const options: LookupOption[] = (accounts.data ?? []).map((account) => ({
    id: account.id,
    code: account.account_code,
    label: `${account.account_code} — ${account.name_ro}`,
  }))

  const columns: EntryColumn<Draft>[] = [
    { key: 'account_id', header: t.accounting.entry.account, kind: 'lookup', options },
    { key: 'description', header: t.accounting.entry.lineDescription, kind: 'text' },
    { key: 'debit', header: t.accounting.entry.debit, kind: 'amount', width: '9rem' },
    { key: 'credit', header: t.accounting.entry.credit, kind: 'amount', width: '9rem' },
  ]

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
              debit: line.debit || '0',
              credit: line.credit || '0',
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

  const totalDebit = lines.reduce((sum, line) => sum + amountUnits(line.debit), 0)
  const totalCredit = lines.reduce((sum, line) => sum + amountUnits(line.credit), 0)
  const filled = lines.filter((line) => line.account_id !== '')
  const balanced = totalDebit === totalCredit && totalDebit > 0
  const postable =
    balanced && filled.length > 0 && description.trim() !== '' && !post.isPending

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
      <h1 className="type-display-2 text-heading">{t.accounting.entry.title}</h1>

      <div className="flex flex-wrap items-end gap-4">
        <Field label={t.accounting.entry.date}>
          <Input
            type="date"
            value={accountingDate}
            onChange={(event) => setAccountingDate(event.target.value)}
            className="w-44"
          />
        </Field>
        <label className="flex flex-1 flex-col gap-1 text-sm">
          <span className="text-ink-muted">{t.accounting.entry.description}</span>
          <Input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={500}
          />
        </label>
      </div>

      {accounts.isError && <Failure error={accounts.error} />}
      {accounts.data?.length === 0 && (
        <p className="text-sm text-ink-muted">{t.accounting.entry.noChart}</p>
      )}

      <Card padding="none">
        <EntryGrid<Draft>
          columns={columns}
          rows={lines}
          onChange={setLines}
          newRow={() => ({ ...EMPTY })}
          onValidate={() => {
            if (postable) post.mutate()
          }}
          balance={{ debit: 'debit', credit: 'credit' }}
          label={t.accounting.entry.title}
          strings={t.accounting.entryGrid}
          footer={<span className="text-xs text-ink-muted">{t.accounting.entryGrid.keys}</span>}
        />
      </Card>

      <div className="flex flex-wrap items-center gap-4">
        <Button variant="secondary"
          type="button"
          onClick={() => setLines((current) => [...current, { ...EMPTY }])}
        >
          {t.accounting.entry.addLine}
        </Button>
        <Button variant="secondary" type="button" onClick={() => post.mutate()} disabled={!postable}>
          {post.isPending ? t.accounting.entry.posting : t.accounting.entry.post}
        </Button>
      </div>

      {totalDebit !== totalCredit && filled.length > 0 && (
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
