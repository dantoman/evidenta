/**
 * Label above, help or refusal below -- the scaffold every form control sits in.
 *
 * `error` replaces `hint` rather than joining it: two lines of small text under a
 * field, one of them stale advice, is how a person reads past the sentence that
 * says why the value was refused.
 */

import type { ReactNode } from 'react'

import { cn } from './cn'

export function Field({
  label,
  hint,
  error,
  required,
  className,
  children,
}: {
  label: string
  hint?: string
  /** What the server refused, in the words of `C10`'s catalogue, never a raw code. */
  error?: string
  required?: boolean
  className?: string
  children: ReactNode
}) {
  return (
    // The label wraps the control, so its text is a hit target without an
    // id/htmlFor pair that has to stay unique on a screen rendering the same
    // form twice.
    <label className={cn('flex flex-col gap-2', className)}>
      <span className="flex gap-1 type-label text-heading">
        {label}
        {required && <span className="text-danger">*</span>}
      </span>
      {children}
      {error ? (
        <span role="alert" className="type-caption text-danger-strong">
          {error}
        </span>
      ) : hint ? (
        <span className="type-caption text-ink-muted">{hint}</span>
      ) : null}
    </label>
  )
}
