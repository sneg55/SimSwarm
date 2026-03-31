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
      placeholder="e.g. How will retail investors and analysts react to our Q1 earnings miss over the next 30 days? What sentiment shifts and price narratives should we expect?"
      class="w-full bg-ocean-abyss border border-mist-depth rounded-2xl p-5 text-base text-mist resize-none min-h-[140px] outline-none leading-relaxed transition-all focus:border-ocean-cyan focus:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]"
    />

    <GoalQualityMeter :goal="goal" />

    <div class="mt-6">
      <GoalTemplateCards @select="onTemplateSelect" />
    </div>
  </div>
</template>

<script setup>
import GoalQualityMeter from './GoalQualityMeter.vue'
import GoalTemplateCards from './GoalTemplateCards.vue'

const props = defineProps({
  goal: { type: String, default: '' },
})

const emit = defineEmits(['update:goal'])

function onTemplateSelect(text) {
  emit('update:goal', text)
}
</script>
