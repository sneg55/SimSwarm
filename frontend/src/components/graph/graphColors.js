const ENTITY_COLORS = {
  University: '#f97316',
  Entity: '#1e40af',
  Alumni: '#991b1b',
  Organization: '#22c55e',
  Student: '#dc2626',
  Professor: '#ea580c',
  Person: '#3b82f6',
  MediaOutlet: '#7c3aed',
  LegalAuthority: '#16a34a',
  OpinionLeader: '#f59e0b',
  GovernmentAgency: '#b91c1c',
}

const FALLBACK_PALETTE = [
  '#6366f1', '#ec4899', '#14b8a6', '#f43f5e', '#84cc16',
  '#a855f7', '#06b6d4', '#eab308', '#ef4444', '#10b981',
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
