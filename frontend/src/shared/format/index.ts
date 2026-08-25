/**
 * Number, money and date formatting -- C18.
 *
 * One module, and no formatting in components. C18 also says what this is and is
 * not: **a display layer**. Calculation precision and rounding live on the
 * server, where the rounding rule is versioned fiscal logic selected by the
 * effective date of the period (Spec B 7.4). Nothing here rounds a value that
 * will be stored.
 *
 * **Amounts are formatted from strings, never from numbers, and that is the
 * point of the module.** The server sends `numeric` as a decimal string
 * precisely so the value never passes through a float; parsing it into one here
 * would undo that at the last step, and the damage would appear as a few bani
 * nobody can attribute to anything.
 *
 * Measured rather than assumed: `Intl.NumberFormat.format` accepts a string and
 * formats it exactly, including values far beyond what a double can hold --
 * `'123456789012345678901234567890.12'` renders every digit.
 *
 * `ro-MD` throughout. The separators, the currency placement and the date order
 * are Moldova's, not the browser's: a report that formats itself differently on
 * a colleague's laptop is a report two people cannot compare over the phone.
 */

export const LOCALE = 'ro-MD'
export const FUNCTIONAL_CURRENCY = 'MDL'

/**
 * What `Intl.NumberFormat.format` actually accepts.
 *
 * The string overload is Intl NumberFormat V3 and is implemented everywhere this
 * application runs; TypeScript's bundled lib types still declare only
 * `number | bigint`. One cast, in one place, with the reason next to it -- rather
 * than a cast at every call site, which is how a rule stops being visible.
 */
type Decimal = number | bigint | string
interface ExactNumberFormat {
  format(value: Decimal): string
}

function exact(options: Intl.NumberFormatOptions): ExactNumberFormat {
  return new Intl.NumberFormat(LOCALE, options) as unknown as ExactNumberFormat
}

const decimal = exact({ minimumFractionDigits: 2, maximumFractionDigits: 2 })
const integer = exact({ maximumFractionDigits: 0 })

const dateOnly = new Intl.DateTimeFormat(LOCALE, {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

const dateAndTime = new Intl.DateTimeFormat(LOCALE, {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

/** An amount with two decimals. Pass the server's string unchanged. */
export function amount(value: Decimal): string {
  return decimal.format(value)
}

/**
 * An amount with its currency.
 *
 * The currency is a parameter with a default rather than a constant, because a
 * journal line carries an amount in the transaction currency as well as in the
 * functional one (Spec B 7.1), and showing the first as MDL would be wrong in a
 * way that looks right.
 */
export function money(value: Decimal, currency: string = FUNCTIONAL_CURRENCY): string {
  return exact({
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export function count(value: Decimal): string {
  return integer.format(value)
}

/**
 * A date the server sent as `YYYY-MM-DD`.
 *
 * Built from parts rather than `new Date(isoDate)`, deliberately: the string
 * form is parsed as UTC midnight, so a viewer east of Greenwich sees the day
 * before. An accounting date that shifts by one day at the year boundary is a
 * posting in the wrong period as far as the reader is concerned.
 */
export function date(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  if (!year || !month || !day) return isoDate
  return dateOnly.format(new Date(year, month - 1, day))
}

/** A timestamp, rendered in the viewer's timezone. */
export function dateTime(isoTimestamp: string): string {
  return dateAndTime.format(new Date(isoTimestamp))
}
