/**
 * `DataGrid` -- the only entry point for reading grids (C16, C17, ADR-001).
 *
 * Screens never import `@tanstack/react-table`; ESLint refuses it everywhere but
 * here and in `EntryGrid`. The rule exists because a second grid does not get
 * built by decision -- it gets built by one screen importing the library for one
 * special case, and then a third.
 *
 * **Totals come from the server and are never computed here** (C19). The prop is
 * called `serverTotals` so a caller who wanted to sum a column in the browser has
 * to notice the name and think about why. In an accounting report a wrong total
 * is a serious defect, not a cosmetic inconsistency -- and a total computed over a
 * paginated or virtualised set is wrong by construction.
 *
 * **No formatting here** (C18). A cell receives what the screen formatted through
 * `@/shared/format`; the grid decides alignment and figures, never separators.
 *
 * **Row height comes from the density tokens** (C21, C26, ADR-042). Nothing in
 * this file writes a pixel value: the scale is the contract, and a literal here
 * would silently opt one grid out of it.
 *
 * What this deliberately does **not** do yet: virtualisation. It renders every
 * row it is given, which is right for a chart of accounts and wrong for a general
 * ledger at volume. ADR-001 reserves hand-written CSS for exactly that work, in
 * exactly this file (C25); the seam is `rows`, and nothing above it changes when
 * virtualisation arrives. Naming the gap is cheaper than discovering it from a
 * frozen browser.
 */

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'
import type { ReactNode } from 'react'

/**
 * Three rungs, and only three. Carbon, Sage and SAP each ship 24 / 32 / 40 --
 * three independent systems landing on the same numbers. `compact` is the
 * default because SAP's desktop default carries that exact name and that exact
 * height, and Sage, an accounting vendor, defaults higher still.
 *
 * `dense` carries no in-row buttons: 24px minus a 1px border leaves 23, under
 * the 24x24 minimum of WCAG 2.2 SC 2.5.8.
 */
export type Density = 'comfortable' | 'compact' | 'dense'

/** Token names, not values. The scale lives in `index.css` (ADR-042). */
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

export interface Column<Row> {
  /** Stable identifier, and the key `serverTotals` is looked up by. */
  key: string
  header: string
  cell: (row: Row) => ReactNode
  /**
   * Amounts, quantities, anything read down a column. Right-aligned and given
   * tabular figures (C27) -- without them the digits shift horizontally from one
   * row to the next, and a column of money that moves is hard to read down.
   */
  numeric?: boolean
  width?: string
}

export interface DataGridProps<Row> {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string
  density?: Density
  /**
   * Totals **as the server computed them** (C19). Keyed by column key. A grid
   * that summed its own rows would be summing the page, not the report.
   */
  serverTotals?: Record<string, ReactNode>
  emptyMessage: string
  onRowClick?: (row: Row) => void
}

export function DataGrid<Row>({
  columns,
  rows,
  rowKey,
  density = 'compact',
  serverTotals,
  emptyMessage,
  onRowClick,
}: DataGridProps<Row>) {
  const definitions: ColumnDef<Row>[] = columns.map((column) => ({
    id: column.key,
    header: column.header,
    cell: (context) => column.cell(context.row.original),
  }))

  const table = useReactTable({
    data: rows,
    columns: definitions,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => rowKey(row),
  })

  const byKey = new Map(columns.map((column) => [column.key, column]))

  const cellStyle = (column: Column<Row>) => ({
    paddingInline: CELL_PADDING[density],
    width: column.width,
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse type-body-sm">
        <thead>
          <tr
            className="border-y border-border bg-surface-muted text-left"
            style={{ height: HEADER_HEIGHT[density] }}
          >
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                // Condensed caps on the sunken ground: the design system marks a
                // column head by voice and background, never by height, so a
                // header row stays the height of a row (ADR-074).
                className={`whitespace-nowrap type-eyebrow text-ink-muted ${column.numeric ? 'text-right' : ''}`}
                style={cellStyle(column)}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {table.getRowModel().rows.length === 0 ? (
            <tr style={{ height: ROW_HEIGHT[density] }}>
              <td
                colSpan={columns.length}
                className="text-center type-body-md text-ink-muted"
                style={{ paddingInline: CELL_PADDING[density] }}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                style={{ height: ROW_HEIGHT[density] }}
                className={`border-b border-border last:border-0 ${
                  onRowClick ? 'cursor-pointer hover:bg-navy-050' : ''
                }`}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
              >
                {row.getVisibleCells().map((cell) => {
                  // Looked up by column id rather than by position. Indexing the
                  // array in parallel works until the day a column is hidden or
                  // reordered, and then it renders the wrong cell in the right
                  // place -- the kind of wrong that reads as correct.
                  const column = byKey.get(cell.column.id)
                  if (!column) return null
                  return (
                    <td
                      key={cell.id}
                      className={column.numeric ? 'text-right tabular' : ''}
                      style={cellStyle(column)}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  )
                })}
              </tr>
            ))
          )}
        </tbody>

        {serverTotals && (
          <tfoot>
            <tr
              // A gold rule over the totals, not a hairline. It is the one place
              // the crest's foil appears in a grid, and it appears there because
              // the line under a column of figures is what a reader looks for.
              className="border-t-2 border-[var(--rule-gold)] type-label text-heading"
              style={{ height: 'var(--spacing-grid-footer)' }}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={column.numeric ? 'text-right tabular' : ''}
                  style={cellStyle(column)}
                >
                  {serverTotals[column.key] ?? null}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
