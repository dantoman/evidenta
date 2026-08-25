import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { t } from '@/locales'
import { login } from '@/shared/api/auth'
import { ApiError } from '@/shared/api/client'
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
 */
export function LoginScreen() {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')

  const attempt = useMutation({
    mutationFn: () =>
      login({ email, password, totp_code: code === '' ? undefined : code }),
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
