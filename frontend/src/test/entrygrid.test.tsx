/**
 * One test per row of ADR-052 section 3, over `EntryGrid` and not over a screen.
 *
 * Keys are fired at the grid; nothing here goes through a screen's handlers,
 * because there are none (C40). What is asserted is the contract -- where the
 * selection went, what the row holds afterwards -- never how it looks.
 */

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { EntryGrid, parseAmount, type EntryColumn, type EntryGridStrings } from '@/shared/EntryGrid'

type Line = { account: string; note: string; debit: string; credit: string }

const STRINGS: EntryGridStrings = {
  balanceDebit: 'Debit',
  balanceCredit: 'Credit',
  balanceDifference: 'Diferență',
  balanced: 'Echilibrat',
  invalidAmount: 'Nu este o sumă',
  noMatch: 'Niciun cont',
  deleteAgain: 'Apăsați din nou pentru a șterge rândul',
}

const ACCOUNTS = [
  { id: 'a1', code: '221', label: '221 — Creanțe' },
  { id: 'a2', code: '611', label: '611 — Venituri' },
  { id: 'a3', code: '534', label: '534 — TVA' },
]

const COLUMNS: EntryColumn<Line>[] = [
  { key: 'account', header: 'Cont', kind: 'lookup', options: ACCOUNTS },
  { key: 'note', header: 'Explicație', kind: 'text' },
  { key: 'debit', header: 'Debit', kind: 'amount' },
  { key: 'credit', header: 'Credit', kind: 'amount' },
]

const EMPTY: Line = { account: '', note: '', debit: '', credit: '' }

function Harness({
  initial = [{ ...EMPTY }],
  onValidate,
  onRows,
}: {
  initial?: Line[]
  onValidate?: () => void
  onRows?: (rows: Line[]) => void
}) {
  const [rows, setRows] = useState<Line[]>(initial)
  return (
    <EntryGrid<Line>
      columns={COLUMNS}
      rows={rows}
      onChange={(next) => {
        setRows(next)
        onRows?.(next)
      }}
      newRow={() => ({ ...EMPTY })}
      onValidate={onValidate}
      balance={{ debit: 'debit', credit: 'credit' }}
      label="Rânduri"
      strings={STRINGS}
    />
  )
}

function grid() {
  return screen.getByRole('grid', { name: 'Rânduri' })
}

function cell(header: string, row: number) {
  return screen.getByRole('gridcell', { name: `${header} ${row}` })
}

function key(target: HTMLElement, key: string, init: KeyboardEventInit = {}) {
  fireEvent.keyDown(target, { key, ...init })
}

function type(text: string) {
  const input = screen.getByRole('textbox') as HTMLInputElement
  fireEvent.change(input, { target: { value: text } })
  return input
}

afterEach(cleanup)

