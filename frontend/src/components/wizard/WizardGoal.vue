<template>
  <div>
    <div class="mb-5">
      <div class="font-mono text-xs text-ocean-cyan tracking-wide mb-2">Step 2 of 3</div>
      <h2 class="text-3xl font-extrabold text-mist-foam tracking-tight leading-tight">What do you want to know?</h2>
      <p class="text-[15px] text-mist-drift mt-2">Describe your research question. The swarm will simulate how stakeholders, markets, and media react.</p>
    </div>

    <textarea
      :value="goal"
      @input="$emit('update:goal', $event.target.value)"
      placeholder="e.g. How will the market react to our Q1 earnings miss? What public sentiment shifts should we expect?"
      class="w-full bg-ocean-abyss border border-mist-depth rounded-2xl p-5 text-base text-mist resize-none min-h-[140px] outline-none leading-relaxed transition-all focus:border-ocean-cyan focus:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]"
    />

    <div class="text-[11px] font-semibold uppercase tracking-wider text-mist-slate mt-5 mb-2.5">Try a prompt</div>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="s in suggestions" :key="s"
        @click="$emit('update:goal', s)"
        class="text-sm text-mist-drift bg-ocean-deep border border-mist-depth px-4 py-2 rounded-xl transition-all ease-spring hover:bg-ocean-cyan/12 hover:border-ocean-cyan hover:text-ocean-glow hover:-translate-y-0.5"
      >
        {{ s }}
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  goal: { type: String, default: '' },
})

defineEmits(['update:goal'])

const suggestions = [
  'How will the market react to...',
  'What will public sentiment be if...',
  'How will stakeholders respond to...',
  'What narrative will form around...',
  'What coalitions will emerge after...',
]
</script>
