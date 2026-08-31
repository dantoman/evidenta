/**
 * The panel a screen's content sits on, against the parchment page.
 *
 * `crestRule` is the 3px gold foil edge from the crest. It marks the one panel on
 * a screen that carries the conclusion -- a balance that balances, a set that is
 * complete -- and it is worth nothing if a screen puts it on four panels.
 *
 * `padding="none"` is what a grid uses: the table's own cell padding is the
 * system's, and a panel padding around it would inset the rules away from the
 * panel edge, which is where a printed register puts them.
 */

import type { ReactNode } from 'react'

import { cn } from './cn'

export type CardTone = 'default' | 'sunken' | 'inverse' | 'outline'

const TONE: Record<CardTone, string> = {
  default: 'border-border bg-surface shadow-card',
  sunken: 'border-border bg-surface-muted',
  inverse: 'border-navy-700 bg-surface-inverse text-on-navy shadow-raised',
  outline: 'border-border-strong bg-transparent',
}

export function Card({
  tone = 'default',
  padding = 'md',
  crestRule,
  eyebrow,
  title,
  actions,
  className,
  children,
}: {
  tone?: CardTone
  padding?: 'md' | 'none'
  crestRule?: boolean
  /** Condensed caps above the title: the period, the source, the section. */
  eyebrow?: string
  title?: string
  actions?: ReactNode
  className?: string
  children?: ReactNode
}) {
  const inset = padding === 'none' ? '' : 'p-6'
  return (
    <section className={cn('overflow-hidden rounded-card border', TONE[tone], className)}>
      {crestRule && <div className="h-[var(--border-width-crest)] bg-[image:var(--gradient-gold-foil)]" />}
      {(eyebrow || title || actions) && (
        // The header keeps its padding even when the body has none -- a
        // deliberate departure from the design system, whose own card computes
        // the header inset from `padding` and therefore lets a title touch the
        // panel edge on a grid card. The body is what must reach the edge, so
        // the table's rules land on it; the title never was.
        <header className="flex items-start justify-between gap-4 p-6 pb-0">
          <div>
            {eyebrow && (
              <div className={cn('mb-1 type-eyebrow', tone === 'inverse' ? 'text-gold-400' : 'text-gold-strong')}>
                {eyebrow}
              </div>
            )}
            {title && (
              <h3 className={cn('type-title m-0', tone === 'inverse' ? 'text-on-navy' : 'text-heading')}>
                {title}
              </h3>
            )}
          </div>
          {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
        </header>
      )}
      {children !== undefined && <div className={inset}>{children}</div>}
    </section>
  )
}
