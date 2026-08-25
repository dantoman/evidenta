import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { App } from './app/App'
import './index.css'

/**
 * One query client for the application.
 *
 * `retry: 1` rather than the default three: a request that failed because the
 * session ended, or because a policy returned nothing, will fail the same way
 * three times -- and three round trips before the user sees anything is how a
 * product feels broken while working correctly. Real transient failures are
 * covered by one retry.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

const root = document.getElementById('root')
if (!root) throw new Error('#root is missing from index.html')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
