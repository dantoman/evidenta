/**
 * The current second-factor code, from the development server.
 *
 * Not a bypass: MFA is mandatory for everyone (ADR-021) and the backend verifies
 * what this returns like any other code. It removes the typing, and with it the
 * race that made the code look broken -- a six digit code lives thirty seconds,
 * and copying it out of a terminal spends a good part of that window.
 *
 * `import.meta.env.DEV` is replaced by the literal `false` in a production
 * build, so the body below is dead code the bundler drops. The route it calls
 * exists only in the dev server, and only when `DEV_TOTP_SECRET` is set.
 */
export async function devTotpCode(): Promise<string | null> {
  if (!import.meta.env.DEV) return null

  try {
    const response = await fetch('/__dev/totp', { cache: 'no-store' })
    if (!response.ok) return null

    const body: unknown = await response.json()
    const code = (body as { code?: unknown }).code
    return typeof code === 'string' ? code : null
  } catch {
    // A convenience that fails is not a failure. The field stays empty and the
    // form works the way it does for everyone else.
    return null
  }
}
