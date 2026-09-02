/**
 * Fiscal parameters, as system settings -- the owner's question answered where
 * they asked it: *"I expect this to be set in the settings of the system. If VAT
 * gets changed?"*
 *
 * What the screen makes visible is the shape `R15` and `OD-92` impose on the
 * answer. A rate is a **row with a date and an act**, not a field to overwrite:
 * when the law changes, an operator writes a new version with the date it
 * applies from and the act whose article sets that date, then activates it as
 * the approver. The old value stays, for the periods it governed. A row whose
 * date was never read from the act shows "fără margine" and cannot be activated
 * -- the button is there, and the server says why.
 *
 * Values are shown as typed, not formatted (`C18` is about accounting amounts on
 * documents and grids; a parameter is configuration, and "1 700 000,00" for a
 * threshold would claim a precision the act does not state). Tables show as
 * compact JSON.
 *
 * Only an `operator` may write or activate (ADR-076 §4.1); the server enforces
 * it, and the screen hides the controls from the other roles so a refusal is
 * not the first thing they learn.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { t } from '@/locales'
import {
  activateFiscalParameter,
  draftFiscalParameter,
  listFiscalParameters,
  staffMe,
  type Confidence,
  type FiscalParameter,
  type MarginBasis,
  type ParameterDraftInput,
  type ValueType,
} from '@/shared/api/platform'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Badge, Button, Card, Field, Input, PageHeader, Select, type BadgeTone } from '@/shared/ui'
import { STAFF_ME_KEY } from './ConsoleLayout'

const LIST_KEY = ['console', 'fiscal-parameters'] as const

export function FiscalParametersScreen() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('')
  const [adding, setAdding] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const me = useQuery({ queryKey: STAFF_ME_KEY, queryFn: staffMe, retry: false })
  const canWrite = me.data?.staff_role === 'operator'

  const parameters = useQuery({ queryKey: LIST_KEY, queryFn: listFiscalParameters })
  const refresh = () => queryClient.invalidateQueries({ queryKey: LIST_KEY })

  const activation = useMutation({
    mutationFn: activateFiscalParameter,
    onSuccess: () => {
      setNotice(null)
      void refresh()
    },
  })

  const rows = (parameters.data?.parameters ?? []).filter(
    (row) => !filter || row.parameter_key.includes(filter.trim()),
  )

  const columns: Column<FiscalParameter>[] = [
    {
      key: 'key',
      header: t.console.fiscal.key,
      cell: (row) => <span className="font-mono">{row.parameter_key}</span>,
    },
    {
      key: 'value',
      header: t.console.fiscal.value,
      cell: (row) => (
        <span className="font-mono">
          {showValue(row.value)}
          {row.unit && <span className="text-ink-muted"> {row.unit}</span>}
        </span>
      ),
      width: '14rem',
    },
    {
      key: 'from',
      header: t.console.fiscal.validFrom,
      cell: (row) =>
        row.valid_from ? (
          <span className="font-mono">{row.valid_from}</span>
        ) : (
          <span className="text-danger" title={t.console.fiscal.noMarginHint}>
            {t.console.fiscal.noMargin}
          </span>
        ),
      width: '8rem',
    },
    {
      key: 'to',
      header: t.console.fiscal.validTo,
      cell: (row) => <span className="font-mono">{row.valid_to ?? ''}</span>,
      width: '8rem',
    },
    {
      key: 'act',
      header: t.console.fiscal.act,
      cell: (row) => (
        <span title={row.act.title ?? undefined}>
          {row.act.act_type} {row.act.act_number}
          {row.act.act_date && <span className="text-ink-muted"> · {row.act.act_date}</span>}
        </span>
      ),
      width: '16rem',
    },
    {
      key: 'confidence',
      header: t.console.fiscal.confidence,
      cell: (row) => (
        <span title={row.provisional_reason ?? undefined}>
          <Badge tone={row.confidence === 'confirmed' ? 'info' : 'caution'}>
            {row.confidence === 'confirmed'
              ? t.console.fiscal.confirmed
              : t.console.fiscal.provisional}
          </Badge>
        </span>
      ),
      width: '8rem',
    },
    {
      key: 'status',
      header: t.console.fiscal.status,
      cell: (row) => <Badge tone={statusTone(row.status)}>{statusLabel(row.status)}</Badge>,
      width: '8rem',
    },
    {
      key: 'action',
      header: '',
      cell: (row) =>
        canWrite && row.status === 'draft' ? (
          <button
            type="button"
            title={t.console.fiscal.activateHint}
            onClick={() => activation.mutate(row.id)}
            disabled={activation.isPending}
            className="text-accent"
          >
            {t.console.fiscal.activate}
          </button>
        ) : null,
      width: '8rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.fiscal.eyebrow}
        title={t.console.fiscal.title}
        lead={t.console.fiscal.lead}
        actions={
          canWrite ? (
            <Button icon="plus" onClick={() => setAdding((open) => !open)}>
              {t.console.fiscal.newVersion}
            </Button>
          ) : undefined
        }
      />

      {me.data && !canWrite && (
        <p className="m-0 type-body-md text-ink-muted">{t.console.fiscal.readOnly}</p>
      )}

      {adding && canWrite && (
        <NewVersionForm
          knownKeys={[...new Set((parameters.data?.parameters ?? []).map((p) => p.parameter_key))]}
          onDone={(message) => {
            setAdding(false)
            setNotice(message)
            void refresh()
          }}
          onCancel={() => setAdding(false)}
        />
      )}

      <div className="flex items-end gap-3">
        <Field label={t.console.fiscal.filterKey}>
          <Input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="vat."
          />
        </Field>
      </div>

      {notice && <p className="m-0 type-body-md text-ink-muted">{notice}</p>}
      {activation.isError && <Failure error={activation.error} />}
      {parameters.isError && <Failure error={parameters.error} />}

      <DataGrid
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        density="compact"
        emptyMessage={t.console.fiscal.empty}
      />
    </section>
  )
}

function showValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function statusLabel(status: FiscalParameter['status']): string {
  switch (status) {
    case 'draft':
      return t.console.fiscal.statusDraft
    case 'approved':
      return t.console.fiscal.statusApproved
    case 'active':
      return t.console.fiscal.statusActive
    case 'superseded':
      return t.console.fiscal.statusSuperseded
  }
}

function statusTone(status: FiscalParameter['status']): BadgeTone {
  if (status === 'active') return 'gold'
  if (status === 'draft') return 'caution'
  return 'neutral'
}

const VALUE_TYPES: { value: ValueType; label: string }[] = [
  { value: 'percentage', label: t.console.fiscal.typePercentage },
  { value: 'money', label: t.console.fiscal.typeMoney },
  { value: 'decimal', label: t.console.fiscal.typeDecimal },
  { value: 'integer', label: t.console.fiscal.typeInteger },
  { value: 'date', label: t.console.fiscal.typeDate },
  { value: 'boolean', label: t.console.fiscal.typeBoolean },
  { value: 'table', label: t.console.fiscal.typeTable },
]

/**
 * A new dated version of a parameter, as a draft.
 *
 * The form asks for the act in full -- type, number, date, title, the date it
 * entered into force, its Monitor position -- because that is what a value needs
 * to be defensible at an inspection three years on (`R15`), and a form that
 * asked for less would let a number arrive without anyone deciding where it
 * came from. The margin is optional and says so: a value whose article was not
 * read is written with where it was observed, and stays unactivatable.
 */
