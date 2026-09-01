/**
 * Where `/` goes: into the books of the company in context.
 *
 * It follows the same selection rule as the header switcher
 * (`useSelectedCompany`): the company last opened, or the only one there is. One
 * rule, one place; a second one here would drift from it, and the two would
 * disagree about which company is open.
 *
 * Otherwise it goes to the company list -- **including on a first sign-in with
 * several companies**, which is not a failure to decide but the honest answer
 * (ADR-085): an entrepreneur holding four firms did not come to the one that
 * sorts first, and the list is where they say which.
 *
 * **Which screen** is `DEFAULT_SECTION`, shared with the company switcher rather
 * than spelled here: one rule, one place, and the two cannot come to disagree
 * about where a company opens.
 *
 * `replace`, so the redirect does not sit in history: a person pressing Back from
 * the panel would otherwise bounce through `/` and land here again.
 */

import { Navigate } from 'react-router'

import { t } from '@/locales'
import { DEFAULT_SECTION } from './sections'
import { useSelectedCompany } from './useSelectedCompany'

export function Landing() {
  const { selected, loading } = useSelectedCompany()

  if (loading) {
    return <p className="type-body-md text-ink-muted">{t.app.loading}</p>
  }

  return (
    <Navigate
      to={selected ? `/companii/${selected.id}/${DEFAULT_SECTION}` : '/companii'}
      replace
    />
  )
}
