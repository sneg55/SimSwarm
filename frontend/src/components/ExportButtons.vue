<template>
  <div class="flex items-center gap-3">
    <span class="text-sm text-gray-600 font-medium">Export:</span>
    <button
      @click="exportPDF"
      class="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-700 hover:bg-gray-50 transition-colors"
    >
      PDF
    </button>
    <button
      @click="exportJSON"
      class="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-700 hover:bg-gray-50 transition-colors"
    >
      JSON
    </button>
    <button
      @click="exportCSV"
      class="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-700 hover:bg-gray-50 transition-colors"
    >
      CSV
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  jobId: String,
  reportContent: String,
  messages: Array,
})

const emit = defineEmits(['export'])

function exportPDF() {
  emit('export', { format: 'pdf', jobId: props.jobId })
  window.print()
}

function exportJSON() {
  const data = {
    jobId: props.jobId,
    report: props.reportContent,
    messages: props.messages,
    exportedAt: new Date().toISOString(),
  }
  downloadFile(JSON.stringify(data, null, 2), `fishcloud-${props.jobId}.json`, 'application/json')
  emit('export', { format: 'json', jobId: props.jobId })
}

function exportCSV() {
  const messages = props.messages || []
  const rows = [['role', 'agent', 'content', 'timestamp']]
  messages.forEach((msg) => {
    rows.push([msg.role || '', msg.agent || '', (msg.content || '').replace(/,/g, ';'), msg.timestamp || ''])
  })
  const csv = rows.map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
  downloadFile(csv, `fishcloud-${props.jobId}.csv`, 'text/csv')
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
