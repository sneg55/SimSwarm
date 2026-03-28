<template>
  <div>
    <div class="border border-mist-depth rounded-2xl overflow-hidden bg-ocean-deep">
      <div
        class="px-6 py-4 border-b border-mist-depth flex items-center justify-between cursor-pointer transition-colors hover:bg-ocean-abyss/50"
        @click="expanded = !expanded"
      >
        <div class="flex items-center gap-2 text-[15px] font-semibold text-mist-foam">
          <span class="text-xs transition-transform" :class="expanded ? 'rotate-90' : ''">&#x25B6;</span>
          Agent Chat Replay
        </div>
        <span class="font-mono text-xs text-mist-slate bg-ocean-abyss px-2 py-0.5 rounded-lg">
          {{ messages.length }} messages
        </span>
      </div>
      <div v-if="expanded" ref="chatContainer" class="max-h-[500px] overflow-y-auto p-4 space-y-2" style="scrollbar-width: thin; scrollbar-color: #164E63 #0B1426;">
        <div v-if="messages.length === 0" class="text-center text-mist-slate text-sm py-8">No messages.</div>
        <div
          v-for="(msg, idx) in messages" :key="idx"
          class="max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm"
          :class="msg.role === 'user'
            ? 'ml-auto bg-ocean-cyan/20 text-mist-foam'
            : msg.role === 'system'
            ? 'max-w-none text-center bg-coral-sand/5 border border-coral-sand/12 text-coral-sand text-xs font-medium'
            : 'bg-ocean-abyss border border-mist-depth text-mist'"
        >
          <div v-if="msg.role === 'assistant'" class="text-[11px] font-semibold mb-1" :style="{ color: agentColor(msg.agent) }">
            {{ msg.agent || 'Agent' }}
          </div>
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>
          <div v-if="msg.timestamp" class="text-[10px] text-mist-slate/50 mt-1 text-right">
            {{ formatTime(msg.timestamp) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  startExpanded: { type: Boolean, default: false },
})

const expanded = ref(props.startExpanded)
const chatContainer = ref(null)

function agentColor(agent) {
  if (!agent) return '#94A3B8'
  const palette = ['#22D3EE', '#A78BFA', '#6EE7B7', '#FF6B6B', '#FBBF24', '#F97316']
  let hash = 0
  for (let i = 0; i < agent.length; i++) hash = ((hash << 5) - hash + agent.charCodeAt(i)) | 0
  return palette[Math.abs(hash) % palette.length]
}

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
)

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}
</script>
