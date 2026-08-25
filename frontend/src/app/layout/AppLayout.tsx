import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Outlet } from 'react-router'

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: IDENTITY_KEY }),
  })

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
        <span className="font-semibold">{t.app.name}</span>
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
            className="text-sm text-accent"
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
