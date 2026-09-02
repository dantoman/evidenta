/**
 * Which workspace this browser is looking at, read off the host.
 *
 * The tenant comes from the subdomain and never from a path or a payload (C8),
 * so this is the only honest source -- and it is also the only part a person
 * recognises. The identifier the server returns is a database key; `alpha` is
 * what somebody typed.
 */
export function workspaceName(): string {
  return window.location.hostname.split('.')[0] ?? ''
}

/**
 * Whether this browser is on the platform's console, `admin.` (ADR-076).
 *
 * The same label the server reserves, read the same way. Nothing else decides
 * it: not a route, not a flag, not a response -- a host is a host, and the
 * server refuses every tenant route on this one regardless of what the client
 * believes.
 */
export function isConsoleHost(hostname: string = window.location.hostname): boolean {
  return hostname.split('.')[0] === 'admin'
}
