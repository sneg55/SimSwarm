<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-xl overflow-hidden mb-5">
    <div class="flex items-center gap-2 px-4 py-3 text-sm font-semibold text-mist-drift cursor-pointer transition-colors hover:text-mist-foam hover:bg-ocean-abyss/50" @click="open = !open">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      What makes a good seed?
      <span class="ml-auto text-[10px] text-mist-slate transition-transform" :class="open ? 'rotate-90' : ''">&#x25B6;</span>
    </div>
    <div v-if="open" class="px-4 pb-4 space-y-1.5">
      <div v-for="tip in tips" :key="tip.text" class="flex items-start gap-2.5 text-sm text-mist-drift leading-snug">
        <span class="flex-shrink-0 mt-0.5" :class="tip.cls">{{ tip.icon }}</span>
        <span><strong class="text-mist">{{ tip.bold }}</strong> {{ tip.text }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const open = ref(false)

const tips = [
  { icon: '✓', cls: 'text-organic-seafoam', bold: 'Specific events', text: '— an earnings report, a policy announcement, a product launch press release.' },
  { icon: '✓', cls: 'text-organic-seafoam', bold: 'Multiple stakeholders', text: '— documents mentioning companies, regulators, media, and public figures.' },
  { icon: '✓', cls: 'text-organic-seafoam', bold: 'Recent context', text: '— news articles or analyst notes from the last few days.' },
  { icon: '○', cls: 'text-coral-sand', bold: '2,000–20,000 characters', text: 'is the sweet spot. Too short = no context, too long = noise.' },
  { icon: '✗', cls: 'text-coral', bold: 'Avoid generic content', text: '— boilerplate pages or Wikipedia summaries won\'t produce interesting results.' },
]
</script>
