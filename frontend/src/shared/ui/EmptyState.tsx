/**
 * Nothing here, and why.
 *
 * An empty grid says "no rows"; this says which rows and what would put one
 * there. In an accounting application the difference matters more than usual,
 * because "no entries in this period" and "you cannot see this company's entries"
 * look identical from the outside and mean opposite things.
 */

import type { ReactNode } from 'react'

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-border-strong bg-surface-muted px-6 py-12 text-center">
      <img src="/brand/owl-outline-gold.png" alt="" className="h-14 w-auto opacity-55" />
      <h3 className="type-display-3 m-0 text-heading">{title}</h3>
      {description && <p className="m-0 max-w-[46ch] type-body-md text-ink-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
