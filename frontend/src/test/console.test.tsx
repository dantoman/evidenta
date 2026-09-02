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
})
