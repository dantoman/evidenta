/**
 * Test setup -- matchers, and the two browser APIs jsdom does not implement.
 *
 * Nothing here fakes application behaviour. A stub that answered like the server
 * would make every test below prove that the stub agrees with itself.
 */

import '@testing-library/jest-dom/vitest'

// jsdom has no `crypto.randomUUID`, and the manual note allocates its
// idempotency key with it. Deterministic here on purpose: a test that asserted a
// random key would be asserting nothing.
if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, 'crypto', {
    value: { ...globalThis.crypto, randomUUID: () => '00000000-0000-4000-8000-000000000000' },
  })
}
