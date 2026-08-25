/**
 * The HTTP client -- thin on purpose.
 *
 * It has one job that matters: turn an error response into an exception carrying
 * the **stable code** from C10, never the message. A client that branched on
 * message text would break the first time a sentence is reworded, and rewording
 * is the cheapest thing in the product -- strings live in resource files exactly
 * so it stays cheap (C32).
 *
 * No axios. That job is thirty lines, and a dependency would not shorten it.
 *
 * Requests are same-origin, so the session cookie goes with them. The cookie is
 * host-only, with no `Domain` attribute, which makes the tenant boundary and the
 * cookie boundary the same line -- a separate API origin would widen the cookie
 * past one tenant.
 */

import { t } from '@/locales'

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, status: number, message?: string) {
    super(message ?? code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }

  /** The message to show a person, resolved from the code. */
  get display(): string {
    const messages: Record<string, string> = t.errors
    return messages[this.code] ?? t.errors.unknown
  }
}

/** The server was unreachable. Distinct from an error the server returned. */
export class NetworkError extends ApiError {
  constructor() {
    super('network', 0, 'network unreachable')
    this.name = 'NetworkError'
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /**
   * Required by the server on any operation with a financial effect (C9), and
   * refused if absent. Not generated here by default: a key the client cannot
   * reproduce is a key that does not survive the retry it exists for, and the
   * caller is the only one who knows what a retry of *this* action means.
   */
  idempotencyKey?: string
  signal?: AbortSignal
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, idempotencyKey, signal } = options

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'same-origin',
      signal,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new NetworkError()
  }

  if (response.status === 204) return undefined as T

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const shape = payload as { code?: string; message?: string } | null
    // A response without a code is a bug on the server side, not something to
    // paper over: it means an endpoint escaped the handler C10 wires in. The
    // fallback names it rather than hiding it.
    throw new ApiError(
      shape?.code ?? 'unknown',
      response.status,
      shape?.message ?? response.statusText,
    )
  }

  return payload as T
}
