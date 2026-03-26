<template>
  <div class="prose max-w-none" v-html="renderedMarkdown" />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  content: {
    type: String,
    default: '',
  },
})

// Simple markdown renderer (without external dep)
const renderedMarkdown = computed(() => {
  if (!props.content) return ''
  return props.content
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(.+)$/gm, (line) => {
      if (line.startsWith('<h') || line.startsWith('<p') || line.startsWith('</p>')) return line
      return line
    })
    .replace(/^(?!<[hp])(.+)/gm, '<p>$1</p>')
})
</script>
