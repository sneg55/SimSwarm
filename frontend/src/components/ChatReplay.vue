<template>
  <div class="space-y-2">
    <h3 class="text-sm font-medium text-gray-700">Agent Chat Log</h3>
    <div
      ref="chatContainer"
      class="h-64 overflow-y-auto border border-gray-200 rounded-lg p-3 space-y-3 bg-gray-50"
    >
      <div v-if="messages.length === 0" class="text-center text-gray-400 text-sm py-8">
        No messages yet.
      </div>
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="flex gap-2"
        :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-xs lg:max-w-md px-3 py-2 rounded-lg text-sm"
          :class="msg.role === 'user'
            ? 'bg-blue-600 text-white'
            : msg.role === 'system'
            ? 'bg-yellow-100 text-yellow-800 border border-yellow-200 w-full max-w-none'
            : 'bg-white text-gray-800 border border-gray-200 shadow-sm'"
        >
          <div v-if="msg.role !== 'user'" class="text-xs font-medium opacity-60 mb-1 capitalize">
            {{ msg.role === 'assistant' ? msg.agent || 'Agent' : msg.role }}
          </div>
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>
          <div v-if="msg.timestamp" class="text-xs opacity-50 mt-1 text-right">
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
  messages: {
    type: Array,
    default: () => [],
  },
})

const chatContainer = ref(null)

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  }
)

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}
</script>
