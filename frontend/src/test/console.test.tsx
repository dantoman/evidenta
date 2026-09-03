/**
 * The platform's console (ADR-076): the host decides, the role decides, and the
 * one screen that exists asks the server what it should and shows what came back.
 *
 * `fetch` is stubbed with the shapes the console views serialise; the rules --
 * who may activate, what a margin needs -- are the server's and are tested there
 * (`tests/isolation/test_console.py`).
 */

import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FiscalParametersScreen } from '@/app/console/FiscalParametersScreen'
import { IncidentsScreen } from '@/app/console/IncidentsScreen'
import { PlannedScreen } from '@/app/console/PlannedScreen'
import { SupportGrantsScreen } from '@/app/console/SupportGrantsScreen'
import { PrivilegedLogScreen } from '@/app/console/PrivilegedLogScreen'
import { SpacesScreen } from '@/app/console/SpacesScreen'
import { StaffScreen } from '@/app/console/StaffScreen'
import { isConsoleHost } from '@/shared/workspace'
import { renderScreen } from './render'

const ME = {
  user_id: '11111111-1111-1111-1111-111111111111',
  email: 'operator@platform.md',
  full_name: 'Operator al platformei',
  staff_role: 'operator',
  granted_at: '2026-09-02T00:00:00Z',
}

const ACT = {
  act_type: 'lege',
  act_number: 'TEST-9/9999',
  act_date: '2000-01-01',
  title: 'Act sintetic',
  effective_from: '2000-01-01',
}

const PARAMETERS = {
  parameters: [
    {
      id: 'p1',
      parameter_key: 'test.console.alpha',
      scope: 'global',
      scope_ref: null,
      value_type: 'percentage',
      value: 7,
      unit: null,
      valid_from: null,
      valid_to: null,
      margin_basis: null,
      margin_reference: null,
      margin_act: null,
      observed_in: 'the value appears in the synthetic act',
      act: ACT,
      status: 'draft',
      confidence: 'provisional',
      provisional_reason: 'test',
      approved_by_user_id: null,
      approved_at: null,
      updated_at: '2026-09-02T00:00:00Z',
    },
    {
      id: 'p2',
      parameter_key: 'test.console.beta',
      scope: 'global',
      scope_ref: null,
      value_type: 'integer',
      value: 25,
      unit: null,
      valid_from: '2000-01-01',
      valid_to: null,
      margin_basis: 'act',
      margin_reference: 'art. 1',
      margin_act: ACT,
      observed_in: null,
      act: ACT,
      status: 'active',
      confidence: 'confirmed',
      provisional_reason: null,
      approved_by_user_id: ME.user_id,
      approved_at: '2026-09-02T00:00:00Z',
      updated_at: '2026-09-02T00:00:00Z',
    },
  ],
}

