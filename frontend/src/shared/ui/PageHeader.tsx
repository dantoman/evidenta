/**
 * The top of every screen: where you are, what the screen is for, and the one or
 * two actions that belong to the whole of it.
 *
 * The eyebrow above the title is the design system's ribbon voice, and it carries
 * the context a title cannot: which company, which period, which version of the
 * chart. Before this, a page title was one notch larger than the rows beneath it
 * and nothing on the screen said where you were.
 */

import type { ReactNode } from 'react'

export function PageHeader({
  eyebrow,
  title,
  lead,
  actions,
}: {
  eyebrow?: string
  title: string
  lead?: string
  actions?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-6">
      <div>
        {eyebrow && <div className="mb-1.5 type-eyebrow text-gold-strong">{eyebrow}</div>}
        <h1 className="type-display-2 m-0 text-heading">{title}</h1>
        {/* Fără limită de măsură. Sistemul de design pune 62ch pe rezumat, iar
            pe o pagină lată aceea e o măsură bună de lectură -- dar aici coloana
            e deja mărginită de acţiunile din dreapta, aşa că limita nu proteja
            nimic: rupea rândul la jumătate şi lăsa dreapta goală. Rezumatele
            sunt una-două propoziţii; ce le mărgineşte e antetul, nu un `ch`. */}
        {lead && <p className="mt-2 mb-0 type-body-md text-ink-muted">{lead}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-3">{actions}</div>}
    </header>
  )
}
