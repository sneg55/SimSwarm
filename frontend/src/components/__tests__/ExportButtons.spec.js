import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ExportButtons from '../ExportButtons.vue'

describe('ExportButtons', () => {
  it('renders PDF and JSON buttons', () => {
    const wrapper = mount(ExportButtons, {
      props: { jobId: 1, reportContent: 'test' },
    })
    const text = wrapper.text()
    expect(text).toMatch(/pdf/i)
    expect(text).toMatch(/json/i)
  })
})
