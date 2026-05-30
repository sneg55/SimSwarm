import { describe, it, expect } from 'vitest'
import { getEntityColor, getPrimaryLabel } from '../graphColors.js'

describe('graphColors', () => {
  it('returns specific color for known entity types', () => {
    expect(getEntityColor('Person')).toBe('#A78BFA')
    expect(getEntityColor('GovernmentAgency')).toBe('#FF6B6B')
    expect(getEntityColor('MediaOutlet')).toBe('#6EE7B7')
  })

  it('returns fallback color for unknown types', () => {
    const color = getEntityColor('SomeNewType')
    expect(color).toBeTruthy()
    expect(color).toMatch(/^#/)
  })

  it('returns consistent color for same unknown type', () => {
    const a = getEntityColor('UnknownTypeXYZ')
    const b = getEntityColor('UnknownTypeXYZ')
    expect(a).toBe(b)
  })

  it('getPrimaryLabel skips Entity and Node', () => {
    expect(getPrimaryLabel(['Entity', 'Node', 'Person'])).toBe('Person')
    expect(getPrimaryLabel(['Entity'])).toBe('Entity')
    expect(getPrimaryLabel(['Node', 'Organization'])).toBe('Organization')
  })
})
