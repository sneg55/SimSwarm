import { describe, it, expect } from 'vitest'
import { buildPricingTiers, PACK_DISPLAY, FALLBACK_PACK_DISPLAY } from '../landingContent.js'

describe('buildPricingTiers', () => {
  it('formats price from cents and overlays display metadata by slug', () => {
    const tiers = buildPricingTiers([
      { slug: 'starter', name: 'Starter', credits: 100, price_cents: 1900 },
      { slug: 'pro', name: 'Pro', credits: 500, price_cents: 7900 },
    ])
    expect(tiers).toHaveLength(2)
    expect(tiers[0]).toMatchObject({
      name: 'Starter',
      credits: 100,
      price: '$19',
      accent: PACK_DISPLAY.starter.accent,
      featured: false,
    })
    expect(tiers[0].features.length).toBeGreaterThan(0)
    expect(tiers[1].name).toBe('Pro')
    expect(tiers[1].featured).toBe(true)
  })

  it('uses fallback display metadata for unknown slugs', () => {
    const tiers = buildPricingTiers([
      { slug: 'enterprise_2027', name: 'Enterprise', credits: 50000, price_cents: 999900 },
    ])
    expect(tiers[0]).toMatchObject({
      name: 'Enterprise',
      credits: 50000,
      price: '$9999',
      accent: FALLBACK_PACK_DISPLAY.accent,
      featured: false,
    })
    expect(tiers[0].features).toEqual([])
  })

  it('returns an empty array for no packs', () => {
    expect(buildPricingTiers([])).toEqual([])
  })
})
