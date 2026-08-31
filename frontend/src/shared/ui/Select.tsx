/**
 * The native select, level with `Input`, with the platform arrow replaced by the
 * system's chevron.
 *
 * Native rather than a listbox built here: it is keyboard-correct on every
 * platform for free, and `C40` puts the keyboard first. The day a screen needs
 * search inside the list -- the nomenclator behind `F` -- that is a different
 * component with a different name, not this one grown a third responsibility.
 */

import type { SelectHTMLAttributes } from 'react'

import { cn } from './cn'
import { CONTROL_BASE } from './Input'
import { Icon } from './Icon'

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean
}

export function Select({ invalid, className, children, ...rest }: SelectProps) {
  return (
    <span className={cn('relative inline-flex w-full items-center', className)}>
      <select
        aria-invalid={invalid || undefined}
        className={cn(
          CONTROL_BASE,
          'w-full appearance-none cursor-pointer pl-3 pr-9 type-body-md',
          invalid ? 'border-danger' : 'border-border',
        )}
        {...rest}
      >
        {children}
      </select>
      <Icon name="chevron-down" size={16} className="pointer-events-none absolute right-3 text-ink-muted" />
    </span>
  )
}
