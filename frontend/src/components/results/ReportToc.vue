<template>
  <div class="fixed left-8 top-[120px] w-[200px] z-30 hidden xl:block">
    <div class="text-[11px] font-semibold uppercase tracking-wider text-mist-slate mb-3">Contents</div>
    <a v-for="(item, i) in items" :key="item.id" :href="`#${item.id}`"
      @click.prevent="scrollTo(item.id)"
      class="block text-xs py-1 border-l-2 transition-all duration-200"
      :class="[
        i === activeIndex ? 'text-ocean-glow border-ocean-glow' : 'text-mist-slate border-mist-depth hover:text-mist-drift hover:border-ocean-teal',
        item.sub ? 'pl-6' : 'pl-3',
      ]">
      {{ item.label }}
    </a>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
})

const activeIndex = ref(0)

function onScroll() {
  for (let i = props.items.length - 1; i >= 0; i--) {
    const el = document.getElementById(props.items[i].id)
    if (el && el.getBoundingClientRect().top < 150) {
      activeIndex.value = i
      return
    }
  }
  activeIndex.value = 0
}

function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
