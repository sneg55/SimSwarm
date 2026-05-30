const ENTITY_COLORS = {
  // People
  Person: '#A78BFA',
  PoliticalFigure: '#A78BFA',
  PrimeMinister: '#A78BFA',
  GovernmentOfficial: '#A78BFA',
  JudicialFigure: '#818CF8',
  OpinionLeader: '#FBBF24',

  // Organizations
  Organization: '#22D3EE',
  GovernmentAgency: '#FF6B6B',
  InternationalOrganization: '#14B8A6',
  RegulatoryAgency: '#10B981',
  LegalAuthority: '#10B981',

  // Media
  MediaOutlet: '#6EE7B7',
  MediaOutlets: '#6EE7B7',

  // Military
  MilitaryUnit: '#EF4444',
  CoalitionMember: '#F97316',

  // Business
  EnergyCompany: '#FBBF24',
  ShippingCompany: '#38BDF8',
  Airline: '#38BDF8',

  // Places
  Country: '#8B5CF6',
  City: '#C084FC',
  Location: '#C084FC',

  // Academic
  University: '#F97316',
  Professor: '#F97316',
  Student: '#FF6B6B',
  Alumni: '#FF6B6B',

  // Generic fallback
  Entity: '#6B7280',
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
