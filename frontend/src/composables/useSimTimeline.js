/**
 * Pure function: maps simulation rounds to calendar dates over the user-
 * selected forecast horizon, and extracts moments to pin on the timeline.
 *
 * Returns: { start: Date|null, end: Date|null, roundDates: Date[], moments: [] }
 */
export function useSimTimeline({
  startedAt,
  forecastDays,
  roundCount,
  structured,
  marketCurves,
  topPosts,
  agentTrajectories,
}) {
  const empty = { start: null, end: null, roundDates: [], moments: [] }
  if (!startedAt || !forecastDays || !roundCount || roundCount < 1) return empty

  const start = new Date(startedAt)
  if (Number.isNaN(start.getTime())) return empty
  const horizonMs = forecastDays * 86400 * 1000
  const end = new Date(start.getTime() + horizonMs)

  const roundDates = []
  if (roundCount === 1) {
    roundDates.push(start)
  } else {
    const step = horizonMs / (roundCount - 1)
    for (let i = 0; i < roundCount; i++) {
      roundDates.push(new Date(start.getTime() + i * step))
    }
  }

  const moments = []
  return { start, end, roundDates, moments }
}
