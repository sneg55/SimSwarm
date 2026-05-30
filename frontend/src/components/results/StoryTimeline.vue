<template>
  <div class="fixed left-6 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-0">
    <template v-for="(section, i) in sections" :key="section.id">
      <div class="flex items-center gap-2.5 py-2 cursor-pointer group" @click="scrollToSection(section.id)">
        <div data-section-dot
             class="w-2 h-2 rounded-full transition-all duration-300 flex-shrink-0"
             :class="i === activeIndex ? 'bg-ocean-glow shadow-[0_0_8px_rgba(34,211,238,0.5)]' : i < activeIndex ? 'bg-ocean-teal' : 'bg-mist-depth'" />
        <span class="text-[11px] text-mist-slate whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">{{ section.label }}</span>
      </div>
      <div v-if="i < sections.length - 1" class="w-0.5 h-6 ml-[3px] transition-colors duration-300"
        :class="i < activeIndex ? 'bg-ocean-teal' : i === activeIndex ? 'bg-gradient-to-b from-ocean-glow to-ocean-teal' : 'bg-mist-depth'" />
    </template>

    <div v-if="momentsWithPct.length" class="mt-4 pl-1 border-l border-mist-depth flex flex-col gap-1">
      <div v-for="m in momentsWithPct" :key="m.id"
           data-moment-dot
           :title="m.title"
           :class="['w-1.5 h-1.5 rounded-full', typeColor(m.type)]"
           :style="{ marginLeft: '-3px', marginTop: (m.pct * 2) + 'px' }" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useStoryScrollSync } from '@/composables/useStoryScrollSync'

const props = defineProps({
  sections: { type: Array, required: true },
  moments: { type: Array, default: () => [] },
  roundCount: { type: Number, default: 0 },
})

const activeIndex = ref(0)
const { setActiveRoundIndex } = useStoryScrollSync()

const momentsWithPct = computed(() => {
  if (!props.roundCount || props.roundCount < 2) {
    return props.moments.map(m => ({ ...m, pct: 0 }))
  }
  return props.moments.map(m => ({ ...m, pct: (m.roundIndex / (props.roundCount - 1)) * 100 }))
})

function onScroll() {
  for (let i = props.sections.length - 1; i >= 0; i--) {
    const el = document.getElementById(props.sections[i].id)
    if (el && el.getBoundingClientRect().top < window.innerHeight * 0.4) {
      activeIndex.value = i
      if (props.roundCount > 1) {
        const frac = i / Math.max(1, props.sections.length - 1)
        setActiveRoundIndex(Math.round(frac * (props.roundCount - 1)))
      }
      return
    }
  }
  activeIndex.value = 0
  setActiveRoundIndex(0)
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function typeColor(type) {
  switch (type) {
    case 'market':    return 'bg-coral'
    case 'coalition': return 'bg-ocean-teal'
    case 'post':      return 'bg-ocean-glow'
    case 'finding':   return 'bg-amber-400'
    default:          return 'bg-mist-slate'
  }
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
