/**
 * Mounting a screen the way the application mounts it.
 *
 * A screen without a `QueryClientProvider` throws on its first `useQuery`, and
 * one without a router throws on `useParams` -- so a helper that supplies both is
 * the difference between testing the screen and testing the harness.
 *
 * `retry: false`: a failing query would otherwise be retried before the test can
 * see the failure, and the test would time out instead of asserting.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'

export function renderScreen(
  element: ReactElement,
  { path = '/', route = '/' }: { path?: string; route?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={path} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
