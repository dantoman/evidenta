/**
 * A state, said in a word: înregistrat, stornată, blocat, închis.
 *
 * Colour is never the only carrier -- the word is always there. A row that means
 * "reversed" has to survive being printed in black and white, and about one man
 * in twelve does not see the red.
 *
 * The tones are the ledger's own language, which is why `credit` is green and
 * `debit` is red here and nowhere else in the palette.
 */

import type { ReactNode } from 'react'

import { cn } from './cn'

export type BadgeTone = 'neutral' | 'navy' | 'gold' | 'credit' | 'debit' | 'caution' | 'info'

const TONE: Record<BadgeTone, string> = {
  neutral: 'border-[var(--ink-200)] bg-[var(--ink-100)] text-[var(--ink-700)]',
  navy: 'border-[var(--navy-100)] bg-[var(--navy-050)] text-[var(--navy-700)]',
  gold: 'border-[var(--gold-200)] bg-[var(--gold-100)] text-[var(--gold-900)]',
  credit: 'border-[#c8e0d2] bg-[var(--credit-100)] text-[var(--credit-700)]',
  debit: 'border-[#efc9c4] bg-[var(--debit-100)] text-[var(--debit-700)]',
  caution: 'border-[#efd9a8] bg-[var(--caution-100)] text-[var(--caution-700)]',
  info: 'border-[#c3dce7] bg-[var(--info-100)] text-[var(--info-700)]',
}

export function Badge({
  tone = 'neutral',
  dot,
  className,
  children,
}: {
  tone?: BadgeTone
  dot?: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex h-[22px] items-center gap-2 whitespace-nowrap rounded-xs border px-2',
        'type-eyebrow tracking-[var(--tracking-caps)]',
        TONE[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}
