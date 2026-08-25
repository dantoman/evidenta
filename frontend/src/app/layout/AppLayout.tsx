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
export function AppLayout({ tenantId }: { tenantId: string }) {
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
          {/* The workspace is identified by the subdomain the browser is on;
              showing the identifier is a skeleton affordance, not a design. */}
          <span className="text-sm text-ink-muted tabular">{tenantId}</span>
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
