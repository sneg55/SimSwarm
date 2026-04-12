import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Stub heavy deps
vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: vi.fn(),
}))
vi.mock('mammoth', () => ({
  default: { extractRawText: vi.fn().mockResolvedValue({ value: 'docx text' }) },
}))
vi.mock('../../../api/index.js', () => ({
  default: { post: vi.fn().mockResolvedValue({ data: { text: 'fetched', char_count: 7 } }) },
}))

import WizardSeed from '../WizardSeed.vue'

describe('WizardSeed', () => {
  it('renders step title and tips', () => {
    const wrapper = mount(WizardSeed)
    expect(wrapper.text()).toContain("Let's seed the ecosystem")
    expect(wrapper.text()).toContain('Direct Upload')
    expect(wrapper.text()).toContain('Import from Source')
    expect(wrapper.text()).toContain('Raw Input')
  })

  it('emits update:seedText when textarea changes', async () => {
    const wrapper = mount(WizardSeed)
    const textarea = wrapper.find('textarea')
    await textarea.setValue('my seed text')
    expect(wrapper.emitted('update:seedText')).toBeTruthy()
    expect(wrapper.emitted('update:seedText').at(-1)).toEqual(['my seed text'])
  })

  it('shows character counter', async () => {
    const wrapper = mount(WizardSeed)
    await wrapper.find('textarea').setValue('abc')
    expect(wrapper.text()).toContain('3 / 20,000')
  })

  it('fetchUrl does nothing when URL is empty', async () => {
    const wrapper = mount(WizardSeed)
    const btns = wrapper.findAll('button')
    const fetchBtn = btns.find(b => b.text().includes('Fetch'))
    await fetchBtn.trigger('click')
    expect(wrapper.text()).toContain('Fetch')
  })

  it('fetchUrl populates seedText on success', async () => {
    const wrapper = mount(WizardSeed)
    await wrapper.find('input[type="url"]').setValue('https://x.com/a')
    const btns = wrapper.findAll('button')
    const fetchBtn = btns.find(b => b.text().includes('Fetch'))
    await fetchBtn.trigger('click')
    await new Promise(r => setTimeout(r, 5))
    expect(wrapper.emitted('update:seedText')).toBeTruthy()
  })
})
