/**
 * The shell every authenticated screen sits inside -- the Evidenta design system's
 * app frame (ADR-074).
 *
 * Two surfaces, and each one carries what it can actually know. The **sidebar** is
 * the crest gradient: identity at the top, then the workspace entries, then the
 * open company's own sections, which appear only when the address names a company.
 * The **topbar** carries the one thing that changes under you -- which company you
 * are looking at -- plus the way out.
 *
 * What the design shows and this does not build: search, notifications, the
 * signed-in person's name and role. None of them has a server behind it yet.
 * Drawing the box anyway would be the worst of both: a control that looks live,
 * answers nothing, and quietly teaches people not to trust the chrome.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { t } from '@/locales'
import { logout } from '@/shared/api/auth'
import { supportSession } from '@/shared/api/support'
import { workspace } from '@/shared/api/workspace'
import { dateTime } from '@/shared/format'
import { Icon, IconButton } from '@/shared/ui'
import { workspaceName } from '@/shared/workspace'
import { IDENTITY_KEY, useIdentity } from '../auth/useIdentity'
import { CompanyNav, navItem } from './CompanyNav'
import { HeaderSearch } from './HeaderSearch'
import { useSelectedCompany, type Selection } from './useSelectedCompany'

export function AppLayout({ tenantId }: { tenantId: string }) {
  void tenantId
  const queryClient = useQueryClient()
  // One selection, owned by the shell and read by both halves of it: the sidebar
  // sections and the header switcher must never disagree about which company is
  // open.
  const selection = useSelectedCompany()
  const signOut = useMutation({
    mutationFn: logout,
    // Iesirea reincarca aplicatia pe `/`, indiferent ce a raspuns serverul.
    //
    // Unconditional on purpose, and the reload is what makes it honest rather
    // than a guess: `/` re-asks `whoami` on a cold start, so the screen that
    // comes back is whatever the server says is true -- the login form for a
    // session that ended, the shell again for one that survived, the error
    // screen if the server is unreachable. Branching on the response instead
    // would have to *decide* what happened, and that decision is exactly what
    // was wrong before: the sign-out request used to fail in transport on a
    // session the server had already revoked, so a truthful-looking `if` left
    // the person sitting in an application they were no longer signed in to.
    //
    // A reload, not a re-render: it also drops the previous session's rows out
    // of memory, which on an accountant's desk is the point.
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
            {/* Deviza livrată cu marca, întreagă. Tăiată la „CONTABI…" nu mai e
                deviză, e un accident. Scrisă cu utilitare explicite şi nu prin
                `type-eyebrow`, fiindcă acela fixează şi corpul şi spaţierea; şi
                dimensionată ca să încapă şi pe fontul de rezervă -- reţeaua
                poate lipsi, iar Barlow Condensed odată cu ea. De aceea stiva de
                rezervă e ea însăşi îngustă (Arial Narrow, Liberation Sans
                Narrow, DejaVu Sans Condensed): un „sans-serif" generic ar fi cu
                un sfert mai lat şi ar tăia din nou.
                Măsura: 248 − 28 padding − 40 emblemă − 10 spaţiu = 170px pentru
                27 de litere; la 10px cu spaţiere .06em ies ~140px. Când s-a
                tăiat prima dată erau 137px disponibili. */}
            <span className="font-eyebrow text-[10px]/[1.1] font-semibold tracking-[.06em] whitespace-nowrap text-gold-400 uppercase">
              {t.nav.tagline}
            </span>
          </span>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2.5 py-3">
          {/* Fara companie in adresa, doar acestea doua: partenerul e al
              spatiului de lucru, iar lista de companii e drumul spre restul. */}
          <NavLink to="/companii" className={({ isActive }) => navItem(isActive)}>
            <Icon name="building-2" size={20} />
            <span>{t.companies.title}</span>
          </NavLink>
          <NavLink to="/parteneri" className={({ isActive }) => navItem(isActive)}>
            <Icon name="users" size={20} />
            <span>{t.partners.title}</span>
          </NavLink>
          {/* Titularul contului si drepturile din el. Ultimul dintre cele trei
              fiindca se citeste rar -- dar existent, fiindca inainte nu-l spunea
              nimic. */}
          <NavLink to="/spatiu-de-lucru" className={({ isActive }) => navItem(isActive)}>
            <Icon name="briefcase" size={20} />
            <span>{t.workspace.title}</span>
          </NavLink>
          <CompanyNav companyId={selection.selected?.id} />
        </nav>

        <div className="border-t border-[rgba(198,161,91,.22)] px-4.5 py-3.5">
          <div className="type-caption text-navy-300">
            {t.nav.workspace} · {workspaceName()}
          </div>
          <div className="mt-1 type-eyebrow text-gold-400">{t.nav.compliance}</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-topbar shrink-0 items-center gap-4 border-b border-border bg-surface px-7">
          <CompanySwitcher selection={selection} />
          <HeaderSearch companyId={selection.selected?.id} />
          <span className="flex-1" />
          {/* Trei controale desenate şi oprite. Forma antetului e a machetei;
              starea e adevărul, fiindcă niciunul n-are server în spate: nu
              există integrare SFS, nu există notificări, nu există ajutor. Un
              punct verde lângă „SFS" ar fi o afirmaţie despre legătura cu
              Fiscul, iar aceea nu se face din CSS. */}
          <span
            title={t.nav.sfsNotConfigured}
            className="flex h-7 shrink-0 items-center gap-2 rounded-full bg-surface-muted px-3"
          >
            <span className="size-1.5 rounded-full bg-ink-faint" />
            <span className="type-eyebrow text-ink-muted">{t.nav.sfs}</span>
          </span>
          <IconButton icon="bell" label={`${t.nav.notifications} — ${t.nav.notYet}`} disabled />
          <IconButton icon="circle-help" label={`${t.nav.help} — ${t.nav.notYet}`} disabled />
          <span className="h-8 w-px shrink-0 bg-border" />
          <SignedInAs />
          <IconButton
            icon="log-out"
            label={t.auth.signOut}
            onClick={() => signOut.mutate()}
            disabled={signOut.isPending}
          />
        </header>

        <SupportBar />

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
 * Which company the application is working in, and the way to another one.
 * **The only such control** -- no screen carries a second one.
 *
 * Three shapes, and what the workspace holds decides which:
 *
 * * **No company** -- nothing is drawn. There is nothing to switch between, and
 *   an empty control is an invitation to a dead end.
 * * **One company** -- the name, and no control. A question with a single answer
 *   is not a question.
 * * **Several** -- the switcher, which may legitimately show **no company
 *   chosen** (ADR-085). An entrepreneur holding four firms arrives without being
 *   in any of them, and choosing one for them would be guessing which books they
 *   came for. The company list is where they choose.
 *
 * A native select wearing the design's chip: the platform's own list is
 * keyboard-correct everywhere, and there is nothing here a built menu would add.
 *
 * Switching from a company screen keeps the **section** and drops everything
 * below it -- `conturi/<id>/fisa` cannot follow, because that account belongs to
 * the company you just left. Switching from a workspace screen changes what the
 * sidebar points at and stays where it is: that screen is not about a company.
 */
