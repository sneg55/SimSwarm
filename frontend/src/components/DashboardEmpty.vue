<template>
  <div class="text-center py-20">
    <div class="relative w-28 h-28 mx-auto mb-8">
      <div
        v-for="(ring, i) in rings" :key="i"
        class="absolute inset-0 rounded-full border"
        :style="{
          borderColor: ring.color,
          animation: 'pulse-ring 4s ease-in-out infinite',
          animationDelay: ring.delay,
        }"
      />
      <div class="absolute w-2.5 h-2.5 rounded-full bg-ocean-glow opacity-60 top-2 left-1/2 -translate-x-1/2 animate-glow-breathe" />
      <div class="absolute w-2 h-2 rounded-full bg-organic-violet opacity-50 bottom-4 right-2 animate-glow-breathe" style="animation-delay: 1s;" />
      <div class="absolute w-2 h-2 rounded-full bg-coral opacity-50 bottom-4 left-2 animate-glow-breathe" style="animation-delay: 2s;" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-ocean-cyan/80" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-mist-foam/80" />
    </div>

    <p class="text-lg text-mist-drift max-w-sm mx-auto mb-6 leading-relaxed">
      Your ecosystem is ready.<br>What would you like to simulate today?
    </p>

    <router-link
      to="/sim/new"
      class="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-base font-semibold text-white
             bg-gradient-to-br from-ocean-cyan to-cyan-500
             glow-cyan transition-all duration-250 ease-spring
             hover:glow-cyan-lg hover:-translate-y-0.5"
    >
      Start your first simulation
    </router-link>
  </div>
</template>

<script setup>
const rings = [
  { color: 'rgba(34, 211, 238, 0.15)', delay: '0s' },
  { color: 'rgba(167, 139, 250, 0.12)', delay: '1.3s' },
  { color: 'rgba(255, 107, 107, 0.1)', delay: '2.6s' },
]
</script>

<style scoped>
@keyframes pulse-ring {
  0%, 100% { transform: scale(0.85); opacity: 0.15; }
  50% { transform: scale(1.15); opacity: 0.04; }
}
</style>
