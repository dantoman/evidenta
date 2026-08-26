/**
 * Date formatting -- C18. One module, and no formatting in components.
 *
 * **This module used to format money as well, and those functions are gone.**
 * They lost their last consumer when the formatting demonstration screen was
 * replaced by the companies list, and an unused money formatter is worse than a
 * missing one: six months on, somebody reuses it assuming it was exercised. It
 * comes back with the first screen that has amounts on it -- balances -- written
 * against real values rather than a demonstration.
 *
 * What must not be lost with them is the reason they were shaped that way, so it
 * is recorded here rather than in deleted code. **Amounts arrive as decimal
 * strings and are formatted from strings, never from numbers.** The server sends
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
