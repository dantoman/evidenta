/**
 * The header's search -- and it searches exactly what it says.
 *
 * The design shows *„Caută document, cont sau contragent"*. Documents are not in
 * it, because nothing on the server can find one: the register filters by period,
 * not by number. The placeholder names the two that work, so the box is never a
 * promise the server refuses.
 *
 * **Accounts are filtered here, partners on the server**, and the asymmetry is
 * the honest one: a company's chart is a few hundred rows the application already
 * holds for the chart screen, so filtering it in the browser costs one pass over
 * an array. The partner directory is not bounded that way -- `q` goes to the
 * server, which answers at most two hundred rows.
 *
 * A partner has no screen of its own yet, so choosing one lands on the directory
 * with the search filled in. That is a real destination rather than a dead link,
 * and it disappears the day a partner gets a page.
 */

import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'

import { t } from '@/locales'
import { listAccounts } from '@/shared/api/coa'
import { listPartners } from '@/shared/api/partners'
import { Icon, Input } from '@/shared/ui'

/** Enough to mean something. One letter matches half the chart. */
const SHORTEST = 2
const PER_GROUP = 5

interface Hit {
  key: string
  label: string
  detail: string
  go: string
}

export function HeaderSearch({ companyId }: { companyId: string | undefined }) {
  const navigate = useNavigate()
  const [typed, setTyped] = useState('')
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(0)
  const box = useRef<HTMLDivElement>(null)

  const asked = typed.trim()
  const enough = asked.length >= SHORTEST

  // The same key the chart screen uses, so opening the chart after a search
  // costs nothing -- and searching after opening it costs nothing either.
  const accounts = useQuery({
    queryKey: ['accounts', companyId, ''],
    queryFn: () => listAccounts(companyId ?? ''),
    enabled: enough && companyId !== undefined,
  })
  const partners = useQuery({
    queryKey: ['partners-directory', asked, false],
    queryFn: () => listPartners({ q: asked, includeInactive: false }),
    enabled: enough,
  })

  const needle = asked.toLocaleLowerCase('ro-MD')
  const accountHits: Hit[] = (accounts.data ?? [])
    .filter(
      (account) =>
        account.account_code.startsWith(asked) ||
        account.name_ro.toLocaleLowerCase('ro-MD').includes(needle),
    )
    .slice(0, PER_GROUP)
    .map((account) => ({
      key: `cont:${account.id}`,
      label: account.name_ro,
      detail: account.account_code,
      go: `/companii/${companyId}/conturi/${account.id}`,
    }))

  const partnerHits: Hit[] = (partners.data ?? []).slice(0, PER_GROUP).map((partner) => ({
    key: `partener:${partner.id}`,
    label: partner.legal_name,
    detail: partner.idno ?? partner.idnp ?? '',
    go: `/parteneri?q=${encodeURIComponent(partner.legal_name)}`,
  }))

  const hits = [...accountHits, ...partnerHits]

  // A click outside closes it. Not blur: blur fires before the click on a result
  // lands, and the result would be gone by the time the mouse button came up.
  useEffect(() => {
    if (!open) return
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [open])

  function choose(hit: Hit) {
    setOpen(false)
    setTyped('')
    void navigate(hit.go)
  }

  function onKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setOpen(false)
      setTyped('')
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (hits.length === 0) return
      const step = event.key === 'ArrowDown' ? 1 : -1
      setCursor((at) => (at + step + hits.length) % hits.length)
      return
    }
    if (event.key === 'Enter' && hits[cursor]) {
      event.preventDefault()
      choose(hits[cursor])
    }
  }

  return (
    // Se strânge înaintea comutatorului şi dispare cu totul pe ecrane înguste:
    // căutarea e o comoditate, iar „în ce companie sunt" nu e. Prima versiune le
    // punea la egalitate, iar la fereastra îngustată de DevTools numele
    // companiei se stingea complet.
    <div ref={box} className="relative hidden min-w-0 max-w-96 flex-1 lg:block">
      <Input
        icon="search"
        type="search"
        value={typed}
        placeholder={t.nav.search}
        aria-label={t.nav.search}
        onChange={(event) => {
          setTyped(event.target.value)
          setCursor(0)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
      />

      {open && enough && (
        <div className="absolute top-full right-0 left-0 z-20 mt-1 overflow-hidden rounded-card border border-border bg-surface shadow-raised">
          {hits.length === 0 ? (
            <p className="m-0 px-3 py-2 type-body-sm text-ink-muted">{t.nav.searchEmpty}</p>
          ) : (
            <ul className="m-0 flex list-none flex-col p-0">
              {accountHits.length > 0 && <Group label={t.nav.searchAccounts} />}
              {hits.map((hit, index) => (
                <li key={hit.key}>
                  {index === accountHits.length && partnerHits.length > 0 && (
                    <Group label={t.nav.searchPartners} />
                  )}
                  <button
                    type="button"
                    onClick={() => choose(hit)}
                    onMouseEnter={() => setCursor(index)}
                    className={`flex w-full items-center gap-3 px-3 py-2 text-left ${
                      index === cursor ? 'bg-navy-050' : ''
                    }`}
                  >
                    <Icon
                      name={hit.key.startsWith('cont:') ? 'list-tree' : 'users'}
                      size={16}
                      className="shrink-0 text-ink-faint"
                    />
                    <span className="min-w-0 flex-1 truncate type-body-sm text-ink">
                      {hit.label}
                    </span>
                    <span className="shrink-0 type-figure-sm text-ink-faint">{hit.detail}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

function Group({ label }: { label: string }) {
  return (
    <div className="border-b border-border bg-surface-muted px-3 py-1 type-eyebrow text-ink-muted">
      {label}
    </div>
  )
}
