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
import { useSearchParams } from 'react-router'

import { t } from '@/locales'
import {
  createPartner,
  updatePartner,
  listPartners,
  setPartnerActive,
  type Partner,
} from '@/shared/api/partners'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { Button, Card, Field, Input, PageHeader, Select } from '@/shared/ui'

/** What the server answers at most. Shown, not paged over. */
const CEILING = 200

export function PartnersScreen() {
  const queryClient = useQueryClient()
  // `?q=` is how the header search lands here: a partner has no screen of its
  // own yet, so choosing one from the search opens the directory already
  // filtered. Read once, into state -- the field stays editable afterwards, and
  // a URL that fought the input would make backspace impossible.
  const [params] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') ?? '')
  const [query, setQuery] = useState(params.get('q') ?? '')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<Partner | null>(null)

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
        <span className="flex gap-4">
          {/* Modificarea stă lângă retragere fiindcă sunt aceeași categorie:
              corecții pe un rând existent. Retragerea nu șterge -- o înregistrare
              postată numește partenerul --, iar modificarea nu atinge nici
              identitatea, nici TVA-ul. */}
          <button type="button" onClick={() => setEditing(partner)} className="text-accent">
            {t.partners.edit}
          </button>
          <button
            type="button"
            onClick={() => activation.mutate({ id: partner.id, active: !partner.is_active })}
            className="text-accent"
          >
            {partner.is_active ? t.partners.retire : t.partners.restore}
          </button>
        </span>
      ),
      width: '12rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title={t.partners.title}
        lead={t.partners.lead}
        actions={
          <Button icon="plus" onClick={() => setAdding((open) => !open)}>
            {adding ? t.companies.cancel : t.partners.add}
          </Button>
        }
      />

      {/* Filtrele stau SUB antet, nu în el: antetul spune unde ești, filtrele
          spun ce se afișează, iar amestecate ajung o bară pe care ochiul o
          citește ca pe un singur lucru. */}
      <div className="flex flex-wrap items-end gap-4">
        <form
          className="flex items-end gap-2"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            setQuery(search.trim())
          }}
        >
          <Input
            icon="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t.partners.search}
            className="w-80"
            aria-label={t.partners.search}
          />
          <Button variant="secondary" type="submit">
            {t.accounting.balance.show}
          </Button>
        </form>
        <label className="flex h-control-md items-center gap-2 type-body-sm text-ink-muted">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)}
            className="size-4 accent-[var(--accent-primary)]"
          />
          <span>{t.partners.showInactive}</span>
        </label>
      </div>

      {adding && (
        <NewPartnerForm
          onCreated={async () => {
            setAdding(false)
            await refresh()
          }}
        />
      )}

      {editing && (
        <EditPartnerForm
          // Keyed by the partner: fields are state, so switching rows has to
          // rebuild the form -- otherwise the second one opens holding the
          // first one's values.
          key={editing.id}
          partner={editing}
          onDone={async () => {
            setEditing(null)
            await refresh()
          }}
          onCancel={() => setEditing(null)}
        />
      )}

      {partners.isError && <Failure error={partners.error} />}
      {activation.isError && <Failure error={activation.error} />}

      {partners.data && (
        <>
          <Card padding="none">
            <DataGrid
              columns={columns}
              rows={partners.data}
              rowKey={(partner) => partner.id}
              emptyMessage={t.partners.empty}
            />
          </Card>
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
  const [internalName, setInternalName] = useState('')
  const [vatCode, setVatCode] = useState('')
  // Asked for together with the code, never derived. Whether the counterparty
  // was registered on the day of a document decides how that document is
  // treated; the day the card was typed answers a different question.
  const [vatValidFrom, setVatValidFrom] = useState('')
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
        internal_name: internalName.trim() || null,
        vat_code: vatCode.trim() || null,
        vat_valid_from: vatValidFrom || null,
        is_customer: isCustomer,
        is_supplier: isSupplier,
      }),
    onSuccess: onCreated,
  })

  const roles = isCustomer || isSupplier
  const vatComplete = vatCode.trim() === '' || vatValidFrom !== ''
  const complete = legalName.trim() !== '' && roles && vatComplete

  return (
    <form
      className="flex flex-wrap items-end gap-4 rounded border border-border bg-surface p-4"
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <Field label={t.partners.legalName}>
        <Input
          value={legalName}
          onChange={(event) => setLegalName(event.target.value)}
          maxLength={255}
          className="w-80"
        />
      </Field>

      <Field label={t.partners.shortName}>
        <Input
          value={shortName}
          onChange={(event) => setShortName(event.target.value)}
          maxLength={255}
          className="w-48"
          title={t.partners.shortNameHint}
        />
      </Field>

      <Field label={t.partners.internalName}>
        <Input
          value={internalName}
          onChange={(event) => setInternalName(event.target.value)}
          maxLength={255}
          className="w-48"
          title={t.partners.internalNameHint}
        />
      </Field>

      <Field label={t.partners.kind}>
        <Select
          value={kind}
          onChange={(event) => setKind(event.target.value)}
          className="w-48"
        >
          <option value="legal_entity">{t.partners.legalEntity}</option>
          <option value="natural_person">{t.partners.naturalPerson}</option>
        </Select>
      </Field>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-ink-muted">
          {kind === 'legal_entity' ? t.partners.idno : t.partners.idnp}
        </span>
        <Input
          value={idno}
          onChange={(event) => setIdno(event.target.value.replace(/\D/g, ''))}
          maxLength={13}
          inputMode="numeric"
          className="w-48 font-mono"
        />
      </label>

      <Field label={t.partners.vatCode}>
        <Input
          value={vatCode}
          onChange={(event) => setVatCode(event.target.value)}
          maxLength={32}
          className="w-40 font-mono"
        />
      </Field>

      <Field label={t.partners.vatValidFrom}>
        <Input
          type="date"
          value={vatValidFrom}
          onChange={(event) => setVatValidFrom(event.target.value)}
          className="w-40"
          title={t.partners.vatValidFromHint}
        />
      </Field>

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

      <Button variant="primary" type="submit" disabled={!complete || create.isPending}>
        {t.partners.create}
      </Button>

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


/**
 * Correcting a partner -- and only what a partner's form owns.
 *
 * The identity and the VAT registration are **not** here, and the note says so
 * out loud rather than leaving a person to discover it: `idno` is what an issued
 * document names the counterparty by, and what keeps two records from splitting
 * one balance (`R20`); a VAT registration is a dated state, so it is added, never
 * overwritten. The server refuses either by name if a caller sends it.
 *
 * A separate form from the one that creates, deliberately. One form in two modes
 * would have to hide half its fields in one of them, and a hidden field is how a
 * value gets cleared by a form that never showed it.
 */
function EditPartnerForm({
  partner,
  onDone,
  onCancel,
}: {
  partner: Partner
  onDone: () => Promise<void> | void
  onCancel: () => void
}) {
  const [legalName, setLegalName] = useState(partner.legal_name)
  const [shortName, setShortName] = useState(partner.short_name ?? '')
  const [internalName, setInternalName] = useState(partner.internal_name ?? '')
  const [currency, setCurrency] = useState(partner.default_currency ?? '')
  const [terms, setTerms] = useState(
    partner.default_payment_terms_days === null ? '' : String(partner.default_payment_terms_days),
  )
  const [isCustomer, setIsCustomer] = useState(partner.is_customer)
  const [isSupplier, setIsSupplier] = useState(partner.is_supplier)

  const save = useMutation({
    mutationFn: () =>
      updatePartner(partner.id, {
        legal_name: legalName.trim(),
        short_name: shortName.trim() || null,
        internal_name: internalName.trim() || null,
        default_currency: currency.trim() || null,
        default_payment_terms_days: terms.trim() === '' ? null : Number(terms),
        is_customer: isCustomer,
        is_supplier: isSupplier,
      }),
    onSuccess: onDone,
  })

  const roles = isCustomer || isSupplier
  const complete = legalName.trim() !== '' && roles

  return (
    <Card>
      <form
        className="flex flex-wrap items-end gap-4"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <Field label={t.partners.legalName}>
          <Input
            value={legalName}
            onChange={(event) => setLegalName(event.target.value)}
            maxLength={255}
            className="w-80"
          />
        </Field>

        <Field label={t.partners.shortName} hint={t.partners.shortNameHint}>
          <Input
            value={shortName}
            onChange={(event) => setShortName(event.target.value)}
            maxLength={255}
            className="w-48"
          />
        </Field>

        <Field label={t.partners.internalName} hint={t.partners.internalNameHint}>
          <Input
            value={internalName}
            onChange={(event) => setInternalName(event.target.value)}
            maxLength={255}
            className="w-48"
          />
        </Field>

        <Field label={t.partners.defaultCurrency}>
          <Input
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase().slice(0, 3))}
            className="w-24 font-mono"
          />
        </Field>

        <Field label={t.partners.paymentTerms} hint={t.partners.paymentTermsHint}>
          <Input
            value={terms}
            onChange={(event) => setTerms(event.target.value.replace(/\D/g, ''))}
            inputMode="numeric"
            maxLength={3}
            className="w-24"
          />
        </Field>

        <span className="flex h-control-md items-center gap-4 type-body-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={isCustomer}
              onChange={(event) => setIsCustomer(event.target.checked)}
              className="size-4 accent-[var(--accent-primary)]"
            />
            {t.partners.customer}
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={isSupplier}
              onChange={(event) => setIsSupplier(event.target.checked)}
              className="size-4 accent-[var(--accent-primary)]"
            />
            {t.partners.supplier}
          </label>
        </span>

        <Button variant="primary" type="submit" disabled={!complete || save.isPending}>
          {t.common.save}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {t.companies.cancel}
        </Button>

        {!roles && <p className="m-0 type-body-sm text-danger">{t.partners.rolesRequired}</p>}
        {save.isError && <Failure error={save.error} />}
      </form>

      <p className="mt-4 mb-0 type-body-sm text-ink-faint">{t.partners.identityNotHere}</p>
    </Card>
  )
}
