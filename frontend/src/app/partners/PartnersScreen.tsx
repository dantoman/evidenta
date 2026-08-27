/**
 * The partner directory -- clients and suppliers, for the whole workspace.
 *
 * **Not under a company, and that is the design rather than a routing choice.**
 * A partner belongs to the tenant: the same legal entity is the same entity for
 * every company of the firm, and a copy per company is how a holding ends up
 * with two identical suppliers whose balances stop reconciling. So the address
 * has no company segment, and the screen is reached from the header.
 *
 * It exists because the opening-balances form could *select* a partner and
 * nothing could *create* one -- the API had landed with no way in, which is the
 * same gap that kept storno, opening balances and templates unreachable.
 *
 * **`legal_name` is what reaches a document or a register** (C39). The short
 * name exists for this screen and for searching, and the form says so where
 * somebody is typing it, not only in a comment.
 *
 * The server answers at most 200 rows and does not paginate, so the screen says
 * when it is at that ceiling instead of implying the list is complete.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { t } from '@/locales'
import {
  createPartner,
  listPartners,
  setPartnerActive,
  type Partner,
} from '@/shared/api/partners'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'
const BUTTON =
  'rounded border border-border bg-surface px-3 text-sm text-accent disabled:text-ink-muted'

/** What the server answers at most. Shown, not paged over. */
const CEILING = 200

export function PartnersScreen() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [adding, setAdding] = useState(false)

  const partners = useQuery({
    queryKey: ['partners-directory', query, includeInactive],
    queryFn: () => listPartners({ q: query || undefined, includeInactive }),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['partners-directory'] })

  const activation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      setPartnerActive(id, active),
    onSuccess: refresh,
  })

  const columns: Column<Partner>[] = [
    {
      key: 'legal_name',
      header: t.partners.legalName,
      cell: (partner) => (
        <span className={partner.is_active ? '' : 'text-ink-muted'}>
          {partner.legal_name}
          {partner.short_name && (
            <span className="text-ink-muted"> · {partner.short_name}</span>
          )}
        </span>
      ),
    },
    {
      key: 'idno',
      header: t.partners.idno,
      // A code, so a monospaced face: IDNO is compared digit by digit.
      cell: (partner) => <span className="font-mono">{partner.idno ?? partner.idnp ?? ''}</span>,
      width: '12rem',
    },
    {
      key: 'roles',
      header: t.partners.roles,
      cell: (partner) =>
        [
          partner.is_customer && t.partners.customer,
          partner.is_supplier && t.partners.supplier,
        ]
          .filter(Boolean)
          .join(', '),
      width: '12rem',
    },
    {
      key: 'state',
      header: t.partners.state,
      cell: (partner) => (
        <span className={partner.is_active ? 'text-ink-muted' : 'text-danger'}>
          {partner.is_active ? t.partners.active : t.partners.inactive}
        </span>
      ),
      width: '8rem',
    },
    {
      key: 'action',
      header: '',
      cell: (partner) => (
        <button
          type="button"
          onClick={() => activation.mutate({ id: partner.id, active: !partner.is_active })}
          className="text-accent"
        >
          {partner.is_active ? t.partners.retire : t.partners.restore}
        </button>
      ),
      width: '10rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-semibold">{t.partners.title}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <form
            className="flex items-center gap-2"
            onSubmit={(event: FormEvent) => {
              event.preventDefault()
              setQuery(search.trim())
            }}
          >
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t.partners.search}
              className={`${FIELD} w-72`}
              aria-label={t.partners.search}
            />
            <button type="submit" className={BUTTON}>
              {t.accounting.balance.show}
            </button>
          </form>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            <span className="text-ink-muted">{t.partners.showInactive}</span>
          </label>
          <button type="button" onClick={() => setAdding((open) => !open)} className={BUTTON}>
            {adding ? t.companies.cancel : t.partners.add}
          </button>
        </div>
      </header>

      {adding && (
        <NewPartnerForm
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}

      {partners.isError && <Failure error={partners.error} />}
      {activation.isError && <Failure error={activation.error} />}

      {partners.data && (
        <>
          <DataGrid
            columns={columns}
            rows={partners.data}
            rowKey={(partner) => partner.id}
            emptyMessage={t.partners.empty}
          />
          {partners.data.length === CEILING && (
            <p className="text-sm text-ink-muted">{t.partners.truncated}</p>
          )}
        </>
      )}
    </section>
  )
}

