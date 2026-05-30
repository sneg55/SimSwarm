import { describe, it, expect } from 'vitest'
import { INSIGHTS, SWARM_COLORS, AGENT_SEEDS, agentStyle } from '../landingContent.js'

describe('landingContent', () => {
  it('INSIGHTS has at least one entry with label, color, text', () => {
    expect(INSIGHTS.length).toBeGreaterThan(0)
    const first = INSIGHTS[0]
    expect(first).toHaveProperty('label')
    expect(first).toHaveProperty('color')
    expect(first).toHaveProperty('text')
  })

  it('SWARM_COLORS entries have bg and glow', () => {
    expect(SWARM_COLORS.length).toBeGreaterThan(0)
    SWARM_COLORS.forEach(c => {
      expect(c).toHaveProperty('bg')
      expect(c).toHaveProperty('glow')
    })
  })

  it('AGENT_SEEDS has 24 entries with required fields', () => {
    expect(AGENT_SEEDS).toHaveLength(24)
    AGENT_SEEDS.forEach(s => {
      expect(s).toHaveProperty('size')
      expect(s).toHaveProperty('colorIdx')
    })
  })

  it('agentStyle returns a style object with width and background', () => {
    const style = agentStyle(1)
    expect(style).toHaveProperty('width')
    expect(style).toHaveProperty('background')
    expect(style).toHaveProperty('left')
    expect(style).toHaveProperty('top')
  })
})
