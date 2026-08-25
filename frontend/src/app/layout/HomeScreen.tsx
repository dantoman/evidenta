import { amount, date, money } from '@/shared/format'

/**
 * A placeholder screen that exists to prove one thing: formatting is Moldova's.
 *
 * The values are literals rather than data, because there is no business
 * endpoint yet and inventing one would settle conventions F0.10.1 already fixed.
 * What they demonstrate is real: amounts come through as **strings**, so the
 * thirty-digit one below renders every digit -- a float would have lost most of
 * them, silently.
 */
export function HomeScreen() {
  return (
    <section className="rounded-lg border border-border bg-surface p-4">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        <dt className="text-ink-muted">Sumă</dt>
        <dd className="tabular text-right">{amount('1234567.895')}</dd>

        <dt className="text-ink-muted">Sumă în valută</dt>
        <dd className="tabular text-right">{money('1234.5', 'EUR')}</dd>

        <dt className="text-ink-muted">Sumă în monedă națională</dt>
        <dd className="tabular text-right">{money('24072.75')}</dd>

        <dt className="text-ink-muted">Precizie păstrată</dt>
        <dd className="tabular text-right">
          {amount('123456789012345678901234567890.12')}
        </dd>

        <dt className="text-ink-muted">Dată</dt>
        <dd className="text-right">{date('2026-03-07')}</dd>
      </dl>
    </section>
  )
}
