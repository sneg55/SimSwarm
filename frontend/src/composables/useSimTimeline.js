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
  const findings = Array.isArray(structured?.findings) ? structured.findings : []
  const phases = Array.isArray(structured?.phase_boundaries) ? structured.phase_boundaries : []
  const midRound = Math.max(1, Math.ceil(roundCount / 2))
  findings.forEach((f, idx) => {
    const phase = phases.find(p => p.phase === f.phase)
    const round = phase ? phase.rounds[1] : midRound
    const roundIndex = Math.max(0, Math.min(roundCount - 1, round - 1))
    moments.push({
      id: `finding:${idx}`,
      type: 'finding',
      roundIndex,
      date: roundDates[roundIndex],
      title: f.title || f.headline || `Finding ${idx + 1}`,
      detail: f.summary || f.description || '',
      refId: `story-finding-${idx}`,
    })
  })
  const postsByRound = new Map()
  for (const p of topPosts || []) {
    const eng = Number(p.engagement) || 0
    if (eng < 1) continue
    const prev = postsByRound.get(p.round_num)
    if (!prev || eng > prev.engagement) postsByRound.set(p.round_num, p)
  }
  for (const [round, p] of postsByRound) {
    const roundIndex = Math.max(0, Math.min(roundCount - 1, round - 1))
    moments.push({
      id: `post:${round}:${p.agent_name}`,
      type: 'post',
      roundIndex,
      date: roundDates[roundIndex],
      title: `${p.agent_name}`,
      detail: (p.text || '').slice(0, 120),
      refId: null,
    })
  }
  return { start, end, roundDates, moments }
}
