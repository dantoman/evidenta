/**
 * The shell of the platform's console -- the same crest frame as the
 * application's (ADR-074), carrying deliberately less.
 *
 * No company switcher, no search, no SFS indicator: none of those has a meaning
 * here. The console has no company in context and cannot have one -- the host
 * it runs on has no tenant (ADR-076 §4.2) -- so a control that named one would
 * be a lie the server refuses on the first request.
 *
 * One entry in the sidebar, because one page exists. ADR-076 §4.3 lists eight;
 * drawing the other seven greyed out would teach people that the chrome says
 * things that are not so, which is the habit the design system exists to avoid.
 * The footer says so in words instead.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router'

import { t } from '@/locales'
import { logout } from '@/shared/api/auth'
import { staffMe } from '@/shared/api/platform'
import { Icon, IconButton, type IconName } from '@/shared/ui'
import { IDENTITY_KEY } from '../auth/useIdentity'
import { navItem } from '../layout/CompanyNav'

export const STAFF_ME_KEY = ['console', 'me'] as const

export function ConsoleLayout() {
  const queryClient = useQueryClient()
  const signOut = useMutation({
    mutationFn: logout,
    // Same reasoning as the application shell: the reload re-asks the server
    // what is true, rather than deciding it here.
    onSettled: () => {
      queryClient.removeQueries({ queryKey: IDENTITY_KEY })
      window.location.replace('/')
    },
  })

  return (
    <div className="flex min-h-screen bg-surface-page">
      <aside className="sticky top-0 flex h-screen w-sidebar shrink-0 flex-col bg-[image:var(--gradient-crest)]">
        <div className="flex items-center gap-2.5 border-b border-[rgba(198,161,91,.22)] px-3.5 py-4">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-gold bg-[var(--parchment-100)]">
            <img src="/brand/owl-navy.png" alt="" className="h-[74%] w-auto" />
          </span>
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="font-display text-[20px]/none font-bold tracking-[.06em] text-on-navy uppercase">
              {t.app.name}
            </span>
            <span className="font-eyebrow text-[10px]/[1.1] font-semibold tracking-[.06em] whitespace-nowrap text-gold-400 uppercase">
              {t.console.tagline}
            </span>
          </span>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2.5 py-3">
          {/* Three groups, from ADR-076 §4.3: the platform's objects, the
              reference data everybody reads, and the audit of who touched what.
              Pages with no server behind them are not drawn -- see the footer. */}
          <Group label={t.console.navPlatform}>
            <Entry to="/spatii" icon="building-2" label={t.console.spaces.title} />
            <Entry
              to="/abonamente"
              icon="coins"
              label={t.console.planned.subscriptions.title}
              planned
            />
            <Entry to="/capabilitati" icon="layout-dashboard" label={t.console.capabilities.title} />
            <Entry to="/ringuri-si-flaguri" icon="copy" label={t.console.flags.title} />
            <Entry to="/angajati" icon="users" label={t.console.staff.title} />
            <Entry
              to="/granturi-de-suport"
              icon="circle-help"
              label={t.console.planned.support.title}
              planned
            />
          </Group>
          <Group label={t.console.navReference}>
            <Entry to="/parametri-fiscali" icon="scale" label={t.console.fiscal.title} />
            <Entry to="/planuri-de-conturi" icon="list-tree" label={t.console.chart.title} />
          </Group>
          <Group label={t.console.navAudit}>
            <Entry to="/jurnal-privilegiat" icon="book-open" label={t.console.log.title} />
            <Entry to="/incidente" icon="bell" label={t.console.planned.incidents.title} planned />
          </Group>
        </nav>

        <div className="border-t border-[rgba(198,161,91,.22)] px-4.5 py-3.5">
          <div className="type-caption text-navy-300">{t.console.title}</div>
          <div className="mt-1 type-caption text-navy-300">{t.console.notBuilt}</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-topbar shrink-0 items-center gap-4 border-b border-border bg-surface px-7">
          <span className="type-label text-heading">{t.console.title}</span>
          <span className="flex-1" />
          <StaffSignedInAs />
          <IconButton
            icon="log-out"
            label={t.auth.signOut}
            onClick={() => signOut.mutate()}
            disabled={signOut.isPending}
          />
        </header>

        <main className="flex-1 p-8">
          <div className="mx-auto max-w-page">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

/**
 * Who is signed in, and as which staff role. From `/api/v1/platform/staff/me`,
 * which answers through two self-row policies and a live `platform_staff` row --
 * a person whose role was revoked since they signed in sees the message, not
 * a stale role.
 */
function StaffSignedInAs() {
  const me = useQuery({ queryKey: STAFF_ME_KEY, queryFn: staffMe, retry: false })
  if (me.isError) {
    return <span className="type-caption text-danger">{t.console.notStaff}</span>
  }
  if (!me.data) return null

  const shown = me.data.full_name.trim() || me.data.email
  const initials = shown
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase('ro-MD') ?? '')
    .join('')

  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-navy-700 type-eyebrow text-gold-400">
        {initials}
      </span>
      <span className="flex min-w-0 flex-col leading-tight">
        <span className="truncate type-label text-heading">{shown}</span>
        <span className="truncate type-caption text-ink-muted">
          {t.console.roles[me.data.staff_role] ?? me.data.staff_role}
        </span>
      </span>
    </span>
  )
}

/** The condensed caps that separate one run of entries from the next. */
function Group({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <div className="px-3 pt-4 pb-1.5 type-eyebrow text-navy-300">{label}</div>
      {children}
    </>
  )
}

/**
 * `planned` marks an entry whose page describes what is not built yet (ADR-093):
 * the marker travels with the label so nobody reads the entry as a feature.
 */
function Entry({
  to,
  icon,
  label,
  planned = false,
}: {
  to: string
  icon: IconName
  label: string
  planned?: boolean
}) {
  return (
    <NavLink to={to} className={({ isActive }) => navItem(isActive)}>
      <Icon name={icon} size={20} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {planned && (
        <span className="shrink-0 type-caption text-gold-400">{t.console.plannedMarker}</span>
      )}
    </NavLink>
  )
}
