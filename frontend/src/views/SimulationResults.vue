<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <div class="mb-6 flex items-center justify-between">
      <div>
        <router-link to="/dashboard" class="text-sm text-blue-600 hover:underline">&larr; Back to Dashboard</router-link>
        <h1 class="text-2xl font-bold text-gray-900 mt-2">Simulation Results</h1>
      </div>
      <ExportButtons
        v-if="job"
        :job-id="jobId"
        :report-content="job.report"
        :messages="job.messages"
      />
    </div>

    <div v-if="loading" class="text-center py-12 text-gray-500">
      Loading results...
    </div>

    <div v-else-if="job" class="space-y-6">
      <div class="bg-white border border-gray-200 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-1">{{ job.goal }}</h2>
        <p class="text-sm text-gray-500 capitalize">
          {{ job.tier }} tier &bull; Completed {{ formatDate(job.completed_at) }}
        </p>
      </div>

      <div class="bg-white border border-gray-200 rounded-lg p-6">
        <h3 class="text-lg font-semibold text-gray-800 mb-4">Report</h3>
        <ReportViewer :content="job.result_report || job.report || 'No report available.'" />
      </div>

      <div v-if="chatMessages.length > 0" class="bg-white border border-gray-200 rounded-lg p-6">
        <h3 class="text-lg font-semibold text-gray-800 mb-4">Agent Conversation</h3>
        <ChatReplay :messages="chatMessages" />
      </div>
    </div>

    <div v-else class="text-center py-12 text-gray-500">
      Results not found.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import ExportButtons from '../components/ExportButtons.vue'
import { getJob } from '../api/jobs.js'

const route = useRoute()
const jobId = route.params.id

const job = ref(null)
const loading = ref(true)

const chatMessages = computed(() => {
  if (!job.value) return []
  try {
    const raw = job.value.result_chat_log || job.value.chat_log || '[]'
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch { return [] }
})

onMounted(async () => {
  try {
    job.value = await getJob(jobId)
  } catch (err) {
    console.error('Failed to load results:', err)
  } finally {
    loading.value = false
  }
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}
</script>