describe('EntryGrid — contractul ADR-052 §3', () => {
  it('Enter avansează la câmpul următor și pe ultimul câmp deschide o linie nouă', () => {
    const rows = vi.fn()
    render(<Harness onRows={rows} />)
    fireEvent.click(cell('Cont', 1))
    expect(cell('Cont', 1)).toHaveAttribute('aria-selected', 'true')

    key(grid(), 'Enter')
    expect(cell('Explicație', 1)).toHaveAttribute('aria-selected', 'true')
    key(grid(), 'Enter')
    key(grid(), 'Enter')
    expect(cell('Credit', 1)).toHaveAttribute('aria-selected', 'true')

    key(grid(), 'Enter')
    expect(cell('Cont', 2)).toHaveAttribute('aria-selected', 'true')
    expect(rows).toHaveBeenLastCalledWith([{ ...EMPTY }, { ...EMPTY }])
  })

  it('Escape anulează celula, iar a doua apăsare anulează rândul în lucru', () => {
    const rows = vi.fn()
    render(<Harness initial={[{ account: 'a1', note: 'veche', debit: '10', credit: '' }]} onRows={rows} />)
    fireEvent.click(cell('Explicație', 1))

    // Type over, then change one's mind about the cell.
    key(grid(), 'n')
    type('nouă')
    key(screen.getByRole('textbox'), 'Escape')
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(cell('Explicație', 1)).toHaveTextContent('veche')

    // Commit a change, then cancel the whole row: back to the snapshot.
    key(grid(), 'x')
    type('schimbat')
    key(screen.getByRole('textbox'), 'Tab')
    expect(rows).toHaveBeenLastCalledWith([{ account: 'a1', note: 'schimbat', debit: '10', credit: '' }])
    key(grid(), 'Escape')
    expect(rows).toHaveBeenLastCalledWith([{ account: 'a1', note: 'veche', debit: '10', credit: '' }])
  })

  it('tastarea peste o celulă selectată înlocuiește conținutul, nu îl completează', () => {
    const rows = vi.fn()
    render(<Harness initial={[{ ...EMPTY, note: 'veche' }]} onRows={rows} />)
    fireEvent.click(cell('Explicație', 1))
    key(grid(), 'a')
    const input = screen.getByRole('textbox') as HTMLInputElement
    expect(input.value).toBe('a')
    type('altceva')
    key(input, 'Tab')
    expect(rows).toHaveBeenLastCalledWith([{ ...EMPTY, note: 'altceva' }])
  })

  it('F4 deschide nomenclatorul câmpului și Enter alege opțiunea evidențiată', () => {
    const rows = vi.fn()
    render(<Harness onRows={rows} />)
    fireEvent.click(cell('Cont', 1))
    key(grid(), 'F4')
    const list = screen.getByRole('listbox', { name: 'Cont' })
    expect(within(list).getAllByRole('option')).toHaveLength(3)

    type('61')
    expect(within(screen.getByRole('listbox')).getAllByRole('option')).toHaveLength(1)
    key(screen.getByRole('textbox'), 'Enter')
    expect(rows).toHaveBeenLastCalledWith([{ ...EMPTY, account: 'a2' }])
    expect(cell('Cont', 1)).toHaveTextContent('611 — Venituri')
  })

  it('Ctrl+Enter validează documentul prin ecran, după ce celula curentă e confirmată', () => {
    const validate = vi.fn()
    const rows = vi.fn()
    render(<Harness onValidate={validate} onRows={rows} />)
    fireEvent.click(cell('Debit', 1))
    key(grid(), '5')
    type('5')
    key(screen.getByRole('textbox'), 'Enter', { ctrlKey: true })
    expect(validate).toHaveBeenCalledTimes(1)
    expect(rows).toHaveBeenLastCalledWith([{ ...EMPTY, debit: '5' }])
  })

  it('săgețile navighează între celule fără a intra în editare', () => {
    render(<Harness initial={[{ ...EMPTY }, { ...EMPTY }]} />)
    fireEvent.click(cell('Cont', 1))
    key(grid(), 'ArrowRight')
    expect(cell('Explicație', 1)).toHaveAttribute('aria-selected', 'true')
    key(grid(), 'ArrowDown')
    expect(cell('Explicație', 2)).toHaveAttribute('aria-selected', 'true')
    key(grid(), 'ArrowLeft')
    key(grid(), 'ArrowUp')
    expect(cell('Cont', 1)).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('Tab avansează ca Enter, dar nu deschide linie nouă pe ultimul câmp; Shift+Tab întoarce', () => {
    const rows = vi.fn()
    render(<Harness onRows={rows} />)
    fireEvent.click(cell('Credit', 1))
    key(grid(), 'Tab')
    expect(cell('Credit', 1)).toHaveAttribute('aria-selected', 'true')
    expect(rows).not.toHaveBeenCalled()
    key(grid(), 'Tab', { shiftKey: true })
    expect(cell('Debit', 1)).toHaveAttribute('aria-selected', 'true')
  })

  it('F2 intră în editare păstrând conținutul', () => {
    render(<Harness initial={[{ ...EMPTY, note: 'păstrat' }]} />)
    fireEvent.click(cell('Explicație', 1))
    key(grid(), 'F2')
    expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('păstrat')
  })

  it('Ctrl+Delete șterge un rând gol imediat și unul cu conținut la a doua apăsare', () => {
    const rows = vi.fn()
    render(<Harness initial={[{ ...EMPTY, note: 'plin' }, { ...EMPTY }]} onRows={rows} />)
    fireEvent.click(cell('Cont', 2))
    key(grid(), 'Delete', { ctrlKey: true })
    expect(rows).toHaveBeenLastCalledWith([{ ...EMPTY, note: 'plin' }])

    fireEvent.click(cell('Cont', 1))
    key(grid(), 'Delete', { ctrlKey: true })
    expect(screen.getByRole('status')).toHaveTextContent('Apăsați din nou')
    expect(rows).toHaveBeenCalledTimes(1)
    key(grid(), 'Delete', { ctrlKey: true })
    expect(rows).toHaveBeenLastCalledWith([])
  })

  it('punctul și virgula produc aceeași sumă, iar indicatorul de echilibru o citește', () => {
    const rows = vi.fn()
    render(<Harness initial={[{ ...EMPTY }, { ...EMPTY }]} onRows={rows} />)
    fireEvent.click(cell('Debit', 1))
    key(grid(), '1')
    type('1234,5')
    key(screen.getByRole('textbox'), 'Enter')
    fireEvent.click(cell('Credit', 2))
    key(grid(), '1')
    type('1234.50')
    key(screen.getByRole('textbox'), 'Tab')

    expect(rows).toHaveBeenLastCalledWith([
      { ...EMPTY, debit: '1234.5' },
      { ...EMPTY, credit: '1234.5' },
    ])
    expect(screen.getByText('Echilibrat')).toBeInTheDocument()
  })

  it('o sumă care nu e număr rămâne în editare, cu mesaj, și nu avansează', () => {
    render(<Harness />)
    fireEvent.click(cell('Debit', 1))
    key(grid(), '1')
    type('1.2.3')
    key(screen.getByRole('textbox'), 'Enter')
    expect(screen.getByRole('alert')).toHaveTextContent('Nu este o sumă')
    expect(cell('Debit', 1)).toHaveAttribute('aria-selected', 'true')
  })
})

describe('parseAmount', () => {
  it('normalizează ambele separatoare la forma serverului', () => {
    expect(parseAmount('1,5')).toBe('1.5')
    expect(parseAmount('1.5')).toBe('1.5')
    expect(parseAmount('1234,50')).toBe('1234.5')
    expect(parseAmount('007')).toBe('7')
    expect(parseAmount('-0,25')).toBe('-0.25')
    expect(parseAmount(',5')).toBe('0.5')
    expect(parseAmount('')).toBe('')
    expect(parseAmount('1.234,56')).toBeNull()
    expect(parseAmount('abc')).toBeNull()
    expect(parseAmount('.')).toBeNull()
  })
})
