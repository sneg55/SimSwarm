<template>
  <section class="relative bg-ocean-deep border border-mist-depth rounded-2xl p-8 overflow-hidden" aria-labelledby="story-question">
    <!-- Subtle glow -->
    <div class="absolute -top-1/2 -left-1/5 w-3/5 h-[200%] pointer-events-none"
         style="background: radial-gradient(ellipse, rgba(34, 211, 238, 0.08), transparent 60%);"></div>

    <div class="relative">
      <div class="flex items-center gap-2 font-mono text-[10px] text-coral-amber tracking-[0.15em] uppercase font-semibold">
        <span class="inline-block w-4 h-px bg-coral-amber"></span>
        The question
      </div>
      <h2 id="story-question" class="text-xl font-semibold text-mist-foam mt-3 leading-snug tracking-tight">{{ question }}</h2>

      <div class="flex items-center gap-2 font-mono text-[10px] text-ocean-glow tracking-[0.15em] uppercase font-semibold mt-7">
        <span class="inline-block w-4 h-px bg-ocean-glow"></span>
        Simulated answer
      </div>
      <div class="text-base text-mist mt-3 leading-relaxed">
        <template v-if="verdict">{{ verdict }}</template>
        <span v-else class="text-mist-slate italic">Verdict pending — rerun the simulation to generate a new answer.</span>
      </div>

      <div v-if="stakeholderPositions.length" class="flex flex-wrap gap-1.5 mt-5">
        <StakeholderChip
          v-for="p in stakeholderPositions"
          :key="p.name"
          :name="p.name"
          :stance="p.stance"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import StakeholderChip from './StakeholderChip.vue'

defineProps({
  question: { type: String, required: true },
  verdict: { type: String, default: '' },
  stakeholderPositions: { type: Array, default: () => [] },
})
</script>