function NewPartnerForm({ onCreated }: { onCreated: () => Promise<void> | void }) {
  const [legalName, setLegalName] = useState('')
  const [shortName, setShortName] = useState('')
  const [kind, setKind] = useState('legal_entity')
  const [idno, setIdno] = useState('')
  const [vatCode, setVatCode] = useState('')
  const [isCustomer, setIsCustomer] = useState(true)
  const [isSupplier, setIsSupplier] = useState(false)

  const create = useMutation({
    mutationFn: () =>
      createPartner({
        legal_name: legalName.trim(),
        kind,
        short_name: shortName.trim() || null,
        // A legal entity carries an IDNO, a natural person an IDNP. The same
        // field, sent under the name the server knows it by -- the form does not
        // ask a person which column they are filling.
        idno: kind === 'legal_entity' ? idno.trim() || null : null,
        idnp: kind === 'natural_person' ? idno.trim() || null : null,
        vat_code: vatCode.trim() || null,
        is_customer: isCustomer,
        is_supplier: isSupplier,
      }),
    onSuccess: onCreated,
  })

  const roles = isCustomer || isSupplier
  const complete = legalName.trim() !== '' && roles

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.partners.legalName}</span>
        <input
          value={legalName}
          onChange={(event) => setLegalName(event.target.value)}
          maxLength={255}
          className={`${FIELD} w-80`}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.partners.shortName}</span>
        <input
          value={shortName}
          onChange={(event) => setShortName(event.target.value)}
          maxLength={255}
          className={`${FIELD} w-48`}
          title={t.partners.shortNameHint}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.partners.kind}</span>
        <select
          value={kind}
          onChange={(event) => setKind(event.target.value)}
          className={`${FIELD} w-48`}
        >
          <option value="legal_entity">{t.partners.legalEntity}</option>
          <option value="natural_person">{t.partners.naturalPerson}</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">
          {kind === 'legal_entity' ? t.partners.idno : t.partners.idnp}
        </span>
        <input
          value={idno}
          onChange={(event) => setIdno(event.target.value.replace(/\D/g, ''))}
          maxLength={13}
          inputMode="numeric"
          className={`${FIELD} w-48 font-mono`}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">{t.partners.vatCode}</span>
        <input
          value={vatCode}
          onChange={(event) => setVatCode(event.target.value)}
          maxLength={32}
          className={`${FIELD} w-40 font-mono`}
        />
      </label>

      <label className="flex items-center gap-2 pb-1 text-sm">
        <input
          type="checkbox"
          checked={isCustomer}
          onChange={(event) => setIsCustomer(event.target.checked)}
        />
        <span className="text-ink-muted">{t.partners.customer}</span>
      </label>
      <label className="flex items-center gap-2 pb-1 text-sm">
        <input
          type="checkbox"
          checked={isSupplier}
          onChange={(event) => setIsSupplier(event.target.checked)}
        />
        <span className="text-ink-muted">{t.partners.supplier}</span>
      </label>

      <button type="submit" disabled={!complete || create.isPending} className={BUTTON}>
        {t.partners.create}
      </button>

      <p className="w-full text-sm text-ink-muted">{t.partners.shortNameHint}</p>
      {!roles && <p className="w-full text-sm text-danger">{t.partners.rolesRequired}</p>}
      {create.isError && (
        <div className="w-full">
          <Failure error={create.error} />
        </div>
      )}
    </form>
  )
}
