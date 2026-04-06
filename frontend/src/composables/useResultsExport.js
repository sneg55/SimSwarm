import { ref } from 'vue'
import { createShareLink } from '../api/jobs.js'

export function useResultsExport(jobId, job, chatMessages, graphVizRef) {
  const pdfLoading = ref(false)
  const shareStatus = ref('')

  function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  async function exportPDF() {
    pdfLoading.value = true
    try {
      const token = localStorage.getItem('auth_token')
      const resp = await fetch(`/api/jobs/${jobId}/export/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        alert(`PDF export failed: ${err.detail || resp.statusText}`)
        return
      }
      const blob = await resp.blob()
      triggerDownload(blob, `simulation-${jobId}.pdf`)
    } catch (err) {
      console.error('PDF export error:', err)
      alert('PDF export failed. Please try again.')
    } finally {
      pdfLoading.value = false
    }
  }

  function exportJSON() {
    const data = {
      jobId,
      report: job.value?.result_report || job.value?.report,
      messages: chatMessages.value,
      exportedAt: new Date().toISOString(),
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    triggerDownload(blob, `simswarm-${jobId}.json`)
  }

  function exportCSV() {
    const messages = chatMessages.value
    const rows = [['role', 'agent', 'content', 'timestamp']]
    messages.forEach((msg) => {
      rows.push([msg.role || '', msg.agent || '', (msg.content || '').replace(/,/g, ';'), msg.timestamp || ''])
    })
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    triggerDownload(blob, `simswarm-${jobId}.csv`)
  }

  function exportPNG() {
    if (graphVizRef.value) {
      graphVizRef.value.exportImage()
    }
  }

  async function handleExport(format) {
    if (format === 'pdf') await exportPDF()
    else if (format === 'json') exportJSON()
    else if (format === 'csv') exportCSV()
    else if (format === 'png') exportPNG()
  }

  async function handleShare() {
    try {
      shareStatus.value = 'generating'
      const data = await createShareLink(jobId)
      const publicUrl = `${window.location.origin}/s/${data.share_token}`
      await navigator.clipboard.writeText(publicUrl)
      shareStatus.value = 'copied'
      setTimeout(() => { shareStatus.value = '' }, 3000)
    } catch (err) {
      console.error('Failed to create share link:', err)
      shareStatus.value = 'error'
      setTimeout(() => { shareStatus.value = '' }, 3000)
    }
  }

  return { pdfLoading, shareStatus, handleExport, handleShare }
}
