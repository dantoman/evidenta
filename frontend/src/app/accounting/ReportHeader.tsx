/**
 * The header every report shares: a title, the window, and the export link.
 *
 * The window is a choice the reader makes each time and the default is the
 * calendar year, never "today" -- a report whose window moves with the clock is
 * one two people cannot compare (the trial balance says the same thing).
 *
 * **The export is a link, not a button that builds a file.** The server produces
 * it from the same result it rendered (C20), and the browser downloads it with
 * the session cookie. Nothing here formats a number for the file.
 */

import { useState, type ReactNode } from 'react'

import { t } from '@/locales'

const FIELD = 'rounded border border-border bg-surface px-2 text-sm'

export function yearStart(): string {
  return `${new Date().getFullYear()}-01-01`
}

export function yearEnd(): string {
  return `${new Date().getFullYear()}-12-31`
}

export interface Window {
  from: string
  to: string
}

export function useWindow(): [Window, (next: Window) => void] {
  const [window, setWindow] = useState<Window>({ from: yearStart(), to: yearEnd() })
  return [window, setWindow]
}

export function ReportHeader({
  title,
  lead,
  window,
  onWindow,
  exportHref,
  children,
}: {
  title: string
  lead?: string
  window: Window
  onWindow: (next: Window) => void
  /** Where the same report is served as CSV; absent when there is nothing yet. */
  exportHref?: string
  children?: ReactNode
}) {
  const [from, setFrom] = useState(window.from)
  const [to, setTo] = useState(window.to)

  return (
    <header className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-base font-semibold">{title}</h1>
          {lead && <p className="text-sm text-ink-muted">{lead}</p>}
        </div>
        <form
          className="flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            onWindow({ from, to })
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.accounting.reports.from}</span>
            <input
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
              className={FIELD}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">{t.accounting.reports.to}</span>
            <input
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
              className={FIELD}
            />
          </label>
          <button
            type="submit"
            className="rounded border border-border bg-surface px-3 text-sm text-accent"
          >
            {t.accounting.reports.show}
          </button>
          {exportHref && (
            <a
              href={exportHref}
              download
              title={t.accounting.reports.exportHint}
              className="rounded border border-border bg-surface px-3 text-sm text-accent"
            >
              {t.accounting.reports.exportCsv}
            </a>
          )}
        </form>
      </div>
      {children}
    </header>
  )
}
