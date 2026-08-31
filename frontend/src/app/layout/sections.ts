/**
 * The company's own sections -- the paths that mean something under
 * `/companii/:companyId/`, with what they are called and what marks them.
 *
 * In one file because two things need it and they must not drift: the sidebar
 * renders them, and the company switcher decides with them **which part of the
 * current address survives a switch**. That second use is why the list is
 * closed rather than "whatever the first path segment happens to be" -- the
 * first version kept the segment as it found it, so switching companies from an
 * account's page produced `/companii/<other>/conturi`, an address no route
 * matches. React Router said so in the console and the screen went blank.
 *
 * What is deliberately **not** here: the screens that hang off a single row --
 * an account, one person's exemptions, a batch of opening balances. They are
 * reached from the row that names them, and they cannot be carried across a
 * company boundary, because the row belongs to the company you just left.
 */

import { t } from '@/locales'
import type { IconName } from '@/shared/ui'

export interface Section {
  /** The path segment under `/companii/:companyId/`. */
  path: string
  /** The screen's own title. A link that says something else than the screen it
   *  opens is a link that has to be learned twice. */
  label: string
  icon: IconName
}

export const ACCOUNTING: Section[] = [
  { path: 'plan-de-conturi', label: t.accounting.chart.title, icon: 'list-tree' },
  { path: 'note', label: t.accounting.entry.title, icon: 'file-plus' },
  { path: 'registru', label: t.accounting.register.title, icon: 'book-open' },
  { path: 'balanta', label: t.accounting.balance.title, icon: 'scale' },
  { path: 'rulaje', label: t.accounting.reports.correspondence, icon: 'arrow-down-up' },
  { path: 'jurnale', label: t.journals.title, icon: 'book-open' },
  { path: 'solduri-initiale', label: t.accounting.opening.title, icon: 'import' },
  { path: 'sabloane', label: t.accounting.operationTemplates.title, icon: 'copy' },
]

export const COMMERCIAL: Section[] = [
  { path: 'facturi', label: t.sales.title, icon: 'file-plus' },
  { path: 'facturi-primite', label: t.purchases.title, icon: 'import' },
  { path: 'trezorerie', label: t.treasury.title, icon: 'coins' },
  { path: 'solduri-deschise', label: t.settlements.title, icon: 'arrow-down-up' },
]

export const PAYROLL: Section[] = [
  { path: 'angajati', label: t.payroll.people, icon: 'users' },
  { path: 'contracte', label: t.payroll.contracts, icon: 'clipboard-list' },
  { path: 'pontaj', label: t.payroll.timesheets, icon: 'calendar-days' },
  { path: 'salarii', label: t.payroll.runs, icon: 'coins' },
]

/** Where a switch lands when the current address is not on a section. */
export const DEFAULT_SECTION = 'plan-de-conturi'

const KNOWN = new Set(
  [...ACCOUNTING, ...COMMERCIAL, ...PAYROLL].map((section) => section.path),
)

/**
 * The section of a path under a company, or the default.
 *
 * `conturi/<id>/fisa` answers `plan-de-conturi`, not `conturi`: the account is
 * the other company's, so there is nothing to follow across -- and `conturi`
 * alone is not an address.
 */
export function sectionOf(splat: string): string {
  const first = splat.split('/')[0] ?? ''
  return KNOWN.has(first) ? first : DEFAULT_SECTION
}
