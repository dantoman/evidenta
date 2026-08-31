/**
 * Operation templates: the recurring note, defined once.
 *
 * **A shortcut to a note, never a second kind of posting.** What a template
 * produces is an ordinary entry -- the register shows it as `standard`, and
 * nothing distinguishes it from one typed line by line. That is deliberate on
 * the server: there is no `template.posted` event type, because the register
 * records what happened and what happened was a manual note. If this screen ever
 * wants to say "posted from template X", that stays here.
 *
 * **A line's amount is either fixed or asked for at posting time**, and the two
 * are different shapes on the wire rather than one field with a magic string. So
 * the form has a checkbox, not a convention: a template whose amount is
 * literally the text "from_input" would be one nobody could post, and nobody
 * would find out until they tried.
 *
 * **Retiring is not deleting.** A withdrawn template cannot produce new entries,
 * but an entry posted last year names it, so its definition stays readable. The
 * list hides retired ones by default and can show them.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import { listAccounts, type Account } from '@/shared/api/coa'
import {
  createTemplate,
  listTemplates,
  postFromTemplate,
  setTemplateActive,
  type TemplateLine,
  type TemplateSummary,
} from '@/shared/api/templates'
import { Failure } from '@/shared/Failure'
import { Button, Field, Input, Select } from '@/shared/ui'

interface LineDraft {
  account_id: string
  side: 'debit' | 'credit'
  /** Fixed decimal, or the name of an input the template will ask for. */
  fromInput: boolean
  value: string
  description: string
}

const EMPTY_LINE: LineDraft = {
  account_id: '',
  side: 'debit',
  fromInput: false,
  value: '',
  description: '',
}

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

