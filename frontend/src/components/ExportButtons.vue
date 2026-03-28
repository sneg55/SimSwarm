<template>
  <div class="flex items-center gap-3">
    <span class="text-sm text-mist-drift font-medium">Export:</span>
    <button
      @click="handleExportPDF"
      :disabled="pdfLoading"
      class="inline-flex items-center px-3 py-1.5 border border-mist-depth rounded-lg text-sm text-mist-drift hover:bg-ocean-teal/10 hover:text-mist-foam transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {{ pdfLoading ? 'Generating...' : 'PDF' }}
    </button>
    <button
      @click="handleExportJSON"
      :disabled="jsonLoading"
      class="inline-flex items-center px-3 py-1.5 border border-mist-depth rounded-lg text-sm text-mist-drift hover:bg-ocean-teal/10 hover:text-mist-foam transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {{ jsonLoading ? 'Downloading...' : 'JSON' }}
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
import { exportPDF, exportJSON } from '@/api/jobs.js'

const props = defineProps({
  jobId: String,
  reportContent: String,
  messages: Array,
})

const emit = defineEmits(['export'])

const pdfLoading = ref(false)
const jsonLoading = ref(false)

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleExportPDF() {
  pdfLoading.value = true
  emit('export', { format: 'pdf', jobId: props.jobId })
  try {
    const blob = await exportPDF(props.jobId)
    triggerDownload(blob, `simulation-${props.jobId}.pdf`)
  } catch (err) {
    console.error('PDF export error:', err)
    alert('PDF export failed. Please try again.')
  } finally {
    pdfLoading.value = false
  }
}

async function handleExportJSON() {
  jsonLoading.value = true
  emit('export', { format: 'json', jobId: props.jobId })
  try {
    const blob = await exportJSON(props.jobId)
    triggerDownload(blob, `simulation-${props.jobId}.json`)
  } catch (err) {
    console.error('JSON export error:', err)
    alert('JSON export failed. Please try again.')
  } finally {
    jsonLoading.value = false
  }
}

function exportCSV() {
  const messages = props.messages || []
  const rows = [['role', 'agent', 'content', 'timestamp']]
  messages.forEach((msg) => {
    rows.push([msg.role || '', msg.agent || '', (msg.content || '').replace(/,/g, ';'), msg.timestamp || ''])
  })
  const csv = rows.map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  triggerDownload(blob, `simswarm-${props.jobId}.csv`)
  emit('export', { format: 'csv', jobId: props.jobId })
}
</script>
