<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl overflow-hidden">
    <button
      @click="open = !open"
      class="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-ocean-teal/5 transition-colors"
    >
      <span class="text-sm font-semibold text-ocean-glow flex items-center gap-2">
        <span class="w-1.5 h-1.5 rounded-full bg-organic-violet animate-[breathe_2.5s_ease-in-out_infinite]" />
        Live Activity
      </span>
      <svg
        class="w-4 h-4 text-mist-slate transition-transform"
        :class="{ 'rotate-180': open }"
        fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"
      >
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <div v-show="open" data-testid="live-body" class="px-5 pb-4">
      <!-- Log lines: shown when no chat messages yet -->
      <div
        v-if="logLines.length > 0 && partialChat.length === 0"
        data-testid="log-lines"
        class="space-y-1 pt-2"
      >
        <div
          v-for="(line, i) in logLines"
          :key="i"
          class="font-mono text-xs text-mist-drift flex items-start gap-2"
        >
          <span class="text-mist-depth mt-0.5 select-none">·</span>
          <span>{{ stripPrefix(line) }}</span>
        </div>
      </div>

      <!-- Agent feed: shown when partial chat messages are available -->
      <div
        v-if="partialChat.length > 0"
        class="space-y-2 pt-2 max-h-[300px] overflow-y-auto"
        style="scrollbar-width: thin; scrollbar-color: #164E63 #0B1426;"
      >
        <div
          v-for="(msg, idx) in partialChat"
          :key="idx"
          class="max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm bg-ocean-abyss border border-mist-depth text-mist"
        >
          <div
            class="text-[11px] font-semibold mb-1 flex items-center gap-1.5"
            :style="{ color: agentColor(msg.agent || msg.agent_id) }"
          >
            {{ msg.agent || msg.agent_id || 'Agent' }}
            <span
              v-if="idx === partialChat.length - 1"
              data-testid="live-badge"
              class="flex items-center gap-1 text-ocean-glow font-normal text-[10px]"
            >
              <span class="w-1 h-1 rounded-full bg-ocean-glow animate-[breathe_2.5s_ease-in-out_infinite]" />
              LIVE
            </span>
          </div>
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  logLines: { type: Array, default: () => [] },
  partialChat: { type: Array, default: () => [] },
  stage: { type: Number, default: 0 },
})

const open = ref(true)

function stripPrefix(line) {
  return line.replace(/^\[(pipeline|vllm)\]\s*/, '')
}

function agentColor(agent) {
  if (!agent) return '#94A3B8'
  const palette = ['#22D3EE', '#A78BFA', '#6EE7B7', '#FF6B6B', '#FBBF24', '#F97316']
  let hash = 0
  for (let i = 0; i < agent.length; i++) hash = ((hash << 5) - hash + agent.charCodeAt(i)) | 0
  return palette[Math.abs(hash) % palette.length]
}
</script>
