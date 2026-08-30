/**
 * `EntryGrid` -- the keyboard-entry primitive (F1.G2, ADR-052, C40).
 *
 * Not "the document-lines grid": the one component every surface that takes
 * rows from a person goes through -- manual notes, opening balances, document
 * lines, account mapping at import, bank-statement matching. Conceived narrowly
 * it would force a second grid the day reconciliation arrives (`OD-41`); so it
 * knows about cells of three kinds and about rows, and nothing about what a row
 * means.
 *
 * **The keyboard belongs here and nowhere else** (C40). The contract is ADR-052
 * section 3, transcribed:
 *
 *   Enter          advance; on the last field of the row, open a new row
 *   Escape         cancel the cell; a second press cancels the row in progress
 *   typing         over a selected cell replaces its content
 *   F4             open the lookup of the field (account, partner, item)
 *   F2             edit the selected cell keeping its content
 *   Ctrl+Enter     hand the document to the screen -- `onValidate`
 *   arrows         move between cells without entering edit
 *   Tab            advance like Enter, without opening a row; Shift+Tab back
 *   Ctrl+Delete    delete the selected row, twice if it holds anything
 *
 * A screen that added a key handler over this would be adding a second
 * semantics; the contract is one, for everyone (R23).
 *
 * **Both decimal separators are accepted and one is stored.** The numeric keypad
 * produces a point, the Romanian interface shows a comma (C18); an amount cell
 * takes either and keeps the canonical form the server reads -- a point, no
 * grouping. Display goes through `@/shared/format`, never through this file.
 *
 * **The balance indicator reflects R11, it does not enforce it.** Σ debit and Σ
 * credit over the rows being typed are added as integers at four decimals --
 * the server's scale -- so a person can see whether the note is finished. The
 * check that matters is the engine's and the database's; this only saves a round
 * trip. It is the one sum computed in the client, and it is over rows that exist
 * nowhere else yet, which is why C19 does not apply to it.
 *
 * **Row height and cell padding come from the density tokens** (C21, C26,
 * ADR-042). Nothing here writes a pixel; ESLint refuses a literal utility in this
 * file.
 */

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

import { amount as formatAmount } from '@/shared/format'
import type { Density } from '@/shared/DataGrid'

const ROW_HEIGHT: Record<Density, string> = {
  comfortable: 'var(--spacing-row-comfortable)',
  compact: 'var(--spacing-row-compact)',
  dense: 'var(--spacing-row-dense)',
}

const HEADER_HEIGHT: Record<Density, string> = {
  comfortable: 'var(--spacing-header-comfortable)',
  compact: 'var(--spacing-header-compact)',
  dense: 'var(--spacing-header-dense)',
}

const CELL_PADDING: Record<Density, string> = {
  comfortable: 'var(--spacing-cell-x-comfortable)',
  compact: 'var(--spacing-cell-x-compact)',
  dense: 'var(--spacing-cell-x-dense)',
}

export type CellKind = 'text' | 'amount' | 'lookup'

export interface LookupOption {
  id: string
  /** What the person reads: `221 — Creanțe comerciale`. */
  label: string
  /** What the person types to find it: the code. Matched before the label. */
  code?: string
}

/** Every row is a map of column key to the string the cell holds. */
export type EntryRow = Record<string, string>

export interface EntryColumn<Row extends EntryRow> {
  key: keyof Row & string
  header: string
  kind: CellKind
  /** For `lookup`: the nomenclature the cell picks from. Stored value is the id. */
  options?: LookupOption[]
  width?: string
  /** A message, or null when the value is acceptable. Shown under the cell. */
  validate?: (value: string, row: Row) => string | null
}

export interface EntryGridProps<Row extends EntryRow> {
  columns: EntryColumn<Row>[]
  rows: Row[]
  onChange: (rows: Row[]) => void
  /** The row Enter opens on the last field. The screen decides what empty means. */
  newRow: () => Row
  /** Ctrl+Enter -- validation is the screen's action; the grid only names the key. */
  onValidate?: () => void
  /** Which two amount columns to show the R11 indicator for. */
  balance?: { debit: keyof Row & string; credit: keyof Row & string }
  density?: Density
  /** Names the grid for assistive technology and for tests. */
  label: string
  /** Rendered below the grid on the indicator line -- a total, a hint. */
  footer?: ReactNode
  strings: EntryGridStrings
}

