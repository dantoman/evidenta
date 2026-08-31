/**
 * The button -- five intents, three heights (ADR-074, from the design system's
 * `components/core/Button.jsx`).
 *
 * Before it, sixteen screens carried the identical string
 * `rounded border border-border bg-surface px-3 text-sm text-accent`, so every
 * action on every screen looked like a link -- including the ones that post to
 * the ledger. The intents exist to stop that: exactly one `primary` per screen,
 * and it is the thing the screen is for.
 *
 * `gold` is the ceremonial one and is spent sparingly: in the design it marks the
 * act that closes something -- a period, an exercise -- not an ordinary save.
 */

import type { ButtonHTMLAttributes } from 'react'

import { cn } from './cn'
import { Icon, type IconName } from './Icon'

export type ButtonVariant = 'primary' | 'gold' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-control border font-semibold ' +
  'tracking-[var(--tracking-tight)] transition-colors ' +
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ' +
  'active:scale-[.985] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100'

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-control-sm px-button-x-sm type-body-sm',
  md: 'h-control-md px-button-x-md type-body-md',
  lg: 'h-control-lg px-button-x-lg type-body-lg',
}

const GLYPH: Record<ButtonSize, number> = { sm: 15, md: 17, lg: 19 }

const VARIANT: Record<ButtonVariant, string> = {
  primary: 'border-accent bg-accent text-on-navy shadow-card hover:border-accent-strong hover:bg-accent-strong',
  gold: 'border-gold-hover bg-gold text-on-gold shadow-card hover:bg-gold-hover',
  secondary:
    'border-border-strong bg-surface text-heading shadow-card hover:border-navy-300 hover:bg-navy-050',
  ghost: 'border-transparent bg-transparent text-link hover:bg-navy-050',
  danger: 'border-danger-strong bg-danger text-white shadow-card hover:bg-danger-strong',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconName
  iconAfter?: IconName
  block?: boolean
}

export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  iconAfter,
  block,
  className,
  type,
  children,
  ...rest
}: ButtonProps) {
  return (
    // `type` defaults to "button", not "submit". The HTML default submits the
    // surrounding form, which here would mean posting a document from a button
    // whose label says something else entirely.
    <button
      type={type ?? 'button'}
      className={cn(BASE, SIZE[size], VARIANT[variant], block && 'w-full', className)}
      {...rest}
    >
      {icon && <Icon name={icon} size={GLYPH[size]} />}
      {children}
      {iconAfter && <Icon name={iconAfter} size={GLYPH[size]} />}
    </button>
  )
}

/** A square button carrying only a glyph. It always says what it does, out loud. */
export function IconButton({
  icon,
  label,
  size = 'md',
  variant = 'ghost',
  className,
  ...rest
}: Omit<ButtonProps, 'icon' | 'children'> & { icon: IconName; label: string }) {
  const box = size === 'sm' ? 'size-control-sm' : size === 'lg' ? 'size-control-lg' : 'size-control-md'
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        BASE,
        box,
        'px-0',
        variant === 'ghost' ? 'border-transparent bg-transparent text-ink-muted hover:bg-navy-050 hover:text-heading' : VARIANT[variant],
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={size === 'sm' ? 16 : size === 'lg' ? 20 : 18} />
    </button>
  )
}
