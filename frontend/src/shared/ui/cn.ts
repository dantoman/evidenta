/**
 * Joining class names, and nothing else.
 *
 * Not `clsx`, not `tailwind-merge`: eleven lines against two dependencies, and
 * the second one exists to resolve conflicting utilities -- which the primitives
 * here avoid by construction. A base that never sets a width cannot conflict with
 * a caller that sets one, and that discipline is cheaper to keep than a resolver
 * is to carry.
 */
export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}
