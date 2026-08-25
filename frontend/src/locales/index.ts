import { ro } from './ro'

/**
 * The active string table.
 *
 * One language today. The indirection exists so that adding a second is a change
 * here and a new file, rather than a change in every component -- which is the
 * whole point of C32.
 */
export const t = ro

export { ro }
