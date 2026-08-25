/**
 * Whether there is a live session, and whose.
 *
 * Server state, so react-query holds it -- not a store. In an accounting ERP
 * almost all state is server state, and a store would be a second source of
 * truth for the same answer (ADR-031). The one thing the application must never
 * do is decide from the browser whether a session is valid: only the server
 * knows, and asking is one request.
 */

import { useQuery } from '@tanstack/react-query'

import { ApiError } from '@/shared/api/client'
import { whoami, type Identity } from '@/shared/api/auth'

export const IDENTITY_KEY = ['identity'] as const

export function useIdentity() {
  return useQuery<Identity | null>({
    queryKey: IDENTITY_KEY,
    queryFn: async () => {
      try {
        return await whoami()
      } catch (error) {
        // Not authenticated is an answer, not a failure: it means "show the
        // login screen".
        //
        // A 404 is **not** one of those, and conflating them was the first
        // version's bug. The tenant comes from the subdomain (C8), so a host
        // with no tenant answers `tenant.not_found` with 404 -- and showing the
        // login form there would invite somebody to type a password into an
        // address that has no workspace behind it.
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          return null
        }
        throw error
      }
    },
    // No retry on the identity check. A retry here turns "you are logged out"
    // into three seconds of a blank screen before the login form appears.
    retry: false,
    staleTime: 30_000,
  })
}
