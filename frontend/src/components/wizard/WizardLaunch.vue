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
        :disabled="!creditsStore.canAfford(tier.id)"
        class="relative overflow-hidden rounded-2xl border-2 p-5 text-center transition-all duration-350 ease-spring"
        :class="[
          selectedTier === tier.id
            ? 'border-[var(--border)] bg-ocean-abyss shadow-[0_0_24px_var(--glow)]'
            : 'border-mist-depth bg-ocean-deep hover:border-[var(--border)] hover:-translate-y-1',
          !creditsStore.canAfford(tier.id) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
        ]"
        :style="{ '--glow': tier.glow, '--border': tier.border, '--accent': tier.accent }"
      >
        <div class="text-base font-bold text-mist-foam transition-colors" :class="selectedTier === tier.id ? '' : ''" :style="selectedTier === tier.id ? { color: tier.accent } : {}">{{ tier.label }}</div>
        <div class="font-mono text-[11px] text-mist-slate">{{ tier.range }}</div>
        <div class="text-2xl font-extrabold mt-3 transition-transform" :style="{ color: tier.accent }" :class="selectedTier === tier.id ? 'scale-105' : ''">{{ creditsStore.getTierCost(tier.id) }} cr</div>
        <div class="text-[11px] text-mist-slate mt-1">{{ tier.duration }}</div>
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

    <!-- Cost summary -->
    <div class="bg-ocean-deep border border-mist-depth rounded-xl p-5 flex items-center justify-between">
      <div>
        <div class="text-sm text-mist-drift">Simulation cost</div>
        <div class="font-mono text-xl font-bold text-ocean-glow">{{ selectedTier ? creditsStore.getTierCost(selectedTier) : 0 }} credits</div>
        <div class="text-xs text-mist-slate mt-0.5">Balance after: <strong class="text-organic-seafoam">{{ balanceAfter }} credits</strong></div>
      </div>
      <div class="text-right">
        <div class="text-xs text-mist-slate">Current balance</div>
        <div class="font-mono text-base font-semibold text-organic-seafoam">{{ creditsStore.balance }} credits</div>
      </div>
    </div>

    <div v-if="creditsStore.isLow" class="flex items-center gap-2 mt-3 px-4 py-2.5 rounded-xl bg-coral-amber/8 border border-coral-amber/20 text-coral-amber text-sm">
      Low credit balance. <router-link to="/account" class="font-semibold underline">Purchase more</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useCreditsStore } from '../../stores/credits.js'

const creditsStore = useCreditsStore()

const emit = defineEmits(['update:tier'])

const selectedTier = ref('medium')
emit('update:tier', 'medium')

const tiers = [
  { id: 'small', label: 'Small', range: '1–500 agents', duration: '< 30 min', accent: '#22D3EE', border: '#0E7490', glow: 'rgba(34,211,238,0.08)' },
  { id: 'medium', label: 'Medium', range: '501–2,000 agents', duration: '< 4 hours', accent: '#A78BFA', border: '#7C3AED', glow: 'rgba(167,139,250,0.08)' },
  { id: 'large', label: 'Large', range: '2,001–10,000 agents', duration: '< 12 hours', accent: '#FBBF24', border: '#D97706', glow: 'rgba(251,191,36,0.08)' },
]

const sizeInfo = [
  { label: 'Small', color: '#22D3EE', traits: ['Fewer perspectives', 'Faster results', 'Key trends only'],
    dots: [{x:'40%',y:'30%',s:'5px',c:'#22D3EE'},{x:'55%',y:'50%',s:'4px',c:'#A78BFA'},{x:'35%',y:'60%',s:'4px',c:'#6EE7B7'}] },
  { label: 'Medium', color: '#A78BFA', traits: ['Balanced depth', 'Coalition detection', 'Most popular'],
    dots: [{x:'30%',y:'20%',s:'5px',c:'#22D3EE'},{x:'60%',y:'25%',s:'4px',c:'#A78BFA'},{x:'25%',y:'50%',s:'4px',c:'#6EE7B7'},{x:'55%',y:'55%',s:'5px',c:'#FF6B6B'},{x:'45%',y:'70%',s:'3px',c:'#FBBF24'},{x:'70%',y:'45%',s:'4px',c:'#22D3EE'}] },
  { label: 'Large', color: '#FBBF24', traits: ['Maximum diversity', 'Emergent coalitions', 'Deepest insights'],
    dots: [{x:'20%',y:'15%',s:'4px',c:'#22D3EE'},{x:'45%',y:'12%',s:'5px',c:'#A78BFA'},{x:'70%',y:'20%',s:'3px',c:'#6EE7B7'},{x:'30%',y:'40%',s:'5px',c:'#FF6B6B'},{x:'55%',y:'45%',s:'4px',c:'#FBBF24'},{x:'15%',y:'60%',s:'4px',c:'#22D3EE'},{x:'65%',y:'55%',s:'3px',c:'#A78BFA'},{x:'40%',y:'70%',s:'5px',c:'#6EE7B7'},{x:'75%',y:'65%',s:'4px',c:'#FF6B6B'}] },
]

const balanceAfter = computed(() => {
  if (!selectedTier.value) return creditsStore.balance
  return Math.max(0, creditsStore.balance - creditsStore.getTierCost(selectedTier.value))
})

function selectTier(id) {
  if (!creditsStore.canAfford(id)) return
  selectedTier.value = id
  emit('update:tier', id)
}
</script>
