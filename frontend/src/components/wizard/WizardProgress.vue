<template>
  <div class="flex items-center justify-center gap-0 mb-10">
    <template v-for="(step, i) in steps" :key="step.id">
      <div class="flex flex-col items-center gap-2 cursor-pointer" @click="$emit('go', i + 1)">
        <div
          class="w-3 h-3 rounded-full border-2 transition-all duration-400 ease-spring relative z-[2]"
          :class="i + 1 < current ? 'border-organic-sage bg-organic-sage shadow-[0_0_8px_rgba(16,185,129,0.3)]'
            : i + 1 === current ? 'border-ocean-glow bg-ocean-glow shadow-[0_0_12px_rgba(34,211,238,0.4)]'
            : 'border-mist-depth bg-transparent'"
        />
        <span class="text-[11px] transition-colors"
          :class="i + 1 === current ? 'text-ocean-glow' : i + 1 < current ? 'text-organic-sage' : 'text-mist-slate'">
          {{ step.label }}
        </span>
      </div>
      <div
        v-if="i < steps.length - 1"
        class="w-20 h-0.5 mb-5 relative overflow-hidden transition-colors"
        :class="i + 1 < current ? 'bg-organic-sage'
          : i + 1 === current ? 'bg-gradient-to-r from-organic-sage to-ocean-glow'
          : 'bg-mist-depth'"
      >
        <div
          v-if="i + 1 === current"
          class="absolute top-0 left-0 w-full h-full animate-shimmer"
          style="background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
defineProps({ current: { type: Number, default: 1 } })
defineEmits(['go'])
const steps = [
  { id: 'seed', label: 'Seed' },
  { id: 'goal', label: 'Goal' },
  { id: 'launch', label: 'Launch' },
]
</script>

<style scoped>
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(200%); } }
.animate-shimmer { animation: shimmer 2s infinite; }
</style>
