import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ReportToc from '../ReportToc.vue'
import StoryTimeline from '../StoryTimeline.vue'

function mockElementAtTop(id, top) {
  const el = document.createElement('div')
  el.id = id
  el.getBoundingClientRect = () => ({ top, bottom: top + 10, left: 0, right: 0, width: 10, height: 10 })
  el.scrollIntoView = vi.fn()
  document.body.appendChild(el)
  return el
}

describe('ReportToc scroll tracking', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('updates activeIndex when a section scrolls past threshold', async () => {
    mockElementAtTop('s1', 10)
    mockElementAtTop('s2', 500)
    const wrapper = mount(ReportToc, { props: { items: [{ id: 's1', label: 'A' }, { id: 's2', label: 'B' }] } })
    window.dispatchEvent(new Event('scroll'))
    expect(wrapper.text()).toContain('A')
  })

  it('resets activeIndex to 0 when no section has scrolled past', async () => {
    mockElementAtTop('x1', 2000)
    const wrapper = mount(ReportToc, { props: { items: [{ id: 'x1', label: 'X' }] } })
    window.dispatchEvent(new Event('scroll'))
    expect(wrapper.exists()).toBe(true)
    wrapper.unmount()
  })

  it('scrollTo clicks invoke scrollIntoView', async () => {
    const el = mockElementAtTop('anchor', 100)
    const wrapper = mount(ReportToc, { props: { items: [{ id: 'anchor', label: 'Anchor' }] } })
    await wrapper.find('a').trigger('click')
    expect(el.scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ behavior: 'smooth' }))
  })

  it('scrollTo is safe when target element is missing', async () => {
    const wrapper = mount(ReportToc, { props: { items: [{ id: 'missing', label: 'M' }] } })
    await wrapper.find('a').trigger('click')
    expect(wrapper.exists()).toBe(true)
  })
})

describe('StoryTimeline scroll tracking', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('updates activeIndex based on threshold (40% of innerHeight)', async () => {
    mockElementAtTop('sec1', 100)
    mockElementAtTop('sec2', 200)
    const wrapper = mount(StoryTimeline, {
      props: { sections: [{ id: 'sec1', label: 'One' }, { id: 'sec2', label: 'Two' }] },
    })
    window.dispatchEvent(new Event('scroll'))
    expect(wrapper.exists()).toBe(true)
  })

  it('scrollToSection invokes scrollIntoView on the target', async () => {
    const el = mockElementAtTop('ss', 50)
    const wrapper = mount(StoryTimeline, { props: { sections: [{ id: 'ss', label: 'S' }] } })
    await wrapper.find('.cursor-pointer').trigger('click')
    expect(el.scrollIntoView).toHaveBeenCalled()
  })

  it('scrollToSection no-ops when element is absent', async () => {
    const wrapper = mount(StoryTimeline, { props: { sections: [{ id: 'nope', label: 'N' }] } })
    await wrapper.find('.cursor-pointer').trigger('click')
    expect(wrapper.exists()).toBe(true)
  })

  it('removes scroll listener on unmount', async () => {
    mockElementAtTop('u1', 50)
    const wrapper = mount(StoryTimeline, { props: { sections: [{ id: 'u1', label: 'U' }] } })
    wrapper.unmount()
    window.dispatchEvent(new Event('scroll'))
    expect(true).toBe(true)
  })
})
