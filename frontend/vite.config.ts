import { createHmac } from 'node:crypto'
import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * The second factor, typed for you -- development server only.
 *
 * This is not an MFA bypass and cannot become one. ADR-021 makes the second
 * factor mandatory for everyone and `authenticate()` has no branch that returns
 * a session without one, so what this endpoint hands the login form is an
 * ordinary TOTP code that the backend verifies exactly as it verifies a code
 * read off a phone. What disappears is the typing, and with it the failure the
 * owner actually hit: a code copied out of a terminal expires during the walk to
 * the browser, and the form then reports it as wrong.
 *
 * `apply: 'serve'` keeps it out of every build, and the plugin is only
 * registered when `DEV_TOTP_SECRET` is set -- so a checkout without that
 * variable has no such route at all.
 */
function devTotpEndpoint(secret: string): Plugin {
  const STEP_SECONDS = 30

  return {
    name: 'evidenta-dev-totp',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/__dev/totp', (_request, response) => {
        const now = Math.floor(Date.now() / 1000)
        response.setHeader('Content-Type', 'application/json')
        // The answer is stale within the half minute. A cached one is the bug
        // this endpoint exists to remove.
        response.setHeader('Cache-Control', 'no-store')
        response.end(
          JSON.stringify({
            code: totp(secret, now, STEP_SECONDS),
            valid_for: STEP_SECONDS - (now % STEP_SECONDS),
          }),
        )
      })
    },
  }
}

/** RFC 4648 base32, the encoding every authenticator app takes a secret in. */
function base32Decode(input: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  const bytes: number[] = []
  let buffer = 0
  let bits = 0

  // Padding and grouping spaces are both things a pasted secret arrives with.
  for (const character of input.replace(/[\s=]/g, '').toUpperCase()) {
    const index = alphabet.indexOf(character)
    if (index < 0) throw new Error(`DEV_TOTP_SECRET is not base32: ${character}`)
    buffer = (buffer << 5) | index
    bits += 5
    if (bits >= 8) {
      bits -= 8
      bytes.push((buffer >> bits) & 0xff)
    }
  }

  return Buffer.from(bytes)
}

/** RFC 6238, six digits, SHA-1 -- what `pyotp.TOTP(...).now()` computes. */
function totp(secret: string, seconds: number, step: number): string {
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(seconds / step)))

  const digest = createHmac('sha1', base32Decode(secret)).update(counter).digest()
  const offset = digest[digest.length - 1]! & 0x0f
  const truncated = digest.readUInt32BE(offset) & 0x7fffffff

  return String(truncated % 1_000_000).padStart(6, '0')
}

export default defineConfig(({ mode }) => {
  // The backend port is configurable in the repo's `.env` (`BACKEND_PORT`), so
  // the proxy target has to follow it -- otherwise the two drift the first time
  // somebody runs the backend anywhere but 8000, and the failure looks like a
  // broken frontend rather than a wrong port.
  //
  // **The root, not `process.cwd()`.** The first version of this line read the
  // frontend directory, where no `.env` exists, so `BACKEND_PORT=8001` in the
  // repo `.env` silently did nothing and every request went to 8000. Found by
  // the owner, whose port 8000 is another project entirely -- so the frontend
  // proxied to somebody else's Django and reported "the server is not
  // responding". Same class as the compose file's unread `DATABASE_URL`:
  // configuration that looks right and has never run.
  const repoRoot = fileURLToPath(new URL('..', import.meta.url))
  const env = loadEnv(mode, repoRoot, '')
  const apiTarget = env.VITE_API_TARGET ?? `http://127.0.0.1:${env.BACKEND_PORT || '8000'}`

  return {
    plugins: [
      react(),
      tailwindcss(),
      // Absent unless the secret is configured -- see `.env.example`.
      ...(env.DEV_TOTP_SECRET ? [devTotpEndpoint(env.DEV_TOTP_SECRET)] : []),
    ],
    resolve: {
      // Declared in both places on purpose: tsconfig teaches the type checker and
      // the editor, this teaches the bundler. Only one of the two is checked by
      // `tsc`, so a missing alias here fails at build rather than at typecheck.
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    // Vitest reads this same config, so `@/` and the React plugin are defined
    // once. `jsdom` because every test here mounts a component; a node
    // environment would fail on the first `document`.
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
    server: {
      // The tenant comes from the subdomain and never from a path or a payload
      // (C8), so development runs on `*.evidenta.localhost` -- ADR-025. Browsers
      // resolve any `*.localhost` to loopback with no hosts entry, so a new
      // development tenant costs nothing.
      host: 'evidenta.localhost',
      port: 5173,
      // Any subdomain of evidenta.localhost, which is the point: `alpha.` and
      // `beta.` must both reach this server.
      allowedHosts: ['.evidenta.localhost'],
      proxy: {
        // Same-origin API calls, so the session cookie -- host-only, no Domain
        // attribute -- is sent. A separate API origin would need CORS and would
        // put the cookie on a domain wider than one tenant, which is exactly the
        // boundary the host-only cookie exists to keep.
        '/api': {
          target: apiTarget,
          changeOrigin: false,
        },
        // Operational probes, proxied too, so `curl` against the dev server
        // reaches the same backend the application does.
        '/healthz': { target: apiTarget, changeOrigin: false },
        '/readyz': { target: apiTarget, changeOrigin: false },
      },
    },
  }
})
