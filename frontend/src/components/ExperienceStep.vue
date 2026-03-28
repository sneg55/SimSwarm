<template>
  <div
    ref="stepRef"
    class="max-w-[1100px] mx-auto py-16 grid grid-cols-1 md:grid-cols-2 gap-16 items-center transition-all duration-800 ease-out"
    :class="[
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10',
      reverse ? 'md:direction-rtl' : '',
    ]"
  >
    <div :class="reverse ? 'md:order-2' : ''">
      <div class="font-mono text-sm text-ocean-cyan tracking-wide mb-2">{{ stepNumber }}</div>
      <h3 class="text-2xl font-bold text-mist-foam tracking-tight mb-3">
        <slot name="title" />
      </h3>
      <p class="text-base text-mist-drift leading-relaxed">
        <slot name="description" />
      </p>
      <p v-if="$slots.detail" class="mt-3 text-sm text-mist-slate">
        <slot name="detail" />
      </p>
    </div>
    <div :class="reverse ? 'md:order-1' : ''">
      <div class="bg-ocean-deep border border-mist-depth rounded-2xl overflow-hidden transition-all duration-500 ease-spring hover:-translate-y-1 hover:shadow-[0_16px_48px_rgba(0,0,0,0.3)]">
        <div class="px-4 py-2.5 bg-ocean-abyss border-b border-mist-depth flex gap-1.5">
          <div class="w-2 h-2 rounded-full bg-coral" />
          <div class="w-2 h-2 rounded-full bg-coral-sand" />
          <div class="w-2 h-2 rounded-full bg-organic-sage" />
        </div>
        <div class="p-6 min-h-[240px]">
          <slot name="mockup" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineProps({
  stepNumber: { type: String, required: true },
  reverse: { type: Boolean, default: false },
})

const stepRef = ref(null)
const visible = ref(false)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    ([entry]) => { if (entry.isIntersecting) visible.value = true },
    { threshold: 0.2 }
  )
  if (stepRef.value) observer.observe(stepRef.value)
})

onUnmounted(() => observer?.disconnect())
</script>
