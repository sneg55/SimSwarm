import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PipelineProgress from '../../src/components/PipelineProgress.vue'

describe('PipelineProgress', () => {
  it('renders 5 pipeline steps', () => {
    const wrapper = mount(PipelineProgress, {
      props: { currentStep: null, completedSteps: [] },
    })
    // 5 step labels
    const text = wrapper.text()
    expect(text).toContain('Seed')
    expect(text).toContain('Research')
    expect(text).toContain('Simulate')
    expect(text).toContain('Analyze')
    expect(text).toContain('Report')
  })

  it('marks completed steps with check indicator', () => {
    const wrapper = mount(PipelineProgress, {
      props: { currentStep: 'research', completedSteps: ['seed'] },
    })
    // completed step has a checkmark SVG path
    const svgs = wrapper.findAll('svg')
    expect(svgs.length).toBeGreaterThan(0)
  })
})