function NewVersionForm({
  knownKeys,
  onDone,
  onCancel,
}: {
  knownKeys: string[]
  onDone: (message: string) => void
  onCancel: () => void
}) {
  const [key, setKey] = useState('')
  const [valueType, setValueType] = useState<ValueType>('percentage')
  const [value, setValue] = useState('')
  const [unit, setUnit] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validTo, setValidTo] = useState('')
  const [marginBasis, setMarginBasis] = useState<MarginBasis>('act')
  const [marginReference, setMarginReference] = useState('')
  const [observedIn, setObservedIn] = useState('')
  const [confidence, setConfidence] = useState<Confidence>('provisional')
  const [reason, setReason] = useState('')
  const [actType, setActType] = useState('lege')
  const [actNumber, setActNumber] = useState('')
  const [actDate, setActDate] = useState('')
  const [actTitle, setActTitle] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [gazetteYear, setGazetteYear] = useState('')
  const [gazetteNumber, setGazetteNumber] = useState('')
  const [gazetteArticle, setGazetteArticle] = useState('')
  const [publishedAt, setPublishedAt] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const write = useMutation({
    mutationFn: draftFiscalParameter,
    onSuccess: (answer) =>
      onDone(answer.outcome === 'unchanged' ? t.console.fiscal.unchanged : t.console.fiscal.written),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setLocalError(null)
    const parsed = parseValue(valueType, value)
    if (parsed.error) {
      setLocalError(parsed.error)
      return
    }
    const publication =
      gazetteYear || gazetteNumber || gazetteArticle
        ? {
            gazette_year: Number(gazetteYear),
            gazette_number: gazetteNumber,
            article: gazetteArticle,
            published_at: publishedAt || null,
          }
        : null
    const input: ParameterDraftInput = {
      parameter_key: key.trim(),
      value_type: valueType,
      value: parsed.value,
      unit: unit.trim() || null,
      valid_from: validFrom || null,
      valid_to: validTo || null,
      margin_basis: validFrom ? marginBasis : null,
      margin_reference: validFrom ? marginReference.trim() || null : null,
      observed_in: observedIn.trim() || null,
      confidence,
      provisional_reason: confidence === 'provisional' ? reason.trim() || null : null,
      act: {
        act_type: actType.trim(),
        act_number: actNumber.trim(),
        act_date: actDate,
        title: actTitle.trim(),
        effective_from: effectiveFrom || null,
        publication,
      },
    }
    write.mutate(input)
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div>
          <h2 className="m-0 type-title text-heading">{t.console.fiscal.newVersion}</h2>
          <p className="mt-1 mb-0 type-body-md text-ink-muted">{t.console.fiscal.newVersionLead}</p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Field label={t.console.fiscal.key}>
            <Input
              list="fiscal-parameter-keys"
              value={key}
              onChange={(event) => setKey(event.target.value)}
              required
              className="font-mono"
            />
            <datalist id="fiscal-parameter-keys">
              {knownKeys.map((known) => (
                <option key={known} value={known} />
              ))}
            </datalist>
          </Field>
          <Field label={t.console.fiscal.valueType}>
            <Select
              value={valueType}
              onChange={(event) => setValueType(event.target.value as ValueType)}
            >
              {VALUE_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t.console.fiscal.value} hint={t.console.fiscal.valueHint}>
            <Input
              value={value}
              onChange={(event) => setValue(event.target.value)}
              required
              className="font-mono"
            />
          </Field>
          <Field label={t.console.fiscal.unit}>
            <Input value={unit} onChange={(event) => setUnit(event.target.value)} />
          </Field>
          <Field label={t.console.fiscal.validFrom} hint={t.console.fiscal.noMarginHint}>
            <Input
              type="date"
              value={validFrom}
              onChange={(event) => setValidFrom(event.target.value)}
            />
          </Field>
          <Field label={t.console.fiscal.validTo}>
            <Input type="date" value={validTo} onChange={(event) => setValidTo(event.target.value)} />
          </Field>
          {validFrom && (
            <>
              <Field label={t.console.fiscal.marginBasis}>
                <Select
                  value={marginBasis}
                  onChange={(event) => setMarginBasis(event.target.value as MarginBasis)}
                >
                  <option value="act">{t.console.fiscal.marginBasisAct}</option>
                  <option value="platform_convention">
                    {t.console.fiscal.marginBasisConvention}
                  </option>
                </Select>
              </Field>
              <Field label={t.console.fiscal.marginReference}>
                <Input
                  value={marginReference}
                  onChange={(event) => setMarginReference(event.target.value)}
                  required
                />
              </Field>
            </>
          )}
          {!validFrom && (
            <Field label={t.console.fiscal.observedIn}>
              <Input value={observedIn} onChange={(event) => setObservedIn(event.target.value)} />
            </Field>
          )}
          <Field label={t.console.fiscal.confidence}>
            <Select
              value={confidence}
              onChange={(event) => setConfidence(event.target.value as Confidence)}
            >
              <option value="provisional">{t.console.fiscal.provisional}</option>
              <option value="confirmed">{t.console.fiscal.confirmed}</option>
            </Select>
          </Field>
          {confidence === 'provisional' && (
            <Field label={t.console.fiscal.provisionalReason}>
              <Input value={reason} onChange={(event) => setReason(event.target.value)} required />
            </Field>
          )}
        </div>

        <div className="type-eyebrow text-gold-strong">{t.console.fiscal.act}</div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Field label={t.console.fiscal.actType}>
            <Input value={actType} onChange={(event) => setActType(event.target.value)} required />
          </Field>
          <Field label={t.console.fiscal.actNumber}>
            <Input
              value={actNumber}
              onChange={(event) => setActNumber(event.target.value)}
              required
              className="font-mono"
            />
          </Field>
          <Field label={t.console.fiscal.actDate}>
            <Input
              type="date"
              value={actDate}
              onChange={(event) => setActDate(event.target.value)}
              required
            />
          </Field>
          <Field label={t.console.fiscal.actTitle}>
            <Input value={actTitle} onChange={(event) => setActTitle(event.target.value)} required />
          </Field>
          <Field label={t.console.fiscal.actEffectiveFrom} hint={t.console.fiscal.actEffectiveHint}>
            <Input
              type="date"
              value={effectiveFrom}
              onChange={(event) => setEffectiveFrom(event.target.value)}
              required
            />
          </Field>
        </div>

        <div className="type-eyebrow text-gold-strong">{t.console.fiscal.gazette}</div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Field label={t.console.fiscal.gazetteYear}>
            <Input
              value={gazetteYear}
              onChange={(event) => setGazetteYear(event.target.value)}
              inputMode="numeric"
            />
          </Field>
          <Field label={t.console.fiscal.gazetteNumber}>
            <Input value={gazetteNumber} onChange={(event) => setGazetteNumber(event.target.value)} />
          </Field>
          <Field label={t.console.fiscal.gazetteArticle}>
            <Input
              value={gazetteArticle}
              onChange={(event) => setGazetteArticle(event.target.value)}
            />
          </Field>
          <Field label={t.console.fiscal.gazettePublishedAt}>
            <Input
              type="date"
              value={publishedAt}
              onChange={(event) => setPublishedAt(event.target.value)}
            />
          </Field>
        </div>

        {localError && (
          <p role="alert" className="m-0 text-sm text-danger">
            {localError}
          </p>
        )}
        {write.isError && <Failure error={write.error} />}

        <div className="flex gap-3">
          <Button type="submit" disabled={write.isPending}>
            {t.console.fiscal.save}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            {t.console.fiscal.cancel}
          </Button>
        </div>
      </form>
    </Card>
  )
}

/**
 * The typed value, as JSON for the server. Comma and dot are both decimal
 * separators (the keyboard contract, ADR-052); a table is JSON as written.
 */
function parseValue(type: ValueType, raw: string): { value?: unknown; error?: string } {
  const text = raw.trim()
  switch (type) {
    case 'table': {
      try {
        return { value: JSON.parse(text) }
      } catch {
        return { error: t.console.fiscal.valueInvalidJson }
      }
    }
    case 'boolean':
      return { value: ['da', 'true', '1', 'yes'].includes(text.toLowerCase()) }
    case 'date':
      return { value: text }
    default: {
      const number = Number(text.replace(/\s/g, '').replace(',', '.'))
      if (!Number.isFinite(number)) return { error: t.console.fiscal.valueNotANumber }
      return { value: number }
    }
  }
}
