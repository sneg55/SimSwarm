<template>
  <div>
    <div class="text-[11px] font-semibold uppercase tracking-wider text-mist-slate mb-2.5">Generate with AI</div>
    <div class="grid grid-cols-1 gap-2">
      <button
        v-for="tpl in templates"
        :key="tpl.id"
        @click="handleClick(tpl)"
        :disabled="loading === tpl.id"
        class="text-left px-4 py-3 bg-ocean-deep border border-mist-depth rounded-xl transition-all ease-spring hover:bg-ocean-cyan/8 hover:border-ocean-cyan/50 hover:-translate-y-0.5 group disabled:opacity-60 disabled:cursor-wait disabled:transform-none"
      >
        <div class="flex items-center gap-2 mb-0.5">
          <span class="text-base">{{ tpl.icon }}</span>
          <span class="text-[12px] font-semibold text-ocean-glow group-hover:text-ocean-cyan transition-colors">{{ tpl.label }}</span>
          <span v-if="loading === tpl.id" class="ml-auto">
            <svg class="w-4 h-4 animate-spin text-ocean-cyan" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
          </span>
        </div>
        <p class="text-[12px] text-mist-slate leading-snug line-clamp-2">{{ tpl.description }}</p>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { generateGoal } from '../../api/ai.js'

const props = defineProps({
  seedText: { type: String, default: '' },
})

const emit = defineEmits(['select'])
const loading = ref(null)

const templates = [
  {
    id: 'market-reaction',
    icon: '📈',
    label: 'Market Reaction',
    description: 'Investor sentiment, price narratives, and trading behavior',
  },
  {
    id: 'crisis-response',
    icon: '🚨',
    label: 'Crisis Response',
    description: 'Stakeholder coalitions, media narratives, and public sentiment',
  },
  {
    id: 'policy-impact',
    icon: '⚖️',
    label: 'Policy Impact',
    description: 'Regulatory cascades, compliance behavior, and industry lobbying',
  },
  {
    id: 'competitive-dynamics',
    icon: '♟️',
    label: 'Competitive Dynamics',
    description: 'Market repositioning, alliances, and disruption response',
  },
  {
    id: 'public-opinion',
    icon: '💬',
    label: 'Public Opinion',
    description: 'Platform discourse, influencer coalitions, and demographic divides',
  },
]

async function handleClick(tpl) {
  if (!props.seedText?.trim()) {
    emit('select', tpl.description)
    return
  }

  loading.value = tpl.id
  try {
    const result = await generateGoal(props.seedText, tpl.id)
    emit('select', result.goal)
  } catch {
    // Fallback to static text if AI fails
    emit('select', tpl.description)
  } finally {
    loading.value = null
  }
}
</script>
