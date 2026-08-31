/**
 * The company's own sections, in the sidebar under the workspace entries.
 *
 * The company comes from the selection the shell holds, not from the address:
 * a firm or a holding is always working in one (see `useSelectedCompany`), so
 * these sections are reachable from the partner list too, pointing at the company
 * in context. Without any company -- a workspace with none yet -- there is
 * nothing to point at and nothing is drawn.
 *
 * Two groups, because that is how the work divides and how the design system
 * groups it -- not because the code has two modules. The screens that hang off a
 * single row (an account's ledger, one person's exemptions, a batch of opening
 * balances) are **not** here: they are reached from the row that names them, and a
 * sidebar entry that has to guess which account you meant is a dead entry.
 */

import { NavLink } from 'react-router'

import { t } from '@/locales'
import { Icon } from '@/shared/ui'
import { ACCOUNTING, COMMERCIAL, PAYROLL, type Section } from './sections'

export function CompanyNav({ companyId }: { companyId: string | undefined }) {
  if (companyId === undefined) return null

  return (
    <>
      <Group label={t.nav.accounting} sections={ACCOUNTING} companyId={companyId} />
      <Group label={t.nav.commercial} sections={COMMERCIAL} companyId={companyId} />
      <Group label={t.nav.payroll} sections={PAYROLL} companyId={companyId} />
    </>
  )
}

/** The condensed caps that separate one run of entries from the next. */
function Group({
  label,
  sections,
  companyId,
}: {
  label: string
  sections: Section[]
  companyId: string
}) {
  return (
    <>
      <div className="px-3 pt-4 pb-1.5 type-eyebrow text-navy-300">{label}</div>
      {sections.map((section) => (
        <NavLink
          key={section.path}
          to={`/companii/${companyId}/${section.path}`}
          // Not `end`: a screen below a section keeps its section marked -- the
          // initialisation form under the chart, a batch under the opening
          // balances, one person's exemptions under the people list.
          className={({ isActive }) => navItem(isActive)}
        >
          <Icon name={section.icon} size={20} />
          <span>{section.label}</span>
        </NavLink>
      ))}
    </>
  )
}

/**
 * The sidebar entry, in both states.
 *
 * The active one is marked three ways at once -- gold wash, gold rule down the
 * leading edge, brighter ink -- because on navy at this size a single one of the
 * three is a difference you have to look for.
 */
export function navItem(isActive: boolean): string {
  const base = 'flex h-10 shrink-0 items-center gap-3 rounded-control px-3 type-body-md'
  return isActive
    ? `${base} bg-[rgba(198,161,91,.16)] text-[var(--parchment-100)] font-semibold shadow-[inset_2px_0_0_var(--gold-500)]`
    : `${base} text-navy-200 hover:bg-[rgba(198,161,91,.09)] hover:text-[var(--parchment-100)]`
}
