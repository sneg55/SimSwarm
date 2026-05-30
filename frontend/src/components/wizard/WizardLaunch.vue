<template>
  <div>
    <div class="mb-5">
      <div class="font-mono text-xs text-ocean-cyan tracking-wide mb-2">Step 3 of 3</div>
      <h2 class="text-3xl font-extrabold text-mist-foam tracking-tight leading-tight">Choose your ecosystem size</h2>
      <p class="text-[15px] text-mist-drift mt-2">Larger ecosystems produce richer simulations with more diverse agent interactions.</p>
    </div>

    <!-- Tier cards -->
    <div class="grid grid-cols-3 gap-3 mb-5">
      <button
        v-for="tier in tiers" :key="tier.id"
        @click="selectTier(tier.id)"
        :disabled="!tierFitsTimeline(tier.id)"
        class="relative overflow-hidden rounded-2xl border-2 p-5 text-center transition-all duration-350 ease-spring"
        :class="[
          selectedTier === tier.id
            ? 'border-[var(--border)] bg-ocean-abyss shadow-[0_0_24px_var(--glow)]'
            : 'border-mist-depth bg-ocean-deep hover:border-[var(--border)] hover:-translate-y-1',
          !tierFitsTimeline(tier.id) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
        ]"
        :style="{ '--glow': tier.glow, '--border': tier.border, '--accent': tier.accent }"
      >
        <div class="text-base font-bold text-mist-foam transition-colors" :style="selectedTier === tier.id ? { color: tier.accent } : {}">{{ tier.label }}</div>
        <div class="font-mono text-[11px] text-mist-slate">{{ tier.range }}</div>
        <div class="text-[11px] text-mist-slate mt-3">{{ tier.duration }}</div>
        <div v-if="!tierFitsTimeline(tier.id)" class="text-[10px] text-coral/70 mt-1">
          Needs {{ tier.id === 'small' ? 'Medium' : 'Large' }}+
        </div>
      </button>
    </div>

    <!-- Size explainer -->
    <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5 mb-5">
      <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate text-center mb-4">How size affects your simulation</div>
      <div class="flex items-center justify-center gap-1">
        <div v-for="(s, i) in sizeInfo" :key="s.label" class="flex items-center gap-1">
          <div class="text-center flex-1 max-w-[140px]">
            <div class="h-16 relative mb-2">
              <span v-for="dot in s.dots" :key="dot.x" class="absolute rounded-full opacity-80" :style="{ left: dot.x, top: dot.y, width: dot.s, height: dot.s, background: dot.c, boxShadow: '0 0 6px ' + dot.c }" />
            </div>
            <div class="text-xs font-bold" :style="{ color: s.color }">{{ s.label }}</div>
            <div class="text-[10px] text-mist-slate leading-snug mt-1" v-for="t in s.traits" :key="t">{{ t }}</div>
          </div>
          <svg v-if="i < sizeInfo.length - 1" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#334155" stroke-width="1.5" class="flex-shrink-0 mb-8"><polyline points="9 6 15 12 9 18"/></svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  forecastDays: { type: Number, default: null },
})

const emit = defineEmits(['update:tier'])

const TIER_MAX_DAYS = { small: 30, medium: 180, large: 365 }

function tierFitsTimeline(tierId) {
  if (!props.forecastDays) return true
  return props.forecastDays <= TIER_MAX_DAYS[tierId]
}

const selectedTier = ref('medium')
emit('update:tier', 'medium')

const tiers = [
  { id: 'small', label: 'Small', range: '10 agents · 15 rounds', duration: '~45 min', accent: '#22D3EE', border: '#0E7490', glow: 'rgba(34,211,238,0.08)' },
  { id: 'medium', label: 'Medium', range: '20 agents · 100 rounds', duration: '~5 hours', accent: '#A78BFA', border: '#7C3AED', glow: 'rgba(167,139,250,0.08)' },
  { id: 'large', label: 'Large', range: '35 agents · 200 rounds', duration: 'up to 12 hours', accent: '#FBBF24', border: '#D97706', glow: 'rgba(251,191,36,0.08)' },
]

const sizeInfo = [
  { label: 'Small', color: '#22D3EE', traits: ['10 agents', 'Fewer perspectives', 'Quick scan'],
    dots: [{x:'40%',y:'30%',s:'5px',c:'#22D3EE'},{x:'55%',y:'50%',s:'4px',c:'#A78BFA'},{x:'35%',y:'60%',s:'4px',c:'#6EE7B7'}] },
  { label: 'Medium', color: '#A78BFA', traits: ['20 agents', 'Balanced depth', 'Most popular'],
    dots: [{x:'30%',y:'20%',s:'5px',c:'#22D3EE'},{x:'60%',y:'25%',s:'4px',c:'#A78BFA'},{x:'25%',y:'50%',s:'4px',c:'#6EE7B7'},{x:'55%',y:'55%',s:'5px',c:'#FF6B6B'},{x:'45%',y:'70%',s:'3px',c:'#FBBF24'},{x:'70%',y:'45%',s:'4px',c:'#22D3EE'}] },
  { label: 'Large', color: '#FBBF24', traits: ['35 agents', 'Maximum diversity', 'Deepest insights'],
    dots: [{x:'20%',y:'15%',s:'4px',c:'#22D3EE'},{x:'45%',y:'12%',s:'5px',c:'#A78BFA'},{x:'70%',y:'20%',s:'3px',c:'#6EE7B7'},{x:'30%',y:'40%',s:'5px',c:'#FF6B6B'},{x:'55%',y:'45%',s:'4px',c:'#FBBF24'},{x:'15%',y:'60%',s:'4px',c:'#22D3EE'},{x:'65%',y:'55%',s:'3px',c:'#A78BFA'},{x:'40%',y:'70%',s:'5px',c:'#6EE7B7'},{x:'75%',y:'65%',s:'4px',c:'#FF6B6B'}] },
]

function selectTier(id) {
  if (!tierFitsTimeline(id)) return
  selectedTier.value = id
  emit('update:tier', id)
}
</script>
