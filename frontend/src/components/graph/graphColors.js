const ENTITY_COLORS = {
  University: '#f97316',
  Entity: '#22D3EE',
  Alumni: '#FF6B6B',
  Organization: '#22D3EE',
  Student: '#FF6B6B',
  Professor: '#F97316',
  Person: '#A78BFA',
  MediaOutlet: '#6EE7B7',
  LegalAuthority: '#10B981',
  OpinionLeader: '#FBBF24',
  GovernmentAgency: '#FF6B6B',
}

const FALLBACK_PALETTE = [
  '#22D3EE', '#A78BFA', '#6EE7B7', '#FF6B6B', '#FBBF24',
  '#F97316', '#10B981', '#0E7490', '#64748B', '#CBD5E1',
]

const dynamicColorCache = {}

export function getEntityColor(entityType) {
  if (ENTITY_COLORS[entityType]) return ENTITY_COLORS[entityType]
  if (dynamicColorCache[entityType]) return dynamicColorCache[entityType]
  let hash = 0
  for (let i = 0; i < entityType.length; i++) {
    hash = ((hash << 5) - hash + entityType.charCodeAt(i)) | 0
  }
  const color = FALLBACK_PALETTE[Math.abs(hash) % FALLBACK_PALETTE.length]
  dynamicColorCache[entityType] = color
  return color
}

export function getPrimaryLabel(labels) {
  return labels.find((l) => l !== 'Entity' && l !== 'Node') || 'Entity'
}

export { ENTITY_COLORS }
