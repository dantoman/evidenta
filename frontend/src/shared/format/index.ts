/**
 * Amount and date formatting -- C18. One module, and no formatting in components.
 *
 * `amount` was deleted when the formatting demonstration screen went, because an
 * unused money formatter is worse than a missing one -- somebody reuses it six
 * months later assuming it was exercised. It is back because the trial balance
 * is here: a screen with real amounts on it, which is what it was waiting for.
 * `money`, `count` and `dateTime` are still gone, and come back the same way.
 *
 * **Amounts arrive as decimal strings and are formatted from strings, never from
 * numbers.** The server sends
 * `numeric` as a string precisely so the value never passes through a float, and
 * parsing it into one at the last step would undo that -- the damage appearing as
 * a few bani nobody can attribute to anything. Measured, not assumed:
 * `Intl.NumberFormat.format` accepts a string and formats it exactly, including
 * `'123456789012345678901234567890.12'`, every digit of which rendered. The
 * string overload is Intl NumberFormat V3; TypeScript's bundled lib types still
 * declare only `number | bigint`, so the cast belongs in one place, here, with
 * this reason next to it.
 *
 * C18 also says what this is and is not: **a display layer**. Calculation
 * precision and rounding live on the server, where the rounding rule is
 * versioned fiscal logic selected by the effective date of the period (Spec B
 * 7.4). Nothing here rounds a value that will be stored.
 *
 * `ro-MD` throughout. The separators and the date order are Moldova's, not the
 * browser's: a report that formats itself differently on a colleague's laptop is
 * a report two people cannot compare over the phone.
 */

const LOCALE = 'ro-MD'

/**
 * What `Intl.NumberFormat.format` actually accepts. TypeScript's bundled lib
 * types still declare only `number | bigint`, so the cast lives here, once,
 * rather than at every call site -- which is how a rule stops being visible.
 */
type Decimal = number | bigint | string
interface ExactNumberFormat {
  format(value: Decimal): string
}

const decimal = new Intl.NumberFormat(LOCALE, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}) as unknown as ExactNumberFormat

/** An amount with two decimals. Pass the server's string unchanged. */
export function amount(value: Decimal): string {
  return decimal.format(value)
}

const dateOnly = new Intl.DateTimeFormat(LOCALE, {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

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

const monthAndYear = new Intl.DateTimeFormat(LOCALE, { month: 'long', year: 'numeric' })
const shortMonth = new Intl.DateTimeFormat(LOCALE, { month: 'short' })

/**
 * The month a server date falls in -- `iunie 2026`.
 *
 * Built from parts, for the reason `date` is: the string form parses as UTC
 * midnight, and a viewer east of Greenwich would read the first of the month as
 * the last of the previous one. On a panel whose whole claim is *which month*
 * this is, that is the one error that must not be possible.
 */
export function month(isoDate: string): string {
  const parts = monthOf(isoDate)
  return parts ? monthAndYear.format(parts) : isoDate
}

/** The same month, short -- for a chart's axis, where the year is in the title. */
export function monthShort(isoDate: string): string {
  const parts = monthOf(isoDate)
  return parts ? shortMonth.format(parts) : isoDate
}

function monthOf(isoDate: string): Date | null {
  const [year, monthNumber, day] = isoDate.split('-').map(Number)
  if (!year || !monthNumber || !day) return null
  return new Date(year, monthNumber - 1, day)
}

/**
 * Today, as the server spells a date.
 *
 * Local parts, never `toISOString()`: that converts to UTC first, so anywhere
 * east of Greenwich the first hours of a day report the previous one -- and on
 * the first of a month that is a panel reporting the wrong month. Here rather
 * than in a screen, because the second screen that needed it would otherwise
 * have written it a second way.
 */
export function today(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
