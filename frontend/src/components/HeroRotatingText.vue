<template>
  <span ref="wrapperRef" class="inline-block relative overflow-hidden align-bottom" :style="{ height: '1.2em', width: wrapperWidth }">
    <span
      v-for="(word, i) in words"
      :key="word"
      class="block text-gradient whitespace-nowrap absolute top-0 left-0 right-0 text-center transition-all duration-600 ease-smooth"
      :class="{
        'translate-y-0 opacity-100': i === current,
        '-translate-y-[110%] opacity-0': i === exiting,
        'translate-y-[110%] opacity-0': i !== current && i !== exiting,
      }"
    >
      {{ word }}
    </span>
  </span>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const words = [
  'public opinion',
  'market reactions',
  'geopolitical shifts',
  'crisis responses',
  'cultural impacts',
  'regulatory cascades',
  'supply-chain ripples',
  'stakeholder coalitions',
  'sentiment waves',
  'escalation paths',
  'economic trajectories',
  'narrative ecosystems',
]

const current = ref(0)
const exiting = ref(-1)
const wrapperRef = ref(null)
const wrapperWidth = ref('auto')
let interval = null

function measureWidth() {
  if (!wrapperRef.value) return
  const wrapper = wrapperRef.value
  const spans = wrapper.querySelectorAll('span')
  let maxW = 0
  spans.forEach(span => {
    span.style.position = 'relative'
    span.style.visibility = 'hidden'
    span.style.opacity = '1'
    span.style.transform = 'none'
    maxW = Math.max(maxW, span.offsetWidth)
    span.style.position = ''
    span.style.visibility = ''
    span.style.opacity = ''
    span.style.transform = ''
  })
  wrapperWidth.value = (maxW + 4) + 'px'
}

function rotate() {
  exiting.value = current.value
  current.value = (current.value + 1) % words.length
  setTimeout(() => { exiting.value = -1 }, 700)
}

onMounted(async () => {
  await nextTick()
  if (document.fonts?.ready) {
    await document.fonts.ready
  }
  measureWidth()
  window.addEventListener('resize', measureWidth)
  interval = setInterval(rotate, 2500)
})

onUnmounted(() => {
  clearInterval(interval)
  window.removeEventListener('resize', measureWidth)
})
</script>