export function OperationTemplatesScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()
  const [includeInactive, setIncludeInactive] = useState(false)
  const [defining, setDefining] = useState(false)
  const [using, setUsing] = useState<TemplateSummary | null>(null)

  const accounts = useQuery({
    queryKey: ['accounts', companyId, ''],
    queryFn: () => listAccounts(companyId),
  })
  const templates = useQuery({
    queryKey: ['operation-templates', companyId, includeInactive],
    queryFn: () => listTemplates(companyId, includeInactive),
  })

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ['operation-templates', companyId] })

  const activation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      setTemplateActive(companyId, id, active),
    onSuccess: refresh,
  })

  return (
    <section className="flex flex-col gap-4">
      <nav className="flex gap-4 text-sm">
        <Link to={`/companii/${companyId}/plan-de-conturi`} className="text-accent">
          {t.accounting.chart.title}
        </Link>
        <Link to={`/companii/${companyId}/note`} className="text-accent">
          {t.accounting.entry.title}
        </Link>
        <Link to={`/companii/${companyId}/registru`} className="text-accent">
          {t.accounting.register.title}
        </Link>
      </nav>

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="type-display-2 text-heading">{t.accounting.operationTemplates.title}</h1>
          <p className="text-sm text-ink-muted">{t.accounting.operationTemplates.lead}</p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            <span className="text-ink-muted">
              {t.accounting.operationTemplates.showInactive}
            </span>
          </label>
          <Button variant="primary" type="button" onClick={() => setDefining((open) => !open)}>
            {defining ? t.companies.cancel : t.common.add}
          </Button>
        </div>
      </header>

      {accounts.isError && <Failure error={accounts.error} />}
      {templates.isError && <Failure error={templates.error} />}
      {activation.isError && <Failure error={activation.error} />}

      {defining && (
        <Definition
          accounts={accounts.data ?? []}
          onCreated={async () => {
            setDefining(false)
            await refresh()
          }}
        />
      )}

      {templates.data?.length === 0 && (
        <p className="text-sm text-ink-muted">{t.accounting.operationTemplates.empty}</p>
      )}

      <div className="flex flex-col gap-2">
        {templates.data?.map((template) => (
          <article
            key={template.id}
            className="flex flex-wrap items-center justify-between gap-4 rounded border border-border bg-surface px-3 py-2 text-sm"
          >
            <div className="flex flex-col">
              <span className="font-medium">{template.name}</span>
              <span className="text-ink-muted">{template.entry_description}</span>
              <span className="text-ink-muted">
                {t.accounting.operationTemplates.lines}: {template.line_count}
                {template.inputs.length > 0 && (
                  <>
                    {' · '}
                    {t.accounting.operationTemplates.inputs}: {template.inputs.join(', ')}
                  </>
                )}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <span className={template.is_active ? 'text-ink-muted' : 'text-danger'}>
                {template.is_active
                  ? t.accounting.operationTemplates.active
                  : t.accounting.operationTemplates.inactive}
              </span>
              {/* A retired template posts nothing, so it offers no button that
                  the server would refuse. */}
              {template.is_active && (
                <button
                  type="button"
                  onClick={() => setUsing(using?.id === template.id ? null : template)}
                  className="text-accent"
                >
                  {t.accounting.operationTemplates.use}
                </button>
              )}
              <button
                type="button"
                onClick={() =>
                  activation.mutate({ id: template.id, active: !template.is_active })
                }
                className="text-accent"
              >
                {template.is_active
                  ? t.accounting.operationTemplates.retire
                  : t.accounting.operationTemplates.restore}
              </button>
            </div>

            {using?.id === template.id && (
              <div className="w-full">
                <Posting
                  companyId={companyId}
                  template={template}
                  onPosted={() => setUsing(null)}
                />
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}

function Definition({
  accounts,
  onCreated,
}: {
  accounts: Account[]
  onCreated: () => Promise<void> | void
}) {
  const { companyId = '' } = useParams()
  const [name, setName] = useState('')
  const [entryDescription, setEntryDescription] = useState('')
  const [lines, setLines] = useState<LineDraft[]>([{ ...EMPTY_LINE }, { ...EMPTY_LINE }])

  const create = useMutation({
    mutationFn: () =>
      createTemplate(companyId, {
        name: name.trim(),
        entry_description: entryDescription.trim(),
        lines: lines
          .filter((line) => line.account_id !== '')
          .map<TemplateLine>((line) => ({
            account_id: line.account_id,
            side: line.side,
            // The shape carries the meaning: a fixed decimal, or the key the
            // template will ask for. Never one field holding both.
            amount: line.fromInput
              ? { from_input: line.value.trim() }
              : line.value.replace(',', '.'),
            description: line.description.trim() || null,
          })),
      }),
    onSuccess: onCreated,
  })

  const set = (index: number, patch: Partial<LineDraft>) =>
    setLines((current) =>
      current.map((line, at) => (at === index ? { ...line, ...patch } : line)),
    )

  const complete =
    name.trim() !== '' &&
    entryDescription.trim() !== '' &&
    lines.filter((line) => line.account_id !== '' && line.value.trim() !== '').length >= 2

  return (
    <form
      className="flex flex-col gap-3 rounded border border-border bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <div className="flex flex-wrap gap-4">
        <Field label={t.accounting.operationTemplates.name}>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-64"
          />
        </Field>
        <label className="flex flex-1 flex-col gap-1 text-sm">
          <span className="text-ink-muted">
            {t.accounting.operationTemplates.entryDescription}
          </span>
          <Input
            value={entryDescription}
            onChange={(event) => setEntryDescription(event.target.value)}
          />
        </label>
      </div>

      {lines.map((line, index) => (
        <div key={index} className="flex flex-wrap items-end gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.accounting.operationTemplates.account}</span>
            <Select
              value={line.account_id}
              onChange={(event) => set(index, { account_id: event.target.value })}
              aria-label={`${t.accounting.operationTemplates.account} ${index + 1}`}
            >
              <option value="" />
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.account_code} — {account.name_ro}
                </option>
              ))}
            </Select>
          </label>
          <Field label={t.accounting.entry.debit}>
            <Select
              value={line.side}
              onChange={(event) =>
                set(index, { side: event.target.value as 'debit' | 'credit' })
              }
              className="w-28"
              aria-label={`${t.accounting.operationTemplates.account} ${index + 1} ${t.accounting.operationTemplates.debit}`}
            >
              <option value="debit">{t.accounting.operationTemplates.debit}</option>
              <option value="credit">{t.accounting.operationTemplates.credit}</option>
            </Select>
          </Field>
          <Field label={t.accounting.operationTemplates.amount}>
            <Input
              value={line.value}
              onChange={(event) => set(index, { value: event.target.value })}
              className="w-40 ${line.fromInput ? '' : 'tabular text-right'}"
              inputMode={line.fromInput ? 'text' : 'decimal'}
              aria-label={`${t.accounting.operationTemplates.amount} ${index + 1}`}
            />
          </Field>
          <label className="flex items-center gap-2 pb-1 text-sm">
            <input
              type="checkbox"
              checked={line.fromInput}
              onChange={(event) => set(index, { fromInput: event.target.checked })}
            />
            <span className="text-ink-muted">{t.accounting.operationTemplates.fromInput}</span>
          </label>
          <button
            type="button"
            onClick={() => setLines((current) => current.filter((_, at) => at !== index))}
            disabled={lines.length <= 2}
            className="pb-1 text-sm text-accent disabled:text-ink-muted"
          >
            {t.accounting.entry.removeLine}
          </button>
        </div>
      ))}

      <div className="flex items-center gap-4">
        <Button variant="secondary"
          type="button"
          onClick={() => setLines((current) => [...current, { ...EMPTY_LINE }])}
        >
          {t.accounting.entry.addLine}
        </Button>
        <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
          {t.common.save}
        </Button>
      </div>
      {create.isError && <Failure error={create.error} />}
    </form>
  )
}

function Posting({
  companyId,
  template,
  onPosted,
}: {
  companyId: string
  template: TemplateSummary
  onPosted: () => void
}) {
  const [accountingDate, setAccountingDate] = useState(today())
  const [description, setDescription] = useState('')
  const [inputs, setInputs] = useState<Record<string, string>>({})
  // One key and one note identity per attempt, allocated when the form opens.
  const [identity, setIdentity] = useState(() => ({
    key: crypto.randomUUID(),
    noteId: crypto.randomUUID(),
  }))

  const post = useMutation({
    mutationFn: () =>
      postFromTemplate(
        companyId,
        template.id,
        {
          accounting_date: accountingDate,
          note_id: identity.noteId,
          // Sent exactly as the template asked: the service refuses a missing
          // key and refuses an extra one, and an unexpected key usually means a
          // form and a template that have drifted.
          inputs: Object.fromEntries(
            template.inputs.map((key) => [key, (inputs[key] ?? '').replace(',', '.')]),
          ),
          description: description.trim() || undefined,
        },
        identity.key,
      ),
    onSuccess: () => {
      setIdentity({ key: crypto.randomUUID(), noteId: crypto.randomUUID() })
      onPosted()
    },
  })

  const filled = template.inputs.every((key) => (inputs[key] ?? '').trim() !== '')

  return (
    <form
      className="mt-2 flex flex-wrap items-end gap-4 border-t border-border pt-3"
      onSubmit={(event) => {
        event.preventDefault()
        post.mutate()
      }}
    >
      <Field label={t.accounting.operationTemplates.date}>
        <Input
          type="date"
          value={accountingDate}
          onChange={(event) => setAccountingDate(event.target.value)}
          className="w-44"
        />
      </Field>

      {template.inputs.map((key) => (
        <label key={key} className="flex flex-col gap-1 text-sm">
          <span className="text-ink-muted">{key}</span>
          <Input
            value={inputs[key] ?? ''}
            onChange={(event) =>
              setInputs((current) => ({ ...current, [key]: event.target.value }))
            }
            inputMode="decimal"
            className="tabular w-40 text-right"
            aria-label={key}
          />
        </label>
      ))}

      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.accounting.operationTemplates.description}</span>
        <Input
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={t.accounting.operationTemplates.descriptionHint}
        />
      </label>

      <Button variant="primary" type="submit" disabled={!filled || post.isPending}>
        {t.accounting.operationTemplates.post}
      </Button>

      {post.isError && (
        <div className="w-full">
          <Failure error={post.error} />
        </div>
      )}
    </form>
  )
}
