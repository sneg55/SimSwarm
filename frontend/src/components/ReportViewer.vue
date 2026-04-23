<template>
  <div class="report-prose" v-html="safeHtml" />
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
})

const props = defineProps({
  content: { type: String, default: '' },
})

// The report generator uses `### slot=<name> — <title>` as a parse sentinel
// for the Story view's FindingSlotCard extraction (saas/jobs/report.py).
// It isn't meant to surface here — strip it to keep the H3 clean.
const SLOT_SENTINEL = /^(#{1,6}\s+)slot=[\w-]+\s*[—–-]\s*/gm

const safeHtml = computed(() => {
  if (!props.content) return ''
  const cleaned = props.content.replace(SLOT_SENTINEL, '$1')
  const rawHtml = md.render(cleaned)
  return DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: ['h1','h2','h3','h4','p','strong','em','code','pre','ul','ol','li','a','blockquote','br','table','thead','tbody','tr','th','td'],
    ALLOWED_ATTR: ['href','target','rel'],
  })
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
