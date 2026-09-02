/**
 * The VAT regime vocabulary -- `fiscal`, read-only.
 *
 * The screen does not know which regimes exist: that is a nomenclature the
 * server holds as data (`R15`), resolved for the date of the document. A row
 * whose rate cannot be resolved comes back with `rate: null` and the fiscal code
 * that says why -- while a rate is `draft` the screen can name what is missing
 * instead of pricing at nothing.
 */

import { request } from './client'

export interface VatRegime {
  code: string
  rate_key: string | null
  /** A percentage as the server's string -- `'20'` -- or null when unresolved. */
  rate: string | null
  unavailable: string | null
}

export interface VatRegimes {
  on: string
  regimes: VatRegime[]
}

export function vatRegimes(on: string): Promise<VatRegimes> {
  return request<VatRegimes>(`/api/v1/fiscal/vat/regimes?on=${on}`)
}
