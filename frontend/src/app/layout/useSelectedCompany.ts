/**
 * Which company the application is working in -- always exactly one, whenever the
 * workspace holds any.
 *
 * **Why this is not just the URL.** A company-scoped screen carries the company in
 * its path (C8 keeps the tenant in the host, the company in the route), but the
 * workspace-level screens -- the company list, the partners, the workspace itself
 * -- carry none.
 *
 * The precedence, and each step's reason:
 *
 * 1. **The path**, when it names one. The address is the strongest statement of
 *    intent there is, and a person who typed or bookmarked it means it.
 * 2. **What was last opened**, remembered per workspace in this browser. Somebody
 *    who works in the same firm every day should not choose it every morning.
 * 3. **The only company**, when there is exactly one. That is not a choice, so
 *    there is nothing to ask.
 * 4. **None** -- and this is a legitimate state, not a gap (ADR-085). An
 *    entrepreneur with four firms opens the application without being in any of
 *    them; picking one for them would be guessing which books they came for.
 *
 * The remembered value is **validated against the list** before it is used: a
 * company that was deleted, or whose access was withdrawn, must not keep being
 * selected. It is a browser convenience, never a right -- what a caller may see is
 * decided by the policy on the table, and this only picks among rows that already
 * came back.
 */

import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { useMatch } from 'react-router'

import { listCompanies, type Company } from '@/shared/api/companies'
import { sectionOf } from './sections'

/** Per workspace, because one browser can hold sessions on several subdomains. */
function storageKey(): string {
  return `evidenta:companie:${window.location.hostname}`
}

function remembered(): string | null {
  try {
    return window.localStorage.getItem(storageKey())
  } catch {
    // A browser with site data blocked is a browser that still has to work.
    return null
  }
}

function remember(companyId: string): void {
  try {
    window.localStorage.setItem(storageKey(), companyId)
  } catch {
    // Nothing to do and nothing to report: the selection still holds for this
    // navigation, it just will not survive a reload.
  }
}

export interface Selection {
  companies: Company[]
  /** Still asking. Distinct from "no companies", which is an answer. */
  loading: boolean
  /** The company in context, or `undefined` while the list is loading or empty. */
  selected: Company | undefined
  /** The section of the current path, so a switch can keep it. */
  section: string
  /** Whether the address itself names the company (as opposed to it being ambient). */
  fromPath: boolean
  select: (companyId: string) => void
}

export function useSelectedCompany(): Selection {
  const match = useMatch('/companii/:companyId/*')
  const inPath = match?.params.companyId
  const companies = useQuery({ queryKey: ['companies'], queryFn: listCompanies })

  // **State, not only storage.** The first version wrote the choice to
  // `localStorage` and read it back during render -- which is not a render
  // input, so choosing a company on a screen that has none in its address
  // changed nothing on screen until the next navigation. The owner reported it
  // as "the company does not change", and that is exactly what it did.
  const [chosen, setChosen] = useState<string | null>(() => remembered())

  const rows = companies.data ?? []
  const byId = (id: string | null | undefined) => rows.find((row) => row.id === id)

  const selected = byId(inPath) ?? byId(chosen) ?? (rows.length === 1 ? rows[0] : undefined)

  // Persisted as an effect, not during render: writing storage inside a pure
  // function is a side effect, and React may render twice.
  useEffect(() => {
    if (selected) remember(selected.id)
  }, [selected])

  const select = useCallback((companyId: string) => {
    setChosen(companyId)
    remember(companyId)
  }, [])

  return {
    companies: rows,
    loading: companies.isPending,
    selected,
    // Checked against the closed list, not taken as found: `conturi/<id>/fisa`
    // would otherwise hand a switch `conturi`, which no route matches.
    section: sectionOf(match?.params['*'] ?? ''),
    fromPath: inPath !== undefined,
    select,
  }
}
