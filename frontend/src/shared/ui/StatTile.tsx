/**
 * One figure, read at a glance -- the panel's headline numbers.
 *
 * **The tile can say it has no figure, and that is half of what it is for.** A
 * panel has four of these and an accountant reads them in a second; a tile that
 * showed `0,00` where the truth is "nothing in this system computes that yet"
 * would be the single most damaging widget in the product. So `value` is
 * `string | null`, and `note` carries the reason when it is null -- named in the
 * screen's resource file, never composed here.
 *
 * **The comparison is a figure, not a percentage.** The design draws "+4,2% faţă
 * de luna trecută"; what this renders is the previous month's amount. Two
 * server decimals turned into a percentage would have to pass through floats in
 * the browser, which is exactly what `@/shared/format` exists to prevent -- and
 * the amount answers the same question without inventing a number nobody can
 * check against a register.
 */

import { Figure, type FigureTone } from './Figure'
import { Icon, type IconName } from './Icon'
import { cn } from './cn'

export type StatTileTone = 'default' | 'inverse'

export function StatTile({
  label,
  icon,
  value,
  currency,
  note,
  figureTone,
  tone = 'default',
}: {
  label: string
  icon: IconName
  /** The server's decimal string, or `null` when nothing can answer it. */
  value: string | null
  currency?: string
  /** The comparison beneath the figure -- or, with no figure, why there is none. */
  note?: string
  figureTone?: FigureTone
  tone?: StatTileTone
}) {
  const inverse = tone === 'inverse'
  return (
    <section
      className={cn(
        'flex flex-col gap-3 rounded-card border p-5',
        inverse
          ? 'border-navy-700 bg-surface-inverse shadow-raised'
          : 'border-border bg-surface shadow-card',
      )}
    >
      <header className="flex items-start justify-between gap-3">
        <span
          className={cn('type-eyebrow', inverse ? 'text-gold-400' : 'text-ink-muted')}
        >
          {label}
        </span>
        <Icon
          name={icon}
          size={18}
          className={inverse ? 'text-navy-300' : 'text-ink-faint'}
        />
      </header>

      {value === null ? (
        // An em-dash, not a zero, and the reason directly under it. The dash is
        // the same one the rest of the interface uses for "nothing here".
        <span className={cn('type-figure-lg', inverse ? 'text-navy-300' : 'text-ink-faint')}>
          —
        </span>
      ) : (
        <Figure
          value={value}
          currency={currency}
          size="lg"
          tone={figureTone}
          className={cn('tabular', inverse && 'text-on-navy')}
        />
      )}

      {note && (
        <p
          className={cn(
            'm-0 type-caption',
            inverse ? 'text-on-navy-muted' : 'text-ink-muted',
          )}
        >
          {note}
        </p>
      )}
    </section>
  )
}