/** Interface strings arrive from the screen's resource file (C32). */
export interface EntryGridStrings {
  balanceDebit: string
  balanceCredit: string
  balanceDifference: string
  balanced: string
  invalidAmount: string
  noMatch: string
  deleteAgain: string
}

interface Position {
  row: number
  col: number
}

// --- amounts -------------------------------------------------------------------

/**
 * A typed amount to the canonical form the server reads, or null if it is not
 * one. `1.234` and `1,234` are both one-point-two-three-four: the grid does not
 * guess grouping, and a value with two separators is refused.
 */
export function parseAmount(text: string): string | null {
  const trimmed = text.trim()
  if (trimmed === '') return ''
  const match = /^(-?)(\d*)(?:[.,](\d*))?$/.exec(trimmed)
  if (!match) return null
  const [, sign = '', whole = '', fraction = ''] = match
  if (whole === '' && fraction === '') return null
  const integer = whole === '' ? '0' : whole.replace(/^0+(?=\d)/, '')
  const decimals = fraction.replace(/0+$/, '')
  const canonical = decimals === '' ? integer : `${integer}.${decimals}`
  return canonical === '0' ? '0' : `${sign}${canonical}`
}

const SCALE = 4

/**
 * A canonical amount as an integer at four decimals -- the server's scale.
 * Exported for the screen that has to decide whether a set of rows is ready to
 * send: the same arithmetic as the indicator, so the button and the indicator
 * cannot disagree. Not a total anybody reads as a figure (C19).
 */
export function amountUnits(canonical: string): number {
  if (canonical === '' || canonical === null) return 0
  const [sign, rest] = canonical.startsWith('-') ? ['-', canonical.slice(1)] : ['', canonical]
  const [whole = '0', fraction = ''] = rest.split('.')
  const scaled = Number(whole) * 10 ** SCALE + Number(fraction.padEnd(SCALE, '0').slice(0, SCALE))
  return sign === '-' ? -scaled : scaled
}

function decimalOf(total: number): string {
  const sign = total < 0 ? '-' : ''
  const absolute = Math.abs(total)
  const whole = Math.floor(absolute / 10 ** SCALE)
  const fraction = String(absolute % 10 ** SCALE).padStart(SCALE, '0')
  return `${sign}${whole}.${fraction}`
}

// --- the component -------------------------------------------------------------

