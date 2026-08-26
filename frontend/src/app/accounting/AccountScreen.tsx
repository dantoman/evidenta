/**
 * One account, and the three things a company may do to it.
 *
 * Rename, block, close -- each its own request, never one "update". They are
 * different operations with different rules and different audit entries on the
 * server, and collapsing them into a full replacement would make "what changed"
 * a diff somebody has to reconstruct. An audit trail is exactly what must not be
 * reconstructed, so the screen is shaped like the services rather than like the
 * row.
 *
 * **A system account is not renamed** (`coa.system_account_immutable`): those are
 * maintained centrally, from the published version the chart was built on.
 * Blocking and closing stay available, because those are the company's own
 * decisions about its own bookkeeping and neither changes what the account *is*.
 * The screen says which of the three is unavailable and why, rather than letting
 * the server refuse a control that looked live.
 *
 * The name is a stored value in Romanian (C33, ADR-016) -- displayed as it
 * arrives, and edited as itself. Nothing here translates one.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { t } from '@/locales'
import { date } from '@/shared/format'
import {
  createSubaccount,
  getAccount,
  updateAccount,
  type Account,
  type AccountChange,
  type AccountClass,
} from '@/shared/api/coa'
import { Failure } from '@/shared/Failure'

const CLASS_LABEL: Record<AccountClass, string> = {
  asset: t.accounting.classes.asset,
  liability: t.accounting.classes.liability,
  equity: t.accounting.classes.equity,
  income: t.accounting.classes.income,
  expense: t.accounting.classes.expense,
}

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

export function AccountScreen() {
  const { companyId = '', accountId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const account = useQuery({
    queryKey: ['account', accountId],
    queryFn: () => getAccount(accountId),
  })

  /**
   * One invalidation for every write: the account itself and the chart it sits
   * in. The grid shows the state and the name, so a rename that refreshed only
   * this screen would leave the chart displaying the old one until something
   * else happened to refetch it.
   */
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['account', accountId] })
    await queryClient.invalidateQueries({ queryKey: ['accounts', companyId] })
  }

  const change = useMutation({
    mutationFn: (patch: AccountChange) => updateAccount(accountId, patch),
    onSuccess: refresh,
  })

  const addSubaccount = useMutation({
    mutationFn: (subaccount: Parameters<typeof createSubaccount>[1]) =>
      createSubaccount(companyId, subaccount),
    onSuccess: async (created: Account) => {
      await refresh()
      void navigate(`/companii/${companyId}/conturi/${created.id}`)
    },
  })

  if (account.isPending) {
    return <p className="text-sm text-ink-muted">{t.app.loading}</p>
  }
  if (account.isError) {
    return <Failure error={account.error} />
  }

  const row = account.data
  const isSystem = row.origin === 'system'

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <Link to={`/companii/${companyId}/plan-de-conturi`} className="text-sm text-accent">
          {t.common.back} — {t.accounting.chart.title}
        </Link>
        <h1 className="text-base font-semibold">
          <span className="font-mono">{row.account_code}</span> {row.name_ro}
        </h1>
      </header>

      <dl className="grid grid-cols-[10rem_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-ink-muted">{t.accounting.account.class}</dt>
        <dd>{CLASS_LABEL[row.account_class]}</dd>

        <dt className="text-ink-muted">{t.accounting.account.normalBalance}</dt>
        <dd>
          {row.normal_balance === 'debit'
            ? t.accounting.account.debit
            : t.accounting.account.credit}
        </dd>

        <dt className="text-ink-muted">{t.accounting.account.origin}</dt>
        <dd>
          {isSystem
            ? t.accounting.chart.originSystem
            : t.accounting.chart.originCompany}
        </dd>

        <dt className="text-ink-muted">{t.accounting.account.parent}</dt>
        <dd>
          {row.parent_id ? (
            <Link
              to={`/companii/${companyId}/conturi/${row.parent_id}`}
              className="text-accent"
            >
              {t.accounting.account.parent}
            </Link>
          ) : (
            t.common.none
          )}
        </dd>

        <dt className="text-ink-muted">{t.accounting.account.validFrom}</dt>
        <dd>{date(row.valid_from)}</dd>

        <dt className="text-ink-muted">{t.accounting.account.validTo}</dt>
        <dd>{row.valid_to ? date(row.valid_to) : t.common.none}</dd>

        <dt className="text-ink-muted">{t.accounting.account.state}</dt>
        <dd className={row.is_blocked ? 'text-danger' : ''}>
          {row.is_blocked
            ? t.accounting.chart.blocked
            : row.valid_to
              ? t.accounting.chart.closed
              : t.accounting.chart.open}
        </dd>

        <dt className="text-ink-muted">{t.accounting.account.tracking}</dt>
        <dd>
          {[
            row.currency_tracking && t.accounting.account.currencyTracking,
            row.quantity_tracking && t.accounting.account.quantityTracking,
            row.allows_subaccounts && t.accounting.account.allowsSubaccounts,
          ]
            .filter(Boolean)
            .join(', ') || t.common.none}
        </dd>

        <dt className="text-ink-muted">{t.accounting.account.requiredDimensions}</dt>
        {/* The keys as the server stores them. They are a closed vocabulary
            (ADR-029), not interface words, and a translation invented here would
            be a second name for a column the posting engine matches by key. */}
        <dd className="font-mono">
          {row.required_dimensions.length > 0
            ? row.required_dimensions.join(', ')
            : t.common.none}
        </dd>
      </dl>

      {change.isError && <Failure error={change.error} />}
      {change.isSuccess && !change.isPending && (
        <p className="text-sm text-ink-muted">{t.accounting.account.saved}</p>
      )}

      {/* Keyed by the account, and on the component rather than inside it: the
          three forms below seed their fields from the account they were handed,
          and `useState` belongs to the component instance. Without the key, the
          route stays mounted while `:accountId` changes -- so one account's name
          would be offered as an edit of another's, and its closing date as that
          one's. The first version put the key on the form's own root element,
          which re-mounts the markup and keeps exactly the state that is wrong. */}
      <Rename
        key={`rename-${row.id}`}
        account={row}
        disabled={isSystem}
        onSave={(name) => change.mutate({ name_ro: name })}
      />

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold">
          {row.is_blocked ? t.accounting.account.unblock : t.accounting.account.block}
        </h2>
        <div>
          <button
            type="button"
            disabled={change.isPending}
            onClick={() => change.mutate({ is_blocked: !row.is_blocked })}
            className={BUTTON}
          >
            {row.is_blocked ? t.accounting.account.unblock : t.accounting.account.block}
          </button>
        </div>
      </section>

      <Close
        key={`close-${row.id}`}
        account={row}
        disabled={change.isPending}
        onClose={(until) => change.mutate({ valid_to: until })}
      />

      <Subaccount
        key={`subaccount-${row.id}`}
        account={row}
        pending={addSubaccount.isPending}
        error={addSubaccount.error}
        onCreate={(input) => addSubaccount.mutate({ ...input, parent_id: row.id })}
      />
    </section>
  )
}

