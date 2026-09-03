/**
 * A page that exists to say it does not yet -- ADR-093, at the owner's word.
 *
 * ADR-076 §4.3 lists nine objects the console administers; three have no server
 * behind them. The first version drew nothing for them and explained in a footer.
 * The owner asked for the opposite: a page per object, so that what remains to be
 * built is visible where it will live, with what it will do, what is missing and
 * which decision governs it. That is a roadmap entry, not a control pretending to
 * work -- the marker in the sidebar and the eyebrow both say so.
 *
 * Everything shown is text from the resource file, lifted from the ADRs it cites.
 * Nothing is fetched: there is no server to ask.
 */

import { t } from '@/locales'
import { Badge, Card, PageHeader } from '@/shared/ui'

export type PlannedPage = 'subscriptions' | 'support' | 'incidents'

export function PlannedScreen({ page }: { page: PlannedPage }) {
  const copy = t.console.planned[page]

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        eyebrow={t.console.planned.eyebrow}
        title={copy.title}
        lead={copy.lead}
        actions={<Badge tone="caution">{t.console.plannedMarker}</Badge>}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section title={t.console.planned.will} items={copy.will} />
        <Section title={t.console.planned.missing} items={copy.missing} tone="danger" />
        <Section title={t.console.planned.decisions} items={copy.decisions} />
        <Card>
          <h2 className="m-0 type-title text-heading">{t.console.planned.trigger}</h2>
          <p className="mt-2 mb-0 type-body-md text-ink-muted">{copy.trigger}</p>
        </Card>
      </div>
    </section>
  )
}

function Section({
  title,
  items,
  tone = 'neutral',
}: {
  title: string
  items: readonly string[]
  tone?: 'neutral' | 'danger'
}) {
  return (
    <Card>
      <h2 className="m-0 type-title text-heading">{title}</h2>
      <ul className="mt-2 mb-0 flex list-disc flex-col gap-1.5 pl-5 type-body-md">
        {items.map((item) => (
          <li key={item} className={tone === 'danger' ? 'text-danger' : 'text-ink'}>
            {item}
          </li>
        ))}
      </ul>
    </Card>
  )
}
