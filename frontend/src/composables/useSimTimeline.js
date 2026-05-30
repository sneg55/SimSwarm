/**
 * Pure function: maps simulation rounds to calendar dates over the user-
 * selected forecast horizon, and extracts moments to pin on the timeline.
 *
 * Returns: { start: Date|null, end: Date|null, roundDates: Date[], moments: [] }
 */
function pluralityStance(round, trajectories) {
  const counts = {}
  for (const a of trajectories) {
    const rounds = a.rounds || a.stance_per_round || []
    const entry = rounds.find(e => (e.round ?? e.round_num) === round)
    if (!entry) continue
    let stance = entry.stance
    if (!stance) {
      const s = Number(entry.sentiment)
      if (!Number.isFinite(s)) continue
      if (s > 0.05) stance = 'pro'
      else if (s < -0.05) stance = 'con'
      else continue
    }
    if (stance === 'neutral' || stance === 'unknown') continue
    counts[stance] = (counts[stance] || 0) + 1
  }
  let best = null, bestCount = 0
  for (const [s, c] of Object.entries(counts)) {
    if (c >= bestCount) { best = s; bestCount = c }
  }
  return best
}

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
  const trajectories = Array.isArray(agentTrajectories) ? agentTrajectories : []
  if (trajectories.length && roundCount >= 2) {
    let prev = pluralityStance(1, trajectories)
    for (let r = 2; r <= roundCount; r++) {
      const curr = pluralityStance(r, trajectories)
      if (prev && curr && prev !== curr) {
        const roundIndex = r - 1
        moments.push({
          id: `coalition:${r}`,
          type: 'coalition',
          roundIndex,
          date: roundDates[roundIndex],
          title: `Majority flips ${prev} → ${curr}`,
          detail: `Round ${r}: plurality shifted from ${prev} to ${curr}`,
          refId: null,
        })
      }
      if (curr) prev = curr
    }
  }
  const THRESHOLD = 0.15
  // NOTE: market_curves.json is not produced by the extractor today; this runs against synthetic input in tests.
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
  // Top-3 posts by engagement overall (not per-round) — keeps the band readable
  const postsSorted = (topPosts || [])
    .filter(p => (Number(p.engagement) || 0) >= 1)
    .sort((a, b) => (b.engagement || 0) - (a.engagement || 0))
    .slice(0, 3)
  for (const p of postsSorted) {
    const round = p.round_num
    const roundIndex = Math.max(0, Math.min(roundCount - 1, round - 1))
    moments.push({
      id: `post:${round}:${p.agent_name}`,
      type: 'post',
      roundIndex,
      date: roundDates[roundIndex],
      title: p.agent_name,
      detail: (p.content || p.text || ''),
      refId: null,
    })
  }
  return { start, end, roundDates, moments }
}

/**
 * Cluster moments whose horizontal position on a start→end axis is within
 * `threshold` (fractional, e.g. 0.02 = 2%) of the previous cluster's anchor.
 * Input is sorted by roundIndex internally (non-destructive; a copy is sorted).
 * Returns [{ position, items[] }].
 */
export function clusterMoments(moments, roundCount, threshold = 0.02) {
  if (!moments?.length || !roundCount) return []
  const sorted = [...moments].sort((a, b) => a.roundIndex - b.roundIndex)
  const denom = Math.max(1, roundCount - 1)
  const clusters = []
  for (const m of sorted) {
    const pos = m.roundIndex / denom
    const last = clusters[clusters.length - 1]
    if (last && Math.abs(pos - last.position) <= threshold) {
      last.items.push(m)
    } else {
      clusters.push({ position: pos, items: [m] })
    }
  }
  return clusters
}