function Rename({
  account,
  disabled,
  onSave,
}: {
  account: Account
  disabled: boolean
  onSave: (name: string) => void
}) {
  const [name, setName] = useState(account.name_ro)

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">{t.accounting.account.rename}</h2>
      {disabled ? (
        <p className="text-sm text-ink-muted">{t.accounting.account.renameSystem}</p>
      ) : (
        <form
          className="flex items-center gap-2"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            onSave(name)
          }}
        >
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={255}
            className={`${FIELD} w-96`}
            aria-label={t.accounting.account.name}
          />
          <button
            type="submit"
            disabled={name.trim() === '' || name === account.name_ro}
            className={BUTTON}
          >
            {t.common.save}
          </button>
        </form>
      )}
    </section>
  )
}

function Close({
  account,
  disabled,
  onClose,
}: {
  account: Account
  disabled: boolean
  onClose: (until: string) => void
}) {
  const [until, setUntil] = useState(account.valid_to ?? '')

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">{t.accounting.account.close}</h2>
      <form
        className="flex items-center gap-2"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          onClose(until)
        }}
      >
        <label className="flex items-center gap-2 text-sm">
          <span className="text-ink-muted">{t.accounting.account.closeFrom}</span>
          <input
            type="date"
            value={until}
            onChange={(event) => setUntil(event.target.value)}
            className={FIELD}
          />
        </label>
        <button type="submit" disabled={until === '' || disabled} className={BUTTON}>
          {t.accounting.account.closeAction}
        </button>
      </form>
    </section>
  )
}

