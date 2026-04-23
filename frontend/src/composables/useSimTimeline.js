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
  const THRESHOLD = 0.15
  for (const market of marketCurves || []) {
    const pts = Array.isArray(market?.points) ? market.points : []
    if (pts.length < 2) continue
    for (let i = 1; i < pts.length; i++) {
      const delta = pts[i].price_yes - pts[i - 1].price_yes
      if (Math.abs(delta) >= THRESHOLD - 1e-9) {
        const round = pts[i].round_num
        const roundIndex = Math.max(0, Math.min(roundCount - 1, round - 1))
        moments.push({
          id: `market:${market.market_id}:${round}`,
          type: 'market',
          roundIndex,
          date: roundDates[roundIndex],
          title: market.question || market.market_id,
          detail: `${delta >= 0 ? '+' : ''}${Math.round(delta * 100)}pp YES`,
          refId: market.market_id,
        })
      }
    }
  }
  return { start, end, roundDates, moments }
}
