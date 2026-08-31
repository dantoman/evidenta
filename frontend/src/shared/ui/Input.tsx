/**
 * A text field at the system's control height, optionally with a leading glyph
 * and a trailing unit.
 *
 * `numeric` is not decoration: it switches the field to the tabular mono face and
 * right-aligns it, so a column of typed amounts lines up digit under digit while
 * it is being typed, not only after it is saved (C27).
 *
 * The base sets no width. That is what lets a caller write `className="w-96"`
 * with nothing to resolve -- there is no `tailwind-merge` here because the base
 * never has an opinion to conflict with.
 */

import type { InputHTMLAttributes } from 'react'

import { cn } from './cn'
import { Icon, type IconName } from './Icon'

export const CONTROL_BASE =
  'h-control-md rounded-control border bg-surface text-ink shadow-[var(--shadow-inset-field)] ' +
  'transition-colors placeholder:text-ink-faint focus:outline-none focus:border-focus ' +
  'focus:shadow-[var(--ring-focus)] disabled:bg-surface-muted disabled:text-ink-muted'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: IconName
  /** A unit or a currency, shown inside the field's right edge. */
  suffix?: string
  /** The server refused this value, or it cannot be sent as typed. */
  invalid?: boolean
  numeric?: boolean
}

export function Input({ icon, suffix, invalid, numeric, className, ...rest }: InputProps) {
  return (
    <span className={cn('relative inline-flex w-full items-center', className)}>
      {icon && (
        <Icon name={icon} size={16} className="pointer-events-none absolute left-3 text-ink-faint" />
      )}
      <input
        aria-invalid={invalid || undefined}
        className={cn(
          CONTROL_BASE,
          'w-full',
          icon ? 'pl-9' : 'pl-3',
          suffix ? 'pr-11' : 'pr-3',
          numeric ? 'type-figure-md text-right' : 'type-body-md',
          invalid ? 'border-danger' : 'border-border',
        )}
        {...rest}
      />
      {suffix && (
        <span className="pointer-events-none absolute right-3 type-body-sm text-ink-muted">
          {suffix}
        </span>
      )}
    </span>
  )
}
