<template>
  <div class="report-prose" v-html="renderedMarkdown" />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  content: { type: String, default: '' },
})

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
    .replace(/^(?!<[hp])(.+)/gm, '<p>$1</p>')
})
</script>

<style scoped>
.report-prose :deep(h1) {
  font-size: 26px; font-weight: 800; color: #F1F5F9;
  letter-spacing: -0.02em;
  margin: 0 0 20px; padding-bottom: 16px;
  border-bottom: 1px solid #1E293B;
}
.report-prose :deep(h2) {
  font-size: 20px; font-weight: 700; color: #F1F5F9;
  letter-spacing: -0.01em; margin: 36px 0 14px;
}
.report-prose :deep(h3) {
  font-size: 16px; font-weight: 600; color: #CBD5E1;
  margin: 28px 0 10px;
}
.report-prose :deep(p) {
  font-size: 15px; color: #CBD5E1; line-height: 1.8;
  margin-bottom: 16px;
}
.report-prose :deep(strong) { color: #F1F5F9; font-weight: 600; }
.report-prose :deep(em) { color: #94A3B8; }
.report-prose :deep(code) {
  font-family: 'JetBrains Mono', monospace; font-size: 13px;
  background: rgba(34, 211, 238, 0.08); color: #22D3EE;
  padding: 2px 6px; border-radius: 4px;
}
</style>
