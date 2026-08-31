import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { t } from '@/locales'
import { login } from '@/shared/api/auth'
import { ApiError } from '@/shared/api/client'
import { Button, Field, Input } from '@/shared/ui'
import { devTotpCode } from './devCode'
import { IDENTITY_KEY } from './useIdentity'

/**
 * The login form, on the crest panel (ADR-074).
 *
 * The left half is the only place in the application where the brand is allowed
 * to be large. It carries the emblem and one sentence about what double entry is
 * for -- Pacioli, the legal adage, Goethe -- because this is the one screen a
 * person looks at while waiting rather than while working.
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
 *
 * What the design shows and this does not: the running clock under the quote. A
 * second date format would have to live somewhere, and `C18` says formatting has
 * exactly one home.
 */

export function LoginScreen() {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [quote, setQuote] = useState(0)

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

  useEffect(() => {
    const turning = setInterval(() => setQuote((n) => (n + 1) % t.auth.quotes.length), 9000)
    return () => clearInterval(turning)
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
  const said = t.auth.quotes[quote]!

  return (
    <main className="flex min-h-screen">
      <aside className="relative hidden shrink-0 basis-[46%] flex-col justify-between gap-8 overflow-hidden bg-[image:var(--gradient-crest)] p-11 lg:flex">
        <img
          src="/brand/emblem-crest-column-owl-navy.png"
          alt=""
          className="pointer-events-none absolute -right-38 -bottom-4 h-110 opacity-20"
        />
        <span className="relative flex min-w-0 items-center gap-6">
          <img
            src="/brand/emblem-crest-column-owl-navy.png"
            alt=""
            className="w-[46%] max-w-62 min-w-28 shrink"
          />
          <span className="flex min-w-0 flex-col gap-1.5">
            <span className="font-display text-[clamp(26px,4.2vw,46px)]/none font-bold uppercase tracking-[.06em] text-on-navy">
              {t.app.name}
            </span>
            <span className="whitespace-nowrap type-eyebrow text-[clamp(10px,1.35vw,15px)]/[1.1] text-gold-400">
              {t.nav.tagline}
            </span>
          </span>
        </span>

        <div className="relative">
          <span className="mb-5.5 block h-0.5 w-16 bg-[image:var(--gradient-gold-foil)]" />
          {/* Fixed height, not `min-h`: the four quotes differ in length, and a
              panel that resizes every nine seconds is a panel that moves while
              somebody is typing a password next to it. */}
          {/* Româna e textul, originalul e citarea. Invers -- cum era -- ecranul
              de intrare cerea cititorului să treacă prin latină ca să afle ce
              scrie, iar traducerea, pusă mic dedesubt, se citea ca o notă de
              subsol la propriul ei înțeles. Limba interfeței e româna (C15);
              originalul rămâne fiindcă el e citatul, cu autorul lui. */}
          <blockquote className="m-0 flex min-h-46 flex-col gap-3.5">
            <p className="m-0 font-display text-[29px]/[1.24] font-bold text-pretty text-on-navy">
              {said.translated}
            </p>
            {/* Cursivul e al originalului, nu al traducerii: el e citatul în
                limba lui, iar româna e textul pe care îl citeşte cineva. */}
            <span className="type-body-lg italic text-pretty text-on-navy-muted">
              {said.original}
            </span>
            <span className="type-eyebrow text-gold-400">{said.source}</span>
          </blockquote>
          <div className="mt-5.5 flex gap-2">
            {t.auth.quotes.map((one, index) => (
              <button
                key={one.source + index}
                type="button"
                aria-label={one.source}
                onClick={() => setQuote(index)}
                className={`h-1.5 w-6 rounded-full ${index === quote ? 'bg-gold' : 'bg-[rgba(198,161,91,.3)]'}`}
              />
            ))}
          </div>
        </div>

        <span className="relative type-eyebrow text-gold-400">{t.auth.jurisdiction}</span>
      </aside>

      <div className="flex flex-1 items-center justify-center p-12">
        <form onSubmit={submit} className="w-full max-w-100">
          <div className="mb-2 type-eyebrow text-gold-strong">
            {t.nav.workspace} · {window.location.hostname.split('.')[0]}
          </div>
          <h1 className="type-display-2 m-0 text-heading">{t.auth.title}</h1>
          <p className="mt-2 mb-7 type-body-md text-ink-muted">{t.auth.lead}</p>

          <div className="flex flex-col gap-4.5">
            <Field label={t.auth.email} required>
              <Input
                type="email"
                icon="mail"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>

            <Field label={t.auth.password} required>
              <Input
                type="password"
                icon="lock"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>

            <Field label={t.auth.code} hint={t.auth.codeHint}>
              <Input
                icon="shield"
                numeric
                inputMode="numeric"
                autoComplete="one-time-code"
                // Six digits, and the field says so. The owner pasted the TOTP
                // *secret* into it on the first try, which is a reasonable thing
                // to do when the field is an unlabelled box and the setup
                // instructions handed them a long string.
                pattern="[0-9]{6}"
                maxLength={6}
                placeholder="123456"
                value={code}
                onChange={(event) => setCode(event.target.value)}
              />
            </Field>

            {failure && (
              <p role="alert" className="type-body-sm text-danger-strong">
                {failure.display}
              </p>
            )}

            <Button variant="primary" type="submit" size="lg" block disabled={attempt.isPending}>
              {attempt.isPending ? t.app.loading : t.auth.submit}
            </Button>
          </div>

          <span className="mt-7 mb-4 block h-0.5 w-full bg-[image:var(--gradient-gold-foil)] opacity-60" />
          <p className="type-caption text-ink-faint">{t.errors.hintSubdomain}</p>
        </form>
      </div>
    </main>
  )
}
