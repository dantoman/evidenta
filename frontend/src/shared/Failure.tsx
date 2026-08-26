/**
 * A refusal, rendered from its **stable code** and never from the server's
 * sentence (C10).
 *
 * It was written once inside the chart screen and copied the moment a second
 * screen needed it, which is how four slightly different renderings of the same
 * failure get into a product. One component, in `shared/`, is the same reasoning
 * C24 applies to a copied component: a second copy made in order to change it
 * for one screen is a defect, not an adaptation.
 */

import { t } from '@/locales'
import { ApiError } from '@/shared/api/client'

export function Failure({ error }: { error: unknown }) {
  const failure = error instanceof ApiError ? error : null
  return (
    <p role="alert" className="text-sm text-danger">
      {failure ? failure.display : t.errors.unknown}
    </p>
  )
}

/** The code, for a caller that has to branch -- `api.not_found` is a state. */
export function codeOf(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null
}
