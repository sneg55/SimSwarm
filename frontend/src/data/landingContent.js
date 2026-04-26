// Static content for the marketing Landing page.
// Kept separate so Landing.vue stays under the file-size budget.

export const INSIGHTS = [
  { label: 'Key Finding', color: '#FF6B6B', text: 'Public sentiment shifts negative within 48 hours of announcement, driven by regulatory agent cluster.' },
  { label: 'Emerging Coalition', color: '#6EE7B7', text: 'Financial analysts and media agents converge on a "cautiously optimistic" narrative by round 3.' },
  { label: 'Confidence', color: '#A78BFA', text: 'Overall: 94.2% · Sentiment: 87.6% · Coalition stability: 91.0%', mono: true },
]

export const PROOFS = [
  { quote: 'We simulated public reaction to our pricing change before announcing. The swarm predicted the exact backlash points our focus groups missed.', author: 'Head of Strategy', role: 'Fortune 500 CPG Company' },
  { quote: 'Replaced three weeks of consultant work with a 5-minute simulation. The coalition mapping alone saved our policy team dozens of hours.', author: 'Policy Director', role: 'Government Affairs Think Tank' },
  { quote: 'The guided story format means I can share simulation results directly with the C-suite. No translation needed — they just scroll.', author: 'VP of Communications', role: 'Global PR Agency' },
]

// Display metadata for credit packs — keyed by pack slug.
// API supplies name/credits/price; this overlay supplies visual styling + bullets.
export const PACK_DISPLAY = {
  starter: { accent: '#22D3EE', featured: false,
    features: ['3-4 small simulations', 'Up to 500 agents per run', 'Full guided story results', 'PDF & JSON export'] },
  pro: { accent: '#A78BFA', featured: true,
    features: ['15-20 medium simulations', 'Up to 2,000 agents per run', 'Priority GPU allocation', 'Full export suite'] },
  heavy: { accent: '#FBBF24', featured: false,
    features: ['Large-scale simulations', 'Up to 10,000 agents per run', 'Dedicated GPU instances', 'Priority support'] },
}

export const FALLBACK_PACK_DISPLAY = { accent: '#22D3EE', featured: false, features: [] }

export const SWARM_COLORS = [
  { bg: '#22D3EE', glow: 'rgba(34,211,238,0.3)' },
  { bg: '#6EE7B7', glow: 'rgba(110,231,183,0.3)' },
  { bg: '#FF6B6B', glow: 'rgba(255,107,107,0.3)' },
  { bg: '#A78BFA', glow: 'rgba(167,139,250,0.3)' },
  { bg: '#FBBF24', glow: 'rgba(251,191,36,0.3)' },
]

export const AGENT_SEEDS = Array.from({ length: 24 }, (_, i) => ({
  size: 6 + ((i * 7 + 3) % 10),
  colorIdx: i % SWARM_COLORS.length,
  left: 10 + ((i * 13 + 5) % 80),
  top: 10 + ((i * 17 + 7) % 80),
  dur: 5 + ((i * 3) % 6),
  delay: -((i * 2) % 5),
  x1: ((i * 11 + 3) % 60) - 30, y1: ((i * 7 + 5) % 60) - 30,
  x2: ((i * 13 + 7) % 60) - 30, y2: ((i * 9 + 11) % 60) - 30,
  x3: ((i * 5 + 13) % 60) - 30, y3: ((i * 11 + 3) % 60) - 30,
  x4: ((i * 7 + 17) % 60) - 30, y4: ((i * 13 + 5) % 60) - 30,
  opacity: 0.5 + ((i * 3) % 5) / 10,
}))

export function buildPricingTiers(packs) {
  return packs.map(p => ({
    name: p.name,
    credits: p.credits,
    price: '$' + (p.price_cents / 100).toFixed(0),
    ...(PACK_DISPLAY[p.slug] || FALLBACK_PACK_DISPLAY),
  }))
}

export function agentStyle(i) {
  const s = AGENT_SEEDS[i - 1]
  const c = SWARM_COLORS[s.colorIdx]
  return {
    width: s.size + 'px', height: s.size + 'px',
    background: c.bg,
    boxShadow: `0 0 ${s.size}px ${c.glow}`,
    left: s.left + '%', top: s.top + '%',
    opacity: s.opacity,
    animation: `swim ${s.dur}s ease-in-out infinite alternate`,
    animationDelay: s.delay + 's',
    '--x1': s.x1 + 'px', '--y1': s.y1 + 'px',
    '--x2': s.x2 + 'px', '--y2': s.y2 + 'px',
    '--x3': s.x3 + 'px', '--y3': s.y3 + 'px',
    '--x4': s.x4 + 'px', '--y4': s.y4 + 'px',
  }
}
