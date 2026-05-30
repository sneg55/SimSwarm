/**
 * Pure constants and utility functions for SimulationStatus.
 * No Vue reactivity — safe to import from both composable and tests.
 */

export const STAGE_NAMES = ['Seeding', 'Researching', 'Simulating', 'Analyzing', 'Generating report']
export const STAGE_STEP_IDS = ['seed', 'research', 'simulate', 'analyze', 'report']

/** Estimated seconds per pipeline stage, by tier. */
export const TIER_ESTIMATES = {
  small:  [30,  60,   300,  120,  60],   // ~10 min total
  medium: [30, 120,   900,  300, 120],   // ~25 min total
  large:  [60, 300,  3600,  900, 300],   // ~1.5 hr total
}

/** Format a duration in seconds to a human-readable string. */
export function formatSeconds(s) {
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

/** Format an ISO date string to a readable locale string. */
export function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