export function EntryGrid<Row extends EntryRow>({
  columns,
  rows,
  onChange,
  newRow,
  onValidate,
  balance,
  density = 'compact',
  label,
  footer,
  strings,
}: EntryGridProps<Row>) {
  const [selected, setSelected] = useState<Position | null>(null)
  const [buffer, setBuffer] = useState<string | null>(null)
  const [lookupOpen, setLookupOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const [cellError, setCellError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<number | null>(null)
  // The row as it was when the selection entered it: the second Escape restores
  // it. Held with the index so a snapshot of one row never lands on another.
  const [snapshot, setSnapshot] = useState<{ row: number; values: Row } | null>(null)
  const container = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)

  const editing = buffer !== null

  useEffect(() => {
    if (editing) input.current?.focus()
    else if (selected) container.current?.focus()
  }, [editing, selected])

  const column = (col: number) => columns[col]!

  const select = (position: Position) => {
    if (!snapshot || snapshot.row !== position.row) {
      setSnapshot({ row: position.row, values: { ...rows[position.row]! } })
    }
    setSelected(position)
    setPendingDelete(null)
  }

  /**
   * Write one cell and hand back the rows as they now are. The caller that
   * goes on to append a row in the same event must build on this value, not on
   * `rows`: two `onChange` calls from one closure would both start from the
   * render's rows, and the second would erase the first -- measured, as a
   * credit that vanished the moment Enter opened the next line.
   */
  const update = (position: Position, value: string): Row[] => {
    const next = rows.map((row, index) =>
      index === position.row ? { ...row, [column(position.col).key]: value } : row,
    )
    onChange(next)
    return next
  }

  const startEdit = (initial: string, withLookup = false) => {
    if (!selected) return
    setBuffer(initial)
    setCellError(null)
    setHighlighted(0)
    setLookupOpen(withLookup || column(selected.col).kind === 'lookup')
  }

  const matches = (): LookupOption[] => {
    if (!selected) return []
    const options = column(selected.col).options ?? []
    const needle = (buffer ?? '').trim().toLowerCase()
    if (needle === '') return options
    return options.filter(
      (option) =>
        (option.code ?? '').toLowerCase().startsWith(needle) ||
        option.label.toLowerCase().includes(needle),
    )
  }

  /** Commit the buffer into the cell: the rows afterwards, or null if refused. */
  const commit = (): Row[] | null => {
    if (!selected || buffer === null) return rows
    const current = column(selected.col)
    let value = buffer
    if (current.kind === 'amount') {
      const parsed = parseAmount(buffer)
      if (parsed === null) {
        setCellError(strings.invalidAmount)
        return null
      }
      value = parsed
    } else if (current.kind === 'lookup') {
      const candidates = matches()
      if (buffer.trim() === '') {
        value = ''
      } else if (candidates.length === 0) {
        setCellError(strings.noMatch)
        return null
      } else {
        value = candidates[Math.min(highlighted, candidates.length - 1)]!.id
      }
    }
    const next = update(selected, value)
    setBuffer(null)
    setLookupOpen(false)
    setCellError(null)
    return next
  }

  const cancelCell = () => {
    setBuffer(null)
    setLookupOpen(false)
    setCellError(null)
  }

  const isEmpty = (row: Row) => {
    const blank = newRow()
    return columns.every((c) => (row[c.key] ?? '') === (blank[c.key] ?? ''))
  }

  const removeRow = (index: number) => {
    const next = rows.filter((_, at) => at !== index)
    onChange(next)
    setPendingDelete(null)
    setSnapshot(null)
    if (next.length === 0) setSelected(null)
    else setSelected({ row: Math.min(index, next.length - 1), col: 0 })
  }

  const cancelRow = () => {
    if (!selected) return
    if (snapshot && snapshot.row === selected.row && isEmpty(snapshot.values)) {
      // A row opened by Enter and never filled: cancelling it is removing it.
      removeRow(selected.row)
      return
    }
    if (snapshot && snapshot.row === selected.row) {
      onChange(rows.map((row, index) => (index === selected.row ? snapshot.values : row)))
    }
  }

  const advance = (openRow: boolean, current: Row[] = rows) => {
    if (!selected) return
    if (selected.col < columns.length - 1) {
      select({ row: selected.row, col: selected.col + 1 })
      return
    }
    if (selected.row < current.length - 1) {
      select({ row: selected.row + 1, col: 0 })
      return
    }
    if (openRow) {
      onChange([...current, newRow()])
      const position = { row: current.length, col: 0 }
      setSnapshot({ row: position.row, values: newRow() })
      setSelected(position)
      setPendingDelete(null)
    }
  }

  const retreat = () => {
    if (!selected) return
    if (selected.col > 0) select({ row: selected.row, col: selected.col - 1 })
    else if (selected.row > 0) select({ row: selected.row - 1, col: columns.length - 1 })
  }

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (!selected) return
    const key = event.key

    if (key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      if (commit() !== null) onValidate?.()
      return
    }

    if (editing) {
      if (key === 'Enter') {
        event.preventDefault()
        const next = commit()
        if (next !== null) advance(true, next)
      } else if (key === 'Tab') {
        event.preventDefault()
        const next = commit()
        if (next !== null) {
          if (event.shiftKey) retreat()
          else advance(false, next)
        }
      } else if (key === 'Escape') {
        event.preventDefault()
        cancelCell()
      } else if (key === 'ArrowDown' || key === 'ArrowUp') {
        if (lookupOpen) {
          event.preventDefault()
          const count = matches().length
          if (count > 0) {
            setHighlighted((at) =>
              key === 'ArrowDown' ? Math.min(at + 1, count - 1) : Math.max(at - 1, 0),
            )
          }
          return
        }
        event.preventDefault()
        const next = commit()
        if (next !== null) {
          const row = key === 'ArrowDown' ? selected.row + 1 : selected.row - 1
          if (row >= 0 && row < next.length) select({ row, col: selected.col })
        }
      } else if (key === 'F4') {
        event.preventDefault()
        if (column(selected.col).kind === 'lookup') setLookupOpen(true)
      }
      return
    }

    // Selected, not editing.
    if (key === 'Enter') {
      event.preventDefault()
      advance(true)
    } else if (key === 'Tab') {
      event.preventDefault()
      if (event.shiftKey) retreat()
      else advance(false)
    } else if (key === 'Escape') {
      event.preventDefault()
      cancelRow()
    } else if (key === 'F2') {
      event.preventDefault()
      startEdit(rows[selected.row]?.[column(selected.col).key] ?? '')
    } else if (key === 'F4') {
      event.preventDefault()
      if (column(selected.col).kind === 'lookup') startEdit('', true)
    } else if (key === 'ArrowRight') {
      event.preventDefault()
      if (selected.col < columns.length - 1) select({ row: selected.row, col: selected.col + 1 })
    } else if (key === 'ArrowLeft') {
      event.preventDefault()
      if (selected.col > 0) select({ row: selected.row, col: selected.col - 1 })
    } else if (key === 'ArrowDown') {
      event.preventDefault()
      if (selected.row < rows.length - 1) select({ row: selected.row + 1, col: selected.col })
    } else if (key === 'ArrowUp') {
      event.preventDefault()
      if (selected.row > 0) select({ row: selected.row - 1, col: selected.col })
    } else if (key === 'Delete' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      const row = rows[selected.row]
      if (row && (isEmpty(row) || pendingDelete === selected.row)) removeRow(selected.row)
      else setPendingDelete(selected.row)
    } else if (key === 'Delete' || key === 'Backspace') {
      event.preventDefault()
      update(selected, '')
    } else if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      // Typing over a selected cell replaces its content: the buffer starts
      // with this character, not with the old value.
      event.preventDefault()
      startEdit(key)
    }
  }

  const cellStyle = (col: number) => ({
    paddingInline: CELL_PADDING[density],
    width: column(col).width,
  })

  const display = (row: Row, col: number): string => {
    const value = row[column(col).key] ?? ''
    const current = column(col)
    if (current.kind === 'amount') return value === '' ? '' : formatAmount(value)
    if (current.kind === 'lookup') {
      const option = current.options?.find((o) => o.id === value)
      return option ? option.label : value
    }
    return value
  }

  const totals =
    balance &&
    rows.reduce(
      (sum, row) => ({
        debit: sum.debit + amountUnits(row[balance.debit] ?? ''),
        credit: sum.credit + amountUnits(row[balance.credit] ?? ''),
      }),
      { debit: 0, credit: 0 },
    )

  return (
    <div className="flex flex-col gap-2">
      <div
        ref={container}
        role="grid"
        aria-label={label}
        tabIndex={0}
        onKeyDown={onKeyDown}
        className="overflow-x-auto rounded border border-border bg-surface outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr
              className="border-b border-border text-left text-ink-muted"
              style={{ height: HEADER_HEIGHT[density] }}
            >
              {columns.map((c, col) => (
                <th
                  key={c.key}
                  scope="col"
                  className={`font-medium ${c.kind === 'amount' ? 'text-right' : ''}`}
                  style={cellStyle(col)}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className={`border-b border-border last:border-0 ${
                  pendingDelete === rowIndex ? 'bg-surface-muted' : ''
                }`}
                style={{ height: ROW_HEIGHT[density] }}
              >
                {columns.map((c, col) => {
                  const isSelected = selected?.row === rowIndex && selected.col === col
                  const isEditing = isSelected && editing
                  const problem = c.validate ? c.validate(row[c.key] ?? '', row) : null
                  return (
                    <td
                      key={c.key}
                      role="gridcell"
                      aria-selected={isSelected}
                      aria-label={`${c.header} ${rowIndex + 1}`}
                      onClick={() => {
                        if (editing && !isSelected) commit()
                        select({ row: rowIndex, col })
                      }}
                      onDoubleClick={() => {
                        select({ row: rowIndex, col })
                        startEdit(row[c.key] ?? '')
                      }}
                      className={`relative align-middle ${c.kind === 'amount' ? 'text-right tabular' : ''} ${
                        isSelected ? 'outline outline-2 -outline-offset-2 outline-accent' : ''
                      }`}
                      style={cellStyle(col)}
                    >
                      {isEditing ? (
                        <>
                          <input
                            ref={input}
                            value={buffer ?? ''}
                            onChange={(event) => {
                              setBuffer(event.target.value)
                              setHighlighted(0)
                              setCellError(null)
                              if (c.kind === 'lookup') setLookupOpen(true)
                            }}
                            onBlur={() => {
                              // Leaving with the mouse commits what was typed; a
                              // refused value stays where the person can see it.
                              if (buffer !== null) commit()
                            }}
                            inputMode={c.kind === 'amount' ? 'decimal' : undefined}
                            aria-label={`${c.header} ${rowIndex + 1}`}
                            aria-invalid={cellError !== null}
                            className={`w-full bg-surface outline-none ${
                              c.kind === 'amount' ? 'tabular text-right' : ''
                            }`}
                          />
                          {cellError && (
                            <span role="alert" className="absolute left-0 top-full z-10 bg-surface px-1 text-xs text-danger">
                              {cellError}
                            </span>
                          )}
                          {lookupOpen && c.kind === 'lookup' && (
                            <ul
                              role="listbox"
                              aria-label={c.header}
                              className="absolute left-0 top-full z-10 min-w-full overflow-y-auto rounded border border-border bg-surface shadow"
                              // Eight rows of the current density, as a token
                              // multiple rather than a literal height (C21).
                              style={{ maxHeight: `calc(8 * ${ROW_HEIGHT[density]})` }}
                            >
                              {matches().length === 0 && (
                                <li className="px-2 text-ink-muted">{strings.noMatch}</li>
                              )}
                              {matches()
                                .slice(0, 50)
                                .map((option, index) => (
                                  <li
                                    key={option.id}
                                    role="option"
                                    aria-selected={index === highlighted}
                                    onMouseDown={(event) => {
                                      event.preventDefault()
                                      setHighlighted(index)
                                      update(selected!, option.id)
                                      setBuffer(null)
                                      setLookupOpen(false)
                                    }}
                                    className={`whitespace-nowrap px-2 ${
                                      index === highlighted ? 'bg-surface-muted' : ''
                                    }`}
                                  >
                                    {option.label}
                                  </li>
                                ))}
                            </ul>
                          )}
                        </>
                      ) : (
                        <span className={problem ? 'text-danger' : ''} title={problem ?? undefined}>
                          {display(row, col)}
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
        <div>{footer}</div>
        {totals && (
          <p
            className={totals.debit === totals.credit ? 'text-ink-muted' : 'text-danger'}
            role={totals.debit === totals.credit ? undefined : 'status'}
          >
            {strings.balanceDebit} <span className="tabular">{formatAmount(decimalOf(totals.debit))}</span>
            {' · '}
            {strings.balanceCredit} <span className="tabular">{formatAmount(decimalOf(totals.credit))}</span>
            {' · '}
            {totals.debit === totals.credit ? (
              <span>{strings.balanced}</span>
            ) : (
              <span>
                {strings.balanceDifference}{' '}
                <span className="tabular">{formatAmount(decimalOf(totals.debit - totals.credit))}</span>
              </span>
            )}
          </p>
        )}
      </div>
      {pendingDelete !== null && (
        <p role="status" className="text-sm text-ink-muted">
          {strings.deleteAgain}
        </p>
      )}
    </div>
  )
}
