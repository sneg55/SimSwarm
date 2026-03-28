<template>
  <div>
    <div class="mb-5">
      <div class="font-mono text-xs text-ocean-cyan tracking-wide mb-2">Step 1 of 3</div>
      <h2 class="text-3xl font-extrabold text-mist-foam tracking-tight leading-tight">Let's seed the ecosystem</h2>
      <p class="text-[15px] text-mist-drift mt-2">Upload a document or paste text to begin. The swarm will extract entities and build a knowledge graph.</p>
    </div>

    <SeedTips />

    <!-- Direct Upload -->
    <div class="text-[11px] font-semibold uppercase tracking-wider text-ocean-cyan mb-2">Direct Upload</div>
    <div
      class="border-2 border-dashed border-ocean-teal rounded-2xl p-7 text-center cursor-pointer transition-all hover:border-ocean-cyan"
      :class="isDragging ? 'border-ocean-glow bg-ocean-glow/5 scale-[1.01] shadow-[0_0_30px_rgba(34,211,238,0.1)_inset]' : 'bg-ocean-deep/40'"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="handleDrop"
      @click="$refs.fileInput.click()"
    >
      <div v-if="fileName" class="flex items-center justify-center gap-3">
        <span class="text-2xl">&#x1F4C4;</span>
        <div class="text-left">
          <div class="text-sm font-semibold text-mist-foam">{{ fileName }}</div>
          <div class="text-xs text-mist-slate">{{ charCount }} characters extracted</div>
        </div>
        <button @click.stop="clearFile" class="text-mist-slate hover:text-coral text-lg ml-2">&times;</button>
      </div>
      <template v-else>
        <div class="text-3xl mb-1.5">&#x1F30A;</div>
        <div class="text-sm font-medium text-mist-drift">Drop your document here</div>
        <div class="text-xs text-mist-slate mt-1">or</div>
        <button class="mt-2 px-5 py-1.5 rounded-lg border border-ocean-teal text-sm font-semibold text-ocean-glow transition-all ease-spring hover:bg-ocean-cyan/15 hover:border-ocean-cyan hover:-translate-y-px" @click.stop="$refs.fileInput.click()">
          Browse files
        </button>
        <div class="font-mono text-[11px] text-mist-slate/60 mt-3">PDF, DOCX, TXT, Markdown — up to 50,000 characters</div>
      </template>
    </div>
    <input ref="fileInput" type="file" class="hidden" accept=".pdf,.docx,.txt,.md" @change="handleFileSelect" />

    <!-- Import from Source -->
    <div class="text-[11px] font-semibold uppercase tracking-wider text-ocean-cyan mt-6 mb-2">Import from Source</div>
    <div class="flex items-center bg-ocean-abyss border border-mist-depth rounded-xl p-1 pl-3.5 gap-2 transition-all focus-within:border-ocean-cyan focus-within:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
      <input v-model="url" type="url" placeholder="https://example.com/press-release" class="flex-1 bg-transparent border-none outline-none text-sm text-mist py-2" />
      <button @click="fetchUrl" :disabled="fetchingUrl" class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-br from-ocean-cyan to-cyan-500 text-white text-sm font-semibold whitespace-nowrap transition-all ease-spring hover:-translate-y-px disabled:opacity-50">
        {{ fetchingUrl ? 'Fetching...' : 'Fetch' }}
      </button>
    </div>
    <div v-if="urlStatus" class="text-xs mt-2" :class="urlError ? 'text-coral' : 'text-organic-seafoam'">{{ urlStatus }}</div>

    <!-- Raw Input -->
    <div class="text-[11px] font-semibold uppercase tracking-wider text-ocean-cyan mt-6 mb-2">Raw Input</div>
    <textarea
      v-model="seedText"
      placeholder="Paste your document text here — news articles, reports, announcements, policy drafts..."
      class="w-full bg-ocean-abyss border border-mist-depth rounded-xl p-3.5 text-sm text-mist resize-vertical min-h-[90px] outline-none transition-all focus:border-ocean-cyan focus:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]"
    />
    <div class="font-mono text-[11px] text-mist-slate text-right mt-1">{{ seedText.length }} / 50,000</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SeedTips from './SeedTips.vue'

const emit = defineEmits(['update:seedText'])

const seedText = ref('')
const fileName = ref('')
const charCount = ref(0)
const isDragging = ref(false)
const url = ref('')
const fetchingUrl = ref(false)
const urlStatus = ref('')
const urlError = ref(false)

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) processFile(file)
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) processFile(file)
}

function processFile(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    seedText.value = e.target.result
    fileName.value = file.name
    charCount.value = e.target.result.length
    emit('update:seedText', seedText.value)
  }
  reader.readAsText(file)
}

function clearFile() {
  fileName.value = ''
  charCount.value = 0
  seedText.value = ''
  emit('update:seedText', '')
}

async function fetchUrl() {
  if (!url.value.trim()) return
  fetchingUrl.value = true
  urlStatus.value = ''
  urlError.value = false
  // TODO: wire to backend URL fetch endpoint
  // For now, show that it would work
  setTimeout(() => {
    urlStatus.value = 'URL fetching requires a backend endpoint (not yet implemented)'
    urlError.value = true
    fetchingUrl.value = false
  }, 1000)
}
</script>