interface SubaccountInput {
  account_code: string
  name_ro: string
  valid_from: string
  currency_tracking: boolean
  quantity_tracking: boolean
  allows_subaccounts: boolean
}

function Subaccount({
  account,
  pending,
  error,
  onCreate,
}: {
  account: Account
  pending: boolean
  error: unknown
  onCreate: (input: SubaccountInput) => void
}) {
  const [input, setInput] = useState<SubaccountInput>({
    account_code: '',
    name_ro: '',
    // The parent's own start, because a subaccount may not begin before it --
    // the service refuses that outright (`coa.invalid_validity_window`), and a
    // default of today would be refused for every account opened later.
    valid_from: account.valid_from,
    currency_tracking: false,
    quantity_tracking: false,
    allows_subaccounts: false,
  })

  if (!account.allows_subaccounts) {
    return (
      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold">{t.accounting.account.subaccount}</h2>
        <p className="text-sm text-ink-muted">{t.accounting.account.subaccountNotAllowed}</p>
      </section>
    )
  }

  const set = <K extends keyof SubaccountInput>(key: K, value: SubaccountInput[K]) =>
    setInput((current) => ({ ...current, [key]: value }))

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">{t.accounting.account.subaccount}</h2>
      <form
        className="flex flex-wrap items-center gap-4"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          onCreate(input)
        }}
      >
        <label className="flex items-center gap-2 text-sm">
          <span className="text-ink-muted">{t.accounting.account.code}</span>
          <input
            value={input.account_code}
            onChange={(event) => set('account_code', event.target.value)}
            maxLength={64}
            className={`${FIELD} w-32 font-mono`}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-ink-muted">{t.accounting.account.name}</span>
          <input
            value={input.name_ro}
            onChange={(event) => set('name_ro', event.target.value)}
            maxLength={255}
            className={`${FIELD} w-96`}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-ink-muted">{t.accounting.account.validFrom}</span>
          <input
            type="date"
            value={input.valid_from}
            onChange={(event) => set('valid_from', event.target.value)}
            className={FIELD}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={input.currency_tracking}
            onChange={(event) => set('currency_tracking', event.target.checked)}
          />
          <span className="text-ink-muted">{t.accounting.account.currencyTracking}</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={input.quantity_tracking}
            onChange={(event) => set('quantity_tracking', event.target.checked)}
          />
          <span className="text-ink-muted">{t.accounting.account.quantityTracking}</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={input.allows_subaccounts}
            onChange={(event) => set('allows_subaccounts', event.target.checked)}
          />
          <span className="text-ink-muted">{t.accounting.account.allowsSubaccounts}</span>
        </label>
        <button
          type="submit"
          disabled={pending || input.account_code.trim() === '' || input.name_ro.trim() === ''}
          className={BUTTON}
        >
          {t.common.add}
        </button>
      </form>
      <p className="text-sm text-ink-muted">{t.accounting.account.subaccountDimensions}</p>
      {error ? <Failure error={error} /> : null}
    </section>
  )
}
