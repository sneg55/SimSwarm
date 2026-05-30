import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

vi.mock('../../api/jobs.js', () => ({
  createShareLink: vi.fn().mockResolvedValue({ share_token: 'tok123' }),
}))

import { useResultsExport } from '../useResultsExport.js'
import { createShareLink } from '../../api/jobs.js'

describe('useResultsExport', () => {
  let clipboard

  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:xxx')
    URL.revokeObjectURL = vi.fn()
    clipboard = { writeText: vi.fn().mockResolvedValue() }
    Object.defineProperty(navigator, 'clipboard', { value: clipboard, configurable: true })
    createShareLink.mockResolvedValue({ share_token: 'tok123' })
  })

  it('exports CSV', async () => {
    const chatMessages = ref([
      { role: 'user', agent: 'A', content: 'hi,there', timestamp: '2024' },
    ])
    const exp = useResultsExport('j', ref({}), chatMessages, ref(null))
    await exp.handleExport('csv')
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('exports PNG via graphVizRef.exportImage', async () => {
    const exportImage = vi.fn()
    const exp = useResultsExport('j', ref({}), ref([]), ref({ exportImage }))
    await exp.handleExport('png')
    expect(exportImage).toHaveBeenCalled()
  })

  it('PNG export no-op if ref empty', async () => {
    const exp = useResultsExport('j', ref({}), ref([]), ref(null))
    await exp.handleExport('png')
  })

  it('exports PDF successfully', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['pdf'])),
    })
    const exp = useResultsExport('j', ref({}), ref([]), ref(null))
    await exp.handleExport('pdf')
    expect(exp.pdfLoading.value).toBe(false)
  })

  it('alerts on PDF export failure', async () => {
    global.alert = vi.fn()
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, statusText: 'Bad',
      json: () => Promise.resolve({ detail: 'oops' }),
    })
    const exp = useResultsExport('j', ref({}), ref([]), ref(null))
    await exp.handleExport('pdf')
    expect(global.alert).toHaveBeenCalled()
  })

  it('alerts on PDF fetch error', async () => {
    global.alert = vi.fn()
    global.fetch = vi.fn().mockRejectedValue(new Error('net'))
    const exp = useResultsExport('j', ref({}), ref([]), ref(null))
    await exp.handleExport('pdf')
    expect(global.alert).toHaveBeenCalled()
  })

  it('handleShare writes URL to clipboard', async () => {
    const exp = useResultsExport('j', ref({}), ref([]), ref(null))
    await exp.handleShare()
    expect(clipboard.writeText).toHaveBeenCalled()
    expect(exp.shareStatus.value).toBe('copied')
  })

  it('handleShare sets error on failure', async () => {
    createShareLink.mockRejectedValueOnce(new Error('fail'))
    const exp = useResultsExport('j', ref({}), ref([]), ref(null))
    await exp.handleShare()
    expect(exp.shareStatus.value).toBe('error')
  })

  it('handleExport ignores unknown format', async () => {
    const exp = useResultsExport('j', ref({}), ref([]), ref(null))
    await exp.handleExport('unknown')
  })
})
