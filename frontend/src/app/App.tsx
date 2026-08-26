import { BrowserRouter, Route, Routes } from 'react-router'

import { t } from '@/locales'
import { ApiError } from '@/shared/api/client'
import { LoginScreen } from './auth/LoginScreen'
import { useIdentity } from './auth/useIdentity'
import { ChartOfAccountsScreen } from './accounting/ChartOfAccountsScreen'
import { AppLayout } from './layout/AppLayout'
import { HomeScreen } from './layout/HomeScreen'

/**
 * The whole routing decision, which is small on purpose.
 *
 * **No route ever carries a tenant identifier.** The tenant comes from the
 * subdomain (C8), so there is no `/:tenantId/` segment here and there will not
 * be one: a path that could name a tenant is a path someone can type.
 *
 * Authentication gates the router rather than living inside it. A route guard
 * that ran per route would let a screen mount for a frame before redirecting,
 * and in an accounting product that frame can show somebody else's numbers.
 */
export function App() {
  const identity = useIdentity()

  if (identity.isPending) {
    return <p className="p-6 text-sm text-ink-muted">{t.app.loading}</p>
  }

  if (identity.isError) {
    // By code, not by one catch-all message. The first version printed
    // "Serverul nu răspunde" for every failure, and the owner hit it on a host
    // with no subdomain: the server had answered, correctly, 404 -- and the
    // screen blamed the network. A message that describes the wrong cause is
    // worse than no message, because it sends the reader to check the wrong
    // thing.
    const failure = identity.error instanceof ApiError ? identity.error : null
    return (
      <main className="p-6">
        <p role="alert" className="text-sm text-danger">
          {failure ? failure.display : t.errors.unknown}
        </p>
        {failure?.code === 'tenant.not_found' && (
          <p className="mt-2 text-sm text-ink-muted">{t.errors.hintSubdomain}</p>
        )}
      </main>
    )
  }

  if (!identity.data) {
    return <LoginScreen />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout tenantId={identity.data.tenant_id} />}>
          <Route index element={<HomeScreen />} />
          <Route path="plan-de-conturi" element={<ChartOfAccountsScreen />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
