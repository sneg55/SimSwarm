<template>
  <div class="space-y-2">
    <h3 class="text-sm font-medium text-gray-700">Pipeline Progress</h3>
    <div class="flex items-center">
      <div
        v-for="(step, index) in steps"
        :key="step.id"
        class="flex items-center"
        :class="index < steps.length - 1 ? 'flex-1' : ''"
      >
        <div class="flex flex-col items-center">
          <div
            class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium border-2 transition-all"
            :class="stepClass(step.id)"
          >
            <svg v-if="isCompleted(step.id)" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
            </svg>
            <span v-else-if="isActive(step.id)" class="w-2 h-2 bg-blue-600 rounded-full animate-pulse"/>
            <span v-else>{{ index + 1 }}</span>
          </div>
          <span class="text-xs text-gray-500 mt-1 text-center w-16">{{ step.label }}</span>
        </div>
        <div
          v-if="index < steps.length - 1"
          class="flex-1 h-0.5 mx-1 mb-5 transition-all"
          :class="isCompleted(step.id) ? 'bg-green-400' : 'bg-gray-200'"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  currentStep: {
    type: String,
    default: null,
  },
  completedSteps: {
    type: Array,
    default: () => [],
  },
})

const steps = [
  { id: 'seed', label: 'Seed' },
  { id: 'research', label: 'Research' },
  { id: 'simulate', label: 'Simulate' },
  { id: 'analyze', label: 'Analyze' },
  { id: 'report', label: 'Report' },
]

function isCompleted(stepId) {
  return props.completedSteps.includes(stepId)
}

function isActive(stepId) {
  return props.currentStep === stepId
}

function stepClass(stepId) {
  if (isCompleted(stepId)) return 'border-green-400 bg-green-50 text-green-600'
  if (isActive(stepId)) return 'border-blue-500 bg-blue-50 text-blue-600'
  return 'border-gray-200 bg-white text-gray-400'
}
</script>
