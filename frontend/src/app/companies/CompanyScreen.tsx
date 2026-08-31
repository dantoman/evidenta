/**
 * One company: what may be corrected, what may not, and how it is closed.
 *
 * The screen exists because the list had no answer to "how do I fix a name" --
 * and the answer turned out to have three parts, which is why they are three
 * visible zones rather than one form (ADR-083).
 *
 * **The rights are read, not assumed.** Reaching a company and being allowed to
 * change it are different questions: a firm's user may hold access to the books
 * and no key over the card. The workspace endpoint already reports which role
 * this reader holds here and what that role may do, so the controls are shown
 * against the answer instead of failing on save.
 *
 * `legal_name` is what appears, never an internal name (C39).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { t } from '@/locales'
import {
  closeCompany,
  getCompany,
  updateCompany,
  type Company,
  type EditableCompany,
} from '@/shared/api/companies'
import { workspace } from '@/shared/api/workspace'
import { Failure } from '@/shared/Failure'
import { Badge, Button, Card, Field, Input, PageHeader } from '@/shared/ui'

const STATUS_LABEL: Record<string, string> = {
  active: t.companies.statusActive,
  suspended: t.companies.statusSuspended,
  closed: t.companies.statusClosed,
}

export function CompanyScreen() {
  const { companyId = '' } = useParams()
  const queryClient = useQueryClient()

  const company = useQuery({
    queryKey: ['company', companyId],
    queryFn: () => getCompany(companyId),
  })
  const space = useQuery({ queryKey: ['workspace'], queryFn: workspace })

  // What this reader may do *here*. A key held on another company of the same
  // workspace does not travel -- the permissions are company-scoped, and so is
  // this lookup.
  const access = space.data?.me.companies.find((row) => row.company_id === companyId)
  const role = space.data?.roles.find((row) => row.key === access?.role_key)
  const may = (key: string) => role?.permissions.includes(key) ?? false

  if (company.isPending) return <p className="text-sm text-ink-muted">{t.app.loading}</p>
  if (company.isError) return <Failure error={company.error} />

  const row = company.data
  const open = row.status === 'active'

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.companies.title}
        title={row.legal_name}
        lead={t.companies.cardLead}
        actions={
          <div className="flex items-center gap-2">
            <Link to={`/companii/${companyId}/plan-de-conturi`}>
              <Button variant="ghost">{t.companies.openChart}</Button>
            </Link>
            <Link to={`/companii/${companyId}/angajati`}>
              <Button variant="ghost">{t.companies.openPeople}</Button>
            </Link>
          </div>
        }
      />

      {!open && (
        <Card>
          <p className="text-sm text-ink-muted">{t.companies.closed}</p>
        </Card>
      )}

      <EditableZone
        company={row}
        allowed={may('company.edit') && open}
        onSaved={() => {
          void queryClient.invalidateQueries({ queryKey: ['company', companyId] })
          void queryClient.invalidateQueries({ queryKey: ['companies'] })
        }}
      />

      <FixedZone company={row} />

      {open && (
        <CloseZone
          companyId={companyId}
          allowed={may('company.close')}
          onClosed={() => {
            void queryClient.invalidateQueries({ queryKey: ['company', companyId] })
            void queryClient.invalidateQueries({ queryKey: ['companies'] })
          }}
        />
      )}
    </section>
  )
}

/** The four fields nothing outside the system stands on. */
function EditableZone({
  company,
  allowed,
  onSaved,
}: {
  company: Company
  allowed: boolean
  onSaved: () => void
}) {
  const [form, setForm] = useState<EditableCompany>({
    legal_name: company.legal_name,
    short_name: company.short_name ?? '',
    cuatm_code: company.cuatm_code ?? '',
    caem_code: company.caem_code ?? '',
  })
  // The server is the source: after a save, or after somebody else's, the fields
  // follow the row rather than keeping what was typed into a stale form.
  useEffect(() => {
    setForm({
      legal_name: company.legal_name,
      short_name: company.short_name ?? '',
      cuatm_code: company.cuatm_code ?? '',
      caem_code: company.caem_code ?? '',
    })
  }, [company])

  const save = useMutation({
    mutationFn: (fields: EditableCompany) => updateCompany(company.id, fields),
    onSuccess: onSaved,
  })

  return (
    <Card>
      <form
        className="flex flex-wrap items-end gap-4"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          save.mutate({
            legal_name: form.legal_name,
            short_name: form.short_name || null,
            cuatm_code: form.cuatm_code || null,
            caem_code: form.caem_code || null,
          })
        }}
      >
        <Field label={t.companies.legalName}>
          <Input
            value={form.legal_name ?? ''}
            onChange={(event) => setForm({ ...form, legal_name: event.target.value })}
            maxLength={255}
            disabled={!allowed}
            className="w-96"
          />
        </Field>
        <Field label={t.companies.shortName}>
          <Input
            value={form.short_name ?? ''}
            onChange={(event) => setForm({ ...form, short_name: event.target.value })}
            maxLength={255}
            disabled={!allowed}
            className="w-48"
          />
        </Field>
        <Field label={t.payroll.cuatm}>
          <Input
            value={form.cuatm_code ?? ''}
            onChange={(event) => setForm({ ...form, cuatm_code: event.target.value })}
            maxLength={16}
            disabled={!allowed}
            className="w-28 font-mono"
          />
        </Field>
        <Field label={t.payroll.caem}>
          <Input
            value={form.caem_code ?? ''}
            onChange={(event) => setForm({ ...form, caem_code: event.target.value })}
            maxLength={16}
            disabled={!allowed}
            className="w-28 font-mono"
          />
        </Field>
        <Button variant="primary" type="submit" disabled={!allowed || save.isPending}>
          {save.isPending ? t.companies.saving : t.companies.save}
        </Button>
      </form>

      {!allowed && <p className="mt-3 text-sm text-ink-muted">{t.companies.noEditRight}</p>}
      {save.isError && <Failure error={save.error} />}
      {save.isSuccess && <p className="mt-3 text-sm text-ink-muted">{t.companies.saved}</p>}
    </Card>
  )
}

