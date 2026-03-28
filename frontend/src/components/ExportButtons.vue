<template>
  <div class="flex items-center gap-3">
    <span class="text-sm text-mist-drift font-medium">Export:</span>
    <button
      @click="exportPDF"
      :disabled="pdfLoading"
      class="inline-flex items-center px-3 py-1.5 border border-mist-depth rounded-lg text-sm text-mist-drift hover:bg-ocean-teal/10 hover:text-mist-foam transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {{ pdfLoading ? 'Generating...' : 'PDF' }}
    </button>
    <button
      @click="exportJSON"
      class="inline-flex items-center px-3 py-1.5 border border-mist-depth rounded-lg text-sm text-mist-drift hover:bg-ocean-teal/10 hover:text-mist-foam transition-colors"
    >
      JSON
    </button>
    <button
      @click="exportCSV"
      class="inline-flex items-center px-3 py-1.5 border border-mist-depth rounded-lg text-sm text-mist-drift hover:bg-ocean-teal/10 hover:text-mist-foam transition-colors"
    >
      CSV
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  jobId: String,
  reportContent: String,
  messages: Array,
})

const emit = defineEmits(['export'])

const pdfLoading = ref(false)

async function exportPDF() {
  pdfLoading.value = true
  emit('export', { format: 'pdf', jobId: props.jobId })
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch(`/api/jobs/${props.jobId}/export/pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      alert(`PDF export failed: ${err.detail || resp.statusText}`)
      return
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `simulation-${props.jobId}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('PDF export error:', err)
    alert('PDF export failed. Please try again.')
  } finally {
    pdfLoading.value = false
  }
}

function exportJSON() {
  const data = {
    jobId: props.jobId,
    report: props.reportContent,
    messages: props.messages,
    exportedAt: new Date().toISOString(),
  }
  downloadFile(JSON.stringify(data, null, 2), `simswarm-${props.jobId}.json`, 'application/json')
  emit('export', { format: 'json', jobId: props.jobId })
}

function exportCSV() {
  const messages = props.messages || []
  const rows = [['role', 'agent', 'content', 'timestamp']]
  messages.forEach((msg) => {
    rows.push([msg.role || '', msg.agent || '', (msg.content || '').replace(/,/g, ';'), msg.timestamp || ''])
  })
  const csv = rows.map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
  downloadFile(csv, `simswarm-${props.jobId}.csv`, 'text/csv')
  emit('export', { format: 'csv', jobId: props.jobId })
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>
