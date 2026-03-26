<template>
  <div class="space-y-2">
    <label class="block text-sm font-medium text-gray-700">Seed Data</label>
    <div
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="handleDrop"
      :class="[
        'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
        isDragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300',
      ]"
      @click="fileInput.click()"
    >
      <div v-if="fileName" class="text-green-600 font-medium">
        {{ fileName }}
      </div>
      <div v-else class="text-gray-500">
        <p>Drag & drop a file here, or click to select</p>
        <p class="text-xs mt-1">.txt, .csv, .json, .md supported</p>
      </div>
    </div>
    <input
      ref="fileInput"
      type="file"
      class="hidden"
      accept=".txt,.csv,.json,.md"
      @change="handleFileSelect"
    />
    <div class="text-sm text-gray-500 text-center">— or —</div>
    <textarea
      v-model="textContent"
      @input="handleTextInput"
      placeholder="Paste your seed text here..."
      rows="4"
      class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const emit = defineEmits(['update'])

const isDragging = ref(false)
const fileName = ref('')
const textContent = ref('')
const fileInput = ref(null)

// Emit update whenever textContent changes (covers v-model, paste, programmatic fill)
watch(textContent, (val) => {
  if (val) {
    fileName.value = ''
    emit('update', { type: 'text', content: val })
  }
})

function handleDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) processFile(file)
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) processFile(file)
}

function processFile(file) {
  fileName.value = file.name
  const reader = new FileReader()
  reader.onload = (e) => {
    emit('update', { type: 'file', name: file.name, content: e.target.result })
  }
  reader.readAsText(file)
}

function handleTextInput() {
  fileName.value = ''
  emit('update', { type: 'text', content: textContent.value })
}
</script>