/** What the card shows and does not offer to change, with the reason. */
function FixedZone({ company }: { company: Company }) {
  return (
    <Card>
      <h2 className="type-title-sm mb-1">{t.companies.fixed}</h2>
      <p className="mb-4 text-sm text-ink-muted">{t.companies.fixedWhy}</p>
      <dl className="flex flex-wrap gap-8">
        <Fact label={t.companies.idno} value={company.idno} mono />
        <Fact label={t.companies.currency} value={company.functional_currency} mono />
        <Fact label={t.companies.accountingStart} value={company.accounting_start_date} mono />
        <div>
          <dt className="type-label text-ink-faint">{t.companies.status}</dt>
          <dd className="mt-1">
            <Badge>{STATUS_LABEL[company.status] ?? company.status}</Badge>
          </dd>
        </div>
      </dl>
    </Card>
  )
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="type-label text-ink-faint">{label}</dt>
      <dd className={mono ? 'mt-1 font-mono' : 'mt-1'}>{value}</dd>
    </div>
  )
}

/** Closing: its own key, its own reason, and no deletion anywhere near it. */
function CloseZone({
  companyId,
  allowed,
  onClosed,
}: {
  companyId: string
  allowed: boolean
  onClosed: () => void
}) {
  const [reason, setReason] = useState('')
  const close = useMutation({
    mutationFn: () => closeCompany(companyId, reason.trim()),
    onSuccess: onClosed,
  })

  return (
    <Card>
      <h2 className="type-title-sm mb-1">{t.companies.close}</h2>
      <p className="mb-4 text-sm text-ink-muted">{t.companies.closeLead}</p>
      <div className="flex flex-wrap items-end gap-4">
        <Field label={t.companies.closeReason}>
          <Input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
            disabled={!allowed}
            className="w-96"
          />
        </Field>
        <Button
          onClick={() => close.mutate()}
          disabled={!allowed || reason.trim() === '' || close.isPending}
        >
          {close.isPending ? t.companies.closing : t.companies.close}
        </Button>
      </div>
      {!allowed && <p className="mt-3 text-sm text-ink-muted">{t.companies.noCloseRight}</p>}
      {close.isError && <Failure error={close.error} />}
    </Card>
  )
}