function stubFetch(routes: Record<string, unknown>) {
  // Two parameters, so `mock.calls` carries the method a test asserts on.
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

describe('consola platformei', () => {
  it('recunoaște gazda consolei după eticheta rezervată, și numai după ea', () => {
    expect(isConsoleHost('admin.evidenta.localhost')).toBe(true)
    expect(isConsoleHost('admin.evidenta.md')).toBe(true)
    expect(isConsoleHost('alpha.evidenta.localhost')).toBe(false)
    expect(isConsoleHost('evidenta.localhost')).toBe(false)
  })

  it('parametrii fiscali: un operator vede lista, marginea lipsă și poate activa o ciornă', async () => {
    const fetcher = stubFetch({
      '/api/v1/platform/fiscal-parameters/p1/activate': {
        outcome: 'activated',
        parameter: PARAMETERS.parameters[0],
      },
      '/api/v1/platform/fiscal-parameters/': PARAMETERS,
      '/api/v1/platform/staff/me': ME,
    })
    renderScreen(<FiscalParametersScreen />)

    // The button appears once both answers are in -- the list and the role --
    // so waiting for it first means the rows below are the settled ones, not a
    // node the next render replaced.
    const activate = await screen.findAllByRole('button', { name: 'Activează' })
    // Only the draft has the button; the active row has nothing to activate.
    expect(activate).toHaveLength(1)
    expect(screen.getByText('test.console.alpha')).toBeInTheDocument()
    expect(screen.getByText('test.console.beta')).toBeInTheDocument()
    // Rândul fără `valid_from` o spune, nu o completează (OD-92).
    expect(screen.getByText('fără margine')).toBeInTheDocument()
    expect(screen.getByText('2000-01-01')).toBeInTheDocument()

    // Queried again at the moment of the click: the grid may have re-rendered
    // its rows since the first query, and a click on a detached node is a click
    // on nothing.
    fireEvent.click(screen.getByRole('button', { name: 'Activează' }))

    await waitFor(() => {
      const calls = fetcher.mock.calls.map(([input, init]) => [
        String(input),
        init?.method ?? 'GET',
      ])
      expect(calls).toContainEqual(['/api/v1/platform/fiscal-parameters/p1/activate', 'POST'])
    })
  })

  it('parametrii fiscali: un rol de suport citește lista fără butoane de scriere', async () => {
    stubFetch({
      '/api/v1/platform/fiscal-parameters/': PARAMETERS,
      '/api/v1/platform/staff/me': { ...ME, staff_role: 'support' },
    })
    renderScreen(<FiscalParametersScreen />)

    // The note appears once the role is known; the list settles with it.
    expect(
      await screen.findByText(
        'Rolul dumneavoastră poate citi lista; scrierea și activarea sunt ale operatorului.',
      ),
    ).toBeInTheDocument()
    expect(await screen.findByText('test.console.alpha')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Activează' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Versiune nouă' })).not.toBeInTheDocument()
  })

  it('parametrii fiscali: „Versiune nouă" scrie o ciornă cu actul ei', async () => {
    const fetcher = stubFetch({
      '/api/v1/platform/fiscal-parameters/': PARAMETERS,
      '/api/v1/platform/staff/me': ME,
    })
    renderScreen(<FiscalParametersScreen />)

    fireEvent.click(await screen.findByRole('button', { name: 'Versiune nouă' }))
    fireEvent.change(screen.getByLabelText('Cheie'), { target: { value: 'vat.standard' } })
    fireEvent.change(screen.getByLabelText(/^Valoare/), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Pe ce se sprijină deducerea'), {
      target: { value: 'test' },
    })
    fireEvent.change(screen.getByLabelText('Numărul actului'), {
      target: { value: '1163-XIII' },
    })
    fireEvent.change(screen.getByLabelText('Data actului'), { target: { value: '1997-04-24' } })
    fireEvent.change(screen.getByLabelText('Titlul actului'), {
      target: { value: 'Codul fiscal' },
    })
    fireEvent.change(screen.getByLabelText(/^În vigoare din/), {
      target: { value: '1998-07-01' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Scrie ciorna' }))

    await waitFor(() => {
      const post = fetcher.mock.calls.find(
        ([input, init]) =>
          String(input) === '/api/v1/platform/fiscal-parameters/' && init?.method === 'POST',
      )
      expect(post).toBeDefined()
      const body = JSON.parse(String(post![1]?.body)) as Record<string, unknown>
      expect(body.parameter_key).toBe('vat.standard')
      expect(body.value).toBe(20)
      expect(body.valid_from).toBeNull()
      expect((body.act as Record<string, unknown>).act_number).toBe('1163-XIII')
    })
  })

  it('spațiile: rândul din tenant, cu numărători, fără conținut', async () => {
    stubFetch({
      '/api/v1/platform/spaces/': {
        spaces: [
          {
            id: 's1',
            subdomain: 'alpha',
            legal_name: 'Alpha SRL',
            legal_form: 'SRL',
            idno: '1013600012345',
            status: 'active',
            claimed_at: '2026-08-01T00:00:00Z',
            suspended_at: null,
            offboarding_started_at: null,
            archived_at: null,
            created_at: '2026-08-01T00:00:00Z',
            company_count: 3,
            member_count: 2,
          },
          {
            id: 's2',
            subdomain: 'beta',
            legal_name: 'Beta SRL',
            legal_form: null,
            idno: null,
            status: 'active',
            claimed_at: null,
            suspended_at: null,
            offboarding_started_at: null,
            archived_at: null,
            created_at: '2026-08-02T00:00:00Z',
            company_count: 0,
            member_count: 0,
          },
        ],
      },
    })
    renderScreen(<SpacesScreen />)

    // Inside `waitFor`, queried fresh each time: the grid may re-render its rows
    // once more after the first paint, and a node found before that is detached.
    await waitFor(() => {
      expect(screen.getByText('alpha')).toBeInTheDocument()
      expect(screen.getByText('Alpha SRL')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
      // Nerevendicat: spațiul creat pentru cineva care încă n-a venit (ADR-081).
      expect(screen.getByText('Nerevendicat')).toBeInTheDocument()
    })
  })

  it('angajații: un administrator acordă un rol; ceilalți doar citesc', async () => {
    const staffRows = {
      staff: [
        {
          user_id: ME.user_id,
          email: ME.email,
          full_name: ME.full_name,
          staff_role: 'admin',
          granted_by_email: ME.email,
          granted_at: '2026-09-02T00:00:00Z',
          revoked_at: null,
        },
        {
          user_id: '22222222-2222-2222-2222-222222222222',
          email: 'suport@platform.md',
          full_name: 'Suport',
          staff_role: 'support',
          granted_by_email: ME.email,
          granted_at: '2026-09-02T00:00:00Z',
          revoked_at: null,
        },
      ],
    }
    const fetcher = stubFetch({
      '/api/v1/platform/staff/me': { ...ME, staff_role: 'admin' },
      '/api/v1/platform/staff/': staffRows,
    })
    renderScreen(<StaffScreen />)

    expect(await screen.findByText('suport@platform.md')).toBeInTheDocument()
    // The admin's own row has no revoke button; the other one does.
    const revoke = await screen.findAllByRole('button', { name: 'Retrage' })
    expect(revoke).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Acordă rol' }))
    fireEvent.change(screen.getByLabelText('E-mail'), {
      target: { value: 'nou@platform.md' },
    })
    fireEvent.change(screen.getByLabelText(/^Rol/), { target: { value: 'operator' } })
    fireEvent.click(screen.getByRole('button', { name: 'Acordă' }))

    await waitFor(() => {
      const post = fetcher.mock.calls.find(
        ([input, init]) =>
          String(input) === '/api/v1/platform/staff/' && init?.method === 'POST',
      )
      expect(post).toBeDefined()
      expect(JSON.parse(String(post![1]?.body))).toEqual({
        email: 'nou@platform.md',
        staff_role: 'operator',
      })
    })
  })

  it('angajații: un operator vede lista fără formular și fără retragere', async () => {
    stubFetch({
      '/api/v1/platform/staff/me': ME,
      '/api/v1/platform/staff/': { staff: [] },
    })
    renderScreen(<StaffScreen />)

    expect(
      await screen.findByText('Doar un administrator acordă și retrage roluri.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Acordă rol' })).not.toBeInTheDocument()
  })

  it('jurnalul: filtrul pe cale ajunge în cerere, rândul arată calea și parametrii', async () => {
    const fetcher = stubFetch({
      '/api/v1/platform/privileged-log/': {
        paths: [
          { code: 'P-4', label: 'P4 Fiscal Rules' },
          { code: 'P-12', label: 'P12 Platform Staff' },
        ],
        rows: [
          {
            id: 1,
            occurred_at: '2026-09-02T10:00:00+00:00',
            path_code: 'P-4',
            actor: 'console:operator',
            actor_user_id: ME.user_id,
            actor_email: ME.email,
            subject_tenant_id: null,
            subject_subdomain: null,
            tenant_count: null,
            request_id: 'r1',
            justification: null,
            payload: { operation: 'activate', key: 'vat.standard' },
          },
        ],
      },
    })
    renderScreen(<PrivilegedLogScreen />)

    // The code appears twice on purpose -- once in the filter's options, once in
    // the row -- so the row is the one asked for.
    await waitFor(() => {
      expect(screen.getByText('P-4', { selector: 'span' })).toBeInTheDocument()
      expect(screen.getByText(/"operation":"activate"/)).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Cale'), { target: { value: 'P-12' } })
    await waitFor(() => {
      const urls = fetcher.mock.calls.map(([input]) => String(input))
      expect(urls).toContain('/api/v1/platform/privileged-log/?path=P-12&limit=100')
    })
  })

  it('paginile de implementat spun ce vor face, ce lipsește și de ce decizie depind', () => {
    stubFetch({})
    renderScreen(<PlannedScreen page="subscriptions" />)

    expect(screen.getByText('Abonamente și planuri')).toBeInTheDocument()
    expect(screen.getByText('de implementat')).toBeInTheDocument()
    expect(screen.getByText('Ce lipsește')).toBeInTheDocument()
    expect(screen.getByText(/ADR-086/)).toBeInTheDocument()
  })

  it('granturile de suport: suportul cere pentru un spațiu, cu numărul solicitării și motivul', async () => {
    const fetcher = stubFetch({
      '/api/v1/platform/support-grants/': { grants: [] },
      '/api/v1/platform/staff/me': { ...ME, staff_role: 'support' },
    })
    renderScreen(<SupportGrantsScreen />)

    fireEvent.click(await screen.findByRole('button', { name: 'Cere acces' }))
    fireEvent.change(screen.getByLabelText(/^Spațiu/), { target: { value: 'alpha' } })
    fireEvent.change(screen.getByLabelText('Solicitarea'), { target: { value: '4711' } })
    fireEvent.change(screen.getByLabelText('Justificare'), {
      target: { value: 'balanța nu se închide' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Trimite cererea' }))

    await waitFor(() => {
      const post = fetcher.mock.calls.find(
        ([input, init]) =>
          String(input) === '/api/v1/platform/support-grants/' && init?.method === 'POST',
      )
      expect(post).toBeDefined()
      expect(JSON.parse(String(post![1]?.body))).toEqual({
        space: 'alpha',
        request_ref: '4711',
        justification: 'balanța nu se închide',
      })
    })
  })

  it('granturile de suport: un operator vede lista fără formular', async () => {
    stubFetch({
      '/api/v1/platform/support-grants/': {
        grants: [
          {
            id: 'g1',
            subdomain: 'alpha',
            legal_name: 'Alpha SRL',
            company_id: null,
            requested_by_email: 'support@platform.md',
            request_ref: '4711',
            justification: 'test',
            requested_at: '2026-09-03T08:00:00+00:00',
            approved_at: null,
            expires_at: null,
            revoked_at: null,
            status: 'pending',
          },
        ],
      },
      '/api/v1/platform/staff/me': ME,
    })
    renderScreen(<SupportGrantsScreen />)

    // The note appears once the role is known; the rows settle with it.
    expect(await screen.findByText(/Doar rolul de suport cere un grant/)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('#4711')).toBeInTheDocument()
      expect(screen.getByText('În așteptare')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: 'Cere acces' })).not.toBeInTheDocument()
  })

  it('incidentele: sondele și ultima rulare a căilor', async () => {
    stubFetch({
      '/api/v1/platform/incidents/': {
        database: { name: 'database', ok: true, detail: null, latency_ms: 3 },
        broker: { name: 'broker', ok: false, detail: 'ConnectionError', latency_ms: null },
        workers: { name: 'workers', ok: false, detail: null, latency_ms: null },
        queues: [{ name: 'celery', depth: null, detail: 'ConnectionError' }],
        paths: [
          {
            code: 'P-4',
            label: 'P4 Fiscal Rules',
            last_run_at: '2026-09-03T08:00:00+00:00',
            last_actor: 'operator@platform.md',
          },
          { code: 'P-3', label: 'P3 Bnm Rates', last_run_at: null, last_actor: null },
        ],
      },
    })
    renderScreen(<IncidentsScreen />)

    expect(await screen.findByText('Baza de date')).toBeInTheDocument()
    expect(screen.getAllByText('răspunde')).toHaveLength(1)
    expect(screen.getAllByText('nu răspunde')).toHaveLength(2)
    expect(screen.getByText('operator@platform.md')).toBeInTheDocument()
    expect(screen.getByText('niciodată')).toBeInTheDocument()
  })
})
