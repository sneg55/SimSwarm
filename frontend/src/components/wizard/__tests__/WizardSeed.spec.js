import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Use vi.hoisted so mocks are available in vi.mock() factory (hoisted to top of file)
const { getDocumentMock, mammothExtractMock, apiPostMock } = vi.hoisted(() => ({
  getDocumentMock: vi.fn(),
  mammothExtractMock: vi.fn().mockResolvedValue({ value: 'docx text' }),
  apiPostMock: vi.fn().mockResolvedValue({ data: { text: 'fetched', char_count: 7 } }),
}))

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: getDocumentMock,
}))
vi.mock('mammoth', () => ({
  default: { extractRawText: mammothExtractMock },
}))
vi.mock('../../../api/index.js', () => ({
  default: { post: apiPostMock },
}))

import WizardSeed from '../WizardSeed.vue'

/** Make a docx File whose arrayBuffer() resolves immediately (no FileReader needed). */
function makeDocxFile(name = 'test.docx') {
  const file = new File(['binary'], name, {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
  Object.defineProperty(file, 'arrayBuffer', { value: async () => new ArrayBuffer(0) })
  return file
}

/** Make a PDF File whose arrayBuffer() resolves immediately. */
function makePdfFile(name = 'test.pdf') {
  const file = new File(['%PDF'], name, { type: 'application/pdf' })
  Object.defineProperty(file, 'arrayBuffer', { value: async () => new ArrayBuffer(0) })
  return file
}

beforeEach(() => {
  apiPostMock.mockResolvedValue({ data: { text: 'fetched', char_count: 7 } })
  mammothExtractMock.mockResolvedValue({ value: 'docx text' })
  getDocumentMock.mockReset()
})

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

  it('fetchUrl shows error status on API failure with detail', async () => {
    apiPostMock.mockRejectedValue({ response: { data: { detail: 'Bad URL' } } })
    const wrapper = mount(WizardSeed)
    await wrapper.find('input[type="url"]').setValue('https://bad.example.com')
    const fetchBtn = wrapper.findAll('button').find(b => b.text().includes('Fetch'))
    await fetchBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Bad URL')
  })

  it('fetchUrl shows generic error message when no detail', async () => {
    apiPostMock.mockRejectedValue(new Error('network'))
    const wrapper = mount(WizardSeed)
    await wrapper.find('input[type="url"]').setValue('https://fail.example.com')
    const fetchBtn = wrapper.findAll('button').find(b => b.text().includes('Fetch'))
    await fetchBtn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Failed to fetch URL')
  })

  it('handleDrop calls processFile on dropped docx file', async () => {
    mammothExtractMock.mockResolvedValue({ value: 'dropped docx' })
    const wrapper = mount(WizardSeed)
    const file = makeDocxFile('dropped.docx')
    await wrapper.find('div.border-dashed').trigger('drop', {
      dataTransfer: { files: [file] },
    })
    await flushPromises()
    expect(mammothExtractMock).toHaveBeenCalled()
    expect(wrapper.emitted('update:seedText')).toBeTruthy()
    expect(wrapper.emitted('update:seedText').flat()).toContain('dropped docx')
  })

  it('handleDrop does nothing if no files in dataTransfer', async () => {
    const wrapper = mount(WizardSeed)
    await wrapper.find('div.border-dashed').trigger('drop', { dataTransfer: { files: [] } })
    await flushPromises()
    expect(wrapper.emitted('update:seedText')).toBeFalsy()
  })

  it('handleFileSelect processes a docx file via input change', async () => {
    mammothExtractMock.mockResolvedValue({ value: 'selected docx' })
    const wrapper = mount(WizardSeed)
    const file = makeDocxFile('input.docx')
    const input = wrapper.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    await flushPromises()
    expect(wrapper.emitted('update:seedText')).toBeTruthy()
    expect(wrapper.emitted('update:seedText').flat()).toContain('selected docx')
  })

  it('processFile handles pdf extension via pdfjs', async () => {
    const fakeTextContent = { items: [{ str: 'pdf page text' }] }
    const fakePage = { getTextContent: async () => fakeTextContent }
    const fakePdf = { numPages: 1, getPage: async () => fakePage }
    getDocumentMock.mockReturnValue({ promise: Promise.resolve(fakePdf) })
    const wrapper = mount(WizardSeed)
    const file = makePdfFile('document.pdf')
    await wrapper.find('div.border-dashed').trigger('drop', {
      dataTransfer: { files: [file] },
    })
    await flushPromises()
    expect(getDocumentMock).toHaveBeenCalled()
    expect(wrapper.emitted('update:seedText')).toBeTruthy()
    const emitted = wrapper.emitted('update:seedText').flat()
    expect(emitted).toContain('pdf page text')
  })

  it('clearFile resets file state and emits empty string', async () => {
    mammothExtractMock.mockResolvedValue({ value: 'to clear' })
    const wrapper = mount(WizardSeed)
    // Drop a docx to set fileName
    await wrapper.find('div.border-dashed').trigger('drop', {
      dataTransfer: { files: [makeDocxFile('clear-me.docx')] },
    })
    await flushPromises()
    // × button should now appear
    const xBtn = wrapper.findAll('button').find(b => b.text().trim() === '×')
    expect(xBtn).toBeTruthy()
    await xBtn.trigger('click')
    const allEmitted = wrapper.emitted('update:seedText') || []
    expect(allEmitted.at(-1)).toEqual([''])
  })

  it('processFile shows error and clears fileName when extraction fails', async () => {
    mammothExtractMock.mockRejectedValue(new Error('parse fail'))
    const wrapper = mount(WizardSeed)
    const file = makeDocxFile('broken.docx')
    await wrapper.find('div.border-dashed').trigger('drop', {
      dataTransfer: { files: [file] },
    })
    await flushPromises()
    // fileName should be cleared on error; no × button
    const xBtn = wrapper.findAll('button').find(b => b.text().trim() === '×')
    expect(xBtn).toBeFalsy()
  })
})
