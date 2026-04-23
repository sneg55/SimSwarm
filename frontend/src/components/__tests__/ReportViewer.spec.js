import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ReportViewer from '../ReportViewer.vue'

describe('ReportViewer', () => {
  it('renders markdown content as HTML', () => {
    const wrapper = mount(ReportViewer, {
      props: { content: '# Hello\n\nWorld' },
    })
    expect(wrapper.html()).toContain('<h1>')
    expect(wrapper.html()).toContain('Hello')
  })

  it('sanitizes script tags', () => {
    const wrapper = mount(ReportViewer, {
      props: { content: '<script>alert("xss")</script>Safe text' },
    })
    expect(wrapper.html()).not.toContain('<script>')
    expect(wrapper.html()).toContain('Safe text')
  })

  it('renders empty string without error', () => {
    const wrapper = mount(ReportViewer, {
      props: { content: '' },
    })
    expect(wrapper.html()).toContain('report-prose')
  })

  it('strips slot=... sentinel from headings', () => {
    const wrapper = mount(ReportViewer, {
      props: {
        content: '### slot=turning_point — Sentiment collapse\n\nBody.',
      },
    })
    const html = wrapper.html()
    expect(html).not.toContain('slot=')
    expect(html).toContain('Sentiment collapse')
  })
})
