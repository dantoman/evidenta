import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { t } from '@/locales'
import { login } from '@/shared/api/auth'
import { ApiError } from '@/shared/api/client'
import { devTotpCode } from './devCode'
import { IDENTITY_KEY } from './useIdentity'

/**
 * The login form.
 *
 * The second factor field is always present rather than appearing after a
 * password round trip. ADR-021 makes it mandatory for everyone, so a field that
 * appeared conditionally would only ever be hiding a step the user has to take
 * anyway -- and hiding it costs a request and a re-render.
 *
 * Errors are shown by **code**, never by the server's message (C10). The mapping
 * lives in the resource file, so rewording is a translation change rather than a
 * client change.
 *
 * In development the code field fills itself -- see `devCode.ts`. Nothing about
 * the request changes: the same field, carrying a real code, verified the same
 * way. In a production build the helper is a `return null` the bundler drops.
 */
export function LoginScreen() {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')

  // What the last automatic fill put in the field, so a hand-typed code can be
  // told apart from one nobody chose. Only ever non-null in development.
  const filled = useRef<string | null>(null)

  useEffect(() => {
    let abandoned = false

    void devTotpCode().then((fresh) => {
      if (abandoned || fresh === null) return
      filled.current = fresh
      // Never over an entry in progress: the fetch is local, but a fast typist
      // is faster, and overwriting what somebody is typing is worse than not
      // helping at all.
      setCode((current) => (current === '' ? fresh : current))
    })

    return () => {
      abandoned = true
    }
  }, [])

  const attempt = useMutation({
    mutationFn: async () => {
      // A filled code is good until its window closes, and a login form left
      // open outlives thirty seconds routinely. Ask again at submit, so what
      // goes out is valid now rather than valid when the page loaded.
      let sending = code
      if (filled.current !== null && sending === filled.current) {
        const fresh = await devTotpCode()
        if (fresh !== null) {
          filled.current = fresh
          sending = fresh
          setCode(fresh)
        }
      }

      return login({ email, password, totp_code: sending === '' ? undefined : sending })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: IDENTITY_KEY }),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    attempt.mutate()
  }

  const failure = attempt.error instanceof ApiError ? attempt.error : null

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-lg border border-border bg-surface p-6 shadow-sm"
      >
        <h1 className="mb-6 text-lg font-semibold">{t.auth.title}</h1>

        <label className="mb-4 block">
          <span className="mb-1 block text-sm text-ink-muted">{t.auth.email}</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded border border-border bg-surface px-3 py-2"
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-sm text-ink-muted">{t.auth.password}</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded border border-border bg-surface px-3 py-2"
          />
        </label>

        <label className="mb-6 block">
          <span className="mb-1 block text-sm text-ink-muted">{t.auth.code}</span>
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            // Six digits, and the field says so. The owner pasted the TOTP
            // *secret* into it on the first try, which is a reasonable thing to
            // do when the field is an unlabelled box and the setup instructions
            // handed them a long string.
            pattern="[0-9]{6}"
            maxLength={6}
            placeholder="123456"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            className="w-full rounded border border-border bg-surface px-3 py-2 tabular"
          />
        </label>

        {failure && (
          <p role="alert" className="mb-4 text-sm text-danger">
            {failure.display}
          </p>
        )}

        <button
          type="submit"
          disabled={attempt.isPending}
          className="w-full rounded bg-accent px-3 py-2 text-surface disabled:opacity-60"
        >
          {attempt.isPending ? t.app.loading : t.auth.submit}
        </button>
      </form>
    </main>
  )
}