function CompanySwitcher({ selection }: { selection: Selection }) {
  const navigate = useNavigate()
  const { companies, selected, section, fromPath, select } = selection

  if (companies.length === 0) return null

  const name = selected ? (
    <>
      {/* Denumirea legala, niciodata cea interna (C39). */}
      {selected.legal_name}{' '}
      <span className="type-figure-sm text-ink-faint">{selected.idno}</span>
    </>
  ) : (
    <span className="text-ink-muted">{t.nav.chooseCompany}</span>
  )

  if (companies.length === 1) {
    return (
      <span className="flex h-10 min-w-0 items-center gap-2.5 rounded-control border border-transparent px-3">
        <Icon name="building-2" size={18} className="shrink-0 text-ink-muted" />
        <span className="min-w-0 truncate type-label text-heading">{name}</span>
      </span>
    )
  }

  return (
    <label className="relative flex h-10 min-w-52 shrink-0 items-center gap-2.5 rounded-control border border-border bg-surface-page px-3 hover:bg-navy-050">
      <Icon name="building-2" size={18} className="shrink-0 text-ink-muted" />
      <span className="min-w-0 truncate type-label text-heading">{name}</span>
      <Icon name="chevrons-up-down" size={16} className="shrink-0 text-ink-muted" />
      <select
        aria-label={t.nav.company}
        value={selected?.id ?? ''}
        onChange={(event) => {
          const chosen = event.target.value
          select(chosen)
          // Only a company screen follows the switch. On the workspace screens
          // the choice is context, not a destination -- jumping into a chart
          // from the partner list would answer a question nobody asked.
          if (fromPath) void navigate(`/companii/${chosen}/${section}`)
        }}
        className="absolute inset-0 cursor-pointer opacity-0"
      >
        {/* Present only while nothing is chosen, and disabled: it can be left,
            never picked. Without it the control would show the first company and
            claim a choice nobody made. */}
        {!selected && (
          <option value="" disabled>
            {t.nav.chooseCompany}
          </option>
        )}
        {companies.map((company) => (
          <option key={company.id} value={company.id}>
            {company.legal_name}
          </option>
        ))}
      </select>
    </label>
  )
}

/**
 * Who is signed in, and as what.
 *
 * Real, and only recently so: `whoami` answers from the context alone and returns
 * no name, deliberately -- it is the honest end-to-end check of the middleware
 * chain, and a query would spoil that. The name and the role come from
 * `/api/v1/workspace` instead, which was built to answer exactly this kind of
 * question (ADR-075).
 *
 * The role is shown by its interface name: the server keeps role keys and no
 * labels (ADR-020), so `owner` becomes *Proprietar* here, in the resource file,
 * next to every other string. A role the tenant composed keeps the name the
 * tenant gave it.
 */
function SignedInAs() {
  const space = useQuery({ queryKey: ['workspace'], queryFn: workspace })
  if (!space.data) return null

  const { full_name: fullName, email, role } = space.data.me
  const shown = fullName.trim() || email
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
        {role && (
          <span className="truncate type-caption text-ink-muted">
            {t.roles[role.key] ?? role.name}
          </span>
        )}
      </span>
    </span>
  )
}


/**
 * The bar that says a session runs on a support grant -- ADR-077 §6: "nu există
 * «modul discret»". Drawn only when `whoami` carries a grant; it then asks the
 * grant itself for the ticket and the expiry, through the same policy that lets
 * the session see anything at all.
 */
function SupportBar() {
  const identity = useIdentity()
  const onGrant = Boolean(identity.data?.support_grant_id)
  const session = useQuery({
    queryKey: ['support-session'],
    queryFn: supportSession,
    enabled: onGrant,
    retry: false,
  })
  if (!onGrant || !session.data?.grant) return null
  const grant = session.data.grant
  return (
    <div
      role="status"
      className="flex items-center gap-3 border-b border-gold bg-[var(--parchment-100)] px-7 py-2 type-label text-heading"
    >
      <Icon name="circle-help" size={16} className="text-gold-strong" />
      {t.nav.supportSession
        .replace('{ref}', grant.request_ref)
        .replace('{until}', grant.expires_at ? dateTime(grant.expires_at) : '')}
    </div>
  )
}
