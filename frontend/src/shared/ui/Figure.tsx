/**
 * Every amount on a screen renders through this.
 *
 * The formatting itself is **not** here: it is `@/shared/format`, the single
 * module `C18` requires, which formats the server's decimal string exactly and
 * never through a float. This component decides face, alignment and tone -- the
 * display concerns -- and delegates the value.
 *
 * `signed` marks negatives only. Colouring every positive amount green makes a
 * register noisy and teaches the eye to ignore the colour, which is the one thing
 * a negative figure cannot afford.
 */

import { amount } from '@/shared/format'
import { cn } from './cn'

export type FigureSize = 'sm' | 'md' | 'lg'
export type FigureTone = 'neutral' | 'positive' | 'negative'

const SIZE: Record<FigureSize, string> = {
  sm: 'type-figure-sm',
  md: 'type-figure-md',
  lg: 'type-figure-lg',
}

const TONE: Record<FigureTone, string> = {
  neutral: 'text-heading',
  positive: 'text-credit',
  negative: 'text-debit',
}

export function Figure({
  value,
  currency,
  size = 'md',
  tone,
  signed,
  className,
}: {
  /** The server's decimal string. A number is accepted for figures computed nowhere. */
  value: string | number
  currency?: string
  size?: FigureSize
  tone?: FigureTone
  signed?: boolean
  className?: string
}) {
  const negative = signed && Number(value) < 0
  const resolved: FigureTone = tone ?? (negative ? 'negative' : 'neutral')
  return (
    <span className={cn('whitespace-nowrap', SIZE[size], TONE[resolved], className)}>
      {amount(value)}
      {currency ? ` ${currency}` : ''}
    </span>
  )
}
