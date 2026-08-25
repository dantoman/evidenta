import { BrowserRouter, Route, Routes } from 'react-router'

import { t } from '@/locales'
import { LoginScreen } from './auth/LoginScreen'
import { useIdentity } from './auth/useIdentity'
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
    return (
      <p role="alert" className="p-6 text-sm text-danger">
        {t.errors.network}
      </p>
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
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
