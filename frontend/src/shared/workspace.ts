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
