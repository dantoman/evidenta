/**
 * The workspace: who holds the account, and what the reader may do in it.
 *
 * It exists because nothing said either. The subdomain was the only visible fact
 * about the account holder -- so *whose books are these* was a question the
 * product answered nowhere -- and the rights a person holds were readable only in
 * the database.
 *
 * **The distinction it is built around** is the one that produced the question:
 * the workspace is the contract, the company is the accounting entity. A holder
 * that keeps its own books does so as one of its companies, and the screen says
 * so plainly rather than letting the reader infer that a workspace has a ledger.
 *
 * **What it refuses to show:** the other people of the workspace. `membership` is
 * policed self-row, so a list would come back holding the reader alone and look
 * like an answer. The screen states the limit and names the decision that would
 * lift it.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { t } from '@/locales'
import { listCompanies } from '@/shared/api/companies'
import { workspace, type WorkspaceRole } from '@/shared/api/workspace'
import {
  approveSupportGrant,
  listSupportGrants,
  revokeSupportGrant,
  type SupportGrant,
} from '@/shared/api/support'
import { dateTime } from '@/shared/format'
import { DataGrid, type Column } from '@/shared/DataGrid'
import { Failure } from '@/shared/Failure'
import { updateProfile } from '@/shared/api/auth'
import { Badge, Button, Card, Field, Icon, Input, PageHeader, Select } from '@/shared/ui'

const MEMBERSHIP_LABEL: Record<string, string> = {
  active: t.workspace.membershipActive,
  invited: t.workspace.membershipInvited,
  suspended: t.workspace.membershipSuspended,
}

const TENANT_STATE_LABEL: Record<string, string> = {
  active: t.workspace.stateActive,
  suspended: t.workspace.stateSuspended,
  offboarding: t.workspace.stateOffboarding,
  archived: t.workspace.stateArchived,
}

function permissionLabel(key: string): string {
  // The key itself when the catalogue gained one this file has not: a right
  // shown as its key is legible; a right silently dropped is not.
  return t.permissions[key] ?? key
}

export function WorkspaceScreen() {
  const [renaming, setRenaming] = useState(false)
  const space = useQuery({ queryKey: ['workspace'], queryFn: workspace })
  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })

  if (space.isPending) return <p className="type-body-md text-ink-muted">{t.app.loading}</p>
  if (space.isError) return <Failure error={space.error} />

  const { tenant, me, roles, delegated_access: delegated } = space.data
  const named = new Map((companies.data ?? []).map((row) => [row.id, row]))

  const accessColumns: Column<(typeof me.companies)[number]>[] = [
    {
      key: 'company',
      header: t.companies.legalName,
      cell: (row) => {
        const company = named.get(row.company_id)
        return company ? (
          <Link to={`/companii/${company.id}/plan-de-conturi`} className="text-link">
            {company.legal_name}
          </Link>
        ) : (
          <span className="type-figure-sm text-ink-muted">{row.company_id}</span>
        )
      },
    },
    {
      key: 'idno',
      header: t.companies.idno,
      cell: (row) => <span className="type-figure-sm">{named.get(row.company_id)?.idno ?? '—'}</span>,
      width: '12rem',
    },
    {
      key: 'granted_via',
      header: t.workspace.membership,
      cell: (row) => (
        <Badge tone={row.granted_via === 'engagement' ? 'gold' : 'navy'}>
          {row.granted_via === 'engagement'
            ? t.workspace.grantedViaEngagement
            : t.workspace.grantedViaMembership}
        </Badge>
      ),
      width: '14rem',
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      {/* Fără supratitlu: spunea „Spaţiu de lucru · alpha" deasupra titlului
          „Spaţiul de lucru" -- acelaşi cuvânt de două ori, la un rând distanţă.
          Adresa e în bara laterală şi în bara de adrese.

          Şi fără denumirea spaţiului ca titlu: `tenant.legal_name` poartă azi
          „Alpha SRL" fiindcă spaţiul a fost creat cu numele unei firme, iar
          afişată aici făcea spaţiul să arate încă o dată a companie -- pe un
          ecran din care tocmai scosesem tot ce arăta aşa. Denumirea rămâne în
          date; ADR-085 §5 o mută la `display_name`, fiindcă „legal" e o scurgere
          de nume: un spaţiu de lucru nu ajunge niciodată pe un document (C39).
          Starea stă lângă titlu: un cartonaş întreg pentru o etichetă era
          zgomot. */}
      <PageHeader
        title={t.workspace.title}
        lead={t.workspace.lead}
        actions={
          <Badge tone={tenant.status === 'active' ? 'credit' : 'caution'}>
            {TENANT_STATE_LABEL[tenant.status] ?? tenant.status}
          </Badge>
        }
      />

      {/* Titularul e PERSOANA (ADR-085). Spaţiul de lucru se atribuie unui
          utilizator, iar companiile dinăuntru sunt egale între ele -- cazul
          obişnuit în Moldova e un antreprenor cu mai multe firme, nu un holding
          cu o companie-mamă. */}
      <Card
        crestRule
        eyebrow={t.workspace.holder}
        title={me.full_name || me.email}
        actions={
          <Button variant="secondary" onClick={() => setRenaming((open) => !open)}>
            {renaming ? t.companies.cancel : t.workspace.editName}
          </Button>
        }
      >
        {renaming && <RenameForm current={me.full_name} onDone={() => setRenaming(false)} />}
        <dl className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-[auto_1fr]">
          <dt className="type-label text-ink-muted">{t.workspace.email}</dt>
          <dd className="m-0 type-body-sm">{me.email}</dd>
          <dt className="type-label text-ink-muted">{t.workspace.myRole}</dt>
          <dd className="m-0 flex flex-wrap items-center gap-2">
            {me.role ? (
              <Badge tone="navy">{t.roles[me.role.key] ?? me.role.name}</Badge>
            ) : (
              <span className="type-body-sm">{t.workspace.noRole}</span>
            )}
            {me.membership_status && (
              <Badge tone={me.membership_status === 'active' ? 'credit' : 'caution'}>
                {MEMBERSHIP_LABEL[me.membership_status] ?? me.membership_status}
              </Badge>
            )}
          </dd>
        </dl>
        {me.role && <Permissions role={me.role} />}
        {/* Fără limită de măsură: textul e scurt și stă într-un cartonaş îngust
            oricum, iar un `max-w` peste el rupea rândurile la jumătatea lăţimii
            şi lăsa dreapta goală. Măsura de lectură are rost la un paragraf
            lung pe o pagină lată -- nu la două propoziţii într-o casetă. */}
        <p className="mt-4 mb-0 type-body-sm text-ink-muted">
          {t.workspace.holderNote}
        </p>
        <p className="mt-2 mb-0 type-body-sm text-ink-faint">
          {t.workspace.peopleUnavailable}
        </p>
      </Card>

      <Card eyebrow={t.workspace.myCompanies} title={t.companies.title} padding="none">
        <DataGrid
          columns={accessColumns}
          rows={me.companies}
          rowKey={(row) => row.company_id}
          emptyMessage={t.workspace.noCompanyAccess}
        />
      </Card>

      <Card eyebrow={t.workspace.roles} title={t.workspace.roles}>
        <div className="mt-4 flex flex-col gap-4">
          {roles.map((role) => (
            <div key={role.key} className="border-t border-border pt-3 first:border-0 first:pt-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="type-label text-heading">{role.name}</span>
                <Badge tone="neutral">
                  {role.level === 'tenant'
                    ? t.workspace.roleLevelTenant
                    : t.workspace.roleLevelCompany}
                </Badge>
                {role.is_system && <Badge tone="gold">{t.workspace.roleSystem}</Badge>}
              </div>
              <Permissions role={role} />
            </div>
          ))}
        </div>
      </Card>

      <SupportGrants canDecide={(me.role?.permissions ?? []).includes('tenant.approve_support_access')} />

      <Card eyebrow={t.workspace.delegated} title={t.workspace.delegated}>
        <p className="mt-3 mb-0 type-body-sm text-ink-muted">{t.workspace.delegatedLead}</p>
        {delegated.length === 0 ? (
          <p className="mt-3 mb-0 type-body-md">{t.workspace.noDelegated}</p>
        ) : (
          <ul className="mt-3 mb-0 flex list-none flex-col gap-2 p-0">
            {delegated.map((row) => (
              <li key={row.engagement_id} className="flex flex-wrap items-center gap-3">
                <Icon name="briefcase" size={16} className="text-ink-muted" />
                <span className="type-label text-heading">{row.firm_name}</span>
                <Badge tone={row.status === 'active' ? 'credit' : 'caution'}>{row.status}</Badge>
                <span className="type-figure-sm text-ink-muted">
                  {t.workspace.validFrom} {row.valid_from}
                  {row.valid_to ? ` · ${t.workspace.validTo} ${row.valid_to}` : ''}
                </span>
                {row.covers_all_companies && (
                  <Badge tone="neutral">{t.workspace.allCompanies}</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  )
}

/** What a role may do, in words rather than in keys. */
function Permissions({ role }: { role: WorkspaceRole }) {
  if (role.permissions.length === 0) {
    return <p className="mt-2 mb-0 type-body-sm text-ink-faint">{t.workspace.noPermissions}</p>
  }
  return (
    <ul className="mt-2 mb-0 flex list-none flex-wrap gap-2 p-0">
      {role.permissions.map((key) => (
        <li key={key}>
          <Badge tone="neutral">{permissionLabel(key)}</Badge>
        </li>
      ))}
    </ul>
  )
}


/**
 * The one field a person owns about themselves here.
 *
 * The e-mail, the password and the second factor are deliberately absent, and
 * the note under the form says so rather than leaving somebody to hunt: the
 * address is the credential and needs the new one proved before it is adopted;
 * the other two start from the current ones. Three different acts, three paths --
 * a single "profile" form would make them look like one.
 */
function RenameForm({ current, onDone }: { current: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(current)

  const save = useMutation({
    mutationFn: () => updateProfile(name.trim()),
    onSuccess: async () => {
      // The shell reads the same answer for the header block, so both change
      // together rather than the page showing one name and the topbar another.
      await queryClient.invalidateQueries({ queryKey: ['workspace'] })
      onDone()
    },
  })

  return (
    <>
      <form
        className="mt-4 flex flex-wrap items-end gap-3"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <Field label={t.workspace.name}>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={200}
            className="w-80"
            autoFocus
          />
        </Field>
        <Button type="submit" disabled={name.trim() === '' || save.isPending}>
          {t.common.save}
        </Button>
      </form>
      {save.isError && <Failure error={save.error} />}
      <p className="mt-3 mb-0 type-body-sm text-ink-faint">{t.workspace.profileNote}</p>
    </>
  )
}


/**
 * The client's side of a support grant -- ADR-077 §5–§6, on the workspace screen.
 *
 * The consent sentence is the one ADR-017 fixes, verbatim, with the real ticket
 * number: a request that cannot name its ticket cannot be written, by
 * constraint, so the sentence can always be completed. Approving and revoking
 * need `tenant.approve_support_access`; without it the list is read-only and the
 * note says which right is missing and who holds it. The window defaults to 24
 * hours and cannot exceed 72 -- the ceiling is in the database, and the select
 * simply does not offer more.
 */
function SupportGrants({ canDecide }: { canDecide: boolean }) {
  const queryClient = useQueryClient()
  const [hours, setHours] = useState<Record<string, number>>({})
  const grants = useQuery({ queryKey: ['support-grants'], queryFn: listSupportGrants })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['support-grants'] })
  const approval = useMutation({
    mutationFn: ({ id, window }: { id: string; window: number }) => approveSupportGrant(id, window),
    onSuccess: refresh,
  })
  const revocation = useMutation({ mutationFn: revokeSupportGrant, onSuccess: refresh })

  const rows = grants.data?.grants ?? []
  const shown = rows.filter((g) => g.status === 'pending' || g.status === 'active')
  const history = rows.filter((g) => g.status === 'expired' || g.status === 'revoked')

  return (
    <Card eyebrow={t.workspace.support} title={t.workspace.support}>
      <p className="mt-3 mb-0 type-body-sm text-ink-muted">{t.workspace.supportLead}</p>
      {!canDecide && (
        <p className="mt-2 mb-0 type-body-sm text-ink-faint">{t.workspace.supportNoRight}</p>
      )}
      {grants.isError && <Failure error={grants.error} />}
      {approval.isError && <Failure error={approval.error} />}
      {revocation.isError && <Failure error={revocation.error} />}
      {rows.length === 0 && !grants.isPending && (
        <p className="mt-3 mb-0 type-body-md">{t.workspace.supportNone}</p>
      )}
      <ul className="mt-3 mb-0 flex list-none flex-col gap-3 p-0">
        {shown.map((grant) => (
          <li key={grant.id} className="flex flex-col gap-2 border-t border-border pt-3 first:border-0 first:pt-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={grant.status === 'active' ? 'gold' : 'caution'}>
                {statusLabel(grant.status)}
              </Badge>
              <span className="type-body-md text-heading">
                {t.workspace.supportConsent.replace('{ref}', grant.request_ref)}
              </span>
            </div>
            <p className="m-0 type-body-sm text-ink-muted">
              {t.workspace.supportJustification}: {grant.justification} ·{' '}
              {t.workspace.supportRequestedAt} {dateTime(grant.requested_at)}
              {grant.expires_at && (
                <>
                  {' '}
                  · {t.workspace.supportExpiresAt} {dateTime(grant.expires_at)}
                </>
              )}
            </p>
            {canDecide && (
              <div className="flex flex-wrap items-end gap-3">
                {grant.status === 'pending' && (
                  <>
                    <Field label={t.workspace.supportHours}>
                      <Select
                        value={String(hours[grant.id] ?? 24)}
                        onChange={(event) =>
                          setHours((current) => ({
                            ...current,
                            [grant.id]: Number(event.target.value),
                          }))
                        }
                      >
                        {[4, 8, 24, 48, 72].map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Button
                      onClick={() => approval.mutate({ id: grant.id, window: hours[grant.id] ?? 24 })}
                      disabled={approval.isPending}
                    >
                      {t.workspace.supportApprove}
                    </Button>
                  </>
                )}
                <Button
                  variant="danger"
                  onClick={() => {
                    if (window.confirm(t.workspace.supportConfirmRevoke)) revocation.mutate(grant.id)
                  }}
                  disabled={revocation.isPending}
                >
                  {t.workspace.supportRevoke}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {history.length > 0 && (
        <ul className="mt-3 mb-0 flex list-none flex-col gap-1 border-t border-border p-0 pt-3">
          {history.map((grant) => (
            <li key={grant.id} className="flex flex-wrap items-center gap-2 type-body-sm text-ink-muted">
              <Badge tone="neutral">{statusLabel(grant.status)}</Badge>
              <span>#{grant.request_ref}</span>
              <span>· {dateTime(grant.requested_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function statusLabel(status: SupportGrant['status']): string {
  switch (status) {
    case 'pending':
      return t.workspace.supportStatusPending
    case 'active':
      return t.workspace.supportStatusActive
    case 'expired':
      return t.workspace.supportStatusExpired
    case 'revoked':
      return t.workspace.supportStatusRevoked
  }
}
