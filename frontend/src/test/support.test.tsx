/**
 * The support grant on the client's side (ADR-077): the consent sentence with the
 * real ticket, approval by whoever holds the right, and the bar that says a
 * session runs on a grant.
 */

import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { WorkspaceScreen } from '@/app/workspace/WorkspaceScreen'
import { renderScreen } from './render'

const WORKSPACE = {
  tenant: {
    id: 't1',
    subdomain: 'alpha',
    legal_name: 'Alpha SRL',
    idno: null,
    legal_form: null,
    status: 'active',
  },
  me: {
    user_id: 'u1',
    email: 'a@example.md',
    full_name: 'Ana',
    membership_status: 'active',
    role: {
      key: 'owner',
      name: 'owner',
      level: 'tenant',
      is_system: true,
      permissions: ['tenant.manage_roles', 'tenant.approve_support_access'],
    },
    companies: [],
  },
  roles: [],
  delegated_access: [],
}

const GRANTS = {
  grants: [
    {
      id: 'g1',
      company_id: null,
      request_ref: '4711',
      justification: 'balanța nu se închide',
      requested_at: '2026-09-03T08:00:00+00:00',
      approved_at: null,
      expires_at: null,
      revoked_at: null,
      status: 'pending',
    },
  ],
}

function stubFetch(routes: Record<string, unknown>) {
  const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    void init
    const url = String(input)
    const match = Object.keys(routes).find((path) => url.startsWith(path))
    if (match === undefined) {
      return new Response(JSON.stringify({ code: 'api.not_found' }), { status: 404 })
    }
    return new Response(JSON.stringify(routes[match]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('grantul de suport', () => {
  it('spațiul de lucru arată propoziția de consimțământ cu numărul real și aprobă pe 24 de ore', async () => {
    const fetcher = stubFetch({
      '/api/v1/support/grants/g1/approve': { grant: { ...GRANTS.grants[0], status: 'active' } },
      '/api/v1/support/grants': GRANTS,
      '/api/v1/workspace': WORKSPACE,
      '/api/v1/companies': [],
    })
    renderScreen(<WorkspaceScreen />)

    expect(
      await screen.findByText(
        'Echipa Evidenta solicită acces temporar la datele companiei pentru rezolvarea solicitării #4711.',
      ),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Aprobă accesul' }))
    await waitFor(() => {
      const post = fetcher.mock.calls.find(
        ([input, init]) =>
          String(input) === '/api/v1/support/grants/g1/approve' && init?.method === 'POST',
      )
      expect(post).toBeDefined()
      expect(JSON.parse(String(post![1]?.body))).toEqual({ hours: 24 })
    })
  })

  it('fără drept, lista se citește și butoanele lipsesc', async () => {
    stubFetch({
      '/api/v1/support/grants': GRANTS,
      '/api/v1/workspace': {
        ...WORKSPACE,
        me: { ...WORKSPACE.me, role: { ...WORKSPACE.me.role, permissions: [] } },
      },
      '/api/v1/companies': [],
    })
    renderScreen(<WorkspaceScreen />)

    expect(await screen.findByText(/solicitării #4711/)).toBeInTheDocument()
    expect(screen.getByText(/Aprobarea și retragerea cer dreptul/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aprobă accesul' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retrage accesul' })).not.toBeInTheDocument()
  })
})
