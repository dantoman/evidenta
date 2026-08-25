import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  // The backend port is already configurable in `.env` (`BACKEND_PORT`), so the
  // proxy target has to be too -- otherwise the two drift the first time someone
  // runs the backend anywhere but 8000, and the failure looks like a broken
  // frontend rather than a wrong port.
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET ?? `http://127.0.0.1:${env.BACKEND_PORT ?? '8000'}`

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      // Declared in both places on purpose: tsconfig teaches the type checker and
      // the editor, this teaches the bundler. Only one of the two is checked by
      // `tsc`, so a missing alias here fails at build rather than at typecheck.
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
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
