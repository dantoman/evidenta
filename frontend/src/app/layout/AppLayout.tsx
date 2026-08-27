import { useMutation, useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router'

import { t } from '@/locales'
import { logout } from '@/shared/api/auth'
import { IDENTITY_KEY } from '../auth/useIdentity'

/**
 * The shell every authenticated screen sits inside.
 *
 * Deliberately almost empty. Navigation, the company switcher and the density
 * control belong with the screens that need them, and the density scale itself
 * is OD-35 -- open. C21 is active from now: spacing in a grid screen is raised,
 * not invented, and there are no grid screens yet.
 */
/** The leading label of the host: `alpha` from `alpha.evidenta.md`. */
function workspaceName(): string {
  return window.location.hostname.split('.')[0] ?? ''
}

export function AppLayout({ tenantId }: { tenantId: string }) {
  void tenantId
  const queryClient = useQueryClient()
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
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
        <div className="flex items-center gap-6">
          {/* Marca duce acasa. `end` fiindca ruta index e `/`: fara el, orice
              ruta de sub layout ar tine marca activa. */}
          <NavLink to="/" end className="font-semibold text-ink">
            {t.app.name}
          </NavLink>
          {/* Un singur link, si e cel corect: planul de conturi apartine unei
              companii, iar antetul nu stie careia. Drumul spre contabilitate
              trece prin lista de companii, ca in rutele serverului. */}
          <NavLink
            to="/companii"
            className={({ isActive }) =>
              `text-sm ${isActive ? 'text-ink' : 'text-ink-muted'}`
            }
          >
            {t.companies.title}
          </NavLink>
          {/* Alaturi de companii, nu sub ele: partenerul e al spatiului de lucru. */}
          <NavLink
            to="/parteneri"
            className={({ isActive }) =>
              `text-sm ${isActive ? 'text-ink' : 'text-ink-muted'}`
            }
          >
            {t.partners.title}
          </NavLink>
        </div>
        <div className="flex items-center gap-4">
          {/* The subdomain, not the identifier. The tenant is identified by the
              host the browser is already on (C8), and that is also the only part
              a person recognises -- a UUID in the header is a database key on a
              screen, which is what it looked like on the first run. `tenantId`
              stays a prop because the shell needs to know a tenant resolved, not
              because it should be read out. */}
          <span className="text-sm text-ink-muted">{workspaceName()}</span>
          <button
            type="button"
            onClick={() => signOut.mutate()}
            disabled={signOut.isPending}
            className="text-sm text-accent disabled:text-ink-muted"
          >
            {t.auth.signOut}
          </button>
        </div>
      </header>
      <main className="p-4">
        <Outlet />
      </main>
    </div>
  )
}
